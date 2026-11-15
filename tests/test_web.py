from fastapi.testclient import TestClient
from rematch.api import create_app


def browser(service):
    return TestClient(create_app(service, auth={'patient-1': 'test-patient-key'}))


def test_browser_session_is_opaque_and_preserves_role_boundaries(service):
    client = browser(service)
    headers = {'X-Rematch-Intent': 'browser'}
    response = client.post('/api/demo/session', json={'actor': 'patient-1'}, headers=headers)
    assert response.status_code == 200
    assert 'test-patient-key' not in response.text
    assert 'HttpOnly' in response.headers['set-cookie']
    assert client.get('/api/me').json()['identity']['name'] == 'Alex Demo'
    assert client.get('/api/team/introductions').status_code == 403
    assert client.post('/api/me/permissions', json={'kind': 'screening', 'granted': True}).status_code == 403
    assert client.post('/api/demo/session', json={'actor': 'team-1'}, headers={**headers, 'Origin': 'https://other.example'}).status_code == 403
    assert client.post('/api/demo/session', json={'actor': 'admin'}, headers=headers).status_code == 404


def test_browser_onboarding_sets_session_without_returning_service_key(service):
    client = browser(service)
    headers = {'X-Rematch-Intent': 'browser'}
    client.post('/api/demo/session', json={'actor': 'onboarding'}, headers=headers)
    result = client.post('/api/profiles', json={'name': 'React Synthetic', 'contact_method': 'email', 'contact': 'react@example.invalid', 'assigned_pcp': 'doctor-1'}, headers=headers)
    assert result.status_code == 200 and 'demo_token' not in result.json()
    assert client.get('/api/me').json()['identity']['name'] == 'React Synthetic'
    assert client.get('/api/me/clinical-summary').json() == {'current': [], 'history': []}
    assert client.post('/api/me/records/connect', headers=headers).status_code == 409


def test_compiled_frontend_and_api_are_served_together(service):
    from rematch.common.config import ROOT
    if not (ROOT / 'frontend/dist/index.html').is_file():
        import pytest
        pytest.skip('Build the React frontend to check compiled asset serving')
    client = browser(service)
    response = client.get('/')
    assert response.status_code == 200 and 'id="root"' in response.text
    assert client.get('/api/health').json()['architecture'] == 'central-v1'
    assert client.get('/.keys/central-auth.json').status_code == 404
