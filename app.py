"""Pramaan Lens frontend (Streamlit). Run: streamlit run app.py"""
import base64
import html
import io
from datetime import date
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageChops, ImageSequence
from backend import custody
from backend.analysis import COLORS, analyze, annotate
from backend.ml_model import predict_risk
from backend.report_pdf import build_report_pdf

# Configuration
st.set_page_config(page_title="Pramaan Lens", page_icon="🔎", layout="wide")
SAMPLE_OPTIONS = {
    "Clean synthetic example": "clean.png",
    "Message-order example": "order_anomaly.png",
    "Date-mismatch example": "date_mismatch.png",
    "Editing-metadata example": "metadata_tag.png",
}
SAMPLE_CLAIMED_DATE = date(2026, 11, 18)

# Load assets
ASSETS = Path(__file__).parent / "assets"
FONT_REGULAR = base64.b64encode(
    (ASSETS / "fonts" / "PlusJakartaSans-Regular.ttf").read_bytes()
).decode("ascii")
FONT_BOLD = base64.b64encode(
    (ASSETS / "fonts" / "PlusJakartaSans-Bold.ttf").read_bytes()
).decode("ascii")

JUSTICE_GIF_BYTES = (ASSETS / "justice.gif").read_bytes()
JUSTICE_GIF = base64.b64encode(JUSTICE_GIF_BYTES).decode("ascii")


# Helpers
def _gif_bottom_gap_ratio(image):
    """Share of the GIF height that is empty (transparent) below the artwork."""
    try:
        height, lowest = image.height, 0
        for frame in ImageSequence.Iterator(image):
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


with Image.open(io.BytesIO(JUSTICE_GIF_BYTES)) as justice_image:
    JUSTICE_ASPECT = justice_image.height / justice_image.width
    JUSTICE_GAP = _gif_bottom_gap_ratio(justice_image)


STYLESHEET = (
    (ASSETS / "styles.css")
    .read_text(encoding="utf-8")
    .replace("__FONT_REGULAR__", FONT_REGULAR)
    .replace("__FONT_BOLD__", FONT_BOLD)
    .replace("__BRAND_HEIGHT__", f"{100 * JUSTICE_ASPECT * (1 - JUSTICE_GAP):.1f}")
    .replace("__BRAND_MOBILE_HEIGHT__", f"{72 * JUSTICE_ASPECT * (1 - JUSTICE_GAP):.1f}")
)
LOTTIE_JS = (
    (ASSETS / "lottie_light.min.js")
    .read_text(encoding="utf-8")
    .replace("</script", "<\\/script")
)
GIRL_JSON = (
    (ASSETS / "search_empty_girl.json")
    .read_text(encoding="utf-8")
    .replace("</script", "<\\/script")
)
EMPTY_STATE_HTML = (
    (ASSETS / "empty_state.html")
    .read_text(encoding="utf-8")
    .replace("__LOTTIE_JS__", LOTTIE_JS)
    .replace("__GIRL_JSON__", GIRL_JSON)
    .replace("__FONT_REGULAR__", FONT_REGULAR)
    .replace("__FONT_BOLD__", FONT_BOLD)
)


def render_styles():
    """Load the local stylesheet into the Streamlit page."""
    st.markdown(f"<style>{STYLESHEET}</style>", unsafe_allow_html=True)


def flag_location(flag):
    """Describe the image region or metadata field associated with a flag."""
    regions = flag.get("regions") or []
    if len(regions) > 1:
        return f"{len(regions)} highlighted image regions"
    if regions:
        return f"image region {regions[0]}"
    if flag.get("region"):
        return f"image region {flag['region']}"
    return f"metadata field {flag.get('field') or 'not specified'}"



def show_animated_inspector():
    # Illustration sits in the empty space BELOW the step cards, at 70% opacity.
    st.markdown("""<div class="steps-grid">
        <div class="step-card"><div class="step-label">STEP 1</div><div class="step-text">Upload screenshot</div></div>
        <div class="step-card"><div class="step-label">STEP 2</div><div class="step-text">Click Seal and analyse</div></div>
        <div class="step-card"><div class="step-label">STEP 3</div><div class="step-text">Verify flags on original device</div></div>
    </div>""", unsafe_allow_html=True)
    components.html(EMPTY_STATE_HTML, height=680)


