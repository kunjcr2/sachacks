import os
import pytest
from fastapi.testclient import TestClient
from rematch.clinic.service import ClinicService
from rematch.clinic.main import create_app
from rematch.clinic.seed import seed_clinic,HERO,STORY
from rematch.extraction.curated import load_trials


@pytest.fixture
def clinic(tmp_path):
    svc = ClinicService("clinic-a",tmp_path/"a.sqlite",key=os.urandom(32))
    seed_clinic(svc)
    for t in load_trials():
        svc.apply_trial(t)
    with TestClient(create_app(svc,keys={"coordinator":"coord","patient":"patient"},polling=False),headers={"X-API-Key":"coord"}) as client:
        yield client,svc


def test_rematch_hero_and_idempotency(clinic):
    c,svc = clinic
    mid = f"{HERO}:SYN-0001"
    initial = c.get(f"/matches/{mid}").json()
    assert initial["result"]["status"]=="NOT_MATCHED"
    assert initial["result"]["watch"]
    assert initial["result"]["blocking_criteria"]==["SYN-0001-C3"]
    assert c.post("/admin/clock/advance",json={"days":90}).status_code==200
    assert c.get(f"/matches/{mid}").json()["result"]["status"]=="NEEDS_INFO"
    assert c.post("/admin/simulate-lab-feed").status_code==200
    current = c.get(f"/matches/{mid}").json()
    assert current["result"]["status"]=="POTENTIAL_MATCH"
    assert current["rematch"]
    assert len([t for t in c.get("/tasks").json() if t["match_id"]==mid and t["kind"]=="NEW_OPPORTUNITY"])==1
    hba = next(d for d in current["history"][-1]["diff"] if d["criterion_id"]=="SYN-0001-C3")
    assert hba["before"]["patient_value"]==11.2
    assert hba["after"]["patient_value"]==9.1
    count = len(svc.store.all("history"))
    c.post("/admin/simulate-lab-feed")
    c.post("/admin/reevaluate")
    assert len(svc.store.all("history"))==count
    assert all(m["result"]["patient_id"]!=STORY["PX-91003"] for m in svc.matches())


def test_auth_identity_and_staleness(clinic):
    c,svc = clinic
    assert c.get("/overview",headers={"X-API-Key":"bad"}).status_code==401
    assert c.get(f"/patients/{HERO}/identity",headers={"X-API-Key":"patient"}).status_code==403
    assert c.get(f"/patients/{HERO}/identity").json()["name"]
    assert c.get("/freshness").json()
    baseline = f"{STORY['PX-10442']}:SYN-0001"
    assert c.get(f"/matches/{baseline}").json()["result"]["status"]=="POTENTIAL_MATCH"
    c.post("/admin/clock/advance",json={"days":90})
    assert c.get(f"/matches/{baseline}").json()["result"]["status"]=="NEEDS_INFO"


def test_matcher_does_not_decrypt_identity(clinic,monkeypatch):
    _,svc = clinic
    def fail(*args,**kwargs):
        raise AssertionError("Matching decrypted an identity")
    monkeypatch.setattr(svc.vault,"reveal",fail)
    svc.reevaluate()


def test_clinic_reset(clinic):
    c,svc = clinic
    c.post("/admin/clock/advance",json={"days":90})
    assert c.post("/admin/reset").status_code==200
    assert c.get("/health").json()["today"]=="2026-11-15"
    assert len(svc.store.all("patient"))==40


def test_research_invitation_cannot_be_bypassed_by_withdrawal(clinic):
    c,svc = clinic
    pid = next(p["id"] for p in svc.store.all("patient") if not p["research_prompt"])
    for initial in ["NOT_ASKED","WITHDRAWN"]:
        c.put(f"/patients/{pid}/consent",json={"broad_status":initial})
        assert c.put(f"/patients/{pid}/consent",json={"broad_status":"OPTED_IN"}).status_code==409
    c.post(f"/patients/{pid}/ask-research").raise_for_status()
    assert c.put(f"/patients/{pid}/consent",json={"broad_status":"OPTED_IN"}).status_code==200
