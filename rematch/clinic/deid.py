import base64
from datetime import date
import hashlib
import hmac
import json
import re
from rematch.common.schemas import CandidatePacket,CandidateEvidence,RematchEvidence


def pseudonym(secret,patient_id,trial_id):
    digest = hmac.new(secret,f"{patient_id}|{trial_id}".encode(),hashlib.sha256).digest()
    return "RM-"+base64.b32encode(digest).decode()[:10]


def age_band(age):
    age = int(age)
    return "90+" if age>=90 else f"{age//5*5}–{age//5*5+4}"


class PIIGuard:
    def __init__(self,vault):
        self.vault = vault

    def check(self,model,allow_dates=False):
        # Re-validate to catch model_copy/update bypasses and forbid unknown keys.
        type(model).model_validate(model.model_dump())
        raw = model.model_dump_json().casefold()
        if re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b\d{3}-\d{2}-\d{4}\b|(?:\+?1[- .]?)?\(?\d{3}\)?[- .]\d{3}[- .]\d{4}",raw):
            raise ValueError("PII_GUARD_BLOCKED: contact/identifier pattern")
        if not allow_dates and re.search(r"\b\d{4}-\d{2}-\d{2}\b",raw):
            raise ValueError("PII_GUARD_BLOCKED: absolute date")
        by_length = {}
        for row in self.vault.store.all("identity_fingerprints"):
            for item in row["values"]:
                by_length.setdefault(item["length"],set()).add(item["digest"])
        for length,digests in by_length.items():
            for start in range(len(raw)-length+1):
                if self.vault.fingerprint(raw[start:start+length]) in digests:
                    raise ValueError("PII_GUARD_BLOCKED: identity fingerprint")
        return True


def candidate_packet(service,row,trial):
    from .matching.snapshot import PatientSnapshot
    pid = row["result"]["patient_id"]
    snapshot = PatientSnapshot.from_facts(pid,service.facts(pid))
    ref = pseudonym(service.pseudonym_secret,pid,trial.trial_id)
    service.store.put("pseudonym_map",f"{pid}:{trial.trial_id}",{"patient_id":pid,"trial_id":trial.trial_id,"ref":ref})
    by_id = {c.id:c for c in trial.criteria}
    evidence = []
    for result in row["result"]["criteria"]:
        c = by_id[result["criterion_id"]]
        value = result["normalized_value"] if result["normalized_value"] is not None else result["patient_value"]
        if c.field=="age" and value is not None:
            value = age_band(value)
        evidence.append(CandidateEvidence(criterion_id=c.id,field=c.field,value=value,
                         unit=None if c.field=="age" else c.unit or result["patient_unit"],
                         days_before_packet=None if c.field in {"age","sex"} else result["age_days"],
                         status=result["status"],reuse_class=result["reuse_class"]))
    fields = {c.field for c in trial.criteria}
    events = []
    for h in service.store.all("history"):
        if h["match_id"]==row["id"] and h["kind"]=="NEW_OPPORTUNITY":
            events.append(RematchEvidence(trigger=h["trigger"],days_before_packet=(service.now()-date.fromisoformat(h["at"])).days,
                          before_status=(h["before"] or {}).get("status","NONE"),after_status=h["after"]["status"]))
    packet = CandidatePacket(ref=ref,trial_id=trial.trial_id,trial_version=trial.version,
                             age_band=age_band(snapshot.facts["age"].value) if "age" in fields and "age" in snapshot.facts else None,
                             sex=snapshot.facts["sex"].value if "sex" in fields and "sex" in snapshot.facts else None,
                             evidence=evidence,rematch=row["rematch"],rematch_history=events[-3:])
    PIIGuard(service.vault).check(packet)
    return packet
