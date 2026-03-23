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

# 获取资源根目录（PyInstaller 解压后或开发环境）
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

def main():
    port = find_free_port()
    host = '127.0.0.1'

    info_file = STORAGE_DIR / 'backend_info.json'
    with open(info_file, 'w', encoding='utf-8') as f:
        json.dump({'host': host, 'port': port, 'storage_dir': str(STORAGE_DIR)}, f)

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
