"""MaterialBundle model - groups multiple episodes into a remix source pack."""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils import beijing_now


class MaterialBundle(Base):
    """A bundle grouping multiple material episodes for remix tasks."""
    __tablename__ = "material_bundles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    material_ids: Mapped[dict] = mapped_column(JSON, nullable=False)  # list of material IDs
    episode_count: Mapped[int] = mapped_column(Integer, default=0)
    total_duration: Mapped[float] = mapped_column(Float, default=0.0)  # sum of all episodes
    total_segments: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ready")  # ready, analyzing, error
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now, onupdate=beijing_now)
