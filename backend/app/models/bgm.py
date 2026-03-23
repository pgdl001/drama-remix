"""BGM library model."""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils import beijing_now


class BGMTrack(Base):
    """Background music track in the library."""
    __tablename__ = "bgm_tracks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    genre: Mapped[str | None] = mapped_column(String(50), nullable=True)  # tense, romantic, comedy, etc.
    mood: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated tags
    license_info: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now)
