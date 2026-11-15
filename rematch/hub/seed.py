"""Offline registry initialization; no HTTP server or testing framework needed."""
import base64
import hashlib
from rematch.common.schemas import SponsorRegistration
from rematch.extraction.curated import load_trials
from rematch.extraction.validate import validate_criteria


def seed_registry(db, public_key_b64):
    registration = SponsorRegistration(
        sponsor_id="meridian", name="Meridian Research Labs", public_key_b64=public_key_b64
    )
    key_id = hashlib.sha256(base64.b64decode(public_key_b64, validate=True)).hexdigest()[:16]
    db.put("sponsor", registration.sponsor_id, registration.model_dump() | {"key_id": key_id})
    if not db.all("trial"):
        trials = load_trials()
        for trial in trials:
            validate_criteria(trial.criteria, trial.raw_eligibility_text, publication=True)
        for trial in trials:
            db.put("trial", trial.trial_id, trial.model_dump(mode="json"))
