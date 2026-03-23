"""Audio Utilities - Centralized audio format normalization.

All audio in the pipeline MUST pass through normalization to ensure
consistent format before any mixing or concatenation.

Standard format: 44100Hz, stereo, PCM s16le WAV
FFmpeg filter format: 44100Hz, stereo, fltp (float planar)
"""

import logging
import os
import subprocess

from app.config import settings

logger = logging.getLogger("audio_utils")

# Pipeline standard audio parameters
STANDARD_SAMPLE_RATE = 44100
STANDARD_CHANNELS = 2

# FFmpeg filter expression to normalize any audio stream to standard format.
# Use this in filter_complex BEFORE any concat/amix/amerge operation.
# It handles: any sample rate -> 44100, any channels -> stereo, any fmt -> fltp
NORMALIZE_FILTER = (
    f"aresample={STANDARD_SAMPLE_RATE},"
    f"aformat=sample_fmts=fltp:sample_rates={STANDARD_SAMPLE_RATE}:channel_layouts=stereo"
)


def normalize_audio_file(input_path: str, output_path: str) -> bool:
    """Convert any audio file to the pipeline standard format (44100Hz stereo PCM WAV).

    This function is the single source of truth for audio normalization.
    Use it after ANY TTS synthesis (CosyVoice, pyttsx3, etc.) to ensure
    consistent format before downstream processing.

    Args:
        input_path: Path to the input audio file (any format)
        output_path: Path to write the normalized WAV file

    Returns:
        True if conversion succeeded
    """
    try:
        cmd = [
            settings.FFMPEG_BIN, "-y",
            "-i", input_path,
            "-ar", str(STANDARD_SAMPLE_RATE),
            "-ac", str(STANDARD_CHANNELS),
            "-acodec", "pcm_s16le",
            "-sample_fmt", "s16",
            output_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0:
            logger.debug(f"Audio normalized: {input_path} -> {output_path}")
            return True
        else:
            logger.warning(f"Audio normalize failed: {result.stderr[-300:]}")
            return False
    except Exception as e:
        logger.error(f"Audio normalize exception: {type(e).__name__}: {e}")
        return False


def probe_audio_format(file_path: str) -> dict:
    """Probe audio file format using ffprobe.

    Returns dict with keys: sample_rate, channels, codec, sample_fmt
    """
    try:
        cmd = [
            settings.FFPROBE_BIN, "-v", "quiet",
            "-print_format", "json",
            "-show_entries", "stream=codec_name,sample_rate,channels,channel_layout,sample_fmt",
            "-select_streams", "a:0",
            file_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            streams = data.get("streams", [])
            if streams:
                s = streams[0]
                return {
                    "sample_rate": int(s.get("sample_rate", 0)),
                    "channels": int(s.get("channels", 0)),
                    "codec": s.get("codec_name", ""),
                    "sample_fmt": s.get("sample_fmt", ""),
                    "channel_layout": s.get("channel_layout", ""),
                }
    except Exception as e:
        logger.warning(f"probe_audio_format error: {e}")
    return {}


def is_standard_format(file_path: str) -> bool:
    """Check if an audio file is already in standard pipeline format."""
    info = probe_audio_format(file_path)
    return (
        info.get("sample_rate") == STANDARD_SAMPLE_RATE
        and info.get("channels") == STANDARD_CHANNELS
    )
