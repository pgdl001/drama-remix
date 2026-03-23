"""Remix schemas."""

from pydantic import BaseModel
from datetime import datetime


class RemixTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    hook_strategy: str = "suspense"
    duration_range_min: int = 30
    duration_range_max: int = 60
    segment_selection: str = "random"
    transition_style: str = "cut"
    bgm_mode: str = "auto"
    text_overlay_enabled: bool = True
    speed_variation: bool = True
    visual_mutation: bool = True
    audio_mutation: bool = True
    metadata_mutation: bool = True
    config_json: dict | None = None


class RemixTemplateResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    hook_strategy: str
    duration_range_min: int
    duration_range_max: int
    segment_selection: str
    transition_style: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RemixTaskCreate(BaseModel):
    name: str
    material_id: str | None = None
    material_ids: list[str] | None = None
    bundle_id: str | None = None
    template_id: str | None = None
    target_count: int = 100
    priority: int = 5
    config_json: dict | None = None
    # V2: New features
    watermark_text: str = ""
    narration_enabled: bool = False
    narration_volume: float = 0.8    # 旁白音量 0-1
    original_volume: float = 0.3     # 旁白开启时原声音量 0-1
    effects_enabled: bool = False    # 高光特效
    # V3: Interspersed narration + Edge TTS
    narration_ratio: float = 30.0    # 旁白在视频中的占比 0-100%
    edge_voice: str = "zh-CN-XiaoxiaoNeural"  # Edge TTS 配音角色
    episode_batch: str | None = None  # 分集批次，如 "0_2" 表示 1-3 集，None 表示全部


class RemixTaskResponse(BaseModel):
    id: str
    name: str
    material_id: str | None = None
    bundle_id: str | None = None
    template_id: str | None = None
    target_count: int
    completed_count: int
    failed_count: int
    status: str
    priority: int
    watermark_text: str = ""
    narration_enabled: bool = False
    narration_volume: float = 0.8
    original_volume: float = 0.3
    effects_enabled: bool = False
    narration_ratio: float = 30.0
    edge_voice: str = "zh-CN-XiaoxiaoNeural"
    episode_batch: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RemixWorkResponse(BaseModel):
    id: str
    task_id: str
    work_index: int
    title: str | None = None
    status: str
    duration: float
    file_size: int
    output_path: str | None = None
    review_passed: bool | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
