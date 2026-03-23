# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

block_cipher = None
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
APP_DIR = os.path.join(SPEC_DIR, 'app')

a = Analysis(
    [os.path.join(SPEC_DIR, 'standalone_main.py')],
    pathex=[SPEC_DIR],
    binaries=[],
    datas=[(APP_DIR, 'app')],
    hiddenimports=[
        'uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
        'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan', 'uvicorn.lifespan.on',
        'starlette', 'starlette.routing', 'starlette.middleware',
        'starlette.middleware.cors', 'starlette.responses', 'starlette.requests',
        'starlette.staticfiles', 'starlette.datastructures',
        'fastapi', 'fastapi.middleware', 'fastapi.middleware.cors',
        'fastapi.responses', 'fastapi.requests',
        'pydantic', 'pydantic_settings',
        'sqlalchemy', 'sqlalchemy.ext.asyncio', 'sqlalchemy.orm',
        'aiosqlite', 'bcrypt', 'python_multipart', 'jose',
        'httpx',
        'edge_tts',
        'soundfile', 'numpy',
        'json5', 'munch',
        'app.main', 'app.config', 'app.database',
        'app.routers.auth', 'app.routers.materials', 'app.routers.annotations',
        'app.routers.bgm', 'app.routers.remix', 'app.routers.render',
        'app.routers.review', 'app.routers.distribution', 'app.routers.dashboard',
        'app.routers.bundle', 'app.routers.voice',
        'app.services.edge_tts', 'app.services.narration_service',
        'app.services.asr_service', 'app.services.audio_utils',
        'app.services.remix_engine', 'app.services.render_service',
        'app.services.task_runner',
    ],
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=True, name='backend',
)
