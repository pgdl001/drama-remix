"""RemixWork and RenderJob models."""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils import beijing_now


class RemixWork(Base):
    """A single generated remix work (output video)."""
    __tablename__ = "remix_works"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("remix_tasks.id"), nullable=False)
    work_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Content plan
    segments_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # ordered list of segment refs
    bgm_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("bgm_tracks.id"), nullable=True)
    hook_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    transition_style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    text_overlays_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mutation_params_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Output
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    # Status
    status: Mapped[str] = mapped_column(String(20), default="planned")
    # planned, rendering, rendered, reviewing, approved, rejected, distributed
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)  # content hash for dedup
    review_passed: Mapped[bool | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now, onupdate=beijing_now)


class RenderJob(Base):
    """FFmpeg render job for a remix work."""
    __tablename__ = "render_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    work_id: Mapped[str] = mapped_column(String(36), ForeignKey("remix_works.id"), nullable=False)
    ffmpeg_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued, running, completed, failed
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)  # render time
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now)
