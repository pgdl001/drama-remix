"""Application configuration using pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Drama Remix Tool"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Database (SQLite for local dev)
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'drama_remix.db'}"

    # JWT Auth
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Storage paths (local filesystem)
    STORAGE_ROOT: Path = BASE_DIR / "storage"
    MATERIALS_DIR: Path = STORAGE_ROOT / "materials"
    OUTPUTS_DIR: Path = STORAGE_ROOT / "outputs"
    TEMP_DIR: Path = STORAGE_ROOT / "temp"
    BGM_DIR: Path = STORAGE_ROOT / "bgm"

    # FFmpeg
    FFMPEG_BIN: str = "ffmpeg"
    FFPROBE_BIN: str = "ffprobe"

    # Remix engine
    MAX_CONCURRENT_RENDERS: int = 2
    DEFAULT_OUTPUT_FORMAT: str = "mp4"
    DEFAULT_VIDEO_CODEC: str = "libx264"
    DEFAULT_AUDIO_CODEC: str = "aac"

    # Review engine
    FINGERPRINT_MUTATION_ENABLED: bool = True
    SELF_CHECK_DEDUP_ENABLED: bool = True

    # DeepSeek LLM (narration script generation)
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # TTS
    TTS_VOICE: str = "zh-CN-YunxiNeural"  # Male narrator voice
    TTS_RATE: str = "+10%"  # Slightly faster for dramatic effect

    # Narration audio dir
    NARRATION_DIR: Path = STORAGE_ROOT / "narration"

    # Voice samples dir
    VOICE_SAMPLES_DIR: Path = STORAGE_ROOT / "voice_samples"

    # CosyVoice model (已废弃)
    COSYVOICE_MODEL_DIR: str = ""
    COSYVOICE_REPO_DIR: str = ""

    # IndexTTS2 (B站开源)
    INDEXTTS_REPO_DIR: str = ""
    INDEXTTS_CHECKPOINT_PATH: str = ""

    # Fish Speech TTS model (已废弃)
    FISH_SPEECH_REPO_DIR: str = ""
    FISH_SPEECH_LLAMA_PATH: str = ""
    FISH_SPEECH_DECODER_PATH: str = ""
    FISH_SPEECH_TOKENIZER_PATH: str = ""

    model_config = {"env_file": BASE_DIR / ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Ensure directories exist
for d in [settings.MATERIALS_DIR, settings.OUTPUTS_DIR, settings.TEMP_DIR, settings.BGM_DIR, settings.NARRATION_DIR, settings.VOICE_SAMPLES_DIR]:
    d.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
