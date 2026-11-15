import httpx
import pytest
from scripts import run_demo


@pytest.mark.parametrize('architecture,page,expected', [
    ('central-v1', '<div id="root"></div><script src="/assets/app.js"></script>', True),
    ('other-app', '<div id="root"></div><script src="/assets/app.js"></script>', False),
    ('central-v1', '<h1>Old backend</h1>', False),
])
def test_only_running_rematch_react_is_reused(monkeypatch, architecture, page, expected):
    real_client = httpx.Client
    def respond(request):
        if request.url.path == '/health':
            return httpx.Response(200, json={'architecture': architecture, 'synthetic_only': True})
        return httpx.Response(200, text=page)
    monkeypatch.setattr(run_demo.httpx, 'Client', lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(respond)))
    assert run_demo.existing_react_demo() is expected


def test_running_demo_is_reopened_without_starting_or_resetting(monkeypatch):
    monkeypatch.setattr(run_demo.sys, 'argv', ['run_demo.py', '--no-browser'])
    monkeypatch.setattr(run_demo, 'existing_react_demo', lambda: True)
    monkeypatch.setattr(run_demo, 'ensure_stopped', lambda: pytest.fail('Should reuse existing demo'))
    monkeypatch.setattr(run_demo, 'initialize', lambda **kwargs: pytest.fail('Must not touch data'))
    run_demo.main()


def test_reset_of_running_demo_is_refused_without_traceback(monkeypatch):
    monkeypatch.setattr(run_demo.sys, 'argv', ['run_demo.py', '--reset'])
    monkeypatch.setattr(run_demo, 'existing_react_demo', lambda: True)
    with pytest.raises(SystemExit, match='Stop its launcher'):
        run_demo.main()
