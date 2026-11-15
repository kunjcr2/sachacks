import base64
import json
import os
from contextlib import ExitStack
import pytest
from fastapi.testclient import TestClient
from nacl.public import PrivateKey
from nacl.exceptions import CryptoError
from pydantic import ValidationError
from rematch.hub.main import create_app as hub_app
from rematch.clinic.main import create_app as clinic_app
from rematch.clinic.service import ClinicService
from rematch.clinic.seed import HERO,STORY,seed_clinic
from rematch.clinic.network import HubGateway
from rematch.clinic.deid import candidate_packet,PIIGuard,pseudonym
from rematch.common.crypto import decrypt_packet
from rematch.common.schemas import TrialBundle
from rematch.extraction.curated import load_trials


@pytest.fixture
def network(tmp_path):
    with ExitStack() as stack:
        hub = hub_app(tmp_path/"hub.sqlite",keys={"sponsor":"s","clinic-a":"a","clinic-b":"b","inspector":"i"})
        h = stack.enter_context(TestClient(hub,headers={"X-API-Key":"s"}))
        private = PrivateKey.generate()
        assert h.post("/sponsors/register",json={"sponsor_id":"meridian","name":"Meridian Research Labs","public_key_b64":base64.b64encode(bytes(private.public_key)).decode()}).status_code==200
        for trial in load_trials():
            assert h.post("/trials",json=trial.model_dump(mode="json")).status_code==200
        svc = ClinicService("clinic-a",tmp_path/"a.sqlite",key=os.urandom(32),gateway=HubGateway("clinic-a",h,"a"))
        seed_clinic(svc)
        svc.sync()
        c = stack.enter_context(TestClient(clinic_app(svc,keys={"coordinator":"c","patient":"p"},polling=False),headers={"X-API-Key":"c"}))
        yield c,svc,h,hub,private


def send_hero(c):
    mid = f"{HERO}:SYN-0001"
    c.post("/admin/clock/advance",json={"days":90}).raise_for_status()
    c.post("/admin/simulate-lab-feed").raise_for_status()
    r = c.post(f"/matches/{mid}/decision",json={"action":"approve","note":"Reviewed synthetic evidence"})
    assert r.status_code==200,r.text
    return mid,r.json()["referral_id"]


def test_full_pipeline_privacy_and_withdrawal(network):
    c,svc,h,hub,private = network
    mid,rid = send_hero(c)
    sealed = next(r for r in h.get("/sponsors/meridian/referrals").json() if r["referral_id"]==rid)
    packet = decrypt_packet(sealed["ciphertext_b64"],private)
    assert packet.rematch and packet.age_band=="55–59"
    assert packet.sex is None # no sex criterion, so no sex disclosure
    assert next(e.value for e in packet.evidence if e.field=="age")=="55–59"
    assert set(packet.model_dump()).isdisjoint({"name","email","mrn","patient_id","dob"})
    with pytest.raises(CryptoError):
        decrypt_packet(sealed["ciphertext_b64"],PrivateKey.generate())
    assert c.post(f"/matches/{mid}/release").status_code==409
    assert h.post(f"/referrals/{rid}/response",json={"referral_id":rid,"decision":"confirm"}).status_code==200
    assert c.post("/admin/sync").status_code==200
    assert c.post(f"/matches/{mid}/release").status_code==200
    assert len(c.get(f"/patients/{HERO}/opportunities").json())==1
    assert c.post(f"/matches/{mid}/patient-response",json={"response":"interested"},headers={"X-API-Key":"p","X-Patient-ID":HERO}).status_code==200
    assert c.post(f"/matches/{mid}/refer").json()["pipeline_state"]=="REFERRED_TO_SCREENING"
    # Every seeded identity stays out of all hub rows and logs; clinic vault has no plaintext identity.
    with hub.state.db.engine.connect() as conn:
        from sqlalchemy import text
        hub_dump = str(conn.execute(text("SELECT body FROM records")).all())
    for p in svc.store.all("patient"):
        identity = svc.vault.reveal(p["id"])
        for value in identity.values():
            assert value not in hub_dump
            assert value.encode() not in svc.store.path.read_bytes()
    assert c.post(f"/patients/{HERO}/withdraw").json()["withdrawn"]
    r = next(r for r in h.get("/sponsors/meridian/referrals").json() if r["referral_id"]==rid)
    assert r["retracted"] and not r["ciphertext_b64"]
    assert c.post(f"/matches/{mid}/decision",json={"action":"approve"}).status_code==409
    svc.sync()
    assert all(m["result"]["patient_id"]!=HERO for m in svc.matches())


