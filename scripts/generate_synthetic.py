"""Initialize independent demo databases and keys. No paid APIs needed."""
import argparse
import base64
import socket
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rematch.common.config import RUNTIME,initialize_credentials
from rematch.common.db import Store
from rematch.common.crypto import sponsor_private_key
from rematch.clinic.service import ClinicService
from rematch.clinic.seed import seed_clinic
from rematch.hub.seed import seed_registry


def ensure_stopped():
    for port in [8000,8101,8102,8501,8502,8503]:
        with socket.socket() as sock:
            sock.settimeout(0.15)
            if sock.connect_ex(("127.0.0.1",port))==0:
                raise RuntimeError(f"Port {port} is in use. Stop the demo with Ctrl+C before resetting databases.")


def initialize(force=False,seed=42):
    os.environ["REMATCH_MULTICLINIC"] = "1"
    initialize_credentials()
    RUNTIME.mkdir(parents=True,exist_ok=True)
    if force:
        ensure_stopped()
    hub_db = Store(RUNTIME/"hub.sqlite")
    if force:
        hub_db.clear()
    private = sponsor_private_key()
    seed_registry(hub_db,base64.b64encode(bytes(private.public_key)).decode())
    for cid in ["clinic-a","clinic-b"]:
        clinic = ClinicService(cid)
        if force:
            clinic.store.clear()
            clinic.store.put("meta","clock",{"today":"2026-11-15"})
            clinic.store.put("meta","privacy",{"min_cell_size":1})
        if not clinic.store.all("patient"):
            seed_clinic(clinic,seed)
        clinic.store.engine.dispose()
    hub_db.engine.dispose()
    print("Ready: 70 fictional patients, five synthetic protocols, two encrypted clinic identity vaults.",flush=True)


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed",type=int,default=42)
    parser.add_argument("--force",action="store_true",help="Reset all demo state; services must be stopped")
    args = parser.parse_args()
    initialize(args.force,args.seed)
