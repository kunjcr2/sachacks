"""Explicitly reset ReMatch in place, or reseed and start the backend if stopped.

Run on the backend machine: python scripts/flush_demo.py
Use --no-start to reseed an offline backend without starting it.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from rematch.common.config import ROOT, credential
from scripts.generate_synthetic import initialize

URL = 'http://127.0.0.1:8000'


def reset_running_backend():
    # Never send the admin key to a configured public/ngrok URL.
    with httpx.Client(base_url=URL, trust_env=False, timeout=30) as client:
        try:
            health = client.get('/health', timeout=3)
        except httpx.ConnectError:
            return False
        except httpx.RequestError:
            raise SystemExit('Port 8000 is not responding. Stop the backend and rerun this command.') from None
        try:
            info = health.json()
        except ValueError:
            raise SystemExit('Port 8000 is occupied by another service. Nothing was reset.') from None
        if health.status_code != 200 or not isinstance(info, dict) or info.get('architecture') != 'central-v1' or not info.get('synthetic_only'):
            raise SystemExit('Port 8000 is not the ReMatch synthetic backend. Nothing was reset.')
        try:
            key = credential('central', 'admin')
        except (OSError, KeyError, ValueError):
            raise SystemExit('Local administrator credentials are missing. Run this script on the backend machine with the same REMATCH_KEYS configuration.') from None
        try:
            response = client.post('/demo/reset', headers={'X-API-Key': key})
        except httpx.RequestError:
            raise SystemExit('The reset response was interrupted. Check the backend terminal before retrying.') from None
        if response.status_code == 404:
            raise SystemExit('The running backend is an older version. Stop it with Ctrl+C, then rerun this script; it will reset and start the updated backend.')
        if response.status_code in {401, 403}:
            raise SystemExit('Administrator authentication failed. Use the same REMATCH_KEYS directory as the running backend.')
        if not response.is_success:
            raise SystemExit(f'Reset returned HTTP {response.status_code}. Check the backend terminal before retrying.')
        return True


def main():
    parser = argparse.ArgumentParser(description='Erase all current synthetic ReMatch data and sessions, restore study drafts, and start fresh. Keeps .env, encryption keys and ngrok configuration.')
    parser.add_argument('--no-start', action='store_true', help='If the backend is stopped, reset without starting it')
    args = parser.parse_args()
    print('Resetting synthetic profiles, records, permissions, matches, discussions, introductions, payments and clock...', flush=True)
    running = reset_running_backend()
    if not running:
        initialize(force=True)
    print('Fresh state: two patient profiles, four unpublished study drafts, no record permissions or introductions.', flush=True)
    print('Reload the Vercel page to establish a fresh session. Keep your ngrok tunnel running.', flush=True)
    if running:
        print('All browser sessions invalidated. The existing backend is ready; no restart needed.', flush=True)
        return
    if args.no_start:
        print('Reset complete. Backend remains stopped.', flush=True)
        return
    print(f'Starting backend at {URL}. Ctrl+C stops it.', flush=True)
    # Replace this process so Ctrl+C reaches Uvicorn directly on macOS/Linux.
    command = [sys.executable, '-m', 'uvicorn', 'rematch.api:create_app', '--factory',
               '--host', '127.0.0.1', '--port', '8000', '--workers', '1', '--no-access-log']
    os.chdir(ROOT)
    if os.name == 'nt':
        try:
            raise SystemExit(subprocess.call(command))
        except KeyboardInterrupt:
            return
    os.execv(sys.executable, command)


if __name__ == '__main__':
    main()
