"""Annotation model for material analysis results."""

import uuid
from datetime import datetime
from sqlalchemy import String, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils import beijing_now


class Annotation(Base):
    """Analysis annotations for a material (subtitle, scene, emotion, etc.)."""
    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    material_id: Mapped[str] = mapped_column(String(36), ForeignKey("materials.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)  # subtitle, scene, emotion, object
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)  # subtitle text or label
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # extra structured data
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now)
