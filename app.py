"""Pramaan Lens frontend (Streamlit). Run: streamlit run app.py"""
import html
import io
import streamlit as st
import streamlit.components.v1 as components
from backend import custody
from backend.analysis import COLORS, analyze, annotate
from report_pdf import build_report_pdf

st.set_page_config(page_title="Pramaan Lens", page_icon="🔎", layout="wide")


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
    .header-bar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; padding-bottom: 16px; margin-bottom: 24px; border-bottom: 1px solid var(--google-border); }
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
    @media (prefers-reduced-motion: reduce) { .analysis-toast { animation-name: analysis-toast-fade; } @keyframes analysis-toast-fade { 0%, 84% { opacity: 1; transform: translate(-50%, -50%); } 100% { opacity: 0; transform: translate(-50%, -50%); visibility: hidden; } } }
    .stButton > button[kind="primary"] { background: var(--google-blue); border: 1px solid var(--google-blue); border-radius: 9999px; color: #FFFFFF !important; font-weight: 600; box-shadow: var(--google-shadow); transition: all .15s ease; }
    .stButton > button[kind="primary"] *, .stButton > button[kind="primary"]:hover { color: #FFFFFF !important; }
    .stButton > button[kind="primary"]:hover { background: #1765CC; border-color: #1765CC; box-shadow: var(--google-shadow-hover); }
    [data-testid="stDownloadButton"] { display: flex; justify-content: flex-end; }
    [data-testid="stDownloadButton"] > button { width: auto; min-width: 220px; max-width: 280px; background: var(--google-blue); color: #FFFFFF; font-size: .9rem; font-weight: 600; padding: 10px 22px; border: 1px solid var(--google-blue); border-radius: 9999px; box-shadow: var(--google-shadow); margin-top: 12px; }
    [data-testid="stDownloadButton"] > button:hover { background: #1765CC; color: #FFFFFF; box-shadow: var(--google-shadow-hover); }
    @media (max-width: 640px) {
      .steps-grid { grid-template-columns: 1fr; }
      .local-badge { white-space: normal; }
      .metric-card, .flag-card, .case-card { padding: 1rem; }
      .metric-value { font-size: 2rem; }
      [data-testid="stDownloadButton"] { justify-content: flex-start; }
    }
    </style>""", unsafe_allow_html=True)



# ---------------------------------------------------------------------------
# Animated empty state: full-page background at 70% opacity. The illustration
# starts as a faint grey outline and is revealed in colour by a scanning lens.
# ---------------------------------------------------------------------------
EMPTY_STATE_HTML = r"""
<style>
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:transparent;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;overflow:hidden}
.card{position:relative;height:100%;overflow:visible;background:transparent}
.stage{position:relative;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:10px 12px}
.content-row{display:flex;align-items:center;justify-content:center;gap:clamp(12px,2.5vw,30px);width:100%;max-width:1000px}
.illustration{flex:0 1 700px;min-width:0}
svg.scene{width:100%;height:auto;aspect-ratio:400/340;display:block;overflow:visible}
.investigating{flex:0 0 clamp(110px,17vw,165px);display:flex;flex-direction:column;align-items:center;gap:12px;color:#526d62;font-size:clamp(.9rem,1.3vw,1.05rem);font-weight:650;letter-spacing:.02em}
.wave-loader{display:flex;align-items:center;justify-content:center;gap:7px;height:38px}
.wave-loader span{width:9px;height:9px;border-radius:50%;background:#5d8978;animation:wave-bob 1s ease-in-out infinite}
.wave-loader span:nth-child(2){animation-delay:.12s;background:#789b8b}
.wave-loader span:nth-child(3){animation-delay:.24s;background:#9bb8aa}
.wave-loader span:nth-child(4){animation-delay:.36s;background:#789b8b}
.wave-loader span:nth-child(5){animation-delay:.48s;background:#5d8978}
@keyframes wave-bob{0%,100%{transform:translateY(7px)}50%{transform:translateY(-7px)}}
.txt{color:#e9f2ec;font-size:1.05rem;font-weight:500;letter-spacing:.2px;opacity:0}
.steam{animation:steam 2.8s ease-in-out infinite}
.steam.b{animation-delay:1.3s}
@keyframes steam{0%{opacity:0;transform:translateY(5px)}40%{opacity:.9}100%{opacity:0;transform:translateY(-12px)}}
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
    <svg class="scene" viewBox="0 0 400 340" role="img" aria-label="A woman at a desk searching with a magnifying glass, no results found">

   <!-- floor shadow -->
   <ellipse cx="225" cy="308" rx="160" ry="8" fill="#0d2418" opacity=".25"/>

   <!-- 1. PLANT + POT (gamla) -->
   <g id="gPlant">
     <path d="M56 262Q60 232 70 196" stroke="#a9c5b6" stroke-width="2" fill="none"/>
     <ellipse cx="44" cy="232" rx="8" ry="22" transform="rotate(-35 44 232)" fill="#b9d2c4"/>
     <ellipse cx="72" cy="218" rx="7" ry="19" transform="rotate(28 72 218)" fill="#b9d2c4"/>
     <ellipse cx="58" cy="246" rx="6" ry="15" transform="rotate(-60 58 246)" fill="#cfe2d6"/>
     <ellipse cx="68" cy="238" rx="5" ry="13" transform="rotate(50 68 238)" fill="#a3beb0"/>
     <path d="M40 262h34q9 22-3 42H43q-12-20-3-42Z" fill="#a8c1b3"/>
     <rect x="38" y="258" width="38" height="8" rx="3" fill="#bcd3c6"/>
   </g>

   <!-- 2. QUESTION BUBBLE -->
   <g id="gBubble">
     <circle cx="118" cy="92" r="27" fill="#a5bfb1"/>
     <path d="M134 112l14 12-24-6Z" fill="#a5bfb1"/>
     <text x="118" y="104" text-anchor="middle" fill="#2b4a3f" font-size="34" font-weight="700" font-family="sans-serif">?</text>
   </g>

   <!-- 3. LADY (body, legs, head) -->
   <g id="gLady">
     <!-- chair, behind her seated pose -->
     <path d="M263 163Q263 159 268 159H280Q285 159 285 164V235H263Z" fill="#789487"/>
     <path d="M269 169V226M279 169V226" stroke="#9bb2a5" stroke-width="2" stroke-linecap="round"/>
     <path d="M195 234Q195 230 201 230H277Q283 230 283 236V243H195Z" fill="#52796b"/>
     <path d="M198 242L194 297M281 242L288 296" stroke="#3f5e52" stroke-width="4" stroke-linecap="round"/>
     <path d="M190 298H199M285 297H293" stroke="#3f5e52" stroke-width="3" stroke-linecap="round"/>
     <!-- far leg: thigh rests across the seat, knee bends into a vertical shin -->
     <path d="M232 238Q242 236 251 241L257 247Q260 252 255 256Q250 260 244 256L229 253Q224 251 225 246Q226 241 232 238Z" fill="#647f73"/>
     <path d="M229 249Q235 249 239 254L239 291Q238 297 232 298Q226 298 225 292L225 258Q225 252 229 249Z" fill="#647f73"/>
     <path d="M226 253Q232 250 238 254" stroke="#91aa9e" stroke-width="2" fill="none" stroke-linecap="round"/>
     <path d="M226 289Q232 292 239 289L240 296Q247 298 251 302Q254 306 249 308H230Q224 307 223 302Z" fill="#34483f"/>
     <path d="M228 295Q234 298 240 295" stroke="#91aa9e" stroke-width="2" fill="none" stroke-linecap="round"/>
     <!-- near leg: horizontal thigh, visible knee, straight lower leg and flat shoe -->
     <path d="M210 238Q220 236 229 241L235 247Q238 252 233 257Q228 261 222 257L207 254Q202 252 203 247Q204 241 210 238Z" fill="#789487"/>
     <path d="M207 249Q213 249 217 254L217 291Q216 297 210 298Q204 298 203 292L203 258Q203 252 207 249Z" fill="#789487"/>
     <path d="M204 253Q210 250 216 254" stroke="#a3b9ad" stroke-width="2" fill="none" stroke-linecap="round"/>
     <path d="M204 289Q210 292 217 289L218 296Q225 298 229 302Q232 306 227 308H208Q202 307 201 302Z" fill="#34483f"/>
     <path d="M206 295Q212 298 218 295" stroke="#91aa9e" stroke-width="2" fill="none" stroke-linecap="round"/>
     <g transform="rotate(-5 237 244)">
       <!-- blouse and jacket, leaning slightly toward the document -->
       <path d="M207 244L209 157Q211 139 226 134L248 134Q263 139 265 157L267 244Q239 252 207 244Z" fill="#42685c"/>
       <path d="M229 135L237 157L245 135L252 145L246 166L237 158L228 166L222 145Z" fill="#f3e8d8"/>
       <path d="M228 166L237 158L246 166L251 195L237 203L223 195Z" fill="#f3e8d8"/>
       <path d="M208 161Q211 143 225 138L230 160L222 193L209 190Z" fill="#52796b"/>
       <path d="M264 161Q261 143 249 138L244 160L252 193L265 190Z" fill="#52796b"/>
       <path d="M237 204L237 240M216 207L219 237M258 207L255 237" stroke="#365b50" stroke-width="2" fill="none" opacity=".7"/>
       <circle cx="237" cy="215" r="2" fill="#e8b66f"/>
       <circle cx="237" cy="228" r="2" fill="#e8b66f"/>
       <rect x="230" y="116" width="14" height="20" rx="6" fill="#e8b99a"/>
       <!-- head -->
       <g id="head" transform="translate(236 101) scale(1.12)">
       <!-- hair silhouette and bun -->
       <path d="M-19 2Q-23 -22 -10 -29Q2 -37 15 -28Q23 -20 19 8L17 23Q11 16 11 4L-12 4Q-12 18-18 24Z" fill="#a94f31"/>
       <circle cx="12" cy="-28" r="9" fill="#bf6039"/>
       <!-- face -->
       <path d="M-14 -1Q-14 -20 0 -20Q14 -20 14 -1Q14 14 0 22Q-14 14 -14 -1Z" fill="#f1c9aa"/>
       <!-- side-swept fringe -->
       <path d="M-17 0Q-20 -25 -2 -27Q14 -29 19 -12Q10 -15 4 -10Q-4 -4 -17 0Z" fill="#bf6039"/>
       <path d="M-14 -15Q-8 -25 1 -25" stroke="#d77a4a" stroke-width="2" fill="none" stroke-linecap="round"/>
       <!-- eyes, brows and expression -->
       <path d="M-11 -5Q-7 -7 -3 -5M3 -5Q7 -7 11 -5" stroke="#713e31" stroke-width="1.5" fill="none" stroke-linecap="round"/>
       <ellipse cx="-7" cy="1" rx="3.5" ry="2.5" fill="#fff"/>
       <ellipse cx="7" cy="1" rx="3.5" ry="2.5" fill="#fff"/>
       <circle id="pupL" cx="-7" cy="1" r="1.8" fill="#315c53"/>
       <circle id="pupR" cx="7" cy="1" r="1.8" fill="#315c53"/>
       <path d="M0 5Q-2 9 1 10M-3 15Q0 17 3 15" stroke="#a75f4d" stroke-width="1.3" fill="none" stroke-linecap="round"/>
       <ellipse cx="-9" cy="10" rx="3" ry="1.7" fill="#d98972" opacity=".42"/>
       <ellipse cx="9" cy="10" rx="3" ry="1.7" fill="#d98972" opacity=".42"/>
       </g>
     </g>
   </g>

   <!-- 4. DESK -->
   <g id="gDesk">
     <rect x="92" y="190" width="292" height="9" rx="3" fill="#b9d0c3"/>
     <rect x="92" y="199" width="292" height="3" fill="#9db8aa"/>
     <rect x="104" y="202" width="7" height="98" fill="#a8c1b3"/>
     <rect x="364" y="202" width="7" height="98" fill="#a8c1b3"/>
   </g>

   <!-- 5. DOCUMENT on the desk -->
   <g id="gDocument">
     <rect x="173" y="170" width="62" height="18" rx="2" fill="#f4f8f5" stroke="#789487" stroke-width="1.5"/>
     <path d="M180 175H227M180 179H221M180 183H214" stroke="#9bb2a5" stroke-width="1.3" stroke-linecap="round"/>
   </g>

   <!-- 6. BOOKS -->
   <g id="gBooks">
     <rect x="116" y="180" width="54" height="10" rx="2" fill="#a8c1b3"/>
     <rect x="120" y="170" width="48" height="10" rx="2" fill="#cfe0d6"/>
     <rect x="115" y="160" width="54" height="10" rx="2" fill="#8fb0a0"/>
   </g>

   <!-- 6. CUP -->
   <g id="gCup">
     <ellipse cx="338" cy="189" rx="17" ry="3.5" fill="#dfe9e4"/>
     <path d="M328 170h20v10q0 9-10 9t-10-9Z" fill="#f4f8f5"/>
     <path d="M348 173h4q3 0 3 4t-3 4h-4" fill="none" stroke="#f4f8f5" stroke-width="2"/>
     <path class="steam" d="M334 165q-5-8 0-16" stroke="#cfe0d6" stroke-width="2" fill="none" stroke-linecap="round"/>
     <path class="steam b" d="M343 165q-5-8 0-16" stroke="#cfe0d6" stroke-width="2" fill="none" stroke-linecap="round"/>
   </g>

   <!-- 7. ARMS + MAGNIFIER -->
   <g id="gArms">
     <path id="armL" stroke="#ecd6c6" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
     <g id="handL" fill="#ecd6c6" stroke="#ecd6c6" stroke-linecap="round" stroke-linejoin="round">
       <path d="M5-3Q2-6-2-4L-9-3Q-12-2-10 0L-5 1L-10 1Q-13 2-10 4L-4 4L-8 5Q-10 7-7 8L1 6Q5 5 7 2Z" stroke-width="1"/>
       <path d="M-7-2L-2-2M-8 2L-3 2M-6 5L-1 4" fill="none" stroke-width="1.6"/>
     </g>
     <path id="armR" stroke="#ecd6c6" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
     <g id="lens" transform="scale(1 0.35)">
       <line x1="24" y1="-24" x2="40" y2="-40" stroke="#2d4a40" stroke-width="2" stroke-linecap="round"/>
       <circle r="15" fill="rgba(255,255,255,.28)" stroke="#2d4a40" stroke-width="2"/>
       <path d="M-22 -8A24 24 0 0 1 2 -32" stroke="#fff" stroke-width="2.2" stroke-linecap="round" fill="none" opacity=".9"/>
     </g>
     <circle id="handR" r="5" fill="#ecd6c6"/>
   </g>
    </svg>

    <div class="txt" id="txt">No results</div>
   </div>
  </div>
 </div>
</div>

<script>
// ---------- helpers & all variables declared up-front ----------
const $ = id => document.getElementById(id);
const clamp = (v,a,b) => Math.max(a,Math.min(b,v));
const easeOut = x => { x = clamp(x,0,1); return 1 - Math.pow(1-x,3); };
const easeBack = x => { x = clamp(x,0,1); const c1 = 1.70158, c3 = c1 + 1; return 1 + c3*Math.pow(x-1,3) + c1*Math.pow(x-1,2); };
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

const L1 = 40, L2 = 40;          // upper arm / forearm length
const HOLD = 3600, FADE = 450;   // pause after last item | fade-out before replay

// serial reveal order: at = start (ms), dur = duration (ms)
const SEQ = [
  {id:"gPlant",  at:150,  dur:520, kind:"grow", origin:"50% 100%"},  // 1. gamla
  {id:"gBubble", at:560,  dur:480, kind:"pop",  origin:"50% 50%"},   // 2. question
  {id:"gDesk",   at:950,  dur:420, kind:"rise"},                     // 3. desk
  {id:"gBooks",  at:1150, dur:380, kind:"rise"},
  {id:"gCup",    at:1300, dur:380, kind:"rise"},
  {id:"gDocument", at:1450, dur:380, kind:"rise"},
  {id:"gLady",   at:1550, dur:520, kind:"rise"},                     // 4. lady
  {id:"gArms",   at:2050, dur:480, kind:"rise"},                     // 5. hand + lens
  {id:"txt",     at:2550, dur:450, kind:"rise"}                      // 6. No results
];
const END = Math.max(...SEQ.map(s => s.at + s.dur));

const els = {};
SEQ.forEach(s => {
  const e = $(s.id);
  els[s.id] = e;
  if (e && s.origin) { e.style.transformBox = "fill-box"; e.style.transformOrigin = s.origin; }
  if (e) e.style.opacity = 0;
});

const content = $("content");
const pupL = $("pupL"), pupR = $("pupR");
const armL = $("armL"), armR = $("armR"), handL = $("handL"), handR = $("handR"), lens = $("lens");

function reveal(s, t){
  const e = els[s.id]; if (!e) return;
  const p = clamp((t - s.at) / s.dur, 0, 1);
  e.style.opacity = clamp(p * 1.8, 0, 1);
  if (s.kind === "grow") e.style.transform = `scale(${0.6 + 0.4*easeOut(p)}, ${0.05 + 0.95*easeOut(p)})`;
  else if (s.kind === "pop") e.style.transform = `scale(${0.3 + 0.7*easeBack(p)})`;
  else e.style.transform = `translateY(${(1 - easeOut(p)) * 16}px)`;
}

// two-bone inverse kinematics: shoulder -> elbow -> wrist
function ik(sx,sy,hx,hy,side){
  let dx = hx - sx, dy = hy - sy, d = Math.hypot(dx,dy);
  const maxd = L1 + L2 - .5;
  if (d > maxd){ hx = sx + dx*maxd/d; hy = sy + dy*maxd/d; dx = hx - sx; dy = hy - sy; d = maxd; }
  d = Math.max(d,10);
  const a = (L1*L1 - L2*L2 + d*d) / (2*d), h = Math.sqrt(Math.max(0, L1*L1 - a*a));
  const ux = dx/d, uy = dy/d, mx = sx + ux*a, my = sy + uy*a;
  const e1 = [mx - uy*h, my + ux*h], e2 = [mx + uy*h, my - ux*h];
  const sc = e => side*e[0] + .8*e[1];
  const e = sc(e1) >= sc(e2) ? e1 : e2;
  return {ex:e[0], ey:e[1], hx:hx, hy:hy};
}

function drawArms(now){
  // Keep the lens level while it scans from left to right and back.
  let px = 200 + Math.sin(now/900)*16;
  let py = 177;
  const off = [24, -8.4];

  const r = ik(254, 154, px + off[0], py + off[1], 1);
  px = r.hx - off[0]; py = r.hy - off[1];
  armR.setAttribute("d", `M254 154L${r.ex} ${r.ey}L${r.hx} ${r.hy}`);
  handR.setAttribute("cx", r.hx); handR.setAttribute("cy", r.hy);
  lens.setAttribute("transform", `translate(${px} ${py}) scale(1 0.35)`);

  // Left palm stays on the document while the elbow remains bent.
  const l = ik(218, 154, 198, 184, -1);
  armL.setAttribute("d", `M218 154L${l.ex} ${l.ey}L${l.hx} ${l.hy}`);
  handL.setAttribute("transform", `translate(${l.hx} ${l.hy})`);

  // eyes follow the lens
  const ex = clamp((px - 236)/40, -1.8, 1.8), ey = clamp((py - 100)/50, -.6, 1.2);
  pupL.setAttribute("cx", -7 + ex); pupL.setAttribute("cy", 2 + ey);
  pupR.setAttribute("cx", 7 + ex);  pupR.setAttribute("cy", 2 + ey);
}

if (reduce){
  SEQ.forEach(s => reveal(s, END + 1));
  drawArms(0);
} else {
  let start = performance.now();
  function frame(now){
    const el = now - start;
    SEQ.forEach(s => reveal(s, el));
    drawArms(now);
    const out = el > END + HOLD ? clamp(1 - (el - END - HOLD)/FADE, 0, 1) : 1;
    content.style.opacity = out;
    if (el > END + HOLD + FADE){
      start = now;
      SEQ.forEach(s => { const e = els[s.id]; if (e) e.style.opacity = 0; });
      content.style.opacity = 1;
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}
</script>
"""
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
    components.html(EMPTY_STATE_HTML, height=640)
render_styles()
st.markdown("""<div class="header-bar">
  <div>
    <h1 class="brand-title">Pramaan Lens</h1>
    <p class="brand-tagline">Forensic screenshot triage, surfaces tampering signals for verification on the source device.</p>
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