def test_consent_guard_and_pseudonyms(network):
    c,svc,h,hub,private = network
    mid = f"{STORY['PX-91003']}:SYN-0001"
    assert c.post(f"/matches/{mid}/decision",json={"action":"approve"}).status_code==404
    mid,rid = send_hero(c)
    row = svc.store.get("match",mid)
    packet = candidate_packet(svc,row,TrialBundle.model_validate(svc.store.get("trial","SYN-0001")))
    identity = svc.vault.reveal(HERO)
    for value in [identity["name"],identity["mrn"],identity["email"],"2026-01-02"]:
        poisoned = packet.model_copy(deep=True)
        poisoned.evidence[0].value = value
        with pytest.raises(ValueError):
            PIIGuard(svc.vault).check(poisoned)
    a = pseudonym(svc.pseudonym_secret,HERO,"SYN-0001")
    assert a==packet.ref
    assert a!=pseudonym(svc.pseudonym_secret,HERO,"SYN-0002")
    # Suppression covers the entire row, preventing subtraction attacks.
    svc.store.put("meta","privacy",{"min_cell_size":100})
    svc.sync()
    assert all(a["evaluated"] is None for a in h.get("/signals/aggregate").json())


def test_amendment_and_stale_sent_packet_retraction(network):
    c,svc,h,hub,private = network
    # A protocol-only amendment can reveal the hero while facts are still fresh.
    trial = svc.store.get("trial","SYN-0001")
    trial["version"] = 2
    criterion = next(x for x in trial["criteria"] if x["field"]=="hba1c")
    old = criterion["source_text"]
    criterion.update(max=11.5,source_text="HbA1c must be between 7.5% and 11.5%.")
    trial["raw_eligibility_text"] = trial["raw_eligibility_text"].replace(old,criterion["source_text"])
    assert h.post("/trials",json=trial).status_code==200
    svc.sync()
    mid = f"{HERO}:SYN-0001"
    assert svc.store.get("match",mid)["result"]["status"]=="POTENTIAL_MATCH"
    sent = c.post(f"/matches/{mid}/decision",json={"action":"approve"})
    assert sent.status_code==200,sent.text
    rid = sent.json()["referral_id"]
    c.post("/admin/clock/advance",json={"days":90})
    svc.sync()
    stored = hub.state.db.get("referral",rid)
    assert stored["retracted"] and stored["retraction_reason"]=="data_changed"
    assert svc.store.get("match",mid)["result"]["status"]=="NEEDS_INFO"


def test_decline_after_sharing_and_reopt_in(network):
    c,svc,h,hub,private = network
    mid,rid = send_hero(c)
    result = c.put(f"/patients/{HERO}/consent",json={"broad_status":"DECLINED","contact_pref":"email"})
    assert result.status_code==200
    assert hub.state.db.get("referral",rid)["retracted"]
    assert not c.get(f"/patients/{HERO}/opportunities").json()
    assert not any(m["result"]["patient_id"]==HERO for m in svc.matches())
    c.put(f"/patients/{HERO}/consent",json={"broad_status":"OPTED_IN","contact_pref":"email"})
    row = svc.store.get("match",mid)
    assert row["pipeline_state"]=="PENDING_REVIEW" and row["referral_id"] is None


def test_offline_withdrawal_persists_retraction(network,monkeypatch):
    c,svc,h,hub,private = network
    mid,rid = send_hero(c)
    original = svc.gateway.request
    def unavailable(*args,**kwargs):
        raise ConnectionError("simulated offline")
    monkeypatch.setattr(svc.gateway,"request",unavailable)
    result = c.post(f"/patients/{HERO}/withdraw").json()
    assert result["withdrawn"] and result["retraction_pending"]
    assert svc.patient(HERO)["consent"]=="WITHDRAWN"
    assert svc.store.all("outbox")
    monkeypatch.setattr(svc.gateway,"request",original)
    svc.sync()
    assert hub.state.db.get("referral",rid)["retracted"]


def test_paused_protocol_retracts_and_prevents_outreach(network):
    c,svc,h,hub,private = network
    mid,rid = send_hero(c)
    h.post(f"/referrals/{rid}/response",json={"referral_id":rid,"decision":"confirm"}).raise_for_status()
    svc.sync()
    trial = svc.store.get("trial","SYN-0001")
    trial.update(status="paused",version=2)
    h.post("/trials",json=trial).raise_for_status()
    svc.sync()
    assert hub.state.db.get("referral",rid)["retracted"]
    assert c.post(f"/matches/{mid}/release").status_code==409
    assert not c.get(f"/patients/{HERO}/opportunities").json()
