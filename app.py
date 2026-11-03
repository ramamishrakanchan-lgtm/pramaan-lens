"""Pramaan Lens frontend (Streamlit). Run: streamlit run app.py"""
import base64
import html
import io
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from backend import custody
from backend.analysis import COLORS, analyze, annotate
from report_pdf import build_report_pdf

st.set_page_config(page_title="Pramaan Lens", page_icon="🔎", layout="wide")

JUSTICE_GIF = base64.b64encode(
    (Path(__file__).parent / "assets" / "justice.gif").read_bytes()
).decode("ascii")


def _gif_bottom_gap_ratio(path):
    """Share of the GIF height that is empty (transparent) below the artwork."""
    try:
        from PIL import Image, ImageChops, ImageSequence
        im = Image.open(path)
        height, lowest = im.height, 0
        for frame in ImageSequence.Iterator(im):
            rgba = frame.convert("RGBA")
            alpha = rgba.getchannel("A")
            if alpha.getextrema()[0] > 20:   # no transparency: compare with the corner colour
                diff = ImageChops.difference(rgba, Image.new("RGBA", rgba.size, rgba.getpixel((0, 0))))
                box = diff.convert("L").point(lambda v: 255 if v > 24 else 0).getbbox()
            else:
                box = alpha.point(lambda a: 255 if a > 20 else 0).getbbox()
            if box:
                lowest = max(lowest, box[3])
        return min(0.45, max(0.0, (height - lowest) / height)) if lowest else 0.0
    except Exception:
        return 0.0


JUSTICE_GAP = _gif_bottom_gap_ratio(Path(__file__).parent / "assets" / "justice.gif")
from PIL import Image as _Img
_g = _Img.open(Path(__file__).parent / "assets" / "justice.gif")
JUSTICE_ASPECT = _g.height / _g.width   # GIF may not be square


