import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import streamlit as st
from rematch.common.config import CLINICS
from rematch.ui.api_client import clinic_api
from rematch.ui.components import setup,load,action,status,disclaimer,empty


def main():
    setup("patient","A possibility, at your pace.","Research opportunities from the people who already care for you.")
    cid = st.sidebar.selectbox("My clinic",list(CLINICS),format_func=CLINICS.get)
    picker = clinic_api(cid,patient=True)
    patients = load(picker,"/patients")
    pmap = {p["id"]:p["alias"] for p in patients}
    pid = st.sidebar.selectbox("Sign in as (demo)",list(pmap),format_func=pmap.get)
    st.sidebar.caption("Synthetic demo accounts. This selector is not production authentication.")
    api = clinic_api(cid,patient=True,patient_id=pid)
    page = st.sidebar.radio("My space",["Opportunities from my clinic","My research preferences","My participation"])
    if st.sidebar.button("Refresh",width='stretch'):
        st.rerun()
    p = load(api,f"/patients/{pid}/consent")
    identity = load(api,f"/patients/{pid}/identity")
    st.caption(f"{pmap[pid]} · {identity['name']} · {CLINICS[cid]}")
    disclaimer()

    if page=="My research preferences":
        st.subheader("Would you like your clinic to consider research opportunities?")
        st.write("If you say yes, your clinic can check your records against study requirements. A coordinator reviews every opportunity before sending a study-specific reference and relevant clinical results for research-team review.")
        st.write("Your name and contact details stay at your clinic. You decide whether to discuss a specific study after your clinic shares it with you.")
        status(p["consent"])
        if not p["research_prompt"] and p["consent"]=="NOT_ASKED":
            st.info("Your clinic has not sent a research invitation yet. Ask your clinic if you would like to learn more.")
        else:
            preference = st.radio("My choice",["Yes, I am open to being considered","Not now","No, thank you"],index=0 if p["consent"]=="OPTED_IN" else 1)
            contact = st.selectbox("Preferred way for my clinic to contact me",["clinic portal","email","phone"],index=["clinic portal","email","phone"].index(p["contact_pref"]))
            if st.button("Save my preferences",type="primary"):
                broad = "OPTED_IN" if preference.startswith("Yes") else "WITHDRAWN" if preference=="Not now" else "DECLINED"
                action(api,f"/patients/{pid}/consent",{"broad_status":broad,"contact_pref":contact},"Your preferences are saved. Your regular care is not affected.",method="put")
        st.caption("Saying no does not change your care. You can change your mind or withdraw at any time.")

    elif page=="Opportunities from my clinic":
        st.subheader("Your clinic will start the conversation")
        opportunities = load(api,f"/patients/{pid}/opportunities")
        if not opportunities:
            empty("Nothing to decide today","Opportunities appear here only after your clinic reviews and releases them. You do not need to search for or apply to studies.")
        for card in opportunities:
            with st.container(border=True):
                st.subheader(card["title"])
                st.write(card["summary"])
                st.write(card["why"])
                st.markdown("**What taking part could involve**")
                st.write(card["visits"])
                with st.expander("Exactly what is shared for research review",expanded=True):
                    for item in card["shared"]:
                        st.write("✓ "+item)
                    st.info(card["identity_notice"])
                if card["pipeline_state"] in {"PATIENT_OUTREACH","PATIENT_DEFERRED"} and p["consent"]=="OPTED_IN":
                    a,b,c = st.columns(3)
                    for column,label,response in [(a,"I'm interested","interested"),(b,"Ask me later","later"),(c,"No thanks","no")]:
                        if column.button(label,key=response+card["id"],type="primary" if response=="interested" else "secondary",width='stretch'):
                            action(api,f"/matches/{card['id']}/patient-response",{"response":response},"Your choice was sent to your clinic. There is no commitment to join a study.")
                else:
                    status(card["pipeline_state"])
                disclaimer()

    elif page=="My participation":
        st.subheader("Support, without pressure")
        opportunities = load(api,f"/patients/{pid}/opportunities")
        for card in opportunities:
            if card["pipeline_state"] in {"PATIENT_INTERESTED","REFERRED_TO_SCREENING"}:
                with st.container(border=True):
                    st.write(f"**{card['title']}**")
                    st.write("Your clinic will contact you to discuss the next step. Being interested does not mean you have enrolled.")
                    if card.get("visit"):
                        st.info(card["visit"]["when"])
                        st.caption(card["visit"]["reminder"])
        if not opportunities:
            st.info("You have no active research conversations right now.")
        if st.button("Contact my clinic"):
            st.info("Demo only: use your usual clinic contact or patient portal. No external message has been sent.")
    st.divider()
    st.write("**You are always free to stop.** Withdrawing from research does not affect your regular care.")
    if st.button("Pause or withdraw from research",disabled=p["consent"]=="WITHDRAWN",width='content'):
        action(api,f"/patients/{pid}/withdraw",message="Research screening stopped. Your clinic will retract shared packets. Your regular care is not affected.")


if __name__=="__main__":
    main()
