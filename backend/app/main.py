"""FastAPI application entry point."""

import logging
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import auth, materials, annotations, bgm, remix, render, review, distribution, dashboard, bundle, voice

logger = logging.getLogger("uvicorn")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown events."""
    await init_db()
    logger.info(f"[OK] {settings.APP_NAME} v{settings.APP_VERSION} started")
    logger.info(f"[OK] Database: {settings.DATABASE_URL}")
    logger.info(f"[OK] Storage: {settings.STORAGE_ROOT}")
    logger.info(f"[OK] Edge TTS voice: {settings.TTS_VOICE}")

    yield
    logger.info("[OK] Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


# Debug exception handler - return full traceback in dev mode
@app.exception_handler(Exception)
async def debug_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": "".join(tb)},
    )

# CORS - allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:*", "http://127.0.0.1:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static file serving for outputs
app.mount("/storage", StaticFiles(directory=str(settings.STORAGE_ROOT)), name="storage")

# Register routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(materials.router, prefix="/api/materials", tags=["materials"])
app.include_router(annotations.router, prefix="/api/annotations", tags=["annotations"])
app.include_router(bgm.router, prefix="/api/bgm", tags=["bgm"])
app.include_router(remix.router, prefix="/api/remix", tags=["remix"])
app.include_router(bundle.router, prefix="/api/bundles", tags=["bundles"])
app.include_router(render.router, prefix="/api/render", tags=["render"])
app.include_router(review.router, prefix="/api/review", tags=["review"])
app.include_router(distribution.router, prefix="/api/distribution", tags=["distribution"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(voice.router, prefix="/api/voice", tags=["voice"])


@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="http://localhost:5173")


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "edge_tts": f"voice={settings.TTS_VOICE}",
    }


@app.get("/api/gpu-info")
async def gpu_info():
    import subprocess
    gpu_info = {
        'has_nvidia_gpu': False,
        'gpu_name': None,
        'driver_installed': False,
        'driver_url': 'https://www.nvidia.com/Download/index.aspx'
    }
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_info['has_nvidia_gpu'] = True
            gpu_info['gpu_name'] = result.stdout.strip().split('\n')[0]
            gpu_info['driver_installed'] = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    if not gpu_info['has_nvidia_gpu']:
        try:
            result = subprocess.run(
                ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    line = line.strip()
                    if line and 'NVIDIA' in line.upper():
                        gpu_info['has_nvidia_gpu'] = True
                        gpu_info['gpu_name'] = line
                        break
        except Exception:
            pass
    return gpu_info
