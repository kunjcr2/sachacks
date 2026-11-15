from contextlib import asynccontextmanager
import asyncio
import hmac
import os
from fastapi import Depends,FastAPI,Header,HTTPException
from rematch.common.config import credential,CLINICS
from rematch.common.fhir import Bundle,BundleEntry,Observation
from rematch.common.schemas import ClockAdvance,ConsentUpdate,TrialBundle,Decision,PatientResponse,Model
from .service import ClinicService
from .seed import seed_clinic,hero_feed


def create_app(service=None,keys=None,polling=True):
    clinic_id = os.getenv("CLINIC_ID","clinic-a") if service is None else service.clinic_id
    service = service or ClinicService(clinic_id)
    keys = keys or {r:credential(clinic_id,r) for r in ["coordinator","patient"]}

    def role(x_api_key:str=Header(default="")):
        for name,token in keys.items():
            if hmac.compare_digest(x_api_key,token):
                return name
        raise HTTPException(401,"Valid X-API-Key is required")

    def coordinator(current=Depends(role)):
        if current!="coordinator":
            raise HTTPException(403,"Clinic coordinator access required")

    def patient_access(pid:str,current=Depends(role),x_patient_id:str=Header(default="")):
        if current!="coordinator" and x_patient_id!=pid:
            raise HTTPException(403,"This demo patient session cannot access another patient")

    async def poll():
        while True:
            try:
                await asyncio.to_thread(service.sync)
                service.last_sync_error = None
            except Exception as exc:
                service.last_sync_error = f"Hub unavailable ({type(exc).__name__}); cached screening continues."
            await asyncio.sleep(max(1,float(os.getenv("SYNC_INTERVAL_SECONDS","5"))))

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(poll()) if polling else None
        yield
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title=f"ReMatch {clinic_id}",dependencies=[Depends(role)],lifespan=lifespan)
    app.state.service = service
    coord = [Depends(coordinator)]

    @app.get("/health")
    def health():
        return {"ok":True,"service":clinic_id,"today":service.now().isoformat()}

    @app.get("/overview",dependencies=coord)
    def overview():
        matches = service.matches()
        return {"clinic_id":clinic_id,"name":CLINICS[clinic_id],"today":service.now().isoformat(),"patients":len(service.store.all("patient")),
                "opted_in":sum(p["consent"]=="OPTED_IN" for p in service.store.all("patient")),"trials":len(service.store.all("trial")),
                "potential":sum(m["result"]["status"]=="POTENTIAL_MATCH" for m in matches),"pending":sum(t["state"]=="OPEN" for t in service.store.all("task")),
                "stale":len(service.freshness()),"sync_error":service.last_sync_error,"outbound":sum(x["event"]=="OUTBOUND" for x in service.store.all("privacy")),
                "min_cell_size":service.store.get("meta","privacy",{"min_cell_size":1})["min_cell_size"]}

    @app.get("/patients")
    def patients(current=Depends(role)):
        rows = service.store.all("patient")
        return rows if current=="coordinator" else [{"id":p["id"],"alias":p["alias"]} for p in rows]

    @app.get("/patients/{pid}",dependencies=[Depends(patient_access)])
    def patient(pid:str):
        return service.patient(pid)

    @app.get("/patients/{pid}/identity",dependencies=[Depends(patient_access)])
    def identity(pid:str,current=Depends(role)):
        return service.reveal(pid,actor=current,reason="selected patient review" if current=="coordinator" else "patient profile")

    @app.get("/patients/{pid}/fhir",dependencies=coord)
    def fhir(pid:str):
        service.patient(pid)
        return {"facts":[f.model_dump(mode="json") for f in service.facts(pid)],"resources":[r for r in service.store.all("resource") if r["subject"]["reference"]==f"Patient/{pid}"]}

    @app.get("/patients/{pid}/consent",dependencies=[Depends(patient_access)])
    def get_consent(pid:str):
        return service.patient(pid)

    @app.put("/patients/{pid}/consent",dependencies=[Depends(patient_access)])
    def put_consent(pid:str,update:ConsentUpdate):
        if update.broad_status=="WITHDRAWN":
            from .outreach import withdraw
            return withdraw(service,pid)
        result = service.consent(pid,update)
        if update.broad_status!="OPTED_IN" and service.gateway:
            try:
                service.gateway.flush(service)
            except Exception:
                pass # Local opt-out is immediate; the persisted retraction retries on sync.
        return result

    @app.post("/patients/{pid}/ask-research",dependencies=coord)
    def ask_research(pid:str):
        return service.store.put("patient",pid,service.patient(pid)|{"research_prompt":True})

    @app.post("/fhir/Observation",dependencies=coord)
    def observation(resource:Observation):
        return service.ingest(Bundle(entry=[BundleEntry(resource=resource)]))

    @app.post("/fhir/Bundle",dependencies=coord)
    def bundle(payload:Bundle):
        return service.ingest(payload)

    @app.get("/matches",dependencies=coord)
    def matches(status:str|None=None,pipeline_state:str|None=None,trial_id:str|None=None):
        return [m for m in service.matches() if (not status or m["result"]["status"]==status) and (not pipeline_state or m["pipeline_state"]==pipeline_state) and (not trial_id or m["result"]["trial_id"]==trial_id)]

    @app.get("/matches/{mid}",dependencies=coord)
    def match_detail(mid:str):
        row = service.store.get("match",mid)
        if not row:
            raise HTTPException(404,"Match not found")
        return row|{"history":[h for h in service.store.all("history") if h["match_id"]==mid]}

    @app.get("/trials",dependencies=coord)
    def trials():
        return service.store.all("trial")

    @app.get("/tasks",dependencies=coord)
    def tasks():
        return [t for t in service.store.all("task") if t["state"]=="OPEN"]

    @app.get("/freshness",dependencies=coord)
    def freshness():
        return service.freshness()

    @app.get("/privacy-log",dependencies=coord)
    def privacy_log():
        return list(reversed(service.store.all("privacy")))

    @app.post("/admin/sync",dependencies=coord)
    def sync():
        try:
            return service.sync()
        except Exception as exc:
            raise HTTPException(503,"Hub unavailable; cached local data is preserved. Check the demo terminal.") from exc

    @app.post("/admin/reevaluate",dependencies=coord)
    def reevaluate():
        return {"matches":len(service.reevaluate())}

    @app.post("/admin/clock/advance",dependencies=coord)
    def advance(update:ClockAdvance):
        return service.advance(update.days)

    @app.post("/admin/simulate-lab-feed",dependencies=coord)
    def simulate():
        return service.ingest(Bundle.model_validate(hero_feed(service.now().isoformat())))

    @app.post("/admin/reset",dependencies=coord)
    def reset():
        with service.store.lock:
            trials = service.store.all("trial")
            from .outreach import withdraw
            for p in service.store.all("patient"):
                if any(m["result"]["patient_id"]==p["id"] and m["referral_id"] for m in service.store.all("match")):
                    withdraw(service,p["id"])
            pending = service.store.all("outbox")
            service.store.clear()
            service.store.put("meta","clock",{"today":"2026-11-15"})
            service.store.put("meta","privacy",{"min_cell_size":1})
            seed_clinic(service)
            for item in pending:
                service.store.put("outbox",item["id"],item)
            for trial in trials:
                service.apply_trial(TrialBundle.model_validate(trial))
        return {"ok":True,"scope":"selected clinic"}

    @app.post("/matches/{mid}/decision",dependencies=coord)
    def decide(mid:str,update:Decision):
        from .outreach import decision
        return decision(service,mid,update)

    @app.post("/matches/{mid}/release",dependencies=coord)
    def release_match(mid:str):
        from .outreach import release
        return release(service,mid)

    def match_patient_access(mid:str,current=Depends(role),x_patient_id:str=Header(default="")):
        row = service.store.get("match",mid)
        if not row:
            raise HTTPException(404,"Match not found")
        if current!="coordinator" and row["result"]["patient_id"]!=x_patient_id:
            raise HTTPException(403,"Wrong patient session")

    @app.post("/matches/{mid}/patient-response",dependencies=[Depends(match_patient_access)])
    def respond_patient(mid:str,update:PatientResponse):
        from .outreach import patient_response
        row = patient_response(service,mid,update.response)
        return {"pipeline_state":row["pipeline_state"]}

    @app.post("/matches/{mid}/refer",dependencies=coord)
    def refer(mid:str):
        from .outreach import get_match,current_opportunity
        with service.store.lock:
            row = get_match(service,mid)
            if row["pipeline_state"]!="PATIENT_INTERESTED":
                raise HTTPException(409,"Patient interest is required first")
            if not current_opportunity(service,row):
                raise HTTPException(409,"Clinical and consent review must still be current")
            row["pipeline_state"] = "REFERRED_TO_SCREENING"
            row["visit"] = {"when":"Your clinic will arrange the visit with you.","reminder":"Demo reminder: contact your clinic if you need help attending."}
            service.store.put("match",mid,row)
            service.cancel_tasks(mid)
            return row

    @app.post("/patients/{pid}/withdraw",dependencies=[Depends(patient_access)])
    def withdraw_patient(pid:str):
        from .outreach import withdraw
        return withdraw(service,pid)

    @app.get("/patients/{pid}/opportunities",dependencies=[Depends(patient_access)])
    def opportunities(pid:str):
        service.patient(pid)
        states = {"PATIENT_OUTREACH","PATIENT_INTERESTED","PATIENT_DEFERRED","PATIENT_DECLINED","REFERRED_TO_SCREENING","WITHDRAWN"}
        output = []
        for row in service.store.all("match"):
            if row["result"]["patient_id"]!=pid or row["pipeline_state"] not in states or not row.get("released") or not row.get("active",True):
                continue
            trial = service.store.get("trial",row["result"]["trial_id"])
            labels = {"dx_t2dm":"Recorded type 2 diabetes", "dx_ckd":"Recorded chronic kidney disease", "dx_htn":"Recorded high blood pressure", "dx_hf":"Recorded heart failure",
                      "rx_metformin":"Metformin use", "rx_insulin":"Insulin use", "rx_sglt2i":"SGLT2 medicine use", "rx_glp1ra":"GLP-1 medicine use", "pregnant":"Pregnancy assessment",
                      "hba1c":"HbA1c", "egfr":"Kidney function (eGFR)", "bmi":"Body mass index", "sbp":"Systolic blood pressure", "dbp":"Diastolic blood pressure", "cpeptide":"C-peptide"}
            shared = ["A study-specific reference that does not contain your name"]
            for evidence in row.get("shared_packet",{}).get("evidence",[]):
                value = evidence["value"]
                field = evidence["field"]
                if field=="age":
                    shared.append(f"Your age range: {value}")
                elif field=="sex":
                    shared.append(f"Recorded sex: {value}")
                else:
                    readable = "not available; assessment may be needed" if value is None else "yes" if value is True else "no" if value is False else str(value)
                    unit = evidence.get("unit") or ""
                    timing = f" ({evidence['days_before_packet']} days before sharing)" if evidence.get("days_before_packet") is not None else ""
                    shared.append(f"{labels.get(field,field.replace('_',' '))}: {readable} {unit}{timing}".strip())
            output.append({"id":row["id"],"trial_id":trial["trial_id"],"title":trial["title"],"summary":trial["plain_language_summary"],
                           "visits":trial["visits_summary"],"pipeline_state":row["pipeline_state"],"visit":row.get("visit"),
                           "why":"Your clinic reviewed your updated records and thought this study might be worth discussing.",
                           "shared":shared,
                           "identity_notice":"Your name and contact details remain with your clinic. The sponsor does not receive them in this demo."})
        return output

    class PrivacySettings(Model):
        min_cell_size:int

    @app.put("/admin/privacy",dependencies=coord)
    def privacy_settings(update:PrivacySettings):
        if not 1<=update.min_cell_size<=100:
            raise HTTPException(422,"Choose a threshold from 1 to 100")
        return service.store.put("meta","privacy",update.model_dump())

    return app


def app_factory():
    from .network import HubGateway
    cid = os.getenv("CLINIC_ID","clinic-a")
    return create_app(ClinicService(cid,gateway=HubGateway(cid)))
