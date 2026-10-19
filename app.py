"""PramaanLens frontend (Streamlit). Run: streamlit run app.py"""
import html
import streamlit as st
from backend import custody, report
from backend.analysis import COLORS, analyze, annotate

st.set_page_config(page_title="PramaanLens", page_icon="🔎", layout="wide")
st.markdown("""<style>
html, body, [class*="css"] { font-family: "Segoe UI", system-ui, sans-serif; }
h1, h2, h3 { font-family: Georgia, "Times New Roman", serif; color: #14283D; letter-spacing: -.01em; }
.flag { border-left: 6px solid var(--c); background: #F3F5F8; padding: .6rem .9rem; margin: .45rem 0; border-radius: 2px; color: #14283D; }
.flag b.lv { color: var(--c); margin-right: .6rem; }
.flag small { display: block; color: #4a5a6a; margin-top: .15rem; }
.seal { font-family: Consolas, monospace; font-size: .82rem; word-break: break-all; background: #14283D; color: #E8EDF3; padding: .6rem .8rem; border-radius: 2px; }
</style>""", unsafe_allow_html=True)

st.title("PramaanLens")
st.write("Upload a chat screenshot. You get risk flags and a checklist of what to verify on the original device. "
         "Nothing leaves this machine, and PramaanLens never calls a screenshot genuine or fake.")

with st.sidebar:
    st.header("Case input")
    claimed = st.date_input("Claimed chat date (optional)", value=None, format="DD/MM/YYYY")
    up = st.file_uploader("Chat screenshot", type=["png", "jpg", "jpeg", "webp"])
    run = st.button("Seal and analyse", type="primary", disabled=up is None)

if run and up:
    with st.spinner("Hashing, reading text, checking consistency..."):
        st.session_state.res = analyze(up.getvalue(), up.name, claimed)

res = st.session_state.get("res")
if not res:
    st.info("Choose a screenshot in the sidebar, then select Seal and analyse.")
    st.stop()

st.markdown(f"**Case {res['case_id']}**")
st.markdown(f'<div class="seal">SHA-256 {res["sha256"]}</div>', unsafe_allow_html=True)

left, right = st.columns([1, 1.2], gap="large")
with left:
    st.subheader("Evidence")
    st.image(annotate(res["image"], res["flags"]), use_container_width=True)
    st.caption("Boxes mark the image regions behind each flag.")
with right:
    st.subheader("What to verify first")
    if not res["flags"]:
        st.success("No rule fired. This is not proof of authenticity: confirm on the original device.")
    for f in res["flags"]:
        link = f"region {f['region']}" if f["region"] else f"field {f['field']}"
        st.markdown(
            f'<div class="flag" style="--c:{COLORS[f["level"]]}"><b class="lv">{f["level"]}</b>'
            f'<b>{html.escape(f["check"])}</b>: {html.escape(f["observation"])}'
            f'<small>Action: {html.escape(f["action"])} | Linked to: {html.escape(str(link))}</small></div>',
            unsafe_allow_html=True)
    trail = custody.trail(res["case_id"])
    st.download_button("Download report (PDF)", report.build_pdf(res, trail),
                       file_name=f"pramaanlens_{res['case_id']}.pdf", mime="application/pdf")
    with st.expander("Metadata fields"):
        st.json(res["metadata"] or {"info": "No metadata found"})
    with st.expander("Custody log"):
        for ts, ev, d in trail:
            st.text(f"{ts}  {ev}  {d}")
