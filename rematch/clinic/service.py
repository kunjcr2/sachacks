from __future__ import annotations
import base64
from datetime import date,timedelta
import functools
import os
import uuid
from fastapi import HTTPException
from rematch.common.clock import T0
from rematch.common.db import Store
from rematch.common.config import RUNTIME
from rematch.common.schemas import TrialBundle,FieldFact
from .identity_vault import IdentityVault,clinic_secrets
from .matching.engine import match
from .matching.snapshot import PatientSnapshot
from .rematch.monitor import criterion_diff,result_hash,transition


def locked(fn):
    @functools.wraps(fn)
    def wrapped(self,*args,**kwargs):
        with self.store.lock:
            return fn(self,*args,**kwargs)
    return wrapped


class ClinicService:
    def __init__(self,clinic_id,path=None,key=None,pseudonym_secret=None,gateway=None):
        self.clinic_id = clinic_id
        self.store = Store(path or RUNTIME/f"{clinic_id}.sqlite")
        if key is None:
            secret = clinic_secrets(clinic_id)
            override = os.getenv("CLINIC_IDENTITY_KEY_B64") if os.getenv("REMATCH_MULTICLINIC")!="1" else None
            key = base64.b64decode(override or secret["key_b64"])
            pseudonym_secret = bytes.fromhex(secret["pseudonym_secret"])
        self.vault = IdentityVault(self.store,clinic_id,key,f"{clinic_id}-v1")
        self.pseudonym_secret = pseudonym_secret or key
        self.gateway = gateway
        self.last_sync_error = None
        self.store.put("meta","clock",self.store.get("meta","clock",{"today":T0.isoformat()}))
        self.store.put("meta","privacy",self.store.get("meta","privacy",{"min_cell_size":int(os.getenv("MIN_CELL_SIZE","1"))}))

    def now(self):
        return date.fromisoformat(self.store.get("meta","clock")["today"])

    def patient(self,pid):
        p = self.store.get("patient",pid)
        if not p:
            raise HTTPException(404,"Patient not found")
        return p

    def facts(self,pid):
        return [FieldFact.model_validate({k:v for k,v in row.items() if k not in {"patient_id","ingested_at"}})
                for row in self.store.all("fact") if row["patient_id"]==pid]

    def audit(self,event,**data):
        row = {"id":uuid.uuid4().hex,"event":event,"today":self.now().isoformat(),**data}
        self.store.put("privacy",row["id"],row)
        return row

    @locked
    def reveal(self,pid,actor="coordinator",reason="coordinator review"):
        p = self.patient(pid)
        identity = self.vault.reveal(pid)
        self.audit("identity_accessed",actor=actor,patient_alias=p["alias"],reason=reason)
        return identity

    @locked
    def apply_trial(self,trial:TrialBundle):
        old = self.store.get("trial",trial.trial_id)
        if old and old["version"]>trial.version:
            return
        if old==trial.model_dump(mode="json"):
            return
        self.store.put("trial",trial.trial_id,trial.model_dump(mode="json"))
        if trial.status=="recruiting":
            self.reevaluate("TRIAL_UPDATE" if old else "SYNC",trial_id=trial.trial_id)
        else:
            for row in self.store.all("match"):
                if row["result"]["trial_id"]==trial.trial_id:
                    self.retract_packet(row,"protocol_changed")
                    row.update(active=False,released=False,pipeline_state="ON_HOLD")
                    self.store.put("match",row["id"],row)
                    self.cancel_tasks(row["id"])

    def cancel_tasks(self,mid):
        for task in self.store.all("task"):
            if task["match_id"]==mid and task["state"]=="OPEN":
                self.store.put("task",task["id"],task|{"state":"CANCELLED"})

    def retract_packet(self,row,reason):
        rid = row.get("referral_id")
        if rid:
            if self.store.get("outbox",rid):
                self.store.delete("outbox",rid)
            else:
                key = f"retract-{rid}"
                self.store.put("outbox",key,{"id":key,"kind":"retract","referral_id":rid,"reason":reason})

    def add_task(self,row,kind,hid):
        tid = f"{row['id']}:{kind}:{hid}"
        self.store.put("task",tid,{"id":tid,"match_id":row["id"],"patient_id":row["result"]["patient_id"],"kind":kind,"state":"OPEN","created_at":self.now().isoformat(),"history_id":hid})

    @locked
    def reevaluate(self,trigger="SYNC",patient_id=None,trial_id=None):
        trials = [TrialBundle.model_validate(t) for t in self.store.all("trial") if t["status"]=="recruiting" and (not trial_id or t["trial_id"]==trial_id)]
        for p in self.store.all("patient"):
            if p["consent"]!="OPTED_IN" or (patient_id and p["id"]!=patient_id):
                continue
            snapshot = PatientSnapshot.from_facts(p["id"],self.facts(p["id"]))
            for trial in trials:
                result = match(snapshot,trial,self.now())
                mid = f"{p['id']}:{trial.trial_id}"
                previous = self.store.get("match",mid)
                digest = result_hash(result)
                if previous and previous["hash"]==digest and previous.get("active",True):
                    continue
                before = previous["result"] if previous else None
                kind = transition(before["status"] if before else None,result.status)
                after = result.model_dump(mode="json")
                hid = f"{mid}:{trial.version}:{digest}:{previous['hash'] if previous else 'initial'}"
                self.store.put("history",hid,{"id":hid,"match_id":mid,"trigger":trigger,"kind":kind,"at":self.now().isoformat(),"before":before,"after":after,"diff":criterion_diff(before,after)})
                row = {"id":mid,"result":after,"hash":digest,"pipeline_state":"PENDING_REVIEW" if result.status=="POTENTIAL_MATCH" else "NONE","referral_id":None,"active":True,"rematch":False,"note":""}
                if previous:
                    for k in ["pipeline_state","referral_id","rematch","note"]:
                        row[k] = previous.get(k,row[k])
                    for k in ["released","visit","sponsor_response","shared_packet"]:
                        if k in previous:
                            row[k] = previous[k]
                    if not previous.get("active",True):
                        row.update(pipeline_state="PENDING_REVIEW" if result.status=="POTENTIAL_MATCH" else "NONE",referral_id=None)
                    if previous["result"]["trial_version"]!=trial.version:
                        self.retract_packet(previous,"protocol_changed")
                        row.update(referral_id=None,released=False,pipeline_state="PENDING_REVIEW" if result.status=="POTENTIAL_MATCH" else "NONE")
                        self.cancel_tasks(mid)
                        if result.status=="POTENTIAL_MATCH":
                            self.add_task(row,"PROTOCOL_REVIEW",hid)
                ever_blocked = any(h["match_id"]==mid and (h.get("before") or {}).get("status")=="NOT_MATCHED" for h in self.store.all("history"))
                if kind=="NEW_OPPORTUNITY" or (previous and not previous.get("active",True) and result.status=="POTENTIAL_MATCH"):
                    row["rematch"] = ever_blocked
                    if not row["referral_id"]:
                        row["pipeline_state"] = "PENDING_REVIEW"
                    self.cancel_tasks(mid)
                    self.add_task(row,"NEW_OPPORTUNITY",hid)
                elif kind=="REGRESSION":
                    self.cancel_tasks(mid)
                    self.add_task(row,"UPDATE_SPONSOR" if row["referral_id"] else "REFRESH_DATA",hid)
                    if row["referral_id"]:
                        self.retract_packet(row,"data_changed")
                    row.update(referral_id=None,released=False,pipeline_state="NONE")
                elif result.status=="NEEDS_INFO" and not any(t["match_id"]==mid and t["state"]=="OPEN" for t in self.store.all("task")):
                    self.add_task(row,"REFRESH_DATA",hid)
                self.store.put("match",mid,row)
        return self.matches()

    def matches(self):
        patients = {p["id"]:p for p in self.store.all("patient")}
        return [m|{"patient_alias":patients[m["result"]["patient_id"]]["alias"]} for m in self.store.all("match")
                if m.get("active",True) and patients[m["result"]["patient_id"]]["consent"]=="OPTED_IN"]

    @locked
    def advance(self,days):
        if not 0<=days<=365:
            raise HTTPException(422,"Clock advance must be 0–365 days")
        today = self.now()+timedelta(days=days)
        self.store.put("meta","clock",{"today":today.isoformat()})
        self.reevaluate("CLOCK")
        return {"today":today.isoformat()}

    @locked
    def ingest(self,bundle):
        incoming = []
        seen_ids = set()
        for entry in bundle.entry:
            resource = entry.resource
            if resource.id in seen_ids:
                raise HTTPException(422,"Bundle contains duplicate resource IDs")
            seen_ids.add(resource.id)
            pid = resource.subject.reference.removeprefix("Patient/")
            self.patient(pid)
            if resource.effectiveDateTime.date()>self.now():
                raise HTTPException(422,"Observation is after the demo clock")
            raw = resource.model_dump(mode="json")
            snapshot = PatientSnapshot.from_fhir(pid,[raw])
            if not snapshot.history:
                raise HTTPException(422,"Unsupported or unmapped clinical code")
            old = self.store.get("resource",resource.id)
            if old and old!=raw:
                raise HTTPException(409,"Resource ID already exists; use a new version ID to preserve history")
            incoming.append((pid,resource.id,raw,snapshot.history[0],old))
        changed = set()
        for pid,rid,raw,fact,old in incoming:
            if old:
                continue
            self.store.put("resource",rid,raw)
            self.store.put("fact",rid,{"patient_id":pid,**fact.model_dump(mode="json"),"ingested_at":self.now().isoformat()})
            changed.add(pid)
        for pid in changed:
            self.reevaluate("LAB_UPDATE",patient_id=pid)
        return {"accepted":len(incoming),"patients_reassessed":len(changed)}

    @locked
    def consent(self,pid,update):
        p = self.patient(pid)
        if not p["research_prompt"] and update.broad_status=="OPTED_IN":
            raise HTTPException(409,"The clinic must initiate the research invitation first")
        p["consent_history"].append({"from":p["consent"],"to":update.broad_status,"at":self.now().isoformat()})
        p.update(consent=update.broad_status,contact_pref=update.contact_pref)
        self.store.put("patient",pid,p)
        if p["consent"]=="OPTED_IN":
            self.reevaluate("CONSENT",patient_id=pid)
        else:
            for row in self.store.all("match"):
                if row["result"]["patient_id"]==pid:
                    self.cancel_tasks(row["id"])
                    if row["referral_id"]:
                        rid = row["referral_id"]
                        if self.store.get("outbox",rid):
                            self.store.delete("outbox",rid)
                        else:
                            self.store.put("outbox",f"retract-{rid}",{"id":f"retract-{rid}","kind":"retract","referral_id":rid,"reason":"withdrawn"})
                    row.update(active=False,pipeline_state="WITHDRAWN")
                    self.store.put("match",row["id"],row)
        return p

    def freshness(self):
        return [{"patient_alias":m["patient_alias"],"patient_id":m["result"]["patient_id"],"trial_id":m["result"]["trial_id"],"criterion_id":c["criterion_id"],"age_days":c["age_days"],"reason":c["reason"],"recommendation":"Coordinator to review whether an updated assessment is appropriate."}
                for m in self.matches() for c in m["result"]["criteria"] if c["reason"] in {"STALE","MISSING"}]

    def sync(self):
        return self.gateway.sync(self) if self.gateway else {"trials":len(self.store.all("trial")),"offline":True}

    def apply_response(self,response):
        from .outreach import apply_response
        return apply_response(self,response)
