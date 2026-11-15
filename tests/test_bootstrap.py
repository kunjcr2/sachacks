import base64
import pytest
from nacl.public import PrivateKey
from rematch.common.db import Store
from rematch.hub.seed import seed_registry
from rematch.extraction.curated import load_trials


def test_registry_bootstrap_preserves_existing_protocol_versions(tmp_path):
    db = Store(tmp_path/"hub.sqlite")
    public_key = base64.b64encode(bytes(PrivateKey.generate().public_key)).decode()
    seed_registry(db,public_key)
    assert len(db.all("trial"))==5
    trial = db.get("trial","SYN-0001")
    db.put("trial","SYN-0001",trial|{"version":2,"status":"paused"})
    seed_registry(db,public_key)
    assert db.get("trial","SYN-0001")["version"]==2
    assert db.get("trial","SYN-0001")["status"]=="paused"
    assert len(db.all("trial"))==5


def test_registry_bootstrap_rejects_unverified_fixtures(tmp_path,monkeypatch):
    trials = load_trials()
    trials[-1].criteria[0].review_status = "draft"
    monkeypatch.setattr("rematch.hub.seed.load_trials",lambda:trials)
    db = Store(tmp_path/"hub.sqlite")
    public_key = base64.b64encode(bytes(PrivateKey.generate().public_key)).decode()
    with pytest.raises(ValueError,match="verification"):
        seed_registry(db,public_key)
    assert not db.all("trial")
