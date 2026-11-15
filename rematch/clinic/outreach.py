"""Consent-gated coordinator and patient actions."""
import uuid
from fastapi import HTTPException
from rematch.common.crypto import encrypt_packet
from rematch.common.schemas import SealedReferral,TrialBundle,ConsentUpdate
from .deid import candidate_packet


def get_match(service,mid):
    row = service.store.get("match",mid)
    if not row:
        raise HTTPException(404,"Match not found")
    return row


def current_opportunity(service,row):
    trial = service.store.get("trial",row["result"]["trial_id"])
    return (row.get("active",True) and trial and trial["status"]=="recruiting"
            and service.patient(row["result"]["patient_id"])["consent"]=="OPTED_IN"
            and row["result"]["status"]=="POTENTIAL_MATCH")


def decision(service,mid,update):
    with service.store.lock:
        row = get_match(service,mid)
        if service.patient(row["result"]["patient_id"])["consent"]!="OPTED_IN":
            raise HTTPException(409,"Patient has not consented to research screening")
        if row["pipeline_state"] not in {"PENDING_REVIEW","ON_HOLD","SPONSOR_NEEDS_DATA"}:
            raise HTTPException(409,"This case is not awaiting coordinator review")
        row["note"] = update.note
        if update.action!="approve":
            row["pipeline_state"] = "ON_HOLD" if update.action=="hold" else "DISMISSED"
            service.cancel_tasks(mid)
            return service.store.put("match",mid,row)
        service.reevaluate("SYNC",patient_id=row["result"]["patient_id"],trial_id=row["result"]["trial_id"])
        row = get_match(service,mid)
        trial = TrialBundle.model_validate(service.store.get("trial",row["result"]["trial_id"]))
        if not row.get("active",True) or trial.status!="recruiting" or row["result"]["status"]!="POTENTIAL_MATCH":
            raise HTTPException(409,"Only a current potential screening match may be sent")
        if service.gateway is None:
            raise HTTPException(503,"Hub connection is unavailable")
        if row["referral_id"] and row["pipeline_state"]!="SPONSOR_NEEDS_DATA":
            service.gateway.flush(service)
            return get_match(service,mid)
        try:
            packet = candidate_packet(service,row,trial)
        except ValueError as exc:
            service.audit("PII_GUARD_BLOCKED",endpoint="/referrals",guard="BLOCKED")
            raise HTTPException(422,"Privacy guard blocked the packet. Check Privacy log.") from exc
        public = service.gateway.request("GET",f"/sponsors/{trial.sponsor_id}/key")
        rid = uuid.uuid4().hex
        sealed = SealedReferral(referral_id=rid,clinic_id=service.clinic_id,trial_id=trial.trial_id,key_id=public["key_id"],
                                ciphertext_b64=encrypt_packet(packet,public["public_key_b64"]),created_at=service.now())
        if row["referral_id"]:
            old_rid = row["referral_id"]
            service.store.put("outbox",f"retract-{old_rid}",{"id":f"retract-{old_rid}","kind":"retract","referral_id":old_rid,"reason":"data_changed"})
        row["referral_id"] = rid
        row["shared_packet"] = packet.model_dump(mode="json")
        row["note"] = update.note
        service.store.put("match",mid,row)
        service.store.put("outbox",rid,{"id":rid,"kind":"referral","match_id":mid,"payload":sealed.model_dump(mode="json")})
        service.audit("PACKET_APPROVED",ref=packet.ref,keys=sorted(packet.model_dump()),guard="PASS")
        try:
            service.gateway.flush(service)
        except Exception as exc:
            raise HTTPException(503,"Packet is encrypted and queued; reconnect the hub and click Sync trials now.") from exc
        return get_match(service,mid)


def apply_response(service,response):
    for row in service.store.all("match"):
        if row["referral_id"]==response["referral_id"] and row["pipeline_state"] in {"SENT_TO_SPONSOR","SPONSOR_NEEDS_DATA"}:
            state = {"confirm":"SPONSOR_CONFIRMED","needs_data":"SPONSOR_NEEDS_DATA","decline":"SPONSOR_DECLINED"}[response["decision"]]
            if row["pipeline_state"]!=state:
                row.update(pipeline_state=state,sponsor_response=response)
                service.store.put("match",row["id"],row)
                if state=="SPONSOR_NEEDS_DATA":
                    service.add_task(row,"SPONSOR_NEEDS_DATA",row["referral_id"])


def release(service,mid):
    with service.store.lock:
        row = get_match(service,mid)
        if row["pipeline_state"]!="SPONSOR_CONFIRMED":
            raise HTTPException(409,"Sponsor confirmation is required before outreach")
        if not current_opportunity(service,row):
            raise HTTPException(409,"Consent and current clinical screening must still be valid")
        row["pipeline_state"] = "PATIENT_OUTREACH"
        row["released"] = True
        service.store.put("match",mid,row)
        service.cancel_tasks(mid)
        return row


def patient_response(service,mid,response):
    with service.store.lock:
        row = get_match(service,mid)
        if row["pipeline_state"] not in {"PATIENT_OUTREACH","PATIENT_DEFERRED"}:
            raise HTTPException(409,"The clinic has not released this opportunity")
        if not current_opportunity(service,row):
            raise HTTPException(409,"Ask your clinic for an updated review before responding")
        row["pipeline_state"] = {"interested":"PATIENT_INTERESTED","later":"PATIENT_DEFERRED","no":"PATIENT_DECLINED"}[response]
        service.store.put("match",mid,row)
        if response=="interested":
            service.add_task(row,"ARRANGE_SCREENING",row["referral_id"])
        return row


def withdraw(service,pid):
    with service.store.lock:
        service.consent(pid,ConsentUpdate(broad_status="WITHDRAWN",contact_pref=service.patient(pid)["contact_pref"]))
        pending_retraction = False
        if service.gateway:
            try:
                service.gateway.flush(service)
            except Exception:
                pending_retraction = True
        return {"withdrawn":True,"retraction_pending":pending_retraction,"message":"Research participation stopped. Your regular care is not affected."}
