from datetime import timedelta
import random
import uuid
from faker import Faker
from rematch.common.clock import T0
from rematch.common.schemas import FieldFact
from rematch.common.fields import FIELDS

HERO = "patient-a-hero"
STORY = {"PX-82914":HERO,"PX-10442":"patient-a-baseline","PX-33071":"patient-a-stale",
         "PX-91003":"patient-a-declined","PX-47716":"patient-a-insulin","PX-55820":"patient-b-baseline"}


def seed_clinic(service, seed=42):
    rng = random.Random(seed+(1 if service.clinic_id=="clinic-b" else 0))
    fake = Faker("en_US")
    fake.seed_instance(seed+(1 if service.clinic_id=="clinic-b" else 0))
    aliases = ["PX-82914","PX-10442","PX-33071","PX-91003","PX-47716"] if service.clinic_id=="clinic-a" else ["PX-55820"]
    count = 40 if service.clinic_id=="clinic-a" else 30
    aliases += [f"PX-{(60000 if service.clinic_id=='clinic-a' else 70000)+i}" for i in range(count-len(aliases))]
    for i,alias in enumerate(aliases):
        pid = STORY.get(alias,uuid.uuid5(uuid.NAMESPACE_DNS,service.clinic_id+alias).hex)
        scripted = alias in STORY
        age = 58 if scripted else rng.randint(28,82)
        consent = "DECLINED" if alias=="PX-91003" else "OPTED_IN" if scripted or i%10<8 else "NOT_ASKED" if i%10==8 else "DECLINED"
        p = {"id":pid,"alias":alias,"consent":consent,"contact_pref":"clinic portal","research_prompt":consent!="NOT_ASKED","consent_history":[],"sex":"female" if i%2 else "male"}
        service.store.put("patient",pid,p)
        identity = {"name":fake.name(),"email":f"demo.{service.clinic_id}.{i}@example.test","phone":f"+1-202-555-{100+i:04}",
                    "mrn":f"SYN-{service.clinic_id.upper()}-{i:05}","dob":f"{T0.year-age}-04-12","address":f"{1200+i} Fictional Orchard Lane, Demo City"}
        service.vault.save(pid,identity,T0.isoformat())
        hba = 11.2 if alias=="PX-82914" else 8.5 if scripted else round(rng.uniform(5.8,12),1)
        values = {"age":age,"sex":p["sex"],"hba1c":hba,"egfr":71 if scripted else rng.randint(25,95),"bmi":31 if scripted else round(rng.uniform(23,44),1),"sbp":rng.randint(115,175),
                  "dx_t2dm":True if scripted else rng.random()<0.6,"dx_ckd":False if scripted else rng.random()<0.25,"dx_htn":rng.random()<0.4,"dx_hf":False,"pregnant":False,
                  "rx_metformin":True if scripted else rng.random()<0.7,"rx_insulin":alias=="PX-47716" if scripted else rng.random()<0.2,"rx_sglt2i":rng.random()<0.2,"rx_glp1ra":False}
        for key,value in values.items():
            ages = [230,120,14] if FIELDS[key].kind in {"lab","vital"} else [0]
            if key=="bmi" and scripted:
                ages = [230,120,0]
            if alias=="PX-33071" and key=="egfr":
                ages = [300,250,210]
            if not scripted and key in {"hba1c","egfr"}:
                ages[-1] = rng.choice([5,35,100,200])
            for j,days in enumerate(ages):
                fid = f"{pid}-{key}-{j}"
                fact = FieldFact(field=key,value=value,unit=FIELDS[key].unit,effective_date=T0-timedelta(days=days),method="HPLC" if i%3 else "POC",source_resource_id=fid)
                service.store.put("fact",fid,{"patient_id":pid,**fact.model_dump(mode="json"),"ingested_at":T0.isoformat()})
    service.store.put("meta","seed",{"seed":seed,"patients":count})


def hero_feed(today):
    def obs(field,value,unit,code):
        return {"resourceType":"Observation","id":f"hero-{field}-{today}","status":"final","code":{"coding":[{"code":code}]},"subject":{"reference":f"Patient/{HERO}"},
                "effectiveDateTime":f"{today}T12:00:00Z","valueQuantity":{"value":value,"unit":unit},"method":{"text":"POC"}}
    resources = [obs("hba1c",9.1,"%","4548-4"),obs("egfr",68,"mL/min/1.73m2","62238-1"),obs("bmi",31,"kg/m2","39156-5"),
                 {"resourceType":"Condition","id":f"hero-pregnancy-{today}","subject":{"reference":f"Patient/{HERO}"},"code":{"coding":[{"system":"http://snomed.info/sct","code":"77386006"}]},"effectiveDateTime":f"{today}T12:00:00Z","valueBoolean":False}]
    return {"resourceType":"Bundle","type":"collection","entry":[{"resource":r} for r in resources]}
