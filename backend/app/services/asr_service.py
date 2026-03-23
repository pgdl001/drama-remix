"""ASR Service - Automatic speech recognition using faster-whisper.

Transcribes audio files to text. Used to auto-extract prompt_text
from uploaded voice samples so users don't need to type it manually.
"""

import logging
import threading

logger = logging.getLogger("asr_service")

# Singleton model (loaded once on first use)
_model = None
_model_lock = threading.Lock()
_model_loaded = False


def _get_model():
    """Lazy-load the faster-whisper model (singleton, thread-safe)."""
    global _model, _model_loaded

    if _model_loaded:
        return _model

    with _model_lock:
        if _model_loaded:
            return _model

        try:
            from faster_whisper import WhisperModel

            # Use "medium" for good Chinese accuracy with reasonable speed on GPU
            # Falls back to CPU if no CUDA available
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"

            logger.info(f"Loading faster-whisper model (medium, {device}, {compute_type})...")
            _model = WhisperModel(
                "medium",
                device=device,
                compute_type=compute_type,
            )
            _model_loaded = True
            logger.info("faster-whisper model loaded successfully")
            return _model

        except Exception as e:
            _model_loaded = True  # Don't retry on failure
            logger.error(f"Failed to load faster-whisper: {e}")
            return None


def transcribe_audio(audio_path: str, language: str = "zh") -> str:
    """Transcribe an audio file to text.

    Args:
        audio_path: Path to audio file (any format ffmpeg can read)
        language: Language code, default "zh" for Chinese

    Returns:
        Transcribed text, or empty string on failure
    """
    model = _get_model()
    if model is None:
        logger.warning("ASR model not available, cannot transcribe")
        return ""

    try:
        segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True,  # Filter out silence
        )

        texts = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                texts.append(text)

        result = "".join(texts)
        logger.info(f"ASR result ({info.language}, {info.duration:.1f}s): {result[:100]}...")
        return result

    except Exception as e:
        logger.error(f"ASR transcription error: {e}")
        return ""
