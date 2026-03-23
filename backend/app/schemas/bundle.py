"""MaterialBundle schemas."""

from pydantic import BaseModel
from datetime import datetime


class BundleCreate(BaseModel):
    name: str
    description: str | None = None
    material_ids: list[str]  # list of material IDs to group


class BundleResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    material_ids: list  # JSON list
    episode_count: int
    total_duration: float
    total_segments: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BundleDetailResponse(BundleResponse):
    """Bundle response with material details included."""
    materials: list[dict] = []  # populated by the router


class EpisodeBatch(BaseModel):
    batch_key: str  # e.g. "0_2" meaning episodes 1-3
    label: str       # e.g. "1-3集"
    material_ids: list[str]  # actual material IDs for this batch
    episode_indices: list[int]  # 1-based indices e.g. [1, 2, 3]
