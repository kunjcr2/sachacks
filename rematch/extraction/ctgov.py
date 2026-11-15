from datetime import datetime,timezone
import hashlib
import json
import re
import httpx
from rematch.common.config import ROOT

API = "https://clinicaltrials.gov/api/v2/studies"


def fetch_trial(nct_id,refresh=False):
    if not re.fullmatch(r"NCT\d{8}",nct_id):
        raise ValueError("Enter a valid NCT ID, for example NCT03548935")
    directory = ROOT/"data/trials/raw"
    directory.mkdir(parents=True,exist_ok=True)
    path = directory/f"{nct_id}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    response = httpx.get(f"{API}/{nct_id}",timeout=25,follow_redirects=True)
    response.raise_for_status()
    raw = response.json()
    eligibility = raw["protocolSection"]["eligibilityModule"]["eligibilityCriteria"]
    cached = {"retrieved_at":datetime.now(timezone.utc).isoformat(),"source_url":str(response.url),
              "source_hash":hashlib.sha256(eligibility.encode()).hexdigest(),"record":raw}
    path.write_text(json.dumps(cached,indent=2,ensure_ascii=False),encoding="utf-8")
    return cached


def cached_trials():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT/"data/trials/raw").glob("NCT*.json"))]


def trial_preview(cached):
    protocol = cached["record"]["protocolSection"]
    return {"nct_id":protocol["identificationModule"]["nctId"],"title":protocol["identificationModule"]["briefTitle"],
            "eligibility":protocol["eligibilityModule"]["eligibilityCriteria"],"status":protocol["statusModule"]["overallStatus"],
            "last_update":protocol["statusModule"]["lastUpdatePostDateStruct"]["date"],"retrieved_at":cached["retrieved_at"],
            "minimum_age":protocol["eligibilityModule"].get("minimumAge"),"maximum_age":protocol["eligibilityModule"].get("maximumAge"),
            "sex":protocol["eligibilityModule"].get("sex"),"source_url":cached["source_url"],"source_hash":cached["source_hash"]}
