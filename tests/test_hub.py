from fastapi.testclient import TestClient
from rematch.hub.main import create_app
from rematch.extraction.curated import load_trials


def test_hub_registry_auth_and_aggregate(tmp_path):
    app = create_app(tmp_path/"hub.sqlite",keys={"sponsor":"s","clinic-a":"a","clinic-b":"b","inspector":"i"})
    with TestClient(app,headers={"X-API-Key":"s"}) as c:
        t = load_trials()[0].model_dump(mode="json")
        t["criteria"][0]["review_status"] = "draft"
        assert c.post("/trials",json=t).status_code==422
        t["criteria"][0]["review_status"] = "verified"
        assert c.post("/trials",json=t).status_code==200
        assert c.get("/trials",headers={"X-API-Key":"bad"}).status_code==401
        for cid,key in [("clinic-a","a"),("clinic-b","b")]:
            headers = {"X-API-Key":key}
            assert c.get("/trials",headers=headers).json()[0]["trial_id"]==t["trial_id"]
            signal = {"clinic_id":cid,"trial_id":t["trial_id"],"trial_version":1,"evaluated":10,"potential":3,"needs_info":2,"not_matched":5,"new_this_period":3}
            assert c.post("/signals/aggregate",json=signal,headers=headers).status_code==200
        assert len(c.get("/signals/aggregate").json())==2
        assert c.post("/trials",json=t,headers={"X-API-Key":"a"}).status_code==403
        audit = c.get("/audit").json()
        assert any(a["keys"] and a["size"]>0 for a in audit)
        assert all("X-API-Key" not in str(a) for a in audit)
