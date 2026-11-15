import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from rematch.common.config import credential

if __name__=="__main__":
    r = httpx.post("http://127.0.0.1:8101/admin/simulate-lab-feed",headers={"X-API-Key":credential("clinic-a","coordinator")},timeout=30)
    r.raise_for_status()
    print(r.json())
