"""Remix task and template models."""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils import beijing_now


class RemixTemplate(Base):
    """A reusable remix strategy template."""
    __tablename__ = "remix_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Strategy config
    hook_strategy: Mapped[str] = mapped_column(String(50), default="suspense")
    duration_range_min: Mapped[int] = mapped_column(Integer, default=30)
    duration_range_max: Mapped[int] = mapped_column(Integer, default=60)
    segment_selection: Mapped[str] = mapped_column(String(50), default="random")
    transition_style: Mapped[str] = mapped_column(String(50), default="cut")
    bgm_mode: Mapped[str] = mapped_column(String(50), default="auto")
    text_overlay_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    speed_variation: Mapped[bool] = mapped_column(Boolean, default=True)
    # Fingerprint mutation config
    visual_mutation: Mapped[bool] = mapped_column(Boolean, default=True)
    audio_mutation: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_mutation: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now, onupdate=beijing_now)


class RemixTask(Base):
    """A batch remix production task."""
    __tablename__ = "remix_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    material_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("materials.id"), nullable=True)
    bundle_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("material_bundles.id"), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("remix_templates.id"), nullable=True)
    target_count: Mapped[int] = mapped_column(Integer, default=100)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    priority: Mapped[int] = mapped_column(Integer, default=5)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # V2: New features
    watermark_text: Mapped[str] = mapped_column(String(200), default="")
    narration_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    narration_volume: Mapped[float] = mapped_column(Float, default=0.8)  # narration volume 0-1
    original_volume: Mapped[float] = mapped_column(Float, default=0.3)   # original audio volume when narration is on
    effects_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # V3: Interspersed narration + Edge TTS
    narration_ratio: Mapped[float] = mapped_column(Float, default=30.0)  # % of video with narration (0-100)
    edge_voice: Mapped[str] = mapped_column(String(50), default="zh-CN-XiaoxiaoNeural")  # Edge TTS voice short name
    episode_batch: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)  # e.g. "0_2" = episodes 1-3, None=all

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now, onupdate=beijing_now)
