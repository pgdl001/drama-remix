"""Material schemas."""

from pydantic import BaseModel
from datetime import datetime


class MaterialCreate(BaseModel):
    title: str
    description: str | None = None


class SegmentResponse(BaseModel):
    id: str
    segment_index: int
    start_time: float
    end_time: float
    duration: float
    label: str | None = None
    emotion: str | None = None
    score: float

    model_config = {"from_attributes": True}


class MaterialResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    file_path: str
    file_size: int
    duration: float
    width: int
    height: int
    fps: float
    status: str
    created_at: datetime
    segments: list[SegmentResponse] = []

    model_config = {"from_attributes": True}


class MaterialListResponse(BaseModel):
    id: str
    title: str
    duration: float
    file_size: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
