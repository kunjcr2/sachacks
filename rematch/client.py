import httpx
from rematch.common.config import API_URL, credential

def request(actor, method, path, body=None, token=None):
    response = httpx.request(method, API_URL + path, json=body,
        headers={'X-API-Key': token or credential('central', actor)}, timeout=110, trust_env=False)
    if not response.is_success:
        try:
            detail = response.json().get('detail', 'Request failed')
        except ValueError:
            detail = 'Backend unavailable'
        raise RuntimeError(str(detail))
    return response.json()
