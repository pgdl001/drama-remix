"""PyInstaller single-entry: start the Drama Remix backend service."""
import sys
import os
import json
import socket
import subprocess
import tempfile
import time
import urllib.request
import asyncio
from pathlib import Path
from uvicorn import Config, Server

def get_resource_dir():
    if getattr(sys, '_MEIPASS', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent

RESOURCE_DIR = get_resource_dir()
APP_DIR = RESOURCE_DIR / 'app'
STORAGE_DIR = Path(tempfile.gettempdir()) / 'drama_remix_storage'
STORAGE_DIR.mkdir(exist_ok=True)

os.environ['STORAGE_ROOT'] = str(STORAGE_DIR)
os.environ['DATABASE_URL'] = f'sqlite+aiosqlite:///{STORAGE_DIR / "drama_remix.db"}'
sys.path.insert(0, str(RESOURCE_DIR))

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]

def detect_gpu():
    gpu_info = {'has_nvidia_gpu': False, 'gpu_name': None, 'driver_installed': False, 'driver_url': None}
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_info['has_nvidia_gpu'] = True
            gpu_info['gpu_name'] = result.stdout.strip().split('\n')[0]
            gpu_info['driver_installed'] = True
            gpu_info['driver_url'] = 'https://www.nvidia.com/Download/index.aspx'
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
                        gpu_info['driver_url'] = 'https://www.nvidia.com/Download/index.aspx'
                        break
        except Exception:
            pass
    return gpu_info

def main():
    port = find_free_port()
    host = '127.0.0.1'

    gpu_info = detect_gpu()
    print("=== GPU Detection ===")
    if gpu_info['has_nvidia_gpu']:
        print(f"  NVIDIA GPU: {gpu_info['gpu_name']}")
        if gpu_info['driver_installed']:
            print("  Driver: Installed")
        else:
            print("  Driver: NOT INSTALLED")
            print(f"  Download: {gpu_info['driver_url']}")
    else:
        print("  No NVIDIA GPU detected (CPU mode)")
    print("====================")

    info_file = STORAGE_DIR / 'backend_info.json'
    info = {'host': host, 'port': port, 'storage_dir': str(STORAGE_DIR)}
    info.update(gpu_info)
    with open(info_file, 'w', encoding='utf-8') as f:
        json.dump(info, f)

    print(f"=== Drama Remix Backend ===")
    print(f"Port: {port}")
    print(f"Storage: {STORAGE_DIR}")
    print("================================")

    sys.path.insert(0, str(APP_DIR))
    from main import app

    config = Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
    )
    server = Server(config)

    print(f"Starting server at http://{host}:{port}")

    try:
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        try:
            if info_file.exists():
                info_file.unlink()
        except Exception:
            pass

if __name__ == '__main__':
    main()
