"""Annotations router: scene detection, subtitle extraction."""

import json
import asyncio
import subprocess
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models.user import User
from app.models.material import Material, MaterialSegment
from app.models.annotation import Annotation
from app.auth_utils import get_current_user
from app.config import settings

router = APIRouter()
logger = logging.getLogger("annotations")


def _ffprobe_scene_sync(file_path: str) -> dict:
    """Run ffprobe scene detection synchronously (Windows compat)."""
    cmd = [
        settings.FFPROBE_BIN, "-v", "quiet",
        "-print_format", "json",
        "-show_frames",
        "-f", "lavfi",
        f"movie={file_path},select=gt(scene\\,0.3)"
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        logger.warning(f"Scene detection ffprobe failed: {type(e).__name__}: {e}")
    return {}


async def _detect_scenes_task(material_id: str):
    """Background task: run simple scene detection via ffprobe scene filter."""
    async with async_session() as db:
        result = await db.execute(select(Material).where(Material.id == material_id))
        material = result.scalar_one_or_none()
        if not material:
            return

        material.status = "analyzing"
        await db.commit()

        # Use ffprobe to detect scene changes (via thread pool for Windows compat)
        loop = asyncio.get_event_loop()
        frames_data = await loop.run_in_executor(None, _ffprobe_scene_sync, material.file_path)

        # Build segments from scene changes
        frames = frames_data.get("frames", [])
        timestamps = [0.0]
        for frame in frames:
            ts = float(frame.get("pts_time", frame.get("pkt_pts_time", 0)))
            if ts > 0:
                timestamps.append(ts)
        timestamps.append(material.duration)
        timestamps = sorted(set(timestamps))

        # If no scenes detected, create uniform segments
        if len(timestamps) <= 2:
            seg_duration = 10.0  # 10-second segments
            timestamps = []
            t = 0.0
            while t < material.duration:
                timestamps.append(t)
                t += seg_duration
            timestamps.append(material.duration)

        # Create segments
        for i in range(len(timestamps) - 1):
            start = timestamps[i]
            end = timestamps[i + 1]
            seg = MaterialSegment(
                material_id=material_id,
                segment_index=i,
                start_time=start,
                end_time=end,
                duration=round(end - start, 3),
                label="segment",
                score=0.5,
            )
            db.add(seg)

        material.status = "ready"
        await db.commit()


@router.post("/{material_id}/analyze")
async def analyze_material(
    material_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Material).where(Material.id == material_id, Material.user_id == current_user.id)
    )
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    background_tasks.add_task(_detect_scenes_task, material_id)
    return {"status": "ok", "message": "Analysis started"}


@router.get("/{material_id}/segments")
async def get_segments(
    material_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(MaterialSegment)
        .where(MaterialSegment.material_id == material_id)
        .order_by(MaterialSegment.segment_index)
    )
    segments = result.scalars().all()
    return [
        {
            "id": s.id,
            "index": s.segment_index,
            "start": s.start_time,
            "end": s.end_time,
            "duration": s.duration,
            "label": s.label,
            "score": s.score,
        }
        for s in segments
    ]


@router.get("/{material_id}/annotations")
async def get_annotations(
    material_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Annotation).where(Annotation.material_id == material_id).order_by(Annotation.start_time)
    )
    annotations = result.scalars().all()
    return [
        {
            "id": a.id,
            "type": a.type,
            "start": a.start_time,
            "end": a.end_time,
            "content": a.content,
            "confidence": a.confidence,
        }
        for a in annotations
    ]
