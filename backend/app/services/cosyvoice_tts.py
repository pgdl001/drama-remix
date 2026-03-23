"""CosyVoice TTS Service - Voice cloning using CosyVoice2.

Loads CosyVoice2-0.5B model and provides zero-shot voice cloning:
given a reference audio sample and text, synthesize speech in the cloned voice.
Falls back to pyttsx3 if CosyVoice is unavailable.
"""

import asyncio
import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path

import torch
import torchaudio

from app.config import settings

logger = logging.getLogger("cosyvoice_tts")

# Singleton model instance (loaded once, reused)
_model = None
_model_loaded = False
_model_load_error = ""
_model_load_attempts = 0
_MODEL_MAX_RETRIES = 3  # Allow up to 3 load attempts before giving up


def _get_cosyvoice_model():
    """Lazy-load the CosyVoice2 model (singleton).

    IMPORTANT: Previous bug — a single transient failure (CUDA init race,
    file lock, import timing) permanently disabled CosyVoice for the
    entire backend process lifetime because _model_loaded was set to True
    on failure. Now we allow up to _MODEL_MAX_RETRIES attempts.
    """
    global _model, _model_loaded, _model_load_error, _model_load_attempts

    # Already loaded successfully → return cached model
    if _model_loaded and _model is not None:
        return _model

    # Exhausted all retries → give up
    if _model_load_attempts >= _MODEL_MAX_RETRIES:
        return None

    _model_load_attempts += 1
    logger.info(f"CosyVoice model load attempt {_model_load_attempts}/{_MODEL_MAX_RETRIES}...")

    try:
        # Add CosyVoice repo AND Matcha-TTS third_party to path
        repo_dir = settings.COSYVOICE_REPO_DIR
        if not repo_dir:
            candidates = [
                Path(settings.STORAGE_ROOT).parent.parent / "cosyvoice_repo",
                Path(__file__).parent.parent.parent.parent / "cosyvoice_repo",
            ]
            for c in candidates:
                if c.exists():
                    repo_dir = str(c)
                    break

        if repo_dir:
            for sub in [repo_dir, os.path.join(repo_dir, "third_party", "Matcha-TTS")]:
                if sub not in sys.path and os.path.isdir(sub):
                    sys.path.insert(0, sub)
            logger.info(f"Added CosyVoice repo to path: {repo_dir}")
        else:
            logger.error("CosyVoice repo_dir not found!")

        logger.info("Importing CosyVoice2...")
        from cosyvoice.cli.cosyvoice import CosyVoice2
        logger.info("CosyVoice2 import OK")

        # Find model directory
        model_dir = settings.COSYVOICE_MODEL_DIR
        if not model_dir:
            # Auto-detect: look in cosyvoice_models or use modelscope ID
            model_candidates = [
                Path(settings.STORAGE_ROOT).parent.parent / "cosyvoice_models" / "iic" / "CosyVoice2-0.5B",
                Path(settings.STORAGE_ROOT).parent.parent / "cosyvoice_models",
            ]
            for mc in model_candidates:
                if mc.exists() and (mc / "cosyvoice2.yaml").exists():
                    model_dir = str(mc)
                    break
                # Check subdirectories
                for sub in mc.glob("**/cosyvoice2.yaml"):
                    model_dir = str(sub.parent)
                    break
                if model_dir:
                    break

            if not model_dir:
                # Use modelscope ID - it will auto-download
                model_dir = "iic/CosyVoice2-0.5B"

        logger.info(f"Loading CosyVoice2 model from: {model_dir}")
        use_fp16 = torch.cuda.is_available()
        logger.info(f"CUDA={'YES' if use_fp16 else 'NO'}, fp16={use_fp16}")
        _model = CosyVoice2(model_dir, load_jit=False, load_trt=False, fp16=use_fp16)

        # On CPU: force all model weights to float32 (checkpoints are BFloat16)
        if not torch.cuda.is_available():
            logger.info("No CUDA - converting CosyVoice2 model to float32")
            _model.model.llm.float()
            _model.model.flow.float()
            _model.model.hift.float()

        _model_loaded = True
        logger.info(f"CosyVoice2 loaded successfully (sample_rate={_model.sample_rate})")
        return _model

    except Exception as e:
        _model_load_error = f"{type(e).__name__}: {e}"
        logger.error(f"Failed to load CosyVoice2 (attempt {_model_load_attempts}/{_MODEL_MAX_RETRIES}): {_model_load_error}")
        # Don't set _model_loaded=True here — allow retry on next call
        return None


