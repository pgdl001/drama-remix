"""Voice sample model for voice cloning."""

import uuid
from datetime import datetime
from sqlalchemy import String, Float, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils import beijing_now


class VoiceSample(Base):
    """An uploaded voice sample for TTS cloning."""
    __tablename__ = "voice_samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    # prompt_text: transcript of the reference audio (for CosyVoice zero-shot)
    prompt_text: Mapped[str] = mapped_column(Text, default="")
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now)
