import httpx
from rematch.common.config import CLINIC_URLS,HUB_URL,credential


class API:
    def __init__(self,url,key,patient_id=None):
        self.url,self.key,self.patient_id = url,key,patient_id

    def request(self,method,path,data=None):
        headers = {"X-API-Key":self.key}
        if self.patient_id:
            headers["X-Patient-ID"] = self.patient_id
        try:
            r = httpx.request(method,self.url+path,headers=headers,json=data,timeout=30,trust_env=False)
        except httpx.RequestError:
            raise RuntimeError("The demo service is unavailable. Start scripts/run_demo.py and use Refresh.") from None
        if r.is_error:
            try:
                detail = r.json().get("detail",r.text)
            except ValueError:
                detail = r.text
            raise RuntimeError(str(detail))
        return r.json()

    def get(self,path):
        return self.request("GET",path)

    def post(self,path,data=None):
        return self.request("POST",path,data)

    def put(self,path,data):
        return self.request("PUT",path,data)


def clinic_api(clinic_id,patient=False,patient_id=None):
    return API(CLINIC_URLS[clinic_id],credential(clinic_id,"patient" if patient else "coordinator"),patient_id)


def sponsor_api():
    return API(HUB_URL,credential("hub","sponsor"))
