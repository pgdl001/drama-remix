"""Remix router: templates, tasks, works."""

import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.remix import RemixTemplate, RemixTask
from app.models.work import RemixWork
from app.models.material import Material, MaterialSegment
from app.models.bundle import MaterialBundle
from app.schemas.remix import (
    RemixTemplateCreate, RemixTemplateResponse,
    RemixTaskCreate, RemixTaskResponse, RemixWorkResponse,
)
from app.auth_utils import get_current_user
from app.config import settings
from app.utils import beijing_now

router = APIRouter()


# --- Templates ---

@router.post("/templates", response_model=RemixTemplateResponse, status_code=201)
async def create_template(
    body: RemixTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = RemixTemplate(**body.model_dump(), user_id=current_user.id)
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


@router.get("/templates", response_model=list[RemixTemplateResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(RemixTemplate).where(RemixTemplate.user_id == current_user.id).order_by(RemixTemplate.created_at.desc())
    )
    return result.scalars().all()


# --- Tasks ---

@router.post("/tasks", response_model=RemixTaskResponse, status_code=201)
async def create_task(
    body: RemixTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bundle_id = body.bundle_id
    material_id = body.material_id

    # Case 1: Multiple materials selected -> auto-create bundle
    if body.material_ids and len(body.material_ids) > 1:
        # Verify all materials exist
        mat_result = await db.execute(
            select(Material).where(
                Material.id.in_(body.material_ids),
                Material.user_id == current_user.id,
            )
        )
        materials = mat_result.scalars().all()
        if len(materials) != len(body.material_ids):
            raise HTTPException(status_code=404, detail="Some materials not found")

        total_duration = sum(m.duration for m in materials)
        seg_count_result = await db.execute(
            select(func.count(MaterialSegment.id)).where(
                MaterialSegment.material_id.in_(body.material_ids)
            )
        )
        total_segments = seg_count_result.scalar() or 0

        bundle = MaterialBundle(
            name=f"{body.name} - 素材包",
            material_ids=body.material_ids,
            episode_count=len(materials),
            total_duration=total_duration,
            total_segments=total_segments,
            status="ready",
            user_id=current_user.id,
        )
        db.add(bundle)
        await db.flush()
        bundle_id = bundle.id
        material_id = body.material_ids[0]  # first episode as primary reference

    # Case 2: Single material_ids list with one entry
    elif body.material_ids and len(body.material_ids) == 1:
        material_id = body.material_ids[0]

    # Validate we have at least material_id or bundle_id
    if not material_id and not bundle_id:
        raise HTTPException(status_code=400, detail="Must provide material_id, material_ids, or bundle_id")

    task = RemixTask(
        name=body.name,
        material_id=material_id,
        bundle_id=bundle_id,
        template_id=body.template_id,
        target_count=body.target_count,
        priority=body.priority,
        config_json=body.config_json,
        watermark_text=body.watermark_text,
        narration_enabled=body.narration_enabled,
        narration_volume=body.narration_volume,
        original_volume=body.original_volume,
        effects_enabled=body.effects_enabled,
        narration_ratio=body.narration_ratio,
        edge_voice=body.edge_voice,
        episode_batch=body.episode_batch,
        user_id=current_user.id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    # Auto-start task in background
    task.status = "running"
    task.started_at = beijing_now()
    await db.commit()
    await db.refresh(task)

    from app.services.task_runner import start_task_processing
    await start_task_processing(task.id)

    return task


@router.get("/tasks", response_model=list[RemixTaskResponse])
async def list_tasks(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(RemixTask).where(RemixTask.user_id == current_user.id)
    if status:
        query = query.where(RemixTask.status == status)
    result = await db.execute(query.order_by(RemixTask.created_at.desc()))
    return result.scalars().all()


@router.get("/tasks/{task_id}", response_model=RemixTaskResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(RemixTask).where(RemixTask.id == task_id, RemixTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks/{task_id}/start")
async def start_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(RemixTask).where(RemixTask.id == task_id, RemixTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in ("pending", "paused"):
        raise HTTPException(status_code=400, detail=f"Cannot start task in status '{task.status}'")

    task.status = "running"
    task.started_at = task.started_at or beijing_now()
    await db.commit()

    # Fire off the background task runner
    from app.services.task_runner import start_task_processing
    await start_task_processing(task_id)

    return {"status": "ok", "message": "Task started and processing in background"}


@router.post("/tasks/{task_id}/pause")
async def pause_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(RemixTask).where(RemixTask.id == task_id, RemixTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "paused"
    await db.commit()

    # Stop the background runner
    from app.services.task_runner import stop_task_processing
    await stop_task_processing(task_id)

    return {"status": "ok", "message": "Task paused"}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(RemixTask).where(RemixTask.id == task_id, RemixTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Stop if running
    from app.services.task_runner import stop_task_processing
    await stop_task_processing(task_id)

    await db.delete(task)
    return {"status": "ok", "message": "Task deleted"}


@router.post("/tasks/batch-delete")
async def batch_delete_tasks(
    task_ids: list[str] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete multiple tasks and their generated files (outputs + narration)."""
    import os
    from pathlib import Path
    from app.models.work import RenderJob

    deleted = 0
    files_removed = 0

    for task_id in task_ids:
        result = await db.execute(
            select(RemixTask).where(RemixTask.id == task_id, RemixTask.user_id == current_user.id)
        )
        task = result.scalar_one_or_none()
        if not task:
            continue

        # Stop if running
        from app.services.task_runner import stop_task_processing
        await stop_task_processing(task_id)

        # Find and delete output files + narration files
        works_result = await db.execute(select(RemixWork).where(RemixWork.task_id == task_id))
        works = works_result.scalars().all()

        for work in works:
            # Delete output video
            if work.output_path and os.path.exists(work.output_path):
                try:
                    os.remove(work.output_path)
                    files_removed += 1
                except Exception:
                    pass

            # Delete narration files for this work
            narr_dir = settings.NARRATION_DIR
            if narr_dir.exists():
                for f in narr_dir.glob(f"*{work.id}*"):
                    try:
                        f.unlink()
                        files_removed += 1
                    except Exception:
                        pass

            # Delete render jobs
            await db.execute(
                select(RenderJob).where(RenderJob.work_id == work.id)
            )
            rj_result = await db.execute(select(RenderJob).where(RenderJob.work_id == work.id))
            for rj in rj_result.scalars().all():
                await db.delete(rj)

            await db.delete(work)

        await db.delete(task)
        deleted += 1

    await db.commit()
    return {"status": "ok", "deleted": deleted, "files_removed": files_removed}


# --- Works ---

@router.get("/tasks/{task_id}/works", response_model=list[RemixWorkResponse])
async def list_works(
    task_id: str,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(RemixWork)
        .where(RemixWork.task_id == task_id)
        .order_by(RemixWork.work_index)
        .offset(offset)
        .limit(page_size)
    )
    return result.scalars().all()
