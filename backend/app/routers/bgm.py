"""BGM library router."""

import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.bgm import BGMTrack
from app.auth_utils import get_current_user
from app.config import settings

router = APIRouter()


@router.post("/upload", status_code=201)
async def upload_bgm(
    file: UploadFile = File(...),
    title: str = Form(...),
    genre: str = Form(None),
    mood: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dest_path = settings.BGM_DIR / file.filename
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    file_size = dest_path.stat().st_size

    track = BGMTrack(
        title=title,
        file_path=str(dest_path),
        file_size=file_size,
        genre=genre,
        mood=mood,
    )
    db.add(track)
    await db.flush()
    await db.refresh(track)
    return {"id": track.id, "title": track.title, "file_size": track.file_size}


@router.get("/")
async def list_bgm(
    genre: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(BGMTrack).order_by(BGMTrack.created_at.desc())
    if genre:
        query = query.where(BGMTrack.genre == genre)
    result = await db.execute(query)
    tracks = result.scalars().all()
    return [
        {"id": t.id, "title": t.title, "genre": t.genre, "mood": t.mood, "duration": t.duration}
        for t in tracks
    ]


@router.delete("/{track_id}")
async def delete_bgm(
    track_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(BGMTrack).where(BGMTrack.id == track_id))
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="BGM track not found")
    await db.delete(track)
    return {"status": "ok"}
