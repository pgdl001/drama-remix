"""Review engine router."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.review import ReviewResult
from app.auth_utils import get_current_user

router = APIRouter()


@router.get("/results")
async def list_review_results(
    work_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(ReviewResult).order_by(ReviewResult.reviewed_at.desc()).limit(limit)
    if work_id:
        query = query.where(ReviewResult.work_id == work_id)
    result = await db.execute(query)
    reviews = result.scalars().all()
    return [
        {
            "id": r.id,
            "work_id": r.work_id,
            "overall_passed": r.overall_passed,
            "visual_check": r.visual_check_passed,
            "audio_check": r.audio_check_passed,
            "dedup_check": r.dedup_check_passed,
            "similarity_score": r.similarity_score,
            "reviewed_at": r.reviewed_at.isoformat(),
        }
        for r in reviews
    ]


@router.get("/results/{result_id}")
async def get_review_detail(
    result_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(ReviewResult).where(ReviewResult.id == result_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review result not found")
    return {
        "id": review.id,
        "work_id": review.work_id,
        "visual_check_passed": review.visual_check_passed,
        "audio_check_passed": review.audio_check_passed,
        "metadata_check_passed": review.metadata_check_passed,
        "dedup_check_passed": review.dedup_check_passed,
        "compliance_check_passed": review.compliance_check_passed,
        "overall_passed": review.overall_passed,
        "similarity_score": review.similarity_score,
        "issues": review.issues_json,
        "details": review.details,
    }
