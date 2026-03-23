"""Bundle router: create, list, get material bundles."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.bundle import MaterialBundle
from app.models.material import Material, MaterialSegment
from app.schemas.bundle import BundleCreate, BundleResponse, BundleDetailResponse, EpisodeBatch
from app.auth_utils import get_current_user

router = APIRouter()


@router.post("/", response_model=BundleResponse, status_code=201)
async def create_bundle(
    body: BundleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a material bundle from a list of material IDs."""
    if not body.material_ids or len(body.material_ids) < 1:
        raise HTTPException(status_code=400, detail="At least 1 material required")

    # Verify all materials exist and belong to user
    result = await db.execute(
        select(Material).where(
            Material.id.in_(body.material_ids),
            Material.user_id == current_user.id,
        )
    )
    materials = result.scalars().all()
    found_ids = {m.id for m in materials}
    missing = set(body.material_ids) - found_ids
    if missing:
        raise HTTPException(status_code=404, detail=f"Materials not found: {list(missing)}")

    # Calculate aggregates
    total_duration = sum(m.duration for m in materials)

    # Count total segments across all materials
    seg_count_result = await db.execute(
        select(func.count(MaterialSegment.id)).where(
            MaterialSegment.material_id.in_(body.material_ids)
        )
    )
    total_segments = seg_count_result.scalar() or 0

    bundle = MaterialBundle(
        name=body.name,
        description=body.description,
        material_ids=body.material_ids,  # stored as JSON list
        episode_count=len(materials),
        total_duration=total_duration,
        total_segments=total_segments,
        status="ready",
        user_id=current_user.id,
    )
    db.add(bundle)
    await db.flush()
    await db.refresh(bundle)
    return bundle


@router.get("/", response_model=list[BundleResponse])
async def list_bundles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(MaterialBundle)
        .where(MaterialBundle.user_id == current_user.id)
        .order_by(MaterialBundle.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{bundle_id}", response_model=BundleDetailResponse)
async def get_bundle(
    bundle_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(MaterialBundle).where(
            MaterialBundle.id == bundle_id,
            MaterialBundle.user_id == current_user.id,
        )
    )
    bundle = result.scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    # Load material details
    mat_result = await db.execute(
        select(Material).where(Material.id.in_(bundle.material_ids))
    )
    materials_list = [
        {"id": m.id, "title": m.title, "duration": m.duration, "status": m.status}
        for m in mat_result.scalars().all()
    ]

    return BundleDetailResponse(
        id=bundle.id,
        name=bundle.name,
        description=bundle.description,
        material_ids=bundle.material_ids,
        episode_count=bundle.episode_count,
        total_duration=bundle.total_duration,
        total_segments=bundle.total_segments,
        status=bundle.status,
        created_at=bundle.created_at,
        materials=materials_list,
    )


@router.delete("/{bundle_id}")
async def delete_bundle(
    bundle_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(MaterialBundle).where(
            MaterialBundle.id == bundle_id,
            MaterialBundle.user_id == current_user.id,
        )
    )
    bundle = result.scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")
    await db.delete(bundle)
    return {"status": "ok", "message": "Bundle deleted"}


@router.get("/{bundle_id}/episodes", response_model=list[EpisodeBatch])
async def get_bundle_episode_batches(
    bundle_id: str,
    window_size: int = 3,
    step: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get episode batches for a bundle.

    Default: 1-3, 2-4, 3-5, 4-6... (window=3, step=1)
    """
    result = await db.execute(
        select(MaterialBundle).where(
            MaterialBundle.id == bundle_id,
            MaterialBundle.user_id == current_user.id,
        )
    )
    bundle = result.scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    material_ids = list(bundle.material_ids)
    n = len(material_ids)
    batches = []

    for start_idx in range(0, n, step):
        end_idx = start_idx + window_size - 1
        if end_idx >= n:
            end_idx = n - 1
        if end_idx < start_idx:
            break

        batch_material_ids = material_ids[start_idx:end_idx + 1]
        batch_key = f"{start_idx}_{end_idx}"
        label = f"{start_idx + 1}-{end_idx + 1}集"
        episode_indices = list(range(start_idx + 1, end_idx + 2))

        batches.append(EpisodeBatch(
            batch_key=batch_key,
            label=label,
            material_ids=batch_material_ids,
            episode_indices=episode_indices,
        ))

    return batches