def synthesize_with_cosyvoice_sync(
    text: str,
    reference_audio_path: str,
    prompt_text: str,
    output_path: str,
    speed: float = 1.0,
) -> bool:
    """Synthesize speech using CosyVoice2 zero-shot voice cloning (sync).

    Args:
        text: The text to synthesize
        reference_audio_path: Path to the reference voice sample (16kHz WAV)
        prompt_text: Transcript of the reference audio
        output_path: Where to save the output WAV
        speed: Speech speed multiplier

    Returns:
        True if successful
    """
    model = _get_cosyvoice_model()
    if model is None:
        logger.warning(f"CosyVoice not available: {_model_load_error}")
        return False

    try:
        import soundfile as sf

        # CRITICAL FIX: Pass the FILE PATH (not a tensor) to CosyVoice.
        #
        # CosyVoice's internal load_wav() reads the file and resamples to
        # multiple target rates:
        #   - _extract_speech_feat  needs 24 kHz
        #   - _extract_speech_token needs 16 kHz
        #   - _extract_spk_embedding needs 16 kHz
        #
        # When a raw tensor is passed, load_wav ASSUMES the tensor is already
        # at the target sample rate (no resampling). We were passing a 16 kHz
        # tensor, so _extract_speech_feat treated 16 kHz data as 24 kHz —
        # producing completely garbled speech features and nonsensical output.
        #
        # By passing the file path, load_wav reads the WAV header, discovers
        # the true sample rate, and resamples correctly for each consumer.

        # Verify reference audio is readable
        info_data, info_sr = sf.read(reference_audio_path, dtype='float32')
        ref_duration = len(info_data) / info_sr
        logger.info(
            f"CosyVoice synthesizing: text={len(text)} chars, "
            f"ref={Path(reference_audio_path).name} ({info_sr}Hz, {ref_duration:.1f}s), "
            f"prompt_text='{prompt_text[:40]}...'"
        )
        del info_data  # free memory

        # Collect all output chunks (pass file path, NOT tensor)
        all_speech = []
        for result in model.inference_zero_shot(
            tts_text=text,
            prompt_text=prompt_text,
            prompt_wav=reference_audio_path,
            stream=False,
            speed=speed,
        ):
            all_speech.append(result["tts_speech"])

        if not all_speech:
            logger.warning("CosyVoice produced no output")
            return False

        # Concatenate and save using soundfile
        speech = torch.cat(all_speech, dim=1)

        # Save raw CosyVoice output first (native sample rate, usually 24000Hz mono)
        raw_path = output_path + ".raw.wav"
        sf.write(raw_path, speech.squeeze(0).cpu().numpy(), model.sample_rate)

        # Normalize to pipeline standard format (44100Hz stereo PCM WAV)
        # using the centralized audio_utils to ensure consistency.
        try:
            from app.services.audio_utils import normalize_audio_file
            if normalize_audio_file(raw_path, output_path):
                try:
                    os.remove(raw_path)
                except OSError:
                    pass
            else:
                # Fallback: use raw file as-is
                logger.warning(f"CosyVoice audio normalize failed, using raw output")
                os.replace(raw_path, output_path)
        except Exception as conv_e:
            logger.warning(f"CosyVoice normalize exception: {conv_e}, using raw")
            if os.path.exists(raw_path):
                os.replace(raw_path, output_path)

        size = Path(output_path).stat().st_size
        duration = speech.shape[1] / model.sample_rate
        logger.info(f"CosyVoice output saved: {output_path} ({size} bytes, {duration:.1f}s)")
        return True

    except Exception as e:
        logger.error(f"CosyVoice synthesis error: {type(e).__name__}: {e}")
        return False


async def synthesize_with_cosyvoice(
    text: str,
    reference_audio_path: str,
    prompt_text: str,
    output_path: str,
    speed: float = 1.0,
) -> bool:
    """Async wrapper for CosyVoice synthesis."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        synthesize_with_cosyvoice_sync,
        text, reference_audio_path, prompt_text, output_path, speed,
    )


def is_cosyvoice_available() -> bool:
    """Check if CosyVoice model can be loaded."""
    model = _get_cosyvoice_model()
    return model is not None
