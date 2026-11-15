"""Optional local-browser acceptance test, screenshots and captioned backup video.

Requires `uv sync --extra dev` and a Playwright browser (or installed Edge).
The running synthetic Clinic A is reset before recording; no real data is used.
"""
import argparse
import os
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rematch.common.config import ROOT
from rematch.ui.api_client import clinic_api


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record",action="store_true",help="Save a 2–3 minute captioned walkthrough")
    parser.add_argument("--channel",default="msedge",help="Use chromium to select Playwright's installed Chromium")
    args = parser.parse_args()
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",str(ROOT/".cache/ms-playwright"))
    from playwright.sync_api import sync_playwright,expect
    api = clinic_api("clinic-a")
    api.post("/admin/reset")
    api.post("/admin/sync")
    shots = ROOT/"docs/screenshots"
    artifacts = ROOT/"artifacts"
    shots.mkdir(parents=True,exist_ok=True)
    artifacts.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,**({"channel":args.channel} if args.channel!="chromium" else {}))
        options = {"viewport":{"width":1600,"height":1100},"device_scale_factor":1}
        if args.record:
            options.update(record_video_dir=str(artifacts),record_video_size={"width":1600,"height":1100})
        context = browser.new_context(**options)
        # Demonstrate that the prepared core screens work without third-party Wi-Fi.
        context.route("**/*",lambda route: route.continue_() if route.request.url.startswith(("http://127.0.0.1:","http://localhost:","ws://127.0.0.1:","data:","blob:")) else route.abort())
        page = context.new_page()
        page.set_default_timeout(45000)
        errors = []
        page.on("pageerror",lambda error:errors.append(str(error)))

        def healthy():
            expect(page.get_by_test_id("stException")).to_have_count(0)

        def go(role,heading):
            port = {"clinic":8501,"sponsor":8502,"patient":8503}[role]
            page.goto(f"http://127.0.0.1:{port}")
            expect(page.get_by_role("heading",name=heading,exact=True)).to_be_visible()
            healthy()

        def nav(name,heading):
            page.get_by_text(name,exact=True).click()
            expect(page.get_by_role("heading",name=heading,exact=True)).to_be_visible()
            healthy()

        def scene(text,filename=None):
            page.evaluate("window.scrollTo(0,0)")
            if filename:
                page.screenshot(path=str(shots/filename),full_page=True)
            if args.record:
                page.evaluate("""text => { let n=document.getElementById('demo-caption'); if(!n){n=document.createElement('div');n.id='demo-caption';document.body.appendChild(n);}n.textContent=text;Object.assign(n.style,{position:'fixed',bottom:'22px',left:'340px',right:'36px',padding:'18px 26px',background:'#173e37',color:'white',font:'600 20px Arial',borderRadius:'12px',zIndex:999999,boxShadow:'0 5px 30px #0003'}); }""",text)
                time.sleep(12)
                page.evaluate("document.getElementById('demo-caption')?.remove()")
            print(text,flush=True)

        go("clinic","A second look. A new possibility.")
        expect(page.get_by_text("A result changes.",exact=False)).to_be_visible()
        expect(page.get_by_test_id("stPlotlyChart").locator("svg.main-svg").first).to_be_visible()
        scene("ReMatch: a patient screened out once should not be forgotten when their clinical facts change.","clinic-overview.png")
        go("sponsor","Research moves forward. Together.")
        expect(page.get_by_text("Original eligibility source",exact=True)).to_be_visible()
        scene("Verified trial rules are published to clinics. An LLM never decides a patient's screening result.","sponsor-protocol.png")
        nav("Network feasibility","One network. Separate clinical records.")
        expect(page.get_by_test_id("stPlotlyChart").locator("svg.main-svg").first).to_be_visible()
        scene("Two independent clinics share aggregate counts. Patient identities and records stay local.","network-feasibility.png")
        go("clinic","A second look. A new possibility.")
        nav("Review Queue","The right case, back in view")
        expect(page.get_by_text("Watching for clinical updates:",exact=False)).to_be_visible()
        scene("PX-82914 has HbA1c 11.2%. The synthetic trial requires 7.5–10.0%, so this case is watched for updates.","review-before.png")
        page.get_by_role("button",name="+90 days",exact=True).click()
        expect(page.get_by_text("90 days passed.",exact=False)).to_be_visible()
        scene("Ninety days alone creates no new result: old clinical evidence becomes unknown when it expires.")
        page.get_by_role("button",name="Simulate lab feed",exact=True).click()
        expect(page.get_by_text("Previously unmet criterion may now be met — coordinator review required.",exact=True)).to_be_visible()
        scene("A real simulated follow-up feed brings HbA1c 9.1% and refreshes the required assessments. A review task appears.","review-after.png")
        page.get_by_role("button",name="Approve & send de-identified packet",exact=True).click()
        expect(page.get_by_text("Approved. A sealed candidate packet",exact=False)).to_be_visible()
        go("sponsor","Research moves forward. Together.")
        nav("Network Inspector","Everything the middle could see")
        expect(page.get_by_text("A referral exactly as stored by the hub",exact=True)).to_be_visible()
        scene("The coordinator approves. The hub receives routing metadata and sealed ciphertext; it cannot read the evidence.","network-inspector.png")
        nav("Candidate inbox","A reference, relevant evidence, and nothing more")
        expect(page.get_by_role("button",name="Confirm for clinic follow-up",exact=True)).to_have_count(1)
        scene("Only the sponsor opens the packet: a per-trial pseudonym, age range, relevant evidence, and a reassessment badge.","sponsor-inbox.png")
        page.get_by_role("button",name="Confirm for clinic follow-up",exact=True).click()
        expect(page.get_by_text("Confirmation sent.",exact=False)).to_be_visible()
        go("clinic","A second look. A new possibility.")
        page.get_by_role("button",name="Sync trials now",exact=True).click()
        expect(page.get_by_text("Trial bundles, aggregate signals",exact=False)).to_be_visible()
        nav("Outreach & participation","From reviewed evidence to a patient choice")
        page.get_by_role("button",name="Release opportunity to patient",exact=True).click()
        expect(page.get_by_text("Opportunity released.",exact=False)).to_be_visible()
        go("patient","A possibility, at your pace.")
        expect(page.get_by_role("button",name="I'm interested",exact=True)).to_be_visible()
        scene("After sponsor confirmation, the clinic releases a plain-language opportunity. The patient chooses freely.","patient-opportunity.png")
        page.get_by_role("button",name="I'm interested",exact=True).click()
        expect(page.get_by_text("Your choice was sent",exact=False)).to_be_visible()
        scene("Interest starts a clinic conversation, not enrollment. Investigators make formal eligibility decisions.")
        page.get_by_role("button",name="Pause or withdraw from research",exact=True).click()
        expect(page.get_by_text("Research screening stopped.",exact=False)).to_be_visible()
        scene("Withdrawal stops local screening and retracts shared evidence. Regular care is not affected.","patient-withdrawn.png")
        healthy()
        assert not errors,errors
        video = page.video
        context.close()
        if args.record:
            video.save_as(str(artifacts/"rematch-backup.webm"))
            print("Saved artifacts/rematch-backup.webm",flush=True)
        browser.close()


if __name__=="__main__":
    main()
