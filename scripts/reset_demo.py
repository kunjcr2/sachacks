import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.generate_synthetic import initialize

if __name__=="__main__":
    initialize(force=True)
    print("Full network reset to day zero. Start scripts/run_demo.py.")
