"""Distribution router."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.distribution import DistributionRecord
from app.auth_utils import get_current_user

router = APIRouter()


class DistributionCreate(BaseModel):
    work_id: str
    platform: str  # douyin, kuaishou, cps
    distribution_config_json: dict | None = None


@router.post("/", status_code=201)
async def create_distribution(
    body: DistributionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = DistributionRecord(
        work_id=body.work_id,
        platform=body.platform,
        distribution_config_json=body.distribution_config_json,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return {"id": record.id, "status": record.status, "platform": record.platform}


@router.get("/")
async def list_distributions(
    platform: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(DistributionRecord).order_by(DistributionRecord.created_at.desc()).limit(limit)
    if platform:
        query = query.where(DistributionRecord.platform == platform)
    result = await db.execute(query)
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "work_id": r.work_id,
            "platform": r.platform,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]