def render_styles():
    st.markdown("""<style>
    :root {
      --google-bg: #F8F9FA;
      --google-card: #FFFFFF;
      --google-text: #202124;
      --google-muted: #5F6368;
      --google-border: #DFE1E5;
      --google-shadow: 0 1px 6px rgba(32, 33, 36, .08);
      --google-shadow-hover: 0 4px 12px rgba(32, 33, 36, .14);
      --google-blue: #1A73E8;
    }
    html, body, [class*="css"], button, input, textarea, select {
      font-family: "Plus Jakarta Sans", "Google Sans", Roboto, -apple-system, BlinkMacSystemFont, sans-serif;
    }
    html, body, [data-testid="stAppViewContainer"] {
      background: var(--google-bg);
      color: var(--google-text);
      font-size: 16px;
    }
    [data-testid="stMainBlockContainer"], .block-container {
      max-width: 1120px;
      padding-top: 2.5rem;
      padding-bottom: 4rem;
      margin: 0 auto;
    }
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div:first-child { background: var(--google-card); }
    [data-testid="stSidebar"] { border-right: 1px solid var(--google-border); }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { color: var(--google-text); }
    [data-testid="stHeader"] { background: transparent; }
    #MainMenu, footer, [data-testid="stFooter"] { visibility: hidden; }
    .header-bar { display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: nowrap; gap: 12px 20px; padding-bottom: 0; margin-bottom: 24px; border-bottom: 1px solid var(--google-border); }
    .brand-group { display: flex; align-items: flex-end; gap: 20px; min-width: 0; }
    .brand-text { padding-bottom: 18px; min-width: 0; }
    .local-badge { margin-bottom: 20px; flex: 0 0 auto; }
    .brand-animation { display: block; flex: 0 0 140px; width: 140px; height: 140px; object-fit: contain; }
    .brand-title { margin: 0; color: var(--google-text); font-size: 2.1rem; line-height: 1.2; font-weight: 600; letter-spacing: -.01em; }
    .brand-tagline { margin: 4px 0 0; color: #80868B; font-size: .95rem; line-height: 1.6; font-weight: 400; }
    .local-badge { border: 1px solid #D2E3FC; background: #E8F0FE; color: #1967D2; border-radius: 9999px; padding: 6px 14px; font-size: .8rem; font-weight: 600; white-space: nowrap; box-shadow: var(--google-shadow); }
    h1, h2, h3, [data-testid="stSubheader"] { color: var(--google-text); font-family: "Plus Jakarta Sans", "Google Sans", Roboto, sans-serif; font-weight: 500; letter-spacing: -.01em; }
    h1 { font-size: 2.1rem; margin-bottom: .25rem; }
    h2 { font-size: 1.5rem; }
    h3 { font-size: 1.35rem; }
    p { color: var(--google-muted); font-size: .95rem; line-height: 1.6; }
    hr { border: 0; border-top: 1px solid var(--google-border); margin: 1rem 0 1.5rem; }
    [data-testid="stTabs"] button { font-weight: 600; }
    [data-testid="stTabs"] button[aria-selected="true"] { color: var(--google-blue); border-bottom-color: var(--google-blue); }
    .steps-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin: 20px 0; }
    .step-card { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; background: var(--google-card); border: 1px solid var(--google-border); border-radius: 24px; padding: 20px 16px; box-shadow: var(--google-shadow); }
    .step-label { margin-bottom: 6px; color: #B06000; font-size: .75rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; text-align: center; }
    .step-text { color: var(--google-text); font-size: 1rem; font-weight: 500; text-align: center; }
    .metric-card { background: var(--google-card); border: 1px solid var(--google-border); border-top: 1px solid var(--google-border); border-left: 1px solid var(--google-border); border-radius: 24px; padding: 22px 28px; box-shadow: var(--google-shadow); transition: box-shadow .2s ease, transform .2s ease; }
    .metric-card:hover { box-shadow: var(--google-shadow-hover); transform: translateY(-1px); }
    .metric-high, .metric-medium, .metric-low { --metric-accent: var(--google-text); }
    .metric-label { color: var(--google-muted); font-size: .78rem; font-weight: 600; letter-spacing: .05em; }
    .metric-value { color: var(--google-text); font-family: "Plus Jakarta Sans", "Google Sans", Roboto, sans-serif; font-size: 2.4rem; line-height: 1.2; font-weight: 500; font-variant-numeric: normal; margin-top: 4px; }
    .flag-card { background: var(--google-card); border: 1px solid var(--google-border); border-left: 1px solid var(--google-border); border-radius: 24px; padding: 22px 28px; margin: .75rem 0; color: var(--google-text); box-shadow: var(--google-shadow); transition: transform .15s ease, box-shadow .15s ease; }
    .flag-card:hover { transform: translateY(-1px); box-shadow: var(--google-shadow-hover); }
    .flag-heading { display: flex; align-items: flex-start; gap: .65rem; flex-wrap: wrap; margin-bottom: .55rem; }
    .severity-badge { display: inline-block; flex: 0 0 auto; border: none; border-radius: 9999px; background: var(--badge-bg); color: var(--badge-text); padding: 4px 12px; font-size: .75rem; line-height: 1.35; font-weight: 600; }
    .flag-title { color: var(--google-text); font-weight: 600; overflow-wrap: anywhere; }
    .flag-description { margin: 0; color: var(--google-text); line-height: 1.6; overflow-wrap: anywhere; }
    .flag-meta { display: flex; align-items: center; flex-wrap: wrap; gap: .45rem; margin-top: .75rem; color: var(--google-muted); font-size: .82rem; line-height: 1.4; }
    .flag-meta span { display: inline-flex; align-items: center; width: fit-content; max-width: 100%; font-size: .82rem; font-weight: 500; color: var(--google-muted); background: #F8F9FA; padding: 6px 14px; border-radius: 9999px; border: 1px solid var(--google-border); box-shadow: 0 1px 2px rgba(32, 33, 36, .05); overflow-wrap: anywhere; }
    .case-card { background: var(--google-card); border: 1px solid var(--google-border); border-radius: 24px; padding: 22px 28px; color: var(--google-text); box-shadow: var(--google-shadow); }
    .case-label { color: var(--google-muted); font-size: .78rem; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; margin: .25rem 0; }
    .case-value { display: inline-block; width: fit-content; max-width: 100%; font-size: .82rem; color: var(--google-text); background: #F8F9FA; padding: 6px 14px; border-radius: 9999px; border: 1px solid var(--google-border); overflow-wrap: anywhere; }
    code, pre { font-family: "Plus Jakarta Sans", "Google Sans", Roboto, sans-serif; font-variant-numeric: normal; }
    [data-testid="stAlert"] { border-radius: 9999px; font-weight: 500; font-size: .92rem; padding: 12px 24px; background: var(--google-card); border: 1px solid var(--google-border); color: #137333; box-shadow: var(--google-shadow); }
    [data-testid="stAlert"] [data-testid="stMarkdownContainer"] p { color: inherit; }
    .analysis-toast { position: fixed; top: 50%; left: 50%; z-index: 999999; width: max-content; max-width: min(34rem, calc(100vw - 2rem)); padding: 14px 22px; border: 1px solid #1765CC; border-radius: 9999px; background: #1A73E8; color: #FFFFFF !important; text-align: center; font-size: .92rem; font-weight: 600; line-height: 1.4; box-shadow: 0 4px 16px rgba(32, 33, 36, .2); animation: analysis-toast-pop 4s ease forwards; }
    .analysis-toast * { color: #FFFFFF !important; }
    @keyframes analysis-toast-pop { 0% { opacity: 0; transform: translate(-50%, -50%) scale(.85); } 10%, 84% { opacity: 1; transform: translate(-50%, -50%) scale(1); } 100% { opacity: 0; transform: translate(-50%, -52%) scale(.96); visibility: hidden; } }
    @media (max-width: 640px) { .analysis-toast { width: max-content; max-width: calc(100vw - 2rem); } }
    @media (max-width: 640px) { .brand-animation { flex-basis: 100px; width: 100px; height: 100px; } .brand-group { gap: 12px; } .brand-title { font-size: 1.8rem; } .header-bar { flex-wrap: wrap; } .local-badge { order: -1; margin-bottom: 8px; } }
    @media (prefers-reduced-motion: reduce) { .analysis-toast { animation-name: analysis-toast-fade; } @keyframes analysis-toast-fade { 0%, 84% { opacity: 1; transform: translate(-50%, -50%); } 100% { opacity: 0; transform: translate(-50%, -50%); visibility: hidden; } } }
    .stButton > button[kind="primary"] { background: var(--google-blue); border: 1px solid var(--google-blue); border-radius: 9999px; color: #FFFFFF !important; font-weight: 600; box-shadow: var(--google-shadow); transition: all .15s ease; }
    .stButton > button[kind="primary"] *, .stButton > button[kind="primary"]:hover { color: #FFFFFF !important; }
    .stButton > button[kind="primary"]:hover { background: #1765CC; border-color: #1765CC; box-shadow: var(--google-shadow-hover); }
    [data-testid="stDownloadButton"] { display: flex; justify-content: flex-end; }
    [data-testid="stDownloadButton"] > button { width: auto; min-width: 220px; max-width: 280px; background: var(--google-blue); color: #FFFFFF !important; font-size: .9rem; font-weight: 600; padding: 10px 22px; border: 1px solid var(--google-blue); border-radius: 9999px; box-shadow: var(--google-shadow); margin-top: 12px; }
    [data-testid="stDownloadButton"] > button *,
    [data-testid="stDownloadButton"] > button:hover { color: #FFFFFF !important; }
    [data-testid="stDownloadButton"] > button:hover { background: #1765CC; box-shadow: var(--google-shadow-hover); }
    @media (max-width: 640px) {
      .steps-grid { grid-template-columns: 1fr; }
      .local-badge { white-space: normal; }
      .metric-card, .flag-card, .case-card { padding: 1rem; }
      .metric-value { font-size: 2rem; }
      [data-testid="stDownloadButton"] { justify-content: flex-start; }
    }
    </style>""", unsafe_allow_html=True)