render_styles()
st.markdown(f"""<div class="header-bar">
  <div class="brand-group">
    <img class="brand-animation" src="data:image/gif;base64,{JUSTICE_GIF}" alt="Justice scales animation">
    <div class="brand-text">
    <h1 class="brand-title">Pramaan Lens</h1>
    </div>
  </div>
  <span class="local-badge"><svg class="local-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="10" width="16" height="11" rx="2"></rect><path d="M8 10V7a4 4 0 0 1 8 0v3"></path></svg>100% Local · Zero Data Leaves Device</span>
</div>""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("New check")
    claimed = st.date_input("Claimed date · optional", value=None, format="DD/MM/YYYY")
    sample_choice = st.selectbox("Synthetic sample", tuple(SAMPLE_OPTIONS))
    try_sample = st.button("Try sample", icon=":material/image:", use_container_width=True)
    st.caption("Examples use 18 Nov 2026")
    up = st.file_uploader("Screenshot", type=["png", "jpg", "jpeg", "webp"])
    run = st.button(
        "Seal & analyse",
        icon=":material/search:",
        type="primary",
        disabled=up is None,
        use_container_width=True,
    )

analysis_bytes = None
analysis_filename = None
analysis_claimed_date = claimed
if try_sample:
    sample_path = ASSETS / "samples" / SAMPLE_OPTIONS[sample_choice]
    if not sample_path.is_file():
        st.error(f"Synthetic sample is missing: {sample_path.name}")
        st.stop()
    analysis_bytes = sample_path.read_bytes()
    analysis_filename = f"synthetic_{sample_path.name}"
    analysis_claimed_date = SAMPLE_CLAIMED_DATE
elif run and up:
    analysis_bytes = up.getvalue()
    analysis_filename = up.name

# Results (single-page flow)
if analysis_bytes is not None and analysis_filename is not None:
    progress_panel = st.empty()
    with progress_panel.container():
        with st.spinner("Hashing, reading text, checking consistency..."):
            show_animated_inspector()
            result = analyze(analysis_bytes, analysis_filename, analysis_claimed_date)
    progress_panel.empty()
    st.session_state.res = result

with st.expander("Responsible AI and limitations"):
    st.markdown(
        "- PramaanLens reports risk flags and verification steps; it never decides whether an image is genuine or fake.\n"
        "- OCR, metadata, compression, and perceptual-hash checks can be incomplete or produce false alarms. "
        "Check the original conversation on its source device.\n"
        "- The optional ML assist is experimental, trained only on generated synthetic examples, and its displayed "
        "class probability is not calibrated for real evidence.\n"
        "- The tool is not legal advice. Its BSA 2023 s.63 Part A content is a draft for review, not a legal certification."
    )

res = st.session_state.get("res")
if not res:
    show_animated_inspector()
    st.stop()

counts = {level: sum(flag["level"] == level for flag in res["flags"]) for level in ("HIGH", "MEDIUM", "LOW")}
metric_columns = st.columns(3)
for column, level in zip(metric_columns, ("HIGH", "MEDIUM", "LOW")):
    with column:
        st.markdown(f'<div class="metric-card metric-{level.lower()}"><div class="metric-label">{level} FLAGS</div><div class="metric-value">{counts[level]}</div></div>', unsafe_allow_html=True)

st.subheader("ML assist (experimental)")
try:
    ml_result = predict_risk(res["features"])
except ImportError as error:
    st.warning(f"ML assist is unavailable because a dependency is missing: {error}")
else:
    if ml_result is None:
        st.info(
            "The optional model is missing or could not be loaded. Run "
            "`python -m backend.train_model` to create or repair `models/model.joblib`."
        )
    else:
        ml_columns = st.columns(2)
        ml_columns[0].metric("Experimental risk label", ml_result["label"])
        ml_columns[1].metric("Model class probability", f'{ml_result["confidence"]:.0%}')
        st.caption("Synthetic-only model output; rule-based flags above are unchanged.")

st.subheader("Risk flags")
if not res["flags"]:
    st.success("No rule fired. This is not proof of authenticity: confirm on the original device.")
for flag in res["flags"]:
    level = flag["level"]
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
        f'<div class="flag-meta"><span>Next step: {html.escape(flag["action"])}</span>'
        f'<span>Linked to: {html.escape(flag_location(flag))}</span></div></article>',
        unsafe_allow_html=True)

st.subheader("Annotated screenshot")
marker_scale = st.slider(
    "Marker size",
    min_value=1,
    max_value=3,
    value=1,
    format="%dx",
    help="Display only; analysis results are unchanged.",
)
st.image(annotate(res["image"], res["flags"], marker_scale), use_container_width=True)
st.caption("Outlined regions use severity labels; the original screenshot is unchanged.")
with st.expander("View original screenshot"):
    st.image(res["image"], use_container_width=True)

trail = custody.trail(res["case_id"])
with st.expander("Case integrity details"):
    st.code(f"Case ID: {res['case_id']}\nSHA-256: {res['sha256']}", language=None)
    with st.expander("Metadata fields"):
        st.json(res["metadata"] or {"info": "No metadata found"})
    with st.expander("Custody log"):
        for ts, ev, detail in trail:
            st.text(f"{ts}  {ev}  {detail}")

# Report
pdf_buffer = io.BytesIO()
pdf_flags = [
    {
        "check": flag["check"],
        "observation": flag["observation"],
        "severity": flag["level"],
        "action": flag["action"],
        "linked_to": flag_location(flag),
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

st.download_button(
    "Download PDF",
    pdf_buffer.getvalue(),
    file_name=f"pramaanlens_{res['case_id']}.pdf",
    mime="application/pdf",
    icon=":material/download:",
)