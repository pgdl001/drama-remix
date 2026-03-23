"""Fish Speech TTS Service - Voice cloning using Fish Speech V1.5.

Fish Speech V1.5 is a multilingual TTS model that supports zero-shot voice cloning
from a reference audio sample. It provides high-quality speech synthesis.
"""

import asyncio
import logging
import os
import queue
import sys
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
import torch

from app.config import settings

logger = logging.getLogger("fish_speech_tts")

_model = None
_model_loaded = False
_model_load_error = ""
_llama_queue = None
_decoder_model = None
_tts_engine = None


def _add_fish_speech_to_path():
    """Add Fish Speech repo to Python path."""
    fish_repo_path = settings.FISH_SPEECH_REPO_DIR
    if fish_repo_path and fish_repo_path not in sys.path:
        sys.path.insert(0, fish_repo_path)
        logger.info(f"Added Fish Speech repo to path: {fish_repo_path}")


def _get_fish_speech_model():
    """Lazy-load the Fish Speech model (singleton)."""
    global _model, _model_loaded, _model_load_error
    global _llama_queue, _decoder_model, _tts_engine

    if _model_loaded:
        return _tts_engine

    try:
        _add_fish_speech_to_path()

        from fish_speech.models.text2semantic.inference import launch_thread_safe_queue
        from fish_speech.models.dac.inference import load_model as load_decoder_model
        from fish_speech.inference_engine import TTSInferenceEngine
        from fish_speech.utils.schema import ServeTTSRequest

        llama_path = settings.FISH_SPEECH_LLAMA_PATH
        decoder_path = settings.FISH_SPEECH_DECODER_PATH
        tokenizer_path = settings.FISH_SPEECH_TOKENIZER_PATH

        if not llama_path or not Path(llama_path).exists():
            raise FileNotFoundError(f"LLAMA model not found: {llama_path}")
        if not decoder_path or not Path(decoder_path).exists():
            raise FileNotFoundError(f"Decoder model not found: {decoder_path}")
        if not tokenizer_path or not Path(tokenizer_path).exists():
            raise FileNotFoundError(f"Tokenizer not found: {tokenizer_path}")

        device = "cuda" if torch.cuda.is_available() else "cpu"
        precision = torch.half if torch.cuda.is_available() else torch.bfloat16

        logger.info(f"Fish Speech loading on {device}, precision={precision}")
        logger.info(f"Loading LLAMA model from: {llama_path}")

        _llama_queue = launch_thread_safe_queue(
            checkpoint_path=llama_path,
            device=device,
            precision=precision,
            compile=False,
        )
        logger.info("LLAMA model loaded")

        logger.info(f"Loading decoder model from: {decoder_path}")
        _decoder_model = load_decoder_model(
            config_name="firefly-gan-vq-fsq-8x1024-21hz",
            checkpoint_path=decoder_path,
            device=device,
        )
        logger.info("Decoder model loaded")

        _tts_engine = TTSInferenceEngine(
            llama_queue=_llama_queue,
            decoder_model=_decoder_model,
            precision=precision,
            compile=False,
        )

        _model_loaded = True
        logger.info("Fish Speech TTS engine loaded successfully")
        return _tts_engine

    except Exception as e:
        _model_load_error = f"{type(e).__name__}: {e}"
        logger.error(f"Failed to load Fish Speech: {_model_load_error}")
        return None


def synthesize_with_fish_speech_sync(
    text: str,
    reference_audio_path: str,
    prompt_text: str,
    output_path: str,
    speed: float = 1.0,
) -> bool:
    """Synthesize speech using Fish Speech zero-shot voice cloning (sync).

    Args:
        text: The text to synthesize
        reference_audio_path: Path to the reference voice sample
        prompt_text: Transcript of the reference audio
        output_path: Where to save the output WAV
        speed: Speech speed multiplier (not directly supported, will use default)

    Returns:
        True if successful
    """
    from fish_speech.utils.schema import ServeTTSRequest

    engine = _get_fish_speech_model()
    if engine is None:
        logger.warning(f"Fish Speech not available: {_model_load_error}")
        return False

    try:
        ref_audio_path = Path(reference_audio_path)
        if not ref_audio_path.exists():
            logger.error(f"Reference audio not found: {reference_audio_path}")
            return False

        logger.info(
            f"Fish Speech synthesizing: text={len(text)} chars, "
            f"ref={ref_audio_path.name}, speed={speed}"
        )

        request = ServeTTSRequest(
            text=text,
            references=[(str(ref_audio_path), prompt_text)],
            reference_id=None,
            max_new_tokens=1024,
            chunk_length=200,
            top_p=0.7,
            repetition_penalty=1.2,
            temperature=0.7,
            format="wav",
            streaming=False,
        )

        audio_result = None
        for result in engine.inference(request):
            if result.code == "final":
                audio_result = result.audio
                break
            elif result.code == "error":
                logger.error(f"Fish Speech inference error: {result.error}")
                return False

        if audio_result is None:
            logger.warning("Fish Speech produced no output")
            return False

        sample_rate, audio_data = audio_result

        if speed != 1.0:
            import scipy.signal as signal
            indices = np.round(np.arange(0, len(audio_data), speed)).astype(int)
            indices = indices[indices < len(audio_data)]
            audio_data = audio_data[indices]

        sf.write(output_path, audio_data, sample_rate)

        size = Path(output_path).stat().st_size
        duration = len(audio_data) / sample_rate
        logger.info(f"Fish Speech output saved: {output_path} ({size} bytes, {duration:.1f}s)")
        return True

    except Exception as e:
        logger.error(f"Fish Speech synthesis error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def synthesize_with_fish_speech(
    text: str,
    reference_audio_path: str,
    prompt_text: str,
    output_path: str,
    speed: float = 1.0,
) -> bool:
    """Async wrapper for Fish Speech synthesis."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        synthesize_with_fish_speech_sync,
        text, reference_audio_path, prompt_text, output_path, speed,
    )


def is_fish_speech_available() -> bool:
    """Check if Fish Speech model can be loaded."""
    engine = _get_fish_speech_model()
    return engine is not None
