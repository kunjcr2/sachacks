import json
from rematch.common.config import ROOT
from rematch.common.schemas import TrialBundle


def load_trials() -> list[TrialBundle]:
    return [TrialBundle.model_validate_json(p.read_text(encoding="utf-8"))
            for p in sorted((ROOT / "data/trials/structured").glob("*.json"))]


class CuratedExtractor:
    def extract(self, trial_id: str, eligibility_text: str):
        trial = TrialBundle.model_validate_json((ROOT / f"data/trials/structured/{trial_id}.json").read_text(encoding="utf-8"))
        if eligibility_text != trial.raw_eligibility_text:
            raise ValueError("Curated rules do not match this source version. Human review is required.")
        return trial.criteria
