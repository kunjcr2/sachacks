from pathlib import Path
import json
import os
import secrets
from threading import RLock
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
RUNTIME = Path(os.getenv('REMATCH_RUNTIME', str(ROOT / 'runtime')))
KEYS = Path(os.getenv('REMATCH_KEYS', str(ROOT / '.keys')))
API_URL = os.getenv('REMATCH_API_URL', 'http://127.0.0.1:8000')
ALLOWED_ORIGINS = frozenset(origin.strip().rstrip('/') for origin in os.getenv('REMATCH_ALLOWED_ORIGINS', '').split(',') if origin.strip())
COOKIE_SECURE = os.getenv('REMATCH_COOKIE_SECURE', 'false').lower() in {'true', '1', 'yes'}
DISCLAIMER = 'Synthetic screening support only. The study investigator determines formal eligibility.'
_credential_lock = RLock()
DEMO_PRINCIPALS = ('onboarding', 'patient-1', 'patient-2', 'doctor-1', 'team-1', 'team-2', 'admin')

def credential(service, role):
    return json.loads((KEYS / f'{service}-auth.json').read_text())[role]

def initialize_credentials():
    KEYS.mkdir(parents=True, exist_ok=True)
    path = KEYS / 'central-auth.json'
    if not path.exists():
        path.write_text(json.dumps({role: secrets.token_urlsafe(32) for role in DEMO_PRINCIPALS}))

def reset_profile_credentials():
    """Remove credentials for profiles erased by an explicit demo reset."""
    with _credential_lock:
        initialize_credentials()
        path = KEYS / 'central-auth.json'
        tokens = json.loads(path.read_text())
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps({actor: tokens.get(actor) or secrets.token_urlsafe(32) for actor in DEMO_PRINCIPALS}))
        temporary.replace(path)

def register_principal(actor):
    with _credential_lock:
        path = KEYS / 'central-auth.json'
        tokens = json.loads(path.read_text())
        tokens[actor] = secrets.token_urlsafe(32)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(tokens))
        temporary.replace(path)
        return tokens[actor]
