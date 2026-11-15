"""Exercise the running demo through Streamlit's official AppTest UI driver.

Run only against this synthetic local demo. This resets Clinic A's demo state.
"""
import argparse
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ["PYTHONUTF8"] = "1"
from streamlit.testing.v1 import AppTest
from rematch.common.config import ROOT
from rematch.ui.api_client import clinic_api


def clean(app):
    assert not app.exception,[e.value for e in app.exception]
    assert not app.error,[e.value for e in app.error]
    return app


def click(app,label):
    buttons = [b for b in app.button if b.label==label]
    assert len(buttons)==1,(label,[b.label for b in app.button])
    return clean(buttons[0].click().run(timeout=45))


def page(app,label):
    radio = next(r for r in app.radio if r.label in {"Workspace","My space"})
    return clean(radio.set_value(label).run(timeout=45))


def run_once():
    api = clinic_api("clinic-a")
    api.post("/admin/reset")
    api.post("/admin/sync")
    c = clean(AppTest.from_file(str(ROOT/"rematch/ui/clinic_app.py"),default_timeout=45).run())
    for name in ["Review Queue","Trials","Patients","Data freshness","Outreach & participation","Privacy log","Overview"]:
        page(c,name)
    click(c,"+90 days")
    click(c,"Simulate lab feed")
    page(c,"Review Queue")
    click(c,"Approve & send de-identified packet")
    s = clean(AppTest.from_file(str(ROOT/"rematch/ui/sponsor_app.py"),default_timeout=45).run())
    for name in ["Network feasibility","Network Inspector","Protocol amendment","Candidate inbox"]:
        page(s,name)
    # Old retracted referrals have no buttons; this run has one active packet.
    click(s,"Confirm for clinic follow-up")
    click(c,"Sync trials now")
    page(c,"Outreach & participation")
    click(c,"Release opportunity to patient")
    p = clean(AppTest.from_file(str(ROOT/"rematch/ui/patient_app.py"),default_timeout=45).run())
    click(p,"I'm interested")
    for name in ["My research preferences","My participation","Opportunities from my clinic"]:
        page(p,name)
    click(c,"Refresh")
    click(c,"Arrange screening referral")
    click(p,"Refresh")
    page(p,"My participation")
    click(p,"Pause or withdraw from research")
    print("PASS: every UI page and the complete hero → approval → confirmation → outreach → interest → referral → withdrawal flow.",flush=True)


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat",type=int,default=1)
    args = parser.parse_args()
    for iteration in range(args.repeat):
        print(f"UI walkthrough {iteration+1}/{args.repeat}",flush=True)
        run_once()
