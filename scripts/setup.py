"""Run with any normal Python 3.11+, or use `uv sync` instead."""
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def main():
    import shutil
    if shutil.which("uv"):
        env = dict(os.environ,UV_CACHE_DIR=str(ROOT/".cache/uv"),UV_PYTHON_INSTALL_DIR=str(ROOT/".python"))
        subprocess.run(["uv","sync","--locked","--python","3.12","--project",str(ROOT)],check=True,env=env)
        print("Ready. Run .venv/Scripts/python scripts/run_demo.py on Windows.")
        return
    target = ROOT / ".venv"
    python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        try:
            venv.create(target, with_pip=True)
        except Exception as exc:
            raise SystemExit("A standard Python with pip is required. Alternatively install uv and run: uv sync") from exc
    subprocess.run([str(python), "-m", "pip", "install", "-e", str(ROOT)], check=True)
    print("Ready. Run .venv/Scripts/python scripts/run_demo.py on Windows.")


if __name__ == "__main__":
    main()
