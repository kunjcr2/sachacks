import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import base64
from datetime import date
import json
import pandas as pd
import plotly.express as px
import streamlit as st
from rematch.common.config import SPONSOR_ID,CLINICS
from rematch.common.crypto import sponsor_private_key,decrypt_packet
from rematch.common.schemas import TrialBundle
from rematch.extraction.curated import load_trials
from rematch.extraction.ctgov import cached_trials,trial_preview,fetch_trial
from rematch.extraction.validate import validate_criteria
from rematch.ui.api_client import sponsor_api
from rematch.ui.components import setup,load,action,status,disclaimer,empty


def main():
    setup("sponsor","Research moves forward. Together.","Publish verified protocols, understand feasibility, and review only the evidence a clinic has approved.")
    st.sidebar.caption("SPONSOR")
    st.sidebar.write("**Meridian Research Labs**")
    page = st.sidebar.radio("Workspace",["Trials & publication","Network feasibility","Candidate inbox","Protocol amendment","Network Inspector"])
    if st.sidebar.button("Refresh",width='stretch'):
        st.rerun()
    api = sponsor_api()
    private = sponsor_private_key()
    disclaimer()
    trials = {t["trial_id"]:t for t in load(api,"/trials")}

    if page=="Trials & publication":
        st.subheader("Public protocol → reviewed rules → local screening")
        st.caption("The five synthetic trials are already published for a dependable offline demo. You can review and republish a version below.")
        library = {t.trial_id:t for t in load_trials()}
        tid = st.selectbox("Synthetic protocol",list(library),format_func=lambda k:f"{k} · {library[k].title}")
        trial = library[tid]
        left,right = st.columns(2)
        with left:
            st.markdown("#### Original eligibility source")
            st.caption(f"Clearly synthetic · {trial.source_ref}")
            st.code(trial.raw_eligibility_text,language=None)
        with right:
            st.markdown("#### Structured rules")
            st.dataframe(pd.DataFrame([{"Field":c.field,"Operator":c.operator,"Minimum":c.min,"Maximum":c.max,"Stage":c.assessment_stage} for c in trial.criteria]),hide_index=True,width='stretch')
        with st.expander("Review each source quotation before publication",expanded=True):
            verified = []
            for c in trial.criteria:
                verified.append(st.checkbox(f"{c.id} · {c.source_text}",key=f"verify-{tid}-{c.id}"))
            if st.button("Publish verified protocol to network",type="primary",disabled=not all(verified)):
                body = trial.model_dump(mode="json")
                body["version"] = trials.get(tid,{}).get("version",0)+1
                action(api,"/trials",body,"Verified protocol published. Clinics will pull this version automatically.")
        st.divider()
        st.subheader("Real public source, cached for offline review")
        cached = cached_trials()
        if cached:
            for raw in cached:
                preview = trial_preview(raw)
                with st.expander(f"{preview['nct_id']} · {preview['title']}",expanded=True):
                    status(preview["status"])
                    st.caption(f"Retrieved {preview['retrieved_at']} · source hash {preview['source_hash'][:16]} · not distributed")
                    st.link_button("Original ClinicalTrials.gov record",f"https://clinicaltrials.gov/study/{preview['nct_id']}")
                    st.code(preview["eligibility"],language=None)
                    st.json({k:preview[k] for k in ["minimum_age","maximum_age","sex","last_update"]})
                    if st.button("Extract draft rules with OpenAI (optional)",key="extract-"+preview["nct_id"]):
                        try:
                            from rematch.extraction.llm import LLMExtractor
                            with st.spinner("Extracting public criteria only; no patient data is sent…"):
                                criteria = LLMExtractor().extract(preview["nct_id"],preview["eligibility"])
                            st.session_state["public_draft"] = [c.model_dump(mode="json") for c in criteria]
                            st.session_state["public_draft_id"] = preview["nct_id"]
                        except Exception as exc:
                            st.error(f"Extraction unavailable ({type(exc).__name__}). Check OPENAI_API_KEY and OPENAI_MODEL in .env. The curated demo remains fully available.")
        else:
            st.info("No public record cached. Use the form below while online; the synthetic demo works offline.")
        with st.expander("Fetch another public trial (requires internet)"):
            nct_id = st.text_input("ClinicalTrials.gov NCT ID",value="NCT03548935")
            if st.button("Fetch & cache source"):
                try:
                    fetch_trial(nct_id.strip(),refresh=True)
                    st.session_state["flash"] = "Public record cached. No criteria were distributed."
                    st.rerun()
                except Exception as exc:
                    st.error(f"Public source unavailable ({type(exc).__name__}). Existing cached sources are preserved.")
        if st.session_state.get("public_draft"):
            st.subheader(f"Unverified extraction · {st.session_state['public_draft_id']}")
            st.warning("Draft only. These public-source extractions are not automatically distributed. The source may be completed or include logic requiring a fuller clinical review.")
            st.json(st.session_state["public_draft"])
            st.download_button("Download draft for manual review",json.dumps(st.session_state["public_draft"],indent=2),file_name=f"{st.session_state['public_draft_id']}-draft.json")

    elif page=="Network feasibility":
        st.subheader("One network. Separate clinical records.")
        signals = load(api,"/signals/aggregate")
        if not signals:
            empty("Waiting for clinics","Open the Clinic workspace and click Sync trials now.")
            return
        tid = st.selectbox("Trial",list(trials),format_func=lambda k:trials[k]["title"])
        rows = [s for s in signals if s["trial_id"]==tid]
        columns = st.columns(3)
        for col,key,label in zip(columns,["evaluated","potential","new_this_period"],["Evaluated locally","Potential screening matches","Reassessment opportunities"]):
            values = [r[key] for r in rows]
            col.metric(label,"Suppressed" if any(v is None for v in values) else sum(values))
        chart = []
        for row in rows:
            if row["suppressed"]:
                st.info(f"{CLINICS.get(row['clinic_id'],row['clinic_id'])}: aggregate row suppressed (threshold {row['min_cell_size']}).")
            else:
                for key,label in [("potential","Potential"),("needs_info","Needs information"),("not_matched","Not currently matched")]:
                    chart.append({"Clinic":CLINICS.get(row["clinic_id"],row["clinic_id"]),"Status":label,"Count":row[key]})
        if chart:
            fig = px.bar(pd.DataFrame(chart),x="Clinic",y="Count",color="Status",barmode="stack",color_discrete_map={"Potential":"#5a55ba","Needs information":"#d7a74c","Not currently matched":"#c4cecb"})
            fig.update_layout(height=390,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",legend=dict(orientation="h",y=1.1),margin=dict(t=50,l=10,r=10,b=10))
            st.plotly_chart(fig,width='stretch')
        st.caption("Counts are aggregate signals, not a list of patients. Later workflow stages remain clinic-local in this prototype.")

    elif page=="Candidate inbox":
        st.subheader("A reference, relevant evidence, and nothing more")
        referrals = load(api,f"/sponsors/{SPONSOR_ID}/referrals")
        if not referrals:
            empty("Your inbox is ready","A coordinator must approve a current potential match before an encrypted packet arrives here.")
        for row in reversed(referrals):
            if row["retracted"]:
                st.info(f"Referral {row['referral_id'][:8]} retracted by the clinic · {row.get('retraction_reason','withdrawn')}. Evidence discarded.")
                continue
            with st.container(border=True):
                try:
                    packet = decrypt_packet(row["ciphertext_b64"],private)
                except Exception:
                    st.error("This packet cannot be opened with this sponsor's local key.")
                    continue
                st.subheader(f"{packet.ref} · {trials[packet.trial_id]['title']}")
                st.caption(f"{CLINICS.get(row['clinic_id'],row['clinic_id'])} · trial v{packet.trial_version} · age range {packet.age_band or 'not requested'}")
                if packet.rematch:
                    st.success("Reassessment opportunity · previously unmet criteria may now be met.")
                st.dataframe(pd.DataFrame([e.model_dump() for e in packet.evidence]).astype(str),hide_index=True,width='stretch')
                disclaimer()
                a,b,c = st.columns(3)
                if a.button("Confirm for clinic follow-up",type="primary",key="confirm-"+row["referral_id"],width='stretch'):
                    action(api,f"/referrals/{row['referral_id']}/response",{"referral_id":row["referral_id"],"decision":"confirm","note":"Evidence reviewed; clinic may discuss formal screening."},"Confirmation sent. The clinic must still release the opportunity to the patient.")
                requested = b.multiselect("Request criterion data",[e.criterion_id for e in packet.evidence],key="requested-"+row["referral_id"])
                if b.button("Request more data",key="needs-"+row["referral_id"],disabled=not requested,width='stretch'):
                    action(api,f"/referrals/{row['referral_id']}/response",{"referral_id":row["referral_id"],"decision":"needs_data","requested_criteria_ids":requested,"note":"Please review the requested protocol assessments."},"Data request sent to the clinic.")
                if c.button("Decline",key="decline-"+row["referral_id"],width='stretch'):
                    action(api,f"/referrals/{row['referral_id']}/response",{"referral_id":row["referral_id"],"decision":"decline","note":"Not progressing to screening on this review."},"Decision sent to the clinic.")
                with st.expander("Decrypted allow-listed packet"):
                    st.json(packet.model_dump(mode="json"))

    elif page=="Protocol amendment":
        st.subheader("When a protocol changes, take another look")
        st.write("This synthetic amendment changes the HbA1c maximum from 10.0% to 11.5%. Clinics pull the new version and reassess locally, without uploading patient records.")
        trial = trials.get("SYN-0001")
        if not trial:
            st.info("Publish ReNew-T2D-01 first.")
            return
        limit = st.number_input("New HbA1c maximum (%)",min_value=7.5,max_value=15.0,value=11.5,step=0.1)
        verify = st.checkbox("I reviewed this synthetic protocol change and its source wording.")
        if st.button("Publish amended protocol",type="primary",disabled=not verify):
            body = json.loads(json.dumps(trial))
            c = next(c for c in body["criteria"] if c["field"]=="hba1c")
            old = c["source_text"]
            c.update(max=limit,source_text=f"HbA1c must be between 7.5% and {limit:g}%.",review_status="verified",extraction="manual")
            body["raw_eligibility_text"] = body["raw_eligibility_text"].replace(old,c["source_text"])
            body["version"] += 1
            action(api,"/trials",body,"Amendment published. Clinics will pull the new version; use Sync trials now to see it immediately.")

    elif page=="Network Inspector":
        st.subheader("Everything the middle could see")
        st.write("The hub sees public trial rules, aggregate counts, routing metadata, sponsor responses, and ciphertext. It holds neither clinic identity keys nor the sponsor's private key.")
        audit = load(api,"/audit")
        referrals = load(api,f"/sponsors/{SPONSOR_ID}/referrals")
        a,b,c = st.columns(3)
        a.metric("Audited requests",len(audit))
        b.metric("Sealed referrals",len(referrals))
        c.metric("Identity fields in referral schema",0)
        if referrals:
            st.markdown("#### A referral exactly as stored by the hub")
            st.json(referrals[-1])
        if audit:
            st.dataframe(pd.DataFrame(audit)[["sender","method","path","size","keys","status"]].astype(str),hide_index=True,width='stretch')
            with st.expander("Validated request previews"):
                st.json(audit[:25])
        st.caption("Rejected request bodies and credentials are never echoed to the audit log. This is a synthetic prototype, not a HIPAA compliance claim.")


if __name__=="__main__":
    main()
