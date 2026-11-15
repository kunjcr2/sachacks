"""Serve the built React UI and FastAPI together in one local backend."""
import argparse
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from rematch.common.config import ROOT, RUNTIME
from scripts.generate_synthetic import initialize, ensure_stopped
from scripts.frontend import build_frontend

def existing_react_demo():
    """Recognize this app without treating an arbitrary open port as ReMatch."""
    try:
        with httpx.Client(base_url='http://127.0.0.1:8000', timeout=2, trust_env=False) as client:
            health = client.get('/health')
            if health.status_code != 200:
                return False
            data = health.json()
            if data.get('architecture') != 'central-v1' or not data.get('synthetic_only'):
                return False
            page = client.get('/')
            return page.status_code == 200 and 'id="root"' in page.text and '/assets/' in page.text
    except (httpx.RequestError, ValueError):
        return False

def wait_for(url, process, log, timeout=45):
    deadline = time.monotonic() + timeout
    last_report = time.monotonic()
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Backend exited during startup. See {log}')
        try:
            if httpx.get(url, timeout=1, trust_env=False).status_code == 200:
                return
        except httpx.RequestError:
            pass
        if time.monotonic() - last_report >= 5:
            print('  Still starting the local backend...', flush=True)
            last_report = time.monotonic()
        time.sleep(.25)
    raise RuntimeError(f'Startup timed out. See {log}')

def main():
    parser = argparse.ArgumentParser(description='ReMatch React + FastAPI local demo')
    parser.add_argument('--reset', action='store_true', help='Explicitly erase and reseed only the central-v1 synthetic database')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--check', action='store_true', help='Verify backend and React asset health, then stop')
    args = parser.parse_args()
    if existing_react_demo():
        if args.reset:
            raise SystemExit('ReMatch is already running at http://localhost:8000. Stop its launcher with Ctrl+C before using --reset.')
        print('ReMatch is already running: http://localhost:8000', flush=True)
        if not args.no_browser and not args.check:
            webbrowser.open('http://localhost:8000')
        return
    try:
        ensure_stopped()
    except RuntimeError:
        raise SystemExit('Port 8000 is occupied by another service or an older ReMatch instance. Stop that process, then run this command again. No data was reset.') from None
    build_frontend()
    initialize(force=args.reset)
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8='1')
    flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == 'nt' else 0
    logs = RUNTIME / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / 'backend.log'
    with log_path.open('w', encoding='utf-8') as handle:
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'rematch.api:create_app', '--factory',
            '--host', '127.0.0.1', '--port', '8000', '--no-access-log'], cwd=ROOT, env=env,
            stdout=handle, stderr=subprocess.STDOUT, creationflags=flags)
        try:
            wait_for('http://127.0.0.1:8000/health', process, log_path)
            response = httpx.get('http://127.0.0.1:8000/', timeout=5, trust_env=False)
            response.raise_for_status()
            if 'id="root"' not in response.text:
                raise RuntimeError('The React entry point is missing.')
            print('Ready: http://localhost:8000 - React UI and API, one backend.', flush=True)
            if args.check:
                return
            if not args.no_browser:
                webbrowser.open('http://localhost:8000')
            print('Ctrl+C stops the local demo. No Node development server is running.', flush=True)
            while process.poll() is None:
                time.sleep(1)
            raise RuntimeError(f'Backend stopped. See {log_path}')
        except KeyboardInterrupt:
            print('Stopping ReMatch...', flush=True)
        finally:
            if process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

if __name__ == '__main__':
    main()
