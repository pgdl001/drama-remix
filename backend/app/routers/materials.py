"""Materials router: upload, list, detail, analyze."""

import shutil
import subprocess
import json
import asyncio
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.material import Material, MaterialSegment
from app.schemas.material import MaterialResponse, MaterialListResponse
from app.auth_utils import get_current_user
from app.config import settings
import subprocess

router = APIRouter()
logger = logging.getLogger("materials")


def _probe_video_sync(file_path: str) -> dict:
    """Use ffprobe (sync) to extract video metadata.
    Uses subprocess.run instead of asyncio subprocess for Windows compatibility.
    """
    cmd = [
        settings.FFPROBE_BIN, "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", file_path
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
        )
        if result.returncode != 0:
            logger.warning(f"ffprobe returned {result.returncode} for {file_path}: {result.stderr[:200]}")
            return {}
        data = json.loads(result.stdout)
        logger.info(f"ffprobe success for {file_path}: duration={data.get('format', {}).get('duration', 'N/A')}")
        return data
    except Exception as e:
        logger.error(f"ffprobe exception for {file_path}: {type(e).__name__}: {e}")
        return {}


async def _probe_video(file_path: str) -> dict:
    """Async wrapper for ffprobe - runs sync probe in thread pool."""
    return await asyncio.get_event_loop().run_in_executor(None, _probe_video_sync, file_path)


