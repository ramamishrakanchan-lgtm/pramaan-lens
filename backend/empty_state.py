import streamlit.components.v1 as components

EMPTY_STATE_HTML = r"""
<style>
:root{--ink:#262326;--mute:#6b6670;--line:#e4e0e6;--ok:#2f8f6b;color-scheme:light dark}
@media(prefers-color-scheme:dark){:root{--ink:#f1eef2;--mute:#a9a3ad;--line:#3a363d}}
html,body{margin:0;background:transparent;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--ink)}
.wrap{max-width:360px;margin:0 auto;text-align:center;padding:4px 8px}
svg{width:100%;height:auto;display:block;overflow:visible}
.ghost{filter:grayscale(1);opacity:.28}
h3{margin:6px 0 2px;font-size:1.25rem}
p.cap{margin:0 0 12px;color:var(--mute);font-size:.85rem}
.bar{height:6px;border-radius:3px;background:var(--line);overflow:hidden}
.bar i{display:block;height:100%;width:0;background:var(--ok)}
ul{list-style:none;margin:10px 0 0;padding:0;text-align:left;font-size:.82rem;color:var(--mute)}
li{display:flex;gap:8px;align-items:center;padding:2px 0}
li b{width:8px;height:8px;border-radius:50%;background:var(--line);flex:none}
li.on{color:var(--ink)} li.on b{background:#e8a33d}
li.done{color:var(--ink)} li.done b{background:var(--ok)}
</style>

<div class="wrap">
<svg viewBox="0 0 340 250" role="img" aria-label="Illustration of a person scanning with a magnifying glass">
  <defs>
    <g id="art">
      <path d="M52 168 C30 122 40 86 62 70 C72 100 70 136 52 168Z" fill="#c9d6cf"/>
      <path d="M288 168 C312 128 304 96 286 78 C272 106 274 140 288 168Z" fill="#c9d6cf"/>
      <ellipse cx="170" cy="238" rx="130" ry="9" fill="#dcdce2"/>
      <path d="M158 168 L150 222 L166 222 L172 168Z" fill="#f2b9a0"/>
      <path d="M178 168 L186 222 L202 222 L192 168Z" fill="#f2b9a0"/>
      <rect x="144" y="222" width="26" height="8" rx="4" fill="#c4622d"/>
      <rect x="182" y="222" width="26" height="8" rx="4" fill="#c4622d"/>
      <rect x="70" y="172" width="5" height="62" fill="#3b4256"/>
      <rect x="265" y="172" width="5" height="62" fill="#3b4256"/>
      <path d="M138 168 L142 100 Q170 88 198 100 L202 168Z" fill="#46506a"/>
      <rect x="164" y="84" width="12" height="14" fill="#f2b9a0"/>
      <circle cx="170" cy="72" r="17" fill="#f2b9a0"/>
      <path d="M152 72 Q150 50 172 50 Q192 52 189 72 Q180 60 160 64Z" fill="#d9692f"/>
      <circle cx="178" cy="44" r="9" fill="#d9692f"/>
      <rect x="86" y="158" width="46" height="7" fill="#58627a"/>
      <rect x="86" y="150" width="46" height="8" fill="#6f7a8f"/>
      <rect x="90" y="142" width="40" height="8" fill="#8d97a9"/>
      <rect x="142" y="132" width="52" height="33" rx="2" fill="#f4f3f6" stroke="#3b4256" stroke-width="2"/>
      <rect x="62" y="165" width="216" height="6" rx="3" fill="#3b4256"/>
      <rect x="236" y="153" width="14" height="12" rx="2" fill="#fff" stroke="#3b4256" stroke-width="2"/>
      <circle cx="96" cy="86" r="14" fill="#cfe0ea"/>
      <text x="96" y="92" text-anchor="middle" font-size="16" font-weight="700" fill="#3b4256">?</text>
    </g>
    <clipPath id="rev">
      <rect id="revRect" x="0" y="0" width="340" height="0"/>
      <circle id="revCirc" r="24" cx="-60" cy="-60"/>
    </clipPath>
  </defs>

  <use href="#art" class="ghost"/>
  <use href="#art" clip-path="url(#rev)"/>
  <line id="scanLine" x1="40" x2="300" y1="0" y2="0" stroke="#2f8f6b" stroke-width="1.5" stroke-dasharray="4 3" opacity=".7"/>
  <line id="arm" stroke="#f2b9a0" stroke-width="7" stroke-linecap="round"/>
  <g id="lens">
    <circle r="20" fill="rgba(160,200,230,.22)" stroke="#3b4256" stroke-width="4"/>
    <path d="M-11 -8 A14 14 0 0 1 -2 -14" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round"/>
    <line x1="14" y1="14" x2="30" y2="30" stroke="#3b4256" stroke-width="6" stroke-linecap="round"/>
  </g>
</svg>

<h3>Ready to inspect a screenshot?</h3>
<p class="cap">Upload a file to begin a local Pramaan Lens review.</p>
<div class="bar"><i id="bar"></i></div>
<ul id="steps">
  <li><b></b>Reading pixels and layout</li>
  <li><b></b>Checking text edges and fonts</li>
  <li><b></b>Comparing dates and status bar</li>
  <li><b></b>Collecting risk flags</li>
</ul>
</div>

<script>
const $=id=>document.getElementById(id);
const lens=$("lens"),arm=$("arm"),rect=$("revRect"),circ=$("revCirc"),scan=$("scanLine"),bar=$("bar");
const lis=[...document.querySelectorAll("#steps li")];
const reduce=matchMedia("(prefers-reduced-motion: reduce)").matches;
const DUR=7000,HOLD=2600,ROWS=5,X0=95,X1=245,Y0=52,Y1=212;

function target(u){
  const r=Math.min(ROWS-1,Math.floor(u*ROWS)), f=u*ROWS-r, t=r%2?1-f:f;
  return {x:X0+(X1-X0)*t, y:Y0+(Y1-Y0)*(r/(ROWS-1))};
}
function paint(u,reveal,px,py,ang){
  rect.setAttribute("height",reveal);
  circ.setAttribute("cx",px); circ.setAttribute("cy",py);
  scan.setAttribute("y1",reveal); scan.setAttribute("y2",reveal);
  scan.style.opacity=reveal>=250?0:.7;
  lens.setAttribute("transform",`translate(${px} ${py}) rotate(${ang})`);
  const a=ang*Math.PI/180, hx=px+26*Math.cos(a)-26*Math.sin(a), hy=py+26*Math.sin(a)+26*Math.cos(a);
  arm.setAttribute("x1",194);arm.setAttribute("y1",108);arm.setAttribute("x2",hx);arm.setAttribute("y2",hy);
  bar.style.width=(u*100)+"%";
  const idx=u>=1?4:Math.min(3,Math.floor(u*4));
  lis.forEach((li,i)=>li.className=i<idx?"done":(i===idx?"on":""));
}

if(reduce){ paint(1,250,170,120,0); }
else{
  let px=170,py=120,vx=0,vy=0,ang=0,reveal=0,start=performance.now(),last=start;
  function frame(now){
    const dt=Math.min(.033,(now-last)/1000); last=now;
    const el=now-start, u=Math.min(1,el/DUR);
    const tg=u<1?target(u):{x:170,y:122};
    const k=60,c=10;                       // spring + damping = natural lens inertia
    vx+=(k*(tg.x-px)-c*vx)*dt; vy+=(k*(tg.y-py)-c*vy)*dt;
    px+=vx*dt; py+=vy*dt;
    ang+=((Math.max(-25,Math.min(25,vx*.12)))-ang)*Math.min(1,dt*8);
    reveal=u<1?Math.max(reveal,Math.min(250,py+22)):250;
    paint(u,reveal,px,py+Math.sin(now/260)*.8,ang);
    if(el>DUR+HOLD){start=now;reveal=0;}
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}
</script>
"""

def render_empty_state():
    components.html(EMPTY_STATE_HTML, height=470)