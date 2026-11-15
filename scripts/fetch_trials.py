import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rematch.extraction.ctgov import fetch_trial,trial_preview


if __name__=="__main__":
    p = argparse.ArgumentParser(description="Cache a public trial for research-team source inspection. No patient data is used.")
    p.add_argument("nct_id",nargs="?",default="NCT03548935")
    p.add_argument("--refresh",action="store_true")
    args = p.parse_args()
    trial = trial_preview(fetch_trial(args.nct_id,args.refresh))
    print(f"Cached {trial['nct_id']}: {trial['title']} ({trial['status']}). Source only — not distributed for matching.")
