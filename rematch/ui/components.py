import html
import pandas as pd
import streamlit as st
from rematch.common.config import DISCLAIMER

COLORS = {"clinic":"#147d72","sponsor":"#5a55ba","patient":"#b86638"}
LABELS = {"POTENTIAL_MATCH":"Potential screening match","NEEDS_INFO":"More information needed","NOT_MATCHED":"Criteria not currently met",
          "MET":"Met","NOT_MET":"Not met","UNKNOWN":"Unknown"}


def setup(role,title,subtitle):
    st.set_page_config(page_title=f"ReMatch · {role.title()}",page_icon="↻",layout="wide",initial_sidebar_state="expanded")
    color = COLORS[role]
    st.markdown(f"""<style>
    :root {{--accent:{color};}}
    html,body,[class*="css"],.stApp {{font-family:'DM Sans',sans-serif;}}
    .stApp {{background:#f7f9f8;color:#243b3a;}}
    h1,h2,h3 {{font-family:'Manrope',sans-serif!important;letter-spacing:-.035em;font-weight:700!important;}}
    h1 {{font-size:2.7rem!important;line-height:1.12!important;}}
    h2 {{font-size:1.65rem!important;}}
    [data-testid="stSidebar"] {{background:#edf2ef;border-right:1px solid #dce5df;}}
    [data-testid="stSidebar"] .block-container {{padding-top:2rem;}}
    .block-container {{max-width:1480px;padding-top:4.5rem;padding-bottom:3rem;}}
    [data-testid="stToolbar"] {{visibility:hidden;}}
    [data-testid="stMetric"] {{background:white;border:1px solid #e0e8e3;border-radius:14px;padding:18px 20px;}}
    [data-testid="stMetricValue"] {{font-family:'Manrope',sans-serif;font-size:2rem;}}
    [data-testid="stVerticalBlockBorderWrapper"] > div {{border-radius:16px!important;}}
    .eyebrow {{font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;color:{color};font-weight:700;margin-bottom:12px;}}
    .brand {{font-size:2rem;font-family:'Manrope',sans-serif;font-weight:800;letter-spacing:-.08em;color:#173e37;}}
    .brand span {{color:{color};}}
    .muted {{color:#657b74;font-size:.93rem;line-height:1.6;}}
    .hero {{border:1px solid #c7ddd2;border-radius:20px;background:linear-gradient(120deg,#e4f0e9,#f4f6ed);padding:28px 32px;margin:18px 0 25px;}}
    .hero-title {{font-family:'Manrope',sans-serif;font-size:1.8rem;font-weight:700;letter-spacing:-.04em;line-height:1.2;margin-bottom:12px;}}
    .pill {{display:inline-block;border-radius:30px;background:#e5eee8;color:{color};padding:5px 11px;font-size:.73rem;font-weight:600;margin:3px 5px 5px 0;}}
    .boundary {{border-left:3px solid {color};padding:9px 14px;background:white;color:#50625d;font-size:.82rem;margin:14px 0 22px;border-radius:0 8px 8px 0;}}
    .stButton button[kind="primary"] {{background:{color};border-color:{color};border-radius:8px;}}
    .stButton button {{border-radius:8px;min-height:2.5rem;}}
    [data-testid="stDataFrame"] {{border-radius:10px;}}
    footer {{visibility:hidden;}}
    </style>""",unsafe_allow_html=True)
    st.sidebar.markdown('<div class="brand">re<span>match</span> ↻</div>',unsafe_allow_html=True)
    st.sidebar.caption("DISCOVER · REASSESS · RE-ENGAGE")
    st.sidebar.divider()
    left,right = st.columns([3,2])
    with left:
        st.markdown(f'<div class="eyebrow">{role} workspace · synthetic demo</div>',unsafe_allow_html=True)
    with right:
        cols = st.columns(3)
        for col,(label,port) in zip(cols,[("Clinic",8501),("Sponsor",8502),("Patient",8503)]):
            col.link_button(label,f"http://localhost:{port}",width='stretch')
    st.title(title)
    st.markdown(f'<div class="muted">{html.escape(subtitle)}</div>',unsafe_allow_html=True)
    boundary = {"clinic":"🔒 Identity Zone · Patient identities stay inside this clinic.","sponsor":"De-identified evidence only · The hub routes sealed packets; only this sponsor can open them.","patient":"Your choice, your care · Research participation is optional and does not affect your regular care."}[role]
    st.markdown(f'<div class="boundary">{boundary}</div>',unsafe_allow_html=True)
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))


def disclaimer():
    st.caption(DISCLAIMER)


def action(api,path,data=None,message="Saved.",method="post"):
    try:
        result = getattr(api,method)(path,data) if method!="get" else api.get(path)
    except RuntimeError as exc:
        st.error(str(exc))
        return False
    st.session_state["flash"] = message
    st.rerun()


def load(api,path):
    try:
        return api.get(path)
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()


def status(value):
    st.markdown(f'<span class="pill">{html.escape(LABELS.get(value,value.replace("_"," ").title()))}</span>',unsafe_allow_html=True)


def criterion_table(trial,result):
    by_id = {r["criterion_id"]:r for r in result["criteria"]}
    rows = []
    for c in trial["criteria"]:
        r = by_id.get(c["id"])
        if not r:
            continue
        value = r["patient_value"]
        rows.append({"Requirement":c["field"].replace("_"," "),"Source":c["source_text"],
                     "Clinic fact":"Missing" if value is None else f"{value} {r['patient_unit'] or ''}",
                     "Age (days)":r["age_days"],"Assessment":LABELS.get(r["status"],r["status"]),"Reason":r["reason"],
                     "Reuse":r["reuse_class"].replace("_"," ").title(),"Stage":c["assessment_stage"].replace("_"," ")})
    st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
    st.caption("Reuse labels support coordinator review; existing results do not automatically replace protocol-required tests.")


def empty(title,body):
    with st.container(border=True):
        st.subheader(title)
        st.write(body)
