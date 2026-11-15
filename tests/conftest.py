import pytest
from fastapi.testclient import TestClient
from rematch.api import create_app
from rematch.common.db import Store
from rematch.common.crypto import Vault
from rematch.seed import seed
from rematch.service import Service

@pytest.fixture
def service(tmp_path):
    result = Service(Store(tmp_path / 'central.sqlite'), Vault(tmp_path / 'keys' / 'vault.key'))
    seed(result)
    yield result
    result.store.engine.dispose()

@pytest.fixture
def api(service):
    tokens = {a: a + '-test-secret' for a in ['patient-1', 'patient-2', 'doctor-1', 'team-1', 'team-2', 'onboarding', 'admin']}
    client = TestClient(create_app(service, auth=tokens))
    def send(actor, method, path, body=None):
        return client.request(method, path, json=body, headers={'X-API-Key': tokens.get(actor, 'invalid')})
    return send

def connect(service, pid='patient-1'):
    service.permission(pid, 'screening', True)
    service.permission(pid, 'records', True)
    service.import_records(pid)