@router.post("/upload", response_model=MaterialListResponse, status_code=201)
async def upload_material(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Save file
    dest_dir = settings.MATERIALS_DIR / current_user.id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / file.filename
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    file_size = dest_path.stat().st_size

    # Probe video metadata
    duration, width, height, fps = 0.0, 0, 0, 0.0
    try:
        probe = await _probe_video(str(dest_path))
        duration = float(probe.get("format", {}).get("duration", 0))
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "video":
                width = int(stream.get("width", 0))
                height = int(stream.get("height", 0))
                r_frame_rate = stream.get("r_frame_rate", "0/1")
                parts = r_frame_rate.split("/")
                if len(parts) == 2 and int(parts[1]) != 0:
                    fps = round(int(parts[0]) / int(parts[1]), 2)
                break
    except Exception:
        pass  # ffprobe may fail on some files; still save the material

    material = Material(
        title=title,
        description=description,
        file_path=str(dest_path),
        file_size=file_size,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        format=dest_path.suffix.lstrip("."),
        status="ready",
        user_id=current_user.id,
    )
    db.add(material)
    await db.flush()
    await db.refresh(material)
    return material


@router.post("/upload-batch", status_code=201)
async def upload_materials_batch(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload multiple material files at once."""
    dest_dir = settings.MATERIALS_DIR / current_user.id
    dest_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for file in files:
        dest_path = dest_dir / file.filename
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        file_size = dest_path.stat().st_size
        title = Path(file.filename).stem

        duration, width, height, fps = 0.0, 0, 0, 0.0
        try:
            probe = await _probe_video(str(dest_path))
            duration = float(probe.get("format", {}).get("duration", 0))
            for stream in probe.get("streams", []):
                if stream.get("codec_type") == "video":
                    width = int(stream.get("width", 0))
                    height = int(stream.get("height", 0))
                    r_frame_rate = stream.get("r_frame_rate", "0/1")
                    parts = r_frame_rate.split("/")
                    if len(parts) == 2 and int(parts[1]) != 0:
                        fps = round(int(parts[0]) / int(parts[1]), 2)
                    break
        except Exception:
            pass

        material = Material(
            title=title,
            file_path=str(dest_path),
            file_size=file_size,
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            format=dest_path.suffix.lstrip("."),
            status="ready",
            user_id=current_user.id,
        )
        db.add(material)
        await db.flush()
        await db.refresh(material)
        results.append({
            "id": material.id,
            "title": material.title,
            "file_size": material.file_size,
            "duration": material.duration,
            "status": material.status,
        })

    return {"uploaded": len(results), "items": results}


@router.get("/", response_model=list[MaterialListResponse])
async def list_materials(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Material)
        .where(Material.user_id == current_user.id)
        .order_by(Material.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    return result.scalars().all()


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(
    material_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Material)
        .options(selectinload(Material.segments))
        .where(Material.id == material_id, Material.user_id == current_user.id)
    )
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


@router.delete("/{material_id}")
async def delete_material(
    material_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Material).where(Material.id == material_id, Material.user_id == current_user.id)
    )
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    # Move file to trash instead of deleting
    file_path = Path(material.file_path)
    if file_path.exists():
        trash_dir = settings.TEMP_DIR / "trash"
        trash_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file_path), str(trash_dir / file_path.name))
    await db.delete(material)
    return {"status": "ok", "message": "Material deleted"}


@router.post("/folder-picker-path")
async def get_folder_picker_path():
    """Use PowerShell to open a native folder picker dialog and return the selected path."""
    ps_script = r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "选择要导入的素材文件夹"
$dialog.ShowNewFolderButton = $false
$result = $dialog.ShowDialog()
if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.SelectedPath
}
'''
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        path = result.stdout.strip()
        if path:
            return {"path": path}
        return {"path": ""}
    except Exception:
        return {"path": ""}


@router.get("/folder-preview")
async def preview_folder(
    folder_path: str,
    current_user: User = Depends(get_current_user),
):
    """Preview video files in a folder (no import yet)."""
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail="Folder does not exist")

    VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"}
    videos = []
    for f in sorted(folder.iterdir()):
        if f.is_file() and f.suffix.lower() in VIDEO_EXTS:
            videos.append({
                "filename": f.name,
                "path": str(f),
                "size_mb": round(f.stat().st_size / 1024 / 1024, 2),
            })

    return {"folder": str(folder), "video_count": len(videos), "videos": videos}


@router.post("/import-folder", status_code=201)
async def import_folder(
    folder_path: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import all video files from a folder as materials."""
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail="Folder does not exist")

    VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"}
    dest_dir = settings.MATERIALS_DIR / current_user.id
    dest_dir.mkdir(parents=True, exist_ok=True)

    video_files = [f for f in sorted(folder.iterdir()) if f.is_file() and f.suffix.lower() in VIDEO_EXTS]
    if not video_files:
        return {"imported": 0, "errors": [], "items": []}

    copied_paths = []
    for f in video_files:
        dest_path = dest_dir / f.name
        try:
            shutil.copy2(str(f), str(dest_path))
            copied_paths.append((f.stem, dest_path, dest_path.stat().st_size))
        except Exception as e:
            pass

    sem = asyncio.Semaphore(4)
    async def probe_one(title: str, dest_path: Path, file_size: int):
        async with sem:
            duration, width, height, fps = 0.0, 0, 0, 0.0
            try:
                probe = await _probe_video(str(dest_path))
                duration = float(probe.get("format", {}).get("duration", 0))
                for stream in probe.get("streams", []):
                    if stream.get("codec_type") == "video":
                        width = int(stream.get("width", 0))
                        height = int(stream.get("height", 0))
                        r_frame_rate = stream.get("r_frame_rate", "0/1")
                        parts = r_frame_rate.split("/")
                        if len(parts) == 2 and int(parts[1]) != 0:
                            fps = round(int(parts[0]) / int(parts[1]), 2)
                        break
            except Exception:
                pass
            return (title, dest_path, file_size, duration, width, height, fps)

    results = await asyncio.gather(*[
        probe_one(t, p, s) for t, p, s in copied_paths
    ])

    imported = []
    for title, dest_path, file_size, duration, width, height, fps in results:
        material = Material(
            title=title,
            file_path=str(dest_path),
            file_size=file_size,
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            format=dest_path.suffix.lstrip("."),
            status="ready",
            user_id=current_user.id,
        )
        db.add(material)
        await db.flush()
        await db.refresh(material)
        imported.append({
            "id": material.id,
            "title": material.title,
            "duration": round(material.duration, 1),
            "file_size": material.file_size,
        })

    await db.commit()
    return {"imported": len(imported), "errors": [], "items": imported}
