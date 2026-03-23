"""Distribution record model."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils import beijing_now


class DistributionRecord(Base):
    """Record of distributing a work to a platform."""
    __tablename__ = "distribution_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    work_id: Mapped[str] = mapped_column(String(36), ForeignKey("remix_works.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # douyin, kuaishou, cps
    platform_work_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending, uploaded, published, rejected, removed
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    distribution_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now, onupdate=beijing_now)
