import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from datetime import date
import html
import uuid
import pandas as pd
import plotly.express as px
import streamlit as st
from rematch.common.config import CLINICS
from rematch.common.fields import FIELDS
from rematch.clinic.seed import HERO
from rematch.ui.api_client import clinic_api
from rematch.ui.components import setup,load,action,status,criterion_table,disclaimer,empty


def main():
    setup("clinic","A second look. A new possibility.","Continuous research screening, with clinical judgment and patient choice at every step.")
    cid = st.sidebar.selectbox("Clinic",list(CLINICS),format_func=CLINICS.get)
    api = clinic_api(cid)
    overview = load(api,"/overview")
    if "next_page" in st.session_state:
        st.session_state["clinic_page"] = st.session_state.pop("next_page")
    page = st.sidebar.radio("Workspace",["Overview","Review Queue","Trials","Patients","Data freshness","Outreach & participation","Privacy log"],key="clinic_page")
    st.sidebar.divider()
    st.sidebar.caption("SIMULATED CLOCK")
    st.sidebar.subheader(date.fromisoformat(overview["today"]).strftime("%b %d, %Y"))
    a,b = st.sidebar.columns(2)
    if a.button("+30 days",width='stretch'):
        action(api,"/admin/clock/advance",{"days":30},"Clock advanced. Clinical records were reassessed for freshness.")
    if b.button("+90 days",width='stretch'):
        action(api,"/admin/clock/advance",{"days":90},"90 days passed. Old results may now need an update.")
    if cid=="clinic-a" and st.sidebar.button("Simulate lab feed",type="primary",width='stretch'):
        action(api,"/admin/simulate-lab-feed",message="Follow-up received: HbA1c 9.1%, eGFR 68, refreshed BMI and pregnancy assessment. Open Review Queue.")
    if st.sidebar.button("Sync trials now",width='stretch'):
        action(api,"/admin/sync",message="Trial bundles, aggregate signals, and sponsor responses synchronized.")
    if st.sidebar.button("Refresh",width='stretch'):
        st.rerun()
    with st.sidebar.expander("Reset selected clinic"):
        st.caption("Restores this clinic to day zero and retracts its prior referrals. Use the terminal reset for the whole network.")
        if st.button("Reset clinic to day zero",width='stretch'):
            action(api,"/admin/reset",message="Selected clinic restored to day zero.")
    if overview["sync_error"]:
        st.warning(overview["sync_error"])
    disclaimer()
    matches = load(api,"/matches")
    trials = {t["trial_id"]:t for t in load(api,"/trials")}
    patients = load(api,"/patients")
    aliases = {p["id"]:p["alias"] for p in patients}
    hero = next((m for m in matches if m["result"]["patient_id"]==HERO and m["result"]["trial_id"]=="SYN-0001"),None)

    if page=="Overview":
        columns = st.columns(4)
        for c,label,value in zip(columns,["Patients opted in","Trials on network","Potential matches","Open review tasks"],[overview["opted_in"],overview["trials"],overview["potential"],overview["pending"]]):
            c.metric(label,value)
        if hero:
            hba = next(c for c in hero["result"]["criteria"] if c["criterion_id"]=="SYN-0001-C3")
            st.markdown(f'<div class="hero"><div class="eyebrow">THE REASSESSMENT STORY · PX-82914</div><div class="hero-title">A result changes.<br>A door opens again.</div><div class="muted">At first review, HbA1c was 11.2%. ReNew-T2D-01 requires 7.5–10.0%.<br>Current recorded HbA1c: <b>{hba["patient_value"]}%</b> · {html.escape(hero["result"]["status"].replace("_"," ").title())}</div></div>',unsafe_allow_html=True)
            a,b = st.columns([1,3])
            if a.button("Open hero review →",type="primary",width='stretch'):
                st.session_state["next_page"] = "Review Queue"
                st.rerun()
            b.caption("Demo: advance 90 days → simulate lab feed → review → approve → sponsor confirms → clinic releases.")
        left,right = st.columns([3,2])
        with left:
            st.subheader("Local screening, at a glance")
            counts = pd.DataFrame([{"Status":label,"Patients × trials":sum(m["result"]["status"]==key for m in matches)} for key,label in [("POTENTIAL_MATCH","Potential"),("NEEDS_INFO","Needs information"),("NOT_MATCHED","Not currently matched")]])
            fig = px.bar(counts,x="Patients × trials",y="Status",orientation="h",color="Status",color_discrete_sequence=["#147d72","#d7a74c","#a9b9b2"])
            fig.update_layout(showlegend=False,height=260,margin=dict(l=0,r=10,t=10,b=0),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig,width='stretch')
        with right:
            with st.container(border=True):
                st.subheader("What left this clinic")
                st.metric("Guarded outbound requests",overview["outbound"])
                st.write("Aggregate counts and sealed candidate evidence. Names, contacts and local patient IDs stay here.")
                st.caption(f"{overview['stale']} criterion assessments need updated information.")

    elif page=="Review Queue":
        st.subheader("The right case, back in view")
        task_rows = load(api,"/tasks")
        rematches = [m for m in matches if m["rematch"] and m["result"]["status"]=="POTENTIAL_MATCH"]
        if rematches:
            st.success(f"{len(rematches)} reassessment opportunities · previously unmet criteria may now be met.")
        selected_trial = st.selectbox("Trial",list(trials),format_func=lambda k:f"{k} · {trials[k]['title']}") if trials else None
        options = [m for m in matches if m["result"]["trial_id"]==selected_trial]
        options.sort(key=lambda m:(m["result"]["patient_id"]!=HERO,not m["rematch"],m["result"]["status"]!="POTENTIAL_MATCH"))
        if not options:
            empty("No cases yet","Sync trials to start local screening for opted-in patients.")
            return
        by_id = {m["id"]:m for m in options}
        mid = st.selectbox("Case",list(by_id),format_func=lambda k:f"{by_id[k]['patient_alias']} · {by_id[k]['result']['status'].replace('_',' ').title()} · {by_id[k]['pipeline_state'].replace('_',' ').title()}")
        row = load(api,f"/matches/{mid}")
        p = load(api,f"/patients/{row['result']['patient_id']}")
        identity = load(api,f"/patients/{p['id']}/identity")
        st.markdown(f"### {p['alias']} · {identity['name']}")
        status(row["result"]["status"])
        status(row["pipeline_state"])
        if row["result"]["watch"]:
            st.info("Watching for clinical updates: all currently blocking criteria can change under this demo's rules.")
        history = row["history"]
        previous = next((h for h in reversed(history) if h["kind"]=="NEW_OPPORTUNITY" and h["before"]),None)
        if row["rematch"] and previous:
            st.success("Previously unmet criterion may now be met — coordinator review required.")
            changes = [{"Criterion":d["criterion_id"],"Before":str((d["before"] or {}).get("patient_value","—")),"After":str(d["after"]["patient_value"]),"Assessment":f"{(d['before'] or {}).get('status','—')} → {d['after']['status']}"} for d in previous["diff"] if (d["before"] or {}).get("patient_value")!=d["after"]["patient_value"]]
            st.dataframe(pd.DataFrame(changes),hide_index=True,width='stretch')
        criterion_table(trials[selected_trial],row["result"])
        st.caption("C-peptide remains a central-lab screening assessment; it is not waived by a potential preliminary match.")
        if row["pipeline_state"] in {"PENDING_REVIEW","ON_HOLD","SPONSOR_NEEDS_DATA"}:
            note = st.text_input("Coordinator note (clinic only)",value=row.get("note",""))
            a,b,c = st.columns([3,1,1])
            if a.button("Approve & send de-identified packet",type="primary",disabled=row["result"]["status"]!="POTENTIAL_MATCH",width='stretch'):
                action(api,f"/matches/{mid}/decision",{"action":"approve","note":note},"Approved. A sealed candidate packet was sent to the sponsor through the hub.")
            if b.button("Hold",width='stretch'):
                action(api,f"/matches/{mid}/decision",{"action":"hold","note":note},"Case placed on hold.")
            if c.button("Dismiss",width='stretch'):
                action(api,f"/matches/{mid}/decision",{"action":"dismiss","note":note},"Case dismissed.")
        if row.get("sponsor_response"):
            st.info(f"Sponsor: {row['sponsor_response']['decision']} · {row['sponsor_response']['note']}")
        with st.expander("Reassessment history"):
            st.dataframe(pd.DataFrame([{"When":h["at"],"Trigger":h["trigger"],"Transition":h["kind"],"Before":(h["before"] or {}).get("status","—"),"After":h["after"]["status"]} for h in history]),hide_index=True,width='stretch')
        st.caption(f"{len(task_rows)} open coordinator tasks across this clinic.")

    elif page=="Trials":
        st.subheader("Verified protocols received from the hub")
        for t in trials.values():
            with st.expander(f"{t['trial_id']} · {t['title']} · v{t['version']} · {t['status']}"):
                st.write(t["plain_language_summary"])
                st.code(t["raw_eligibility_text"],language=None)
                local = [m for m in matches if m["result"]["trial_id"]==t["trial_id"]]
                st.write(f"{len(local)} opted-in patients evaluated locally; {sum(m['result']['status']=='POTENTIAL_MATCH' for m in local)} potential screening matches.")

    elif page=="Patients":
        search = st.text_input("Search patient alias",placeholder="PX-82914")
        choices = [p for p in patients if search.lower() in p["alias"].lower()]
        if not choices:
            st.info("No patients found.")
            return
        pmap = {p["id"]:p for p in choices}
        pid = st.selectbox("Patient",list(pmap),format_func=lambda k:pmap[k]["alias"])
        identity = load(api,f"/patients/{pid}/identity")
        st.subheader(f"{pmap[pid]['alias']} · {identity['name']}")
        status(pmap[pid]["consent"])
        with st.expander("Clinic-only contact details"):
            st.json(identity)
        if pmap[pid]["consent"]=="NOT_ASKED" and st.button("Ask about research"):
            action(api,f"/patients/{pid}/ask-research",message="Research invitation released to the patient's preferences page.")
        clinical = load(api,f"/patients/{pid}/fhir")
        latest = {}
        for fact in sorted(clinical["facts"],key=lambda f:f["effective_date"]):
            latest[fact["field"]] = fact
        st.dataframe(pd.DataFrame(latest.values())[["field","value","unit","effective_date","method"]].astype(str),hide_index=True,width='stretch')
        with st.expander("Ingest a new clinic-verified observation"):
            st.caption("Synthetic values only. This is a clinic workflow; patients cannot upload clinical records.")
            field = st.selectbox("Measurement",[k for k,v in FIELDS.items() if v.code and v.kind in {"lab","vital"}])
            with st.form("new_lab"):
                value = st.number_input("Value",value=9.1)
                unit = st.text_input("Unit",value=FIELDS[field].unit or "",key="lab-unit-"+field)
                effective = st.date_input("Collected",value=date.fromisoformat(overview["today"]),max_value=date.fromisoformat(overview["today"]))
                method = st.selectbox("Method",["HPLC","POC","STANDARD"])
                submit = st.form_submit_button("Ingest & reassess")
            if submit:
                payload = {"resourceType":"Observation","id":uuid.uuid4().hex,"status":"final","code":{"coding":[{"code":FIELDS[field].code}]},"subject":{"reference":f"Patient/{pid}"},"effectiveDateTime":f"{effective}T12:00:00Z","valueQuantity":{"value":value,"unit":unit},"method":{"text":method}}
                action(api,"/fhir/Observation",payload,"Observation ingested. Local screening reassessed.")
        with st.expander("Full clinical history"):
            st.json(clinical)

    elif page=="Data freshness":
        st.subheader("A prompt to follow up, not a guessed result")
        st.write("Time passing does not create new clinical facts. Missing and expired assessments stay unknown until the clinic receives an update.")
        rows = load(api,"/freshness")
        if rows:
            st.dataframe(pd.DataFrame(rows).drop(columns=["patient_id"]),hide_index=True,width='stretch')
        else:
            empty("Everything is current","No missing or stale preliminary assessments need follow-up.")

    elif page=="Outreach & participation":
        st.subheader("From reviewed evidence to a patient choice")
        active = [m for m in matches if m["referral_id"]]
        if not active:
            empty("No referrals sent yet","Approve a potential screening match in Review Queue, then confirm it in the Sponsor workspace.")
        for m in active:
            with st.container(border=True):
                st.write(f"**{m['patient_alias']} · {trials[m['result']['trial_id']]['title']}**")
                status(m["pipeline_state"])
                if m["pipeline_state"]=="SPONSOR_CONFIRMED" and st.button("Release opportunity to patient",key="release"+m["id"],type="primary"):
                    action(api,f"/matches/{m['id']}/release",message="Opportunity released. The patient can now respond in their app.")
                if m["pipeline_state"]=="PATIENT_INTERESTED" and st.button("Arrange screening referral",key="refer"+m["id"],type="primary"):
                    action(api,f"/matches/{m['id']}/refer",message="Screening referral recorded. The clinic will arrange the visit.")
                if m["pipeline_state"]=="REFERRED_TO_SCREENING":
                    st.caption("Screening referral recorded; no external appointment or message has been sent.")

    elif page=="Privacy log":
        st.subheader("Every outbound payload has a boundary")
        st.write("Identity is encrypted at rest using a separate AES-GCM key for each clinic. Sponsor-bound evidence is sealed with the sponsor's public key.")
        minimum = st.select_slider("Small-cell suppression threshold",options=[1,5,10],value=overview["min_cell_size"] if overview["min_cell_size"] in [1,5,10] else 1)
        st.caption("1 is a synthetic-demo setting. With 5 or 10, any small nonzero cell suppresses its entire aggregate row to prevent subtraction.")
        if st.button("Apply suppression & sync"):
            try:
                api.put("/admin/privacy",{"min_cell_size":minimum})
                action(api,"/admin/sync",message="Suppression applied and aggregate signals synchronized.")
            except RuntimeError as exc:
                st.error(str(exc))
        rows = load(api,"/privacy-log")
        if rows:
            st.dataframe(pd.DataFrame(rows).fillna("").astype(str),hide_index=True,width='stretch')
        else:
            st.info("No audit entries yet.")


if __name__=="__main__":
    main()
