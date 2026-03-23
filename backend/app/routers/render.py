"""Render router: render jobs management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.work import RenderJob
from app.auth_utils import get_current_user

router = APIRouter()


@router.get("/jobs")
async def list_render_jobs(
    status: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(RenderJob).order_by(RenderJob.created_at.desc()).limit(limit)
    if status:
        query = query.where(RenderJob.status == status)
    result = await db.execute(query)
    jobs = result.scalars().all()
    return [
        {
            "id": j.id,
            "work_id": j.work_id,
            "status": j.status,
            "progress": j.progress,
            "duration_seconds": j.duration_seconds,
            "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]


@router.get("/jobs/{job_id}")
async def get_render_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(RenderJob).where(RenderJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Render job not found")
    return {
        "id": job.id,
        "work_id": job.work_id,
        "status": job.status,
        "progress": job.progress,
        "ffmpeg_command": job.ffmpeg_command,
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
