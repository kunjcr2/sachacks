import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rematch.extraction.ctgov import fetch_trial,trial_preview
from rematch.extraction.llm import LLMExtractor


if __name__=="__main__":
    p = argparse.ArgumentParser(description="Optional public-text extraction. Output is always an unverified draft.")
    p.add_argument("nct_id")
    args = p.parse_args()
    preview = trial_preview(fetch_trial(args.nct_id))
    try:
        criteria = LLMExtractor().extract(args.nct_id,preview["eligibility"])
    except Exception as exc:
        raise SystemExit(f"Extraction failed ({type(exc).__name__}). The offline curated demo remains available. Check configuration and public source text.") from exc
    out = Path("runtime")/f"{args.nct_id}-draft.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text("["+",\n".join(c.model_dump_json(indent=2) for c in criteria)+"]")
    print(f"Draft saved to {out}. Human verification is mandatory before publication.")
