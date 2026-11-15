"""Start all six processes; stop every child on Ctrl+C."""
import argparse
import os
import sys
from pathlib import Path
import subprocess
import time
import webbrowser
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from rematch.common.config import ROOT,RUNTIME,credential
from scripts.generate_synthetic import initialize,ensure_stopped


def wait_for(url,key,process,log,timeout=60):
    deadline = time.monotonic()+timeout
    last_report = time.monotonic()
    while time.monotonic()<deadline:
        if process.poll() is not None:
            detail = log.read_text(encoding="utf-8",errors="replace")[-2500:]
            raise RuntimeError(f"Service exited with code {process.returncode} while starting {url}.\n{detail}\nFull log: {log}")
        try:
            r = httpx.get(url,headers={"X-API-Key":key} if key else {},timeout=1,trust_env=False)
            if r.status_code==200:
                return
        except httpx.RequestError:
            pass
        if time.monotonic()-last_report>=5:
            print(f"    Still starting {url} ...",flush=True)
            last_report = time.monotonic()
        time.sleep(0.25)
    raise RuntimeError(f"Timed out starting {url}. See {log}")


def main():
    parser = argparse.ArgumentParser(description="ReMatch local hackathon demo")
    parser.add_argument("--reset",action="store_true",help="Restore the network before starting")
    parser.add_argument("--no-browser",action="store_true")
    parser.add_argument("--check",action="store_true",help="Start six processes, verify health, then stop")
    args = parser.parse_args()
    ensure_stopped()
    initialize(force=args.reset)
    children,logs = [],[]
    env = dict(os.environ,PYTHONPATH=str(ROOT),PYTHONUTF8="1",STREAMLIT_BROWSER_GATHER_USAGE_STATS="false",REMATCH_MULTICLINIC="1")
    env.pop("CLINIC_IDENTITY_KEY_B64",None)
    # Give each child its own process group so console control events from a
    # child cannot target the launcher's group on Windows.
    flags = (subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=="nt" else 0
    log_dir = RUNTIME/"logs"
    log_dir.mkdir(parents=True,exist_ok=True)

    def start(name,command,port,key=None,extra_env=None,streamlit=False):
        print(f"  Starting {name} on port {port} ...",flush=True)
        log_path = log_dir/f"{name}.log"
        handle = log_path.open("w",encoding="utf-8")
        logs.append(handle)
        proc = subprocess.Popen([sys.executable,*command],cwd=ROOT,env={**env,**(extra_env or {})},stdout=handle,stderr=subprocess.STDOUT,creationflags=flags)
        children.append(proc)
        endpoint = "/_stcore/health" if streamlit else "/health"
        wait_for(f"http://127.0.0.1:{port}{endpoint}",key,proc,log_path)
        print(f"  {name:12} ready at http://localhost:{port}",flush=True)

    try:
        print("Starting ReMatch (synthetic demo only)…",flush=True)
        start("hub",["-m","uvicorn","rematch.hub.main:app_factory","--factory","--host","127.0.0.1","--port","8000","--no-access-log"],8000,credential("hub","sponsor"))
        for cid,port in [("clinic-a",8101),("clinic-b",8102)]:
            start(cid,["-m","uvicorn","rematch.clinic.main:app_factory","--factory","--host","127.0.0.1","--port",str(port),"--no-access-log"],port,credential(cid,"coordinator"),{"CLINIC_ID":cid})
            r = httpx.post(f"http://127.0.0.1:{port}/admin/sync",headers={"X-API-Key":credential(cid,"coordinator")},timeout=45,trust_env=False)
            r.raise_for_status()
        for role,port,color in [("clinic",8501,"#147d72"),("sponsor",8502,"#5a55ba"),("patient",8503,"#b86638")]:
            start(role,["-m","streamlit","run",f"rematch/ui/{role}_app.py","--server.port",str(port),"--server.address","127.0.0.1","--server.headless","true","--browser.gatherUsageStats","false","--theme.base","light","--theme.primaryColor",color,"--theme.backgroundColor","#f7f9f8","--theme.secondaryBackgroundColor","#edf2ef"],port,streamlit=True)
        print("\nAll six processes are healthy. Read DEMO.md for the judges' walkthrough.",flush=True)
        if args.check:
            return
        if not args.no_browser:
            webbrowser.open("http://localhost:8501")
        print("Keep this terminal open. Ctrl+C stops the entire demo. Logs: runtime/logs/",flush=True)
        while True:
            if any(p.poll() is not None for p in children):
                raise RuntimeError("A demo process stopped. Inspect runtime/logs/, then restart the launcher.")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nLauncher received an interrupt; stopping ReMatch. No service crash is implied.",flush=True)
    finally:
        for proc in reversed(children):
            if proc.poll() is None:
                proc.terminate()
        for proc in children:
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        for handle in logs:
            handle.close()


if __name__ == "__main__":
    main()
