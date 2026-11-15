from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
RUNTIME = Path(os.getenv("REMATCH_RUNTIME", str(ROOT / "runtime")))
KEYS = Path(os.getenv("REMATCH_KEYS", str(ROOT / ".keys")))
HUB_URL = os.getenv("HUB_URL", "http://127.0.0.1:8000")
CLINICS = {"clinic-a": "Sunrise Family Health", "clinic-b": "Delta Valley Endocrinology"}
CLINIC_URLS = {"clinic-a": "http://127.0.0.1:8101", "clinic-b": "http://127.0.0.1:8102"}
SPONSOR_ID = "meridian"
DISCLAIMER = "Screening support only — formal eligibility is determined by the study investigator."


def credential(service: str, role: str) -> str:
    """Each process reads its own credential file, never other clinics' vault keys."""
    override = os.getenv(f"{service}_{role}_KEY".upper().replace("-", "_"))
    if override:
        return override
    path = KEYS / f"{service}-auth.json"
    if not path.exists():
        raise RuntimeError("Demo is not initialized. Run python scripts/generate_synthetic.py first.")
    return json.loads(path.read_text())[role]


def initialize_credentials() -> None:
    KEYS.mkdir(parents=True, exist_ok=True)
    groups = {"hub": ["clinic-a", "clinic-b", "sponsor", "inspector"],
              "clinic-a": ["coordinator", "patient"], "clinic-b": ["coordinator", "patient"]}
    for service, roles in groups.items():
        path = KEYS / f"{service}-auth.json"
        if not path.exists():
            path.write_text(json.dumps({r: secrets.token_urlsafe(32) for r in roles}), encoding="utf-8")
