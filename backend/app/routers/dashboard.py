"""Dashboard router: aggregated stats."""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.material import Material
from app.models.remix import RemixTask
from app.models.work import RemixWork, RenderJob
from app.models.review import ReviewResult
from app.auth_utils import get_current_user

router = APIRouter()


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Material count
    mat_result = await db.execute(
        select(func.count(Material.id)).where(Material.user_id == current_user.id)
    )
    material_count = mat_result.scalar() or 0

    # Task counts
    task_result = await db.execute(
        select(RemixTask.status, func.count(RemixTask.id))
        .where(RemixTask.user_id == current_user.id)
        .group_by(RemixTask.status)
    )
    task_stats = {row[0]: row[1] for row in task_result.all()}

    # Work counts
    work_result = await db.execute(
        select(RemixWork.status, func.count(RemixWork.id)).group_by(RemixWork.status)
    )
    work_stats = {row[0]: row[1] for row in work_result.all()}

    # Review pass rate
    review_total = await db.execute(select(func.count(ReviewResult.id)))
    review_passed = await db.execute(
        select(func.count(ReviewResult.id)).where(ReviewResult.overall_passed == True)
    )
    total_reviews = review_total.scalar() or 0
    passed_reviews = review_passed.scalar() or 0

    return {
        "materials": material_count,
        "tasks": task_stats,
        "works": work_stats,
        "review": {
            "total": total_reviews,
            "passed": passed_reviews,
            "pass_rate": round(passed_reviews / total_reviews, 4) if total_reviews > 0 else 0,
        },
    }
