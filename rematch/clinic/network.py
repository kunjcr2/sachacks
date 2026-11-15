import json
import uuid
import httpx
from rematch.common.config import HUB_URL,CLINICS,credential
from rematch.common.schemas import AggregateSignal,TrialBundle
from .deid import PIIGuard
from .service import locked


class HubGateway:
    def __init__(self,clinic_id,client=None,key=None):
        self.clinic_id = clinic_id
        self.client = client or httpx.Client(base_url=HUB_URL,timeout=8,trust_env=False)
        self.key = key or credential("hub",clinic_id)

    def request(self,method,path,payload=None):
        r = self.client.request(method,path,json=payload,headers={"X-API-Key":self.key})
        r.raise_for_status()
        return r.json()

    def outgoing(self,service,path,model):
        try:
            PIIGuard(service.vault).check(model,allow_dates=True)
        except ValueError:
            service.audit("PII_GUARD_BLOCKED",endpoint=path,guard="BLOCKED")
            raise
        body = model.model_dump(mode="json")
        result = self.request("POST",path,body)
        service.audit("OUTBOUND",endpoint=path,keys=sorted(body),size=len(json.dumps(body).encode()),guard="PASS")
        return result

    def flush(self,service):
        from rematch.common.schemas import SealedReferral
        for item in service.store.all("outbox"):
            if item["kind"]=="referral":
                self.outgoing(service,"/referrals",SealedReferral.model_validate(item["payload"]))
                row = service.store.get("match",item["match_id"])
                if row and row["pipeline_state"]!="WITHDRAWN":
                    row["pipeline_state"] = "SENT_TO_SPONSOR"
                    service.store.put("match",row["id"],row)
                    service.cancel_tasks(row["id"])
            else:
                self.request("POST",f"/referrals/{item['referral_id']}/retract",{"reason":item["reason"]})
                service.audit("OUTBOUND",endpoint="/referrals/{id}/retract",keys=["reason"],size=24,guard="PASS")
            service.store.delete("outbox",item["id"])

    def sync(self,service):
        with service.store.lock:
            self.request("POST","/clinics/register",{"clinic_id":self.clinic_id,"name":CLINICS[self.clinic_id]})
            trials = self.request("GET","/trials")
            for t in trials:
                service.apply_trial(TrialBundle.model_validate(t))
            self.flush(service)
            for response in self.request("GET",f"/clinics/{self.clinic_id}/responses"):
                service.apply_response(response)
            for trial in service.store.all("trial"):
                matches = [m for m in service.matches() if m["result"]["trial_id"]==trial["trial_id"]]
                counts = {"evaluated":len(matches),"potential":sum(m["result"]["status"]=="POTENTIAL_MATCH" for m in matches),
                          "needs_info":sum(m["result"]["status"]=="NEEDS_INFO" for m in matches),"not_matched":sum(m["result"]["status"]=="NOT_MATCHED" for m in matches),
                          "new_this_period":sum(m["rematch"] and m["result"]["status"]=="POTENTIAL_MATCH" for m in matches)}
                minimum = service.store.get("meta","privacy",{"min_cell_size":1})["min_cell_size"]
                # Suppress the whole row if any nonzero cell is small: prevents
                # recovering suppressed cells by subtraction from a total.
                suppressed = any(0<v<minimum for v in counts.values())
                signal = AggregateSignal(clinic_id=self.clinic_id,trial_id=trial["trial_id"],trial_version=trial["version"],
                         **({k:None for k in counts} if suppressed else counts),min_cell_size=minimum,suppressed=suppressed)
                signature = signal.model_dump_json()
                if service.store.get("sent_signal",trial["trial_id"])!={"hash":signature}:
                    self.outgoing(service,"/signals/aggregate",signal)
                    service.store.put("sent_signal",trial["trial_id"],{"hash":signature})
            return {"trials":len(trials),"today":service.now().isoformat(),"ok":True}
