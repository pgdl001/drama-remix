"""Voice sample router: upload, list, delete voice samples for cloning."""

import logging
import shutil
import uuid
import subprocess
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.voice import VoiceSample
from app.auth_utils import get_current_user
from app.config import settings
from app.services.asr_service import transcribe_audio

logger = logging.getLogger("voice_router")

router = APIRouter()


def _probe_duration(file_path: str) -> float:
    try:
        cmd = [
            settings.FFPROBE_BIN, "-v", "quiet", "-print_format", "json",
            "-show_format", file_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data.get("format", {}).get("duration", 0))
    except Exception:
        pass
    return 0.0


@router.post("/upload")
async def upload_voice_sample(
    file: UploadFile = File(...),
    name: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a voice sample audio file for TTS cloning.

    Audio should be 3-30 seconds of clear speech, minimal background noise.
    The transcript (prompt_text) is automatically extracted via ASR — no manual input needed.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".webm"):
        raise HTTPException(status_code=400, detail="不支持的音频格式，请上传 wav/mp3/m4a/flac/ogg/aac 格式")

    sample_id = str(uuid.uuid4())
    save_filename = f"{sample_id}{ext}"
    save_path = settings.VOICE_SAMPLES_DIR / save_filename

    # Save uploaded file
    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Convert to WAV 16kHz mono (CosyVoice requires 16k mono)
    wav_path = settings.VOICE_SAMPLES_DIR / f"{sample_id}_16k.wav"
    try:
        subprocess.run(
            [
                settings.FFMPEG_BIN, "-y", "-i", str(save_path),
                "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
                str(wav_path),
            ],
            capture_output=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        wav_path = save_path  # fallback: use original

    final_path = wav_path if wav_path.exists() else save_path
    duration = _probe_duration(str(final_path))

    # Duration validation
    if duration < 3.0:
        for p in [save_path, wav_path]:
            if p.exists():
                try: p.unlink()
                except Exception: pass
        raise HTTPException(
            status_code=400,
            detail=f"音频太短({duration:.1f}秒)，建议上传3-30秒的清晰人声录音"
        )
    if duration > 60.0:
        for p in [save_path, wav_path]:
            if p.exists():
                try: p.unlink()
                except Exception: pass
        raise HTTPException(
            status_code=400,
            detail=f"音频太长({duration:.1f}秒)，建议上传3-30秒即可，太长反而影响效果"
        )

    # ASR: auto-transcribe audio to get prompt_text
    logger.info(f"ASR transcribing voice sample: {final_path} ({duration:.1f}s)")
    prompt_text = transcribe_audio(str(final_path), language="zh")
    if not prompt_text:
        # Retry with the original file in case 16k conversion lost quality
        prompt_text = transcribe_audio(str(save_path), language="zh")

    if not prompt_text:
        logger.warning(f"ASR could not transcribe voice sample {sample_id}, using placeholder")
        prompt_text = ""  # CosyVoice will still work, just less accurate cloning

    logger.info(f"Voice sample {sample_id}: ASR result = '{prompt_text[:80]}...'")

    display_name = name or Path(file.filename).stem
    sample = VoiceSample(
        id=sample_id,
        name=display_name,
        file_path=str(final_path),
        duration=duration,
        prompt_text=prompt_text,
        user_id=current_user.id,
    )
    db.add(sample)
    await db.commit()
    await db.refresh(sample)

    return {
        "id": sample.id,
        "name": sample.name,
        "duration": round(sample.duration, 1),
        "prompt_text": sample.prompt_text,
        "created_at": sample.created_at.isoformat(),
    }


@router.get("/samples")
async def list_voice_samples(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(VoiceSample)
        .where(VoiceSample.user_id == current_user.id)
        .order_by(VoiceSample.created_at.desc())
    )
    samples = result.scalars().all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "duration": round(s.duration, 1),
            "prompt_text": s.prompt_text,
            "created_at": s.created_at.isoformat(),
        }
        for s in samples
    ]


@router.delete("/samples/{sample_id}")
async def delete_voice_sample(
    sample_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(VoiceSample).where(
            VoiceSample.id == sample_id,
            VoiceSample.user_id == current_user.id,
        )
    )
    sample = result.scalar_one_or_none()
    if not sample:
        raise HTTPException(status_code=404, detail="Voice sample not found")

    # Remove file
    for p in [Path(sample.file_path), Path(sample.file_path.replace("_16k.wav", ""))]:
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    await db.delete(sample)
    await db.commit()
    return {"status": "ok"}
