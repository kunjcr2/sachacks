"""Initialize only the new central schema. Old runtime files are never interpreted."""
import argparse
import socket
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rematch.common.config import RUNTIME, initialize_credentials, reset_profile_credentials
from rematch.service import Service
from rematch.seed import seed

def ensure_stopped():
    for port in [8000]:
        with socket.socket() as sock:
            sock.settimeout(0.15)
            if sock.connect_ex(('127.0.0.1', port)) == 0:
                raise RuntimeError(f'Port {port} is in use. Stop existing demo processes with Ctrl+C before starting/resetting.')

def initialize(force=False, seed_value=42):
    initialize_credentials()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if force:
        ensure_stopped()
    service = Service()
    if force:
        service.reset_demo()
        reset_profile_credentials()
    seed(service)
    service.store.engine.dispose()
    print('Ready: central-v1 synthetic database, two fake patient profiles, four study fixtures. Permissions start off.', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='Explicitly erase and reseed only central-v1 demo records')
    args = parser.parse_args()
    initialize(args.force)
