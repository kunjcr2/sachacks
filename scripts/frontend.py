"""Build the React client only when its inputs changed; no background Node server."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'frontend'

def build_frontend():
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Install Node.js 20.19+ or 22+, then run python scripts/setup.py.')
    tools = FRONTEND / 'node_modules'
    if not (tools / 'vite' / 'bin' / 'vite.js').is_file():
        raise RuntimeError('React dependencies are missing. Run npm ci --prefix frontend first, or python scripts/setup.py.')
    inputs = [FRONTEND / p for p in ['package.json', 'package-lock.json', 'index.html', 'vite.config.ts', 'tsconfig.json']]
    inputs += [p for folder in ['src', 'public'] for p in (FRONTEND / folder).rglob('*') if p.is_file()]
    output = FRONTEND / 'dist' / 'index.html'
    if output.is_file() and output.stat().st_mtime >= max(p.stat().st_mtime for p in inputs):
        print('React build is current.', flush=True)
        return
    print('Building React frontend...', flush=True)
    subprocess.run([node, str(tools / 'typescript' / 'bin' / 'tsc'), '-b'], cwd=FRONTEND, check=True)
    subprocess.run([node, str(tools / 'vite' / 'bin' / 'vite.js'), 'build'], cwd=FRONTEND, check=True)
