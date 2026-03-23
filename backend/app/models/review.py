"""Review result model."""

import uuid
from datetime import datetime
from sqlalchemy import String, Float, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils import beijing_now


class ReviewResult(Base):
    """Review/audit result for a remix work."""
    __tablename__ = "review_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    work_id: Mapped[str] = mapped_column(String(36), ForeignKey("remix_works.id"), nullable=False)
    # 3-layer check results
    visual_check_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    audio_check_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_check_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    dedup_check_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    compliance_check_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    overall_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    # Details
    similarity_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1, lower is more unique
    issues_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # list of detected issues
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now)
