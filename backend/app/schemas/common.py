"""Common response schemas."""

from pydantic import BaseModel
from typing import Any


class StatusResponse(BaseModel):
    status: str
    message: str = ""
    data: Any = None


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int = 1
    page_size: int = 20
