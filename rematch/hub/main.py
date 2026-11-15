from __future__ import annotations
import base64
from datetime import datetime,timezone
import hashlib
import hmac
import json
import re
import uuid
from fastapi import Depends,FastAPI,Header,HTTPException,Request
from rematch.common.config import RUNTIME,credential,SPONSOR_ID
from rematch.common.db import Store
from rematch.common.schemas import (AggregateSignal,ClinicRegistration,SealedReferral,SponsorRegistration,SponsorResponse,TrialBundle,Model)
from rematch.extraction.validate import validate_criteria


class Retraction(Model):
    reason: str = "withdrawn"


def create_app(path=None,keys=None):
    db = Store(path or RUNTIME/"hub.sqlite")
    keys = keys or {r:credential("hub",r) for r in ["clinic-a","clinic-b","sponsor","inspector"]}

    def role(x_api_key:str=Header(default="")):
        for r,key in keys.items():
            if hmac.compare_digest(x_api_key,key):
                return r
        raise HTTPException(401,"Valid X-API-Key required")

    def require(current,*allowed):
        if current not in allowed:
            raise HTTPException(403,"This service credential cannot perform that action")

    def referral(rid):
        row = db.get("referral",rid)
        if not row:
            raise HTTPException(404,"Referral not found")
        return row

    app = FastAPI(title="ReMatch ciphertext routing hub",dependencies=[Depends(role)])
    app.state.db = db

    @app.middleware("http")
    async def audit(request:Request,call_next):
        body = await request.body()
        response = await call_next(request)
        # Never echo rejected bodies, unknown paths, headers or credentials.
        try:
            payload = json.loads(body) if body else None
        except ValueError:
            payload = None
        sender = next((r for r,k in keys.items() if hmac.compare_digest(k,request.headers.get("x-api-key",""))),"unauthorized")
        route = request.scope.get("route")
        entry = {"id":uuid.uuid4().hex,"at":datetime.now(timezone.utc).isoformat(),"sender":sender,
                 "path":getattr(route,"path","[unrecognized route]"),"method":request.method,"size":len(body),
                 "keys":sorted(payload) if isinstance(payload,dict) and response.status_code<400 else [],
                 "body_preview":body.decode(errors="replace")[:900] if 200<=response.status_code<300 and payload else "[no body or rejected payload]",
                 "status":response.status_code}
        db.put("audit",entry["id"],entry)
        return response

    @app.get("/health")
    def health():
        return {"ok":True,"service":"hub"}

    @app.post("/sponsors/register")
    def sponsor(payload:SponsorRegistration,current=Depends(role)):
        require(current,"sponsor")
        if payload.sponsor_id!=SPONSOR_ID:
            raise HTTPException(403,"Unknown demo sponsor")
        try:
            raw = base64.b64decode(payload.public_key_b64,validate=True)
            if len(raw)!=32:
                raise ValueError()
        except ValueError:
            raise HTTPException(422,"Expected a base64 X25519 public key")
        key_id = hashlib.sha256(raw).hexdigest()[:16]
        return db.put("sponsor",payload.sponsor_id,{**payload.model_dump(),"key_id":key_id})

    @app.get("/sponsors/{sid}/key")
    def sponsor_key(sid:str):
        row = db.get("sponsor",sid)
        if not row:
            raise HTTPException(404,"Sponsor not registered")
        return row

    @app.post("/clinics/register")
    def clinic(payload:ClinicRegistration,current=Depends(role)):
        require(current,payload.clinic_id)
        return db.put("clinic",payload.clinic_id,payload.model_dump())

    @app.post("/trials")
    def publish(payload:TrialBundle,current=Depends(role)):
        require(current,"sponsor")
        if payload.sponsor_id!=SPONSOR_ID:
            raise HTTPException(403,"Trial belongs to another sponsor")
        try:
            validate_criteria(payload.criteria,payload.raw_eligibility_text,publication=True)
        except ValueError as exc:
            raise HTTPException(422,str(exc))
        with db.lock:
            previous = db.get("trial",payload.trial_id)
            body = payload.model_dump(mode="json")
            if previous==body:
                return previous
            if previous and payload.version<=previous["version"]:
                raise HTTPException(409,"A changed protocol requires a higher version and renewed human verification")
            return db.put("trial",payload.trial_id,body)

    @app.get("/trials")
    def trials(since_version:int=0):
        # Return paused/closed protocols too so clinics can stop distributing them.
        return [t for t in db.all("trial") if t["version"]>=since_version]

    @app.post("/signals/aggregate")
    def push_signal(payload:AggregateSignal,current=Depends(role)):
        require(current,payload.clinic_id)
        if not db.get("trial",payload.trial_id):
            raise HTTPException(404,"Unknown trial")
        return db.put("aggregate",f"{payload.clinic_id}:{payload.trial_id}",payload.model_dump())

    @app.get("/signals/aggregate")
    def get_signals(trial_id:str|None=None):
        return [a for a in db.all("aggregate") if not trial_id or a["trial_id"]==trial_id]

    @app.post("/referrals")
    def send_referral(payload:SealedReferral,current=Depends(role)):
        require(current,payload.clinic_id)
        trial = db.get("trial",payload.trial_id)
        if not trial or trial["status"]!="recruiting":
            raise HTTPException(409,"Trial is not recruiting")
        sponsor = db.get("sponsor",trial["sponsor_id"])
        if not sponsor or sponsor["key_id"]!=payload.key_id:
            raise HTTPException(409,"Refresh the sponsor public key")
        try:
            raw = base64.b64decode(payload.ciphertext_b64,validate=True)
            if len(raw)<48 or raw.startswith((b"{",b"[")):
                raise ValueError()
        except ValueError:
            raise HTTPException(422,"Expected sealed-box ciphertext")
        with db.lock:
            old = db.get("referral",payload.referral_id)
            if old:
                if all(old[k]==v for k,v in payload.model_dump(mode="json").items()):
                    return old
                raise HTTPException(409,"Referral ID already exists")
            return db.put("referral",payload.referral_id,{**payload.model_dump(mode="json"),"retracted":False})

    @app.get("/sponsors/{sid}/referrals")
    def inbox(sid:str,current=Depends(role)):
        require(current,"sponsor")
        if sid!=SPONSOR_ID:
            raise HTTPException(403,"Unknown sponsor")
        return db.all("referral")

    @app.post("/referrals/{rid}/response")
    def respond(rid:str,payload:SponsorResponse,current=Depends(role)):
        require(current,"sponsor")
        row = referral(rid)
        if row["retracted"]:
            raise HTTPException(409,"Referral has been retracted")
        if payload.referral_id!=rid:
            raise HTTPException(422,"Referral ID mismatch")
        old = db.get("response",rid)
        if old:
            if old==payload.model_dump():
                return old
            raise HTTPException(409,"A decision was already recorded. The clinic must submit a reviewed update for another decision.")
        # Notes are short protocol/coordinator messages, never identity/contact data.
        if re.search(r"@|\b\d{4}-\d{2}-\d{2}\b|\b\d{3}[- .]\d{3}[- .]\d{4}\b",payload.note):
            raise HTTPException(422,"Do not include identifiers or dates in sponsor notes")
        criterion_ids = {c["id"] for c in db.get("trial",row["trial_id"])["criteria"]}
        if not set(payload.requested_criteria_ids)<=criterion_ids:
            raise HTTPException(422,"Unknown requested criterion")
        return db.put("response",rid,payload.model_dump())

    @app.get("/clinics/{cid}/responses")
    def responses(cid:str,since:str|None=None,current=Depends(role)):
        require(current,cid)
        return [r for r in db.all("response") if referral(r["referral_id"])["clinic_id"]==cid]

    @app.post("/referrals/{rid}/retract")
    def retract(rid:str,payload:Retraction,current=Depends(role)):
        row = referral(rid)
        require(current,row["clinic_id"])
        if payload.reason not in {"withdrawn","data_changed","protocol_changed","clinic_reset"}:
            raise HTTPException(422,"Unsupported retraction reason")
        row.update(retracted=True,retraction_reason=payload.reason,ciphertext_b64="")
        db.put("referral",rid,row)
        db.delete("response",rid)
        return {"referral_id":rid,"retracted":True}

    @app.get("/audit")
    def audit_feed(current=Depends(role)):
        require(current,"sponsor","inspector")
        return list(reversed(db.all("audit")[-250:]))

    return app


def app_factory():
    return create_app()
