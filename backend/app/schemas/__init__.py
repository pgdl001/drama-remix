"""Pydantic schemas for API request/response validation."""

from app.schemas.auth import Token, TokenData, UserCreate, UserResponse, LoginRequest
from app.schemas.material import MaterialCreate, MaterialResponse, MaterialListResponse, SegmentResponse
from app.schemas.remix import (
    RemixTemplateCreate,
    RemixTemplateResponse,
    RemixTaskCreate,
    RemixTaskResponse,
    RemixWorkResponse,
)
from app.schemas.common import PaginatedResponse, StatusResponse

__all__ = [
    "Token", "TokenData", "UserCreate", "UserResponse", "LoginRequest",
    "MaterialCreate", "MaterialResponse", "MaterialListResponse", "SegmentResponse",
    "RemixTemplateCreate", "RemixTemplateResponse",
    "RemixTaskCreate", "RemixTaskResponse", "RemixWorkResponse",
    "PaginatedResponse", "StatusResponse",
]