# ---------------------------------------------------------------------------
# Animated empty state: the "No results" woman (Lottie, drawer_search_empty)
# plays on loop at 70% opacity. Lottie player + animation JSON are both loaded
# from ./assets and inlined, so nothing is fetched from the internet.
# ---------------------------------------------------------------------------
ASSETS = Path(__file__).parent / "assets"
LOTTIE_JS = (ASSETS / "lottie_light.min.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
GIRL_JSON = (ASSETS / "search_empty_girl.json").read_text(encoding="utf-8").replace("</script", "<\\/script")

EMPTY_STATE_HTML = r"""
<style>
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:transparent;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;overflow:hidden}
.card{position:relative;height:100%;overflow:visible;background:transparent}
.stage{position:relative;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;gap:10px;padding:0 12px}
.content-row{display:flex;align-items:center;justify-content:center;gap:clamp(12px,2.5vw,30px);width:100%;max-width:1450px}
.illustration{flex:0 1 1000px;min-width:0;display:flex;flex-direction:column;align-items:center;gap:6px}
#girl{width:100%;aspect-ratio:720/500;display:block}
#girl svg path[fill="rgb(255,255,255)"],#girl svg path[fill="#ffffff"]{fill:#c8d5ce}
.investigating{flex:0 0 clamp(150px,22vw,230px);display:flex;flex-direction:column;align-items:center;gap:16px;color:#526d62;font-size:clamp(1.1rem,1.7vw,1.4rem);opacity:0;font-weight:650;letter-spacing:.02em}
.wave-loader{display:flex;align-items:center;justify-content:center;gap:10px;height:56px}
.wave-loader span{width:14px;height:14px;border-radius:50%;background:#5d8978;animation:wave-bob 1s ease-in-out infinite}
.wave-loader span:nth-child(2){animation-delay:.12s;background:#789b8b}
.wave-loader span:nth-child(3){animation-delay:.24s;background:#9bb8aa}
.wave-loader span:nth-child(4){animation-delay:.36s;background:#789b8b}
.wave-loader span:nth-child(5){animation-delay:.48s;background:#5d8978}
@keyframes wave-bob{0%,100%{transform:translateY(10px)}50%{transform:translateY(-10px)}}
.txt{color:#5F6368;font-size:1.05rem;font-weight:500;letter-spacing:.2px}
@media(max-width:640px){.content-row{flex-direction:column;gap:4px}.investigating{flex-basis:auto;gap:5px}.wave-loader{height:28px}.illustration{width:min(100%,520px);flex-basis:auto}}
@media(prefers-reduced-motion:reduce){.wave-loader span{animation:none;transform:none}}
</style>

<div class="card">
 <div class="stage" id="content">
  <div class="content-row">
   <div class="investigating" role="status" aria-label="Investigating">
    <div class="wave-loader" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span></div>
    <span>Investigating...</span>
   </div>
   <div class="illustration">
    <div id="girl" role="img" aria-label="A woman at a desk searching with a magnifying glass, no results found"></div>
   </div>
  </div>
 </div>
</div>

<script>__LOTTIE_JS__</script>
<script>
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const anim = lottie.loadAnimation({
  container: document.getElementById("girl"),
  renderer: "svg",
  rendererSettings: { viewBoxSize: "60 50 720 500" },   // crop empty margin so the woman fills the frame
  loop: !reduce,
  autoplay: !reduce,
  animationData: __GIRL_JSON__
});
anim.setSpeed(0.5);   // half speed = one round takes 2x longer
const inv = document.querySelector(".investigating");
// "Investigating..." fades in together with the woman (first ~30 frames of every loop)
anim.addEventListener("enterFrame", e => { inv.style.opacity = Math.min(1, e.currentTime / 30); });
if (reduce) { anim.goToAndStop(90, true); inv.style.opacity = 1; }   // still frame for reduced-motion users
</script>
""".replace("__LOTTIE_JS__", LOTTIE_JS).replace("__GIRL_JSON__", GIRL_JSON)



def show_animated_inspector():
    # Illustration sits in the empty space BELOW the step cards, at 70% opacity.
    st.markdown("""<style>
    iframe[srcdoc] { opacity: .7; border: 0; pointer-events: none; }
    </style>""", unsafe_allow_html=True)
    st.markdown("""<div class="steps-grid">
        <div class="step-card"><div class="step-label">STEP 1</div><div class="step-text">Upload screenshot</div></div>
        <div class="step-card"><div class="step-label">STEP 2</div><div class="step-text">Click Seal and analyse</div></div>
        <div class="step-card"><div class="step-label">STEP 3</div><div class="step-text">Verify flags on original device</div></div>
    </div>""", unsafe_allow_html=True)
    components.html(EMPTY_STATE_HTML, height=680)
render_styles()
st.markdown(f"""<style>
.brand-animation {{ height: {140 * JUSTICE_ASPECT * (1 - JUSTICE_GAP):.1f}px !important; object-fit: cover !important; object-position: center top; margin-bottom: 23px; }}
@media (max-width: 640px) {{ .brand-animation {{ height: {100 * JUSTICE_ASPECT * (1 - JUSTICE_GAP):.1f}px !important; }} }}
@media (max-width: 640px) {{ .brand-title {{ font-size: 1.5rem !important; }} .brand-tagline {{ font-size: .8rem !important; }} .brand-text {{ padding-bottom: 12px !important; }} .brand-animation {{ flex-basis: 84px !important; width: 84px !important; height: {84 * JUSTICE_ASPECT * (1 - JUSTICE_GAP):.1f}px !important; margin-bottom: 14px; }} }}
</style>
<div class="header-bar">
  <div class="brand-group">
    <img class="brand-animation" src="data:image/gif;base64,{JUSTICE_GIF}" alt="Justice scales animation">
    <div class="brand-text">
    <h1 class="brand-title">Pramaan Lens</h1>
    <p class="brand-tagline">Forensic screenshot triage, surfaces tampering signals for verification on the source device.</p>
    </div>
  </div>
  <span class="local-badge">🔒 100% Local · Zero Data Leaves Device</span>
</div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Case input")
    claimed = st.date_input("Claimed chat date (optional)", value=None, format="DD/MM/YYYY")
    up = st.file_uploader("Chat screenshot", type=["png", "jpg", "jpeg", "webp"])
    run = st.button("Seal and analyse", type="primary", disabled=up is None, use_container_width=True)

if run and up:
    progress_panel = st.empty()
    with progress_panel.container():
        with st.spinner("Hashing, reading text, checking consistency..."):
            show_animated_inspector()
            result = analyze(up.getvalue(), up.name, claimed)
    progress_panel.empty()
    st.session_state.res = result
    st.session_state.analysis_complete = True

res = st.session_state.get("res")
if not res:
    show_animated_inspector()
    st.stop()

if st.session_state.get("analysis_complete"):
    st.markdown(
        '<div class="analysis-toast" role="status">Analysis complete. Review each flag against the original device.</div>',
        unsafe_allow_html=True,
    )
    st.session_state.analysis_complete = False

counts = {level: sum(flag["level"] == level for flag in res["flags"]) for level in ("HIGH", "MEDIUM", "LOW")}
metric_columns = st.columns(3)
for column, level in zip(metric_columns, ("HIGH", "MEDIUM", "LOW")):
    with column:
        st.markdown(f'<div class="metric-card metric-{level.lower()}"><div class="metric-label">{level} FLAGS</div><div class="metric-value">{counts[level]}</div></div>', unsafe_allow_html=True)

flags_tab, evidence_tab, details_tab = st.tabs(["Flags", "Evidence", "Hash & Case details"])
with flags_tab:
    st.subheader("Risk flags")
    if not res["flags"]:
        st.success("No rule fired. This is not proof of authenticity: confirm on the original device.")
    for flag in res["flags"]:
        level = flag["level"]
        link = f"region {flag['region']}" if flag["region"] else f"field {flag['field']}"
        badge_background, badge_text = {
            "HIGH": ("#FCE9E7", "#9D2823"),
            "MEDIUM": ("#FFF2D6", "#805400"),
            "LOW": ("#E7F3EB", "#28613C"),
        }[level]
        st.markdown(
            f'<article class="flag-card" style="--severity:{COLORS[level]};--badge-bg:{badge_background};--badge-text:{badge_text}">'
            f'<div class="flag-heading"><span class="severity-badge">{html.escape(level)}</span>'
            f'<span class="flag-title">{html.escape(flag["check"])}</span></div>'
            f'<p class="flag-description">{html.escape(flag["observation"])}</p>'
            f'<div class="flag-meta"><span>Action: {html.escape(flag["action"])}</span>'
            f'<span>Linked to: {html.escape(str(link))}</span></div></article>',
            unsafe_allow_html=True)

with evidence_tab:
    st.subheader("Annotated evidence")
    st.image(annotate(res["image"], res["flags"]), use_container_width=True)
    st.caption("Flagged regions are highlighted where coordinates are available.")
    with st.expander("View original screenshot"):
        st.image(res["image"], use_container_width=True)

trail = custody.trail(res["case_id"])
with details_tab:
    st.subheader("Case seal")
    st.markdown(
        f'<div class="case-card"><div class="case-label">Case ID</div><div class="case-value">{html.escape(res["case_id"])}</div>'
        f'<div class="case-label" style="margin-top:.8rem">SHA-256</div><div class="case-value">{html.escape(res["sha256"])}</div></div>',
        unsafe_allow_html=True)
    st.caption("Copy-friendly values")
    st.code(f"Case ID: {res['case_id']}\nSHA-256: {res['sha256']}", language=None)
    with st.expander("Metadata fields"):
        st.json(res["metadata"] or {"info": "No metadata found"})
    with st.expander("Custody log"):
        for ts, ev, detail in trail:
            st.text(f"{ts}  {ev}  {detail}")

pdf_buffer = io.BytesIO()
pdf_flags = [
    {
        "check": flag["check"],
        "observation": flag["observation"],
        "severity": flag["level"],
        "action": flag["action"],
        "linked_to": f"region {flag['region']}" if flag["region"] else f"field {flag['field']}",
    }
    for flag in res["flags"]
]
build_report_pdf(
    pdf_buffer,
    file_name=res["filename"],
    case_id=res["case_id"],
    sha256=res["sha256"],
    flags=pdf_flags,
    custody_log=trail,
)

st.download_button("Download report (PDF)", pdf_buffer.getvalue(),
                   file_name=f"pramaanlens_{res['case_id']}.pdf", mime="application/pdf")