"""PyInstaller 单入口：启动 Drama Remix 后端服务。"""
import sys
import os
import json
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

def get_resource_dir():
    if getattr(sys, '_MEIPASS', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent

RESOURCE_DIR = get_resource_dir()
APP_DIR = RESOURCE_DIR / 'app'
STORAGE_DIR = Path(tempfile.gettempdir()) / 'drama_remix_storage'
STORAGE_DIR.mkdir(exist_ok=True)

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
    print(f"=== GPU Detection ===")
    if gpu_info['has_nvidia_gpu']:
        print(f"  NVIDIA GPU: {gpu_info['gpu_name']}")
        if gpu_info['driver_installed']:
            print(f"  Driver: Installed")
        else:
            print(f"  Driver: NOT INSTALLED")
            print(f"  Download: {gpu_info['driver_url']}")
    else:
        print(f"  No NVIDIA GPU detected (CPU mode)")
    print(f"====================")

    info_file = STORAGE_DIR / 'backend_info.json'
    info = {'host': host, 'port': port, 'storage_dir': str(STORAGE_DIR)}
    info.update(gpu_info)
    with open(info_file, 'w', encoding='utf-8') as f:
        json.dump(info, f)

    print(f"=== Drama Remix Backend ===")
    print(f"Port: {port}")
    print(f"Storage: {STORAGE_DIR}")
    print(f"================================")

    python_exe = sys.executable
    env = os.environ.copy()
    env['STORAGE_ROOT'] = str(STORAGE_DIR)
    env['DATABASE_URL'] = f'sqlite+aiosqlite:///{STORAGE_DIR / "drama_remix.db"}'
    env['PYTHONPATH'] = str(RESOURCE_DIR)

    cmd = [python_exe, '-m', 'uvicorn', 'app.main:app',
           '--host', host, '--port', str(port)]

    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(APP_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        print(f"Backend PID: {proc.pid}")
        print(f"Waiting for server to start...")

        for _ in range(60):
            if proc.poll() is not None:
                print(f"Backend process exited with code: {proc.poll()}")
                break
            try:
                urllib.request.urlopen(f'http://{host}:{port}/api/health', timeout=2)
                print(f"Backend ready at http://{host}:{port}")
                break
            except Exception:
                time.sleep(1)
        else:
            print("WARNING: Backend may not have started properly")

        for line in proc.stdout:
            print(line, end='')

    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            proc.wait()
        try:
            if info_file.exists():
                info_file.unlink()
        except Exception:
            pass

if __name__ == '__main__':
    main()
