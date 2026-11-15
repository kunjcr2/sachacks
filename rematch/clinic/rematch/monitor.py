import hashlib
import json


def result_hash(result):
    return hashlib.sha256(json.dumps(result.model_dump(mode="json",exclude={"as_of"}),sort_keys=True).encode()).hexdigest()


def transition(before,after):
    if after=="POTENTIAL_MATCH" and before!=after:
        return "NEW_OPPORTUNITY"
    if before=="NOT_MATCHED" and after=="NEEDS_INFO":
        return "PROGRESS"
    if before=="POTENTIAL_MATCH" and after!=before:
        return "REGRESSION"
    return "REASSESSED"


def criterion_diff(before,after):
    old = {c["criterion_id"]:c for c in (before or {}).get("criteria",[])}
    return [{"criterion_id":item["criterion_id"],"before":old.get(item["criterion_id"]),"after":item}
            for item in after["criteria"] if old.get(item["criterion_id"])!=item]
