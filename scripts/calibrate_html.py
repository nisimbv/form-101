#!/usr/bin/env python3
"""
scripts/calibrate_html.py
--------------------------
Interactive HTML calibration tool for PDF field positions.

Features:
  - Blank official form as background with colored field overlays
  - Hover → tooltip: bindKey, Hebrew section, position in mm
  - Drag fields to correct position → Export corrections as JSON
  - Ctrl+scroll to zoom, drag background to pan, reset zoom button
  - Select field + arrow keys to nudge (0.5mm / Shift=0.1mm)
  - Synchronized scroll in split view
  - Distance measurement tool
  - Hebrew section names throughout

Usage:
    python scripts/calibrate_html.py
"""
import base64, json, os, sys
from pathlib import Path

try:
    import fitz
except ImportError:
    print("Missing: pip install pymupdf"); sys.exit(1)

BASE     = Path(__file__).parent.parent
MAPPING  = BASE / "NEW 3" / "form_101_mapping_1772880459281.json"
REF_PDF  = BASE / "NEW 3" / "101LAST.pdf"
FILL_PDF = BASE / "e2e_result_v2.pdf"
OUT_HTML = BASE / "calibration.html"
JPEG_Q   = 82
DPI      = 180

# ── Hebrew section labels ─────────────────────────────────────────────────────
SECTION_LABELS = {
    "meta":           "מטא — שנת מס",
    "employer":       "א׳ — מעסיק",
    "employee":       "ב׳ — עובד (טקסט)",
    "gender":         "ב׳ — מין",
    "marital":        "ב׳ — מצב משפחתי",
    "has_id":         "ב׳ — תעודת זהות",
    "kibbutz":        "ב׳ — חבר קיבוץ",
    "hmo":            "ב׳ — קופת חולים",
    "income":         "ד׳ — סוג הכנסה",
    "no_other":       "ד׳ — אין הכנסה אחרת",
    "no_training":    "ד׳ — אין קרן השתלמות",
    "no_pension":     "ד׳ — אין פנסיה",
    "credit_request": "ד׳ — בקשת זיכוי",
    "children":       "ג׳ — ילדים",
    "other_income":   "ה׳ — הכנסות אחרות",
    "spouse":         "ו׳ — בן/בת זוג",
    "credits":        "ח׳ — זכאויות",
    "tax_coord":      "ת׳ — תיאום מס",
    "signature":      "י׳ — חתימה",
}

# ── Section colors (hex) ──────────────────────────────────────────────────────
COLORS = {
    "meta":           "#3399ee",
    "employer":       "#22aa44",
    "employee":       "#e87510",
    "gender":         "#9933cc",
    "marital":        "#9933cc",
    "has_id":         "#9933cc",
    "kibbutz":        "#9933cc",
    "hmo":            "#9933cc",
    "income":         "#33bb22",
    "no_other":       "#33bb22",
    "no_training":    "#33bb22",
    "no_pension":     "#33bb22",
    "credit_request": "#33bb22",
    "children":       "#cc1166",
    "other_income":   "#4455cc",
    "spouse":         "#dd4411",
    "credits":        "#00aaaa",
    "tax_coord":      "#bb1111",
    "signature":      "#887700",
}

def color_for(bk): return COLORS.get(bk.split(".")[0], "#777777")
def label_for(bk): return SECTION_LABELS.get(bk.split(".")[0], bk.split(".")[0])

def pdf_to_b64_jpeg(pdf_path, page_idx, dpi=DPI, quality=JPEG_Q):
    doc = fitz.open(pdf_path)
    pix = doc[page_idx].get_pixmap(dpi=dpi)
    jpg = pix.tobytes(output="jpeg", jpg_quality=quality)
    doc.close()
    return base64.b64encode(jpg).decode()


def build_html(mapping, imgs):
    canvas_w = mapping["canvas_dimensions"]["width"]
    canvas_h = mapping["canvas_dimensions"]["height"]
    fields   = mapping["fields"]

    # Unique sections in order of appearance
    seen = {}
    for f in fields:
        sec = f["bindKey"].split(".")[0]
        if sec not in seen:
            seen[sec] = label_for(f["bindKey"])
    sections = list(seen.items())  # [(key, hebrew_label), ...]

    MM = 0.26274  # canvas_px → mm
    js_fields = []
    for f in fields:
        bk  = f.get("bindKey") or f.get("name", "?")
        col = color_for(bk)
        sec = bk.split(".")[0]
        js_fields.append({
            "bk":       bk,
            "type":     f.get("type", "text"),
            "page":     f.get("page", 0),
            "x": f["x"], "y": f["y"], "w": f["w"], "h": f["h"],
            "xmm": round(f["x"]*MM, 2),
            "ymm": round(f["y"]*MM, 2),
            "wmm": round(f["w"]*MM, 2),
            "hmm": round(f["h"]*MM, 2),
            "col": col,
            "sec": sec,
            "sec_label": label_for(bk),
        })

    has_filled = bool(imgs.get("filled"))

    legend_html = "".join(
        '<div class="leg-item" onclick="filterSection(\'{sec}\')" title="לחץ לסינון">'
        '<div class="leg-sw" style="background:{col}"></div>'
        '<span>{lbl}</span></div>'.format(sec=sec, col=COLORS.get(sec, "#777"), lbl=lbl)
        for sec, lbl in sections
    )

    dropdown_opts = "".join(
        f'<option value="{sec}">{lbl}</option>'
        for sec, lbl in sections
    )

    filled_btns = (
        '<button class="btn" onclick="setView(\'filled\')" id="v-filled">PDF ממולא</button>'
        '<button class="btn" onclick="setView(\'both\')"   id="v-both">שניהם</button>'
    ) if has_filled else ""

    filled_panel = (
        '<div class="panel" id="panel-filled" style="display:none">'
        '<div class="panel-label">PDF ממולא</div>'
        '<img class="form-img" id="img-filled"></div>'
    ) if has_filled else ""

    imgs_blank_js  = json.dumps({str(k): v for k, v in imgs["blank"].items()})
    imgs_filled_js = json.dumps({str(k): v for k, v in imgs.get("filled", {}).items()})

    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<title>כלי כיול — טופס 101</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Arial,sans-serif;background:#1a1a2e;color:#eee;direction:rtl;overflow-x:hidden}}

/* ── Toolbar ── */
#tb{{position:sticky;top:0;z-index:200;background:#16213e;border-bottom:2px solid #0f3460;
  padding:6px 12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
#tb h1{{font-size:14px;color:#e94560;white-space:nowrap;margin-left:4px}}
.btn-g{{display:flex;gap:3px}}
.btn{{padding:4px 10px;border:1px solid #0f3460;border-radius:4px;background:#0f3460;
  color:#ccc;cursor:pointer;font-size:12px;transition:background .15s;white-space:nowrap}}
.btn.active{{background:#e94560;color:#fff;border-color:#e94560}}
.btn:hover:not(.active){{background:#1a3a6e}}
.btn.warn{{background:#aa5500;border-color:#aa5500;color:#fff}}
.btn.warn:hover{{background:#cc6600}}
select,input[type=text]{{padding:4px 7px;border-radius:4px;border:1px solid #0f3460;
  background:#0f3460;color:#eee;font-size:12px}}
input[type=text]{{width:140px}}
label{{font-size:12px;display:flex;align-items:center;gap:4px;cursor:pointer}}
#fc{{font-size:11px;color:#888;margin-right:auto;white-space:nowrap}}
#zoom-level{{font-size:11px;color:#aaa;min-width:40px;text-align:center}}

/* ── Viewport + canvas ── */
#viewport{{overflow:auto;padding:16px;display:flex;justify-content:center;
  cursor:crosshair}}
#canvas-wrap{{display:flex;gap:16px;transform-origin:top center;
  transition:transform .1s}}

/* ── Panel ── */
.panel{{position:relative;display:inline-block;border:1px solid #0f3460;
  border-radius:4px;overflow:visible;background:#fff;flex-shrink:0}}
.panel-label{{position:absolute;top:5px;right:7px;z-index:20;
  background:rgba(0,0,0,.65);color:#fff;font-size:11px;padding:2px 8px;
  border-radius:10px;pointer-events:none}}
.form-img{{display:block;width:900px;height:auto;user-select:none;pointer-events:none}}

/* ── Field boxes ── */
.fb{{position:absolute;border:2px solid;cursor:grab;user-select:none;
  transition:box-shadow .1s}}
.fb:hover,.fb.sel{{box-shadow:0 0 0 2px #fff,0 0 0 4px currentColor;z-index:50}}
.fb.cb{{border-radius:50%}}
.fb.moved{{border-style:dashed!important;opacity:1!important}}
.fb.hidden{{display:none!important}}
.fl{{position:absolute;bottom:1px;right:2px;font-size:8.5px;line-height:1;
  white-space:nowrap;overflow:hidden;max-width:98%;font-weight:bold;
  pointer-events:none;text-shadow:0 0 3px rgba(255,255,255,.9)}}

/* ── Tooltip ── */
#tip{{position:fixed;background:rgba(8,8,25,.95);color:#eee;
  border:1px solid #e94560;border-radius:6px;padding:8px 12px;font-size:12px;
  line-height:1.65;pointer-events:none;z-index:9999;display:none;
  max-width:300px;direction:ltr;text-align:left}}
#tip .tbk{{color:#e94560;font-weight:bold;font-size:13px}}
#tip .tsec{{color:#ffcc44;font-size:11px}}

/* ── Corrections panel ── */
#corr-panel{{display:none;position:fixed;bottom:0;left:0;right:0;
  background:#0d1b2a;border-top:2px solid #e94560;z-index:300;
  padding:10px 16px;max-height:40vh;overflow:auto}}
#corr-panel h2{{font-size:13px;color:#e94560;margin-bottom:6px}}
#corr-json{{width:100%;height:120px;background:#0a1520;color:#7fff7f;
  border:1px solid #1a4a30;border-radius:4px;font-family:monospace;font-size:11px;
  padding:6px;resize:vertical}}
.corr-actions{{display:flex;gap:8px;margin-top:6px}}

/* ── Measure line ── */
#measure-line{{position:fixed;pointer-events:none;z-index:8000;display:none}}
#measure-label{{position:fixed;background:#ffcc00;color:#000;
  padding:3px 8px;border-radius:4px;font-size:12px;font-weight:bold;
  pointer-events:none;z-index:8001;display:none}}

/* ── Toast ── */
#toast{{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);
  background:#22aa44;color:#fff;padding:7px 18px;border-radius:20px;
  font-size:12px;opacity:0;transition:opacity .3s;pointer-events:none;z-index:9999}}

/* ── Legend ── */
#legend{{padding:8px 14px 14px;display:flex;flex-wrap:wrap;gap:6px 14px}}
.leg-item{{display:flex;align-items:center;gap:4px;font-size:11px;
  cursor:pointer;padding:2px 4px;border-radius:3px}}
.leg-item:hover{{background:#1a3a6e}}
.leg-sw{{width:12px;height:12px;border-radius:2px;flex-shrink:0}}
</style>
</head>
<body>

<!-- Toolbar -->
<div id="tb">
  <h1>📐 כיול שדות — טופס 101</h1>

  <div class="btn-g">
    <button class="btn active" onclick="setPage(0)" id="p0-btn">דף 1</button>
    <button class="btn"        onclick="setPage(1)" id="p1-btn">דף 2</button>
  </div>

  <div class="btn-g">
    <button class="btn active" onclick="setView('boxes')"  id="v-boxes">ריק + קופסאות</button>
    {filled_btns}
  </div>

  <select id="sec-sel" onchange="applyFilters()">
    <option value="">כל הסעיפים</option>
    {dropdown_opts}
  </select>

  <input type="text" id="search" placeholder="חיפוש bindKey..." oninput="applyFilters()">

  <label><input type="checkbox" id="show-lbl" checked onchange="applyFilters()">תוויות</label>

  <button class="btn" onclick="resetZoom()" title="איפוס זום">🔍 100%</button>
  <span id="zoom-level">100%</span>

  <button class="btn" id="measure-btn" onclick="toggleMeasure()" title="מדידת מרחק">📏 מדוד</button>

  <button class="btn warn" id="export-btn" onclick="showCorrections()" style="display:none">
    📤 ייצא תיקונים
  </button>

  <span id="fc"></span>
</div>

<!-- Main viewport -->
<div id="viewport">
  <div id="canvas-wrap">
    <!-- Blank form panel -->
    <div class="panel" id="panel-blank">
      <div class="panel-label" id="lbl-blank">טופס ריק — דף 1</div>
      <img class="form-img" id="img-blank">
      <div id="overlay"></div>
    </div>
    <!-- Filled panel -->
    {filled_panel}
  </div>
</div>

<!-- Legend -->
<div id="legend">{legend_html}</div>

<!-- Corrections panel -->
<div id="corr-panel">
  <h2>📤 תיקוני מיקומים — שלח לי את ה-JSON הזה</h2>
  <textarea id="corr-json" readonly></textarea>
  <div class="corr-actions">
    <button class="btn" onclick="copyCorrections()">העתק JSON</button>
    <button class="btn" onclick="resetAllMoves()">אפס גרירות</button>
    <button class="btn" onclick="document.getElementById('corr-panel').style.display='none'">סגור</button>
  </div>
</div>

<!-- Tooltip -->
<div id="tip"></div>
<!-- Measure -->
<canvas id="measure-line"></canvas>
<div id="measure-label"></div>
<!-- Toast -->
<div id="toast"></div>

<script>
// ── Constants ─────────────────────────────────────────────────────────────
const CANVAS_W = {canvas_w};
const CANVAS_H = {canvas_h};
const IMG_W    = 900;
const SCALE    = IMG_W / CANVAS_W;  // 1.125
const MM       = 0.26274;           // canvas px → mm

const FIELDS = {json.dumps(js_fields, ensure_ascii=False)};
const IMGS = {{
  blank:  {imgs_blank_js},
  filled: {imgs_filled_js}
}};

// ── State ─────────────────────────────────────────────────────────────────
let page       = 0;
let view       = 'boxes';
let zoomLevel  = 1.0;
let panX       = 0, panY = 0;
let panStart   = null;
let selEl      = null;        // selected field element
let moves      = {{}};         // {{bk: {{dx,dy}} in canvas units}}
let measureMode= false;
let measureP1  = null;

// ── Init ──────────────────────────────────────────────────────────────────
window.addEventListener('load', () => {{ setPage(0); applyZoom(); }});

// ── Page ──────────────────────────────────────────────────────────────────
function setPage(pg) {{
  page = pg;
  document.getElementById('p0-btn').classList.toggle('active', pg===0);
  document.getElementById('p1-btn').classList.toggle('active', pg===1);
  loadImages();
  buildOverlay();
  applyFilters();
}}

function loadImages() {{
  const bi = IMGS.blank[page];
  document.getElementById('img-blank').src = bi ? 'data:image/jpeg;base64,'+bi : '';
  document.getElementById('lbl-blank').textContent = 'טופס ריק — דף '+(page+1);
  const fi = IMGS.filled[page];
  const pf = document.getElementById('img-filled');
  if (pf) pf.src = fi ? 'data:image/jpeg;base64,'+fi : '';
}}

// ── View ──────────────────────────────────────────────────────────────────
function setView(v) {{
  view = v;
  ['boxes','filled','both'].forEach(x=>{{
    const e=document.getElementById('v-'+x); if(e) e.classList.toggle('active',x===v);
  }});
  const pb = document.getElementById('panel-blank');
  const pf = document.getElementById('panel-filled');
  const ov = document.getElementById('overlay');
  if (v==='boxes')  {{ pb.style.display=''; if(pf)pf.style.display='none'; ov.style.visibility=''; }}
  else if(v==='filled') {{ pb.style.display='none'; if(pf)pf.style.display=''; }}
  else /* both */   {{ pb.style.display=''; if(pf)pf.style.display=''; ov.style.visibility=''; }}
}}

// ── Overlay ───────────────────────────────────────────────────────────────
function buildOverlay() {{
  selEl = null;
  const wrap = document.getElementById('overlay');
  wrap.innerHTML = '';

  FIELDS.filter(f=>f.page===page).forEach(f=>{{
    const moved = moves[f.bk];
    const cx = f.x + (moved ? moved.dx : 0);
    const cy = f.y + (moved ? moved.dy : 0);

    const div = document.createElement('div');
    div.className = 'fb' + (f.type==='checkbox'?' cb':'') + (moved?' moved':'');
    div.dataset.bk  = f.bk;
    div.dataset.sec = f.sec;
    div.dataset.origx = f.x;
    div.dataset.origy = f.y;
    div.dataset.idx   = FIELDS.indexOf(f);

    const l=cx*SCALE, t=cy*SCALE, w=f.w*SCALE, h=f.h*SCALE;
    div.style.cssText = `left:${{l}}px;top:${{t}}px;width:${{w}}px;height:${{h}}px;`+
      `border-color:${{f.col}};background-color:${{f.col}}28;color:${{f.col}};`;

    const lbl = document.createElement('span');
    lbl.className = 'fl';
    lbl.textContent = f.bk.split('.').pop();
    div.appendChild(lbl);

    // Hover tooltip
    div.addEventListener('mouseenter', e=>showTip(e,f,cx,cy));
    div.addEventListener('mousemove',  moveTip);
    div.addEventListener('mouseleave', hideTip);

    // Click = select
    div.addEventListener('mousedown', e => {{
      if (measureMode) {{ handleMeasureClick(e); return; }}
      e.stopPropagation();
      selectField(div);
    }});

    // Drag
    makeDraggable(div, f);

    wrap.appendChild(div);
  }});
  applyFilters();
}}

// ── Selection ──────────────────────────────────────────────────────────────
function selectField(el) {{
  if (selEl) selEl.classList.remove('sel');
  selEl = el;
  el.classList.add('sel');
}}

// ── Drag ──────────────────────────────────────────────────────────────────
function makeDraggable(el, f) {{
  let startX, startY, startL, startT;
  el.addEventListener('mousedown', e => {{
    if (measureMode) return;
    e.preventDefault();
    startX = e.clientX; startY = e.clientY;
    startL = parseFloat(el.style.left);
    startT = parseFloat(el.style.top);

    function onMove(e) {{
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      el.style.left = (startL+dx) + 'px';
      el.style.top  = (startT+dy) + 'px';
    }}
    function onUp(e) {{
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup',   onUp);
      const dx_px = parseFloat(el.style.left) - startL;
      const dy_px = parseFloat(el.style.top)  - startT;
      if (Math.abs(dx_px)+Math.abs(dy_px) < 2) return; // was a click, not drag
      // Convert px delta → canvas units → store
      const dx_canvas = dx_px / SCALE;
      const dy_canvas = dy_px / SCALE;
      const prev = moves[f.bk] || {{dx:0,dy:0}};
      moves[f.bk] = {{dx: prev.dx+dx_canvas, dy: prev.dy+dy_canvas}};
      el.classList.add('moved');
      el.dataset.origx = f.x;
      el.dataset.origy = f.y;
      document.getElementById('export-btn').style.display = '';
      updateExportPanel();
    }}
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup',   onUp);
  }});
}}

// ── Keyboard nudge ─────────────────────────────────────────────────────────
document.addEventListener('keydown', e => {{
  if (!selEl || document.activeElement.tagName==='INPUT'
             || document.activeElement.tagName==='TEXTAREA') return;
  const step = (e.shiftKey ? 0.1 : 0.5) / MM; // mm → canvas units
  let dx=0, dy=0;
  if (e.key==='ArrowLeft')  {{ dx= step; e.preventDefault(); }}
  if (e.key==='ArrowRight') {{ dx=-step; e.preventDefault(); }}
  if (e.key==='ArrowUp')    {{ dy=-step; e.preventDefault(); }}
  if (e.key==='ArrowDown')  {{ dy= step; e.preventDefault(); }}
  if (!dx && !dy) return;

  const bk   = selEl.dataset.bk;
  const fidx = parseInt(selEl.dataset.idx);
  const f    = FIELDS[fidx];
  const prev = moves[bk] || {{dx:0,dy:0}};
  moves[bk]  = {{dx:prev.dx+dx, dy:prev.dy+dy}};

  selEl.style.left = (parseFloat(selEl.style.left) + dx*SCALE) + 'px';
  selEl.style.top  = (parseFloat(selEl.style.top)  + dy*SCALE) + 'px';
  selEl.classList.add('moved');
  document.getElementById('export-btn').style.display='';
  updateExportPanel();
}});

// ── Export corrections ────────────────────────────────────────────────────
function buildCorrectionsJSON() {{
  const out = {{}};
  for (const [bk, d] of Object.entries(moves)) {{
    out[bk] = {{
      dx_mm: Math.round(d.dx*MM*100)/100,
      dy_mm: Math.round(d.dy*MM*100)/100,
    }};
  }}
  return JSON.stringify(out, null, 2);
}}
function updateExportPanel() {{
  document.getElementById('corr-json').value = buildCorrectionsJSON();
}}
function showCorrections() {{
  updateExportPanel();
  document.getElementById('corr-panel').style.display='block';
}}
function copyCorrections() {{
  navigator.clipboard.writeText(buildCorrectionsJSON())
    .then(()=>toast('✓ JSON הועתק!'));
}}
function resetAllMoves() {{
  moves = {{}};
  document.getElementById('export-btn').style.display='none';
  buildOverlay();
  document.getElementById('corr-panel').style.display='none';
}}

// ── Zoom / Pan ────────────────────────────────────────────────────────────
function applyZoom() {{
  const w = document.getElementById('canvas-wrap');
  w.style.transform = `scale(${{zoomLevel}})`;
  document.getElementById('zoom-level').textContent = Math.round(zoomLevel*100)+'%';
}}
function resetZoom() {{
  zoomLevel=1; panX=0; panY=0; applyZoom();
}}
document.getElementById('viewport').addEventListener('wheel', e => {{
  if (!e.ctrlKey) return;
  e.preventDefault();
  const delta = e.deltaY > 0 ? -0.1 : 0.1;
  zoomLevel = Math.max(0.3, Math.min(5, zoomLevel+delta));
  applyZoom();
}}, {{passive:false}});

// Pan on blank background
document.getElementById('viewport').addEventListener('mousedown', e => {{
  if (e.target.id!=='viewport' && e.target.id!=='canvas-wrap') return;
  if (measureMode) return;
  panStart = {{x:e.clientX, y:e.clientY,
               sx:document.getElementById('viewport').scrollLeft,
               sy:document.getElementById('viewport').scrollTop}};
  document.getElementById('viewport').style.cursor='grabbing';
}});
document.addEventListener('mousemove', e => {{
  if (!panStart) return;
  const dx = e.clientX-panStart.x, dy=e.clientY-panStart.y;
  document.getElementById('viewport').scrollLeft = panStart.sx-dx;
  document.getElementById('viewport').scrollTop  = panStart.sy-dy;
}});
document.addEventListener('mouseup', ()=>{{
  panStart=null;
  document.getElementById('viewport').style.cursor='';
}});

// ── Sync scroll ───────────────────────────────────────────────────────────
(function(){{
  const pb = document.getElementById('panel-blank');
  const pf = document.getElementById('panel-filled');
  if (!pf) return;
  let syncing=false;
  function sync(src,dst){{
    src.addEventListener('scroll',()=>{{
      if(syncing)return; syncing=true;
      dst.scrollTop=src.scrollTop; dst.scrollLeft=src.scrollLeft;
      setTimeout(()=>syncing=false,50);
    }});
  }}
  sync(pb,pf); sync(pf,pb);
}})();

// ── Filters ───────────────────────────────────────────────────────────────
function filterSection(sec) {{
  document.getElementById('sec-sel').value = sec;
  applyFilters();
}}
function applyFilters() {{
  const showL = document.getElementById('show-lbl').checked;
  const sec   = document.getElementById('sec-sel').value;
  const q     = document.getElementById('search').value.toLowerCase().trim();
  let vis=0;
  document.querySelectorAll('.fb').forEach(el=>{{
    const bk   = el.dataset.bk;
    const esec = el.dataset.sec;
    const show = (!sec||esec===sec) && (!q||bk.toLowerCase().includes(q));
    el.classList.toggle('hidden',!show);
    const lbl=el.querySelector('.fl');
    if(lbl) lbl.style.display=(showL&&show)?'':'none';
    if(show) vis++;
  }});
  document.getElementById('fc').textContent=vis+' שדות';
}}

// ── Tooltip ───────────────────────────────────────────────────────────────
function showTip(e,f,cx,cy){{
  const xmm=(cx*MM).toFixed(1), ymm=(cy*MM).toFixed(1);
  const wmm=(f.w*MM).toFixed(1), hmm=(f.h*MM).toFixed(1);
  const moved=moves[f.bk];
  const movedStr=moved?`<div style="color:#ffcc44">⚡ הוזזה: Δx=${{(moved.dx*MM).toFixed(1)}}mm Δy=${{(moved.dy*MM).toFixed(1)}}mm</div>`:'';
  document.getElementById('tip').innerHTML=`
    <div class="tbk">${{f.bk}}</div>
    <div class="tsec">${{f.sec_label}}</div>
    <hr style="border-color:#333;margin:4px 0">
    <div>x:<b>${{xmm}}mm</b> y:<b>${{ymm}}mm</b></div>
    <div>w:<b>${{wmm}}mm</b> h:<b>${{hmm}}mm</b></div>
    <div style="color:#aaa;font-size:10px">${{f.type}}</div>
    ${{movedStr}}
    <div style="color:#666;font-size:10px;margin-top:2px">גרור לכיול · חצים לנודג׳</div>`;
  document.getElementById('tip').style.display='block';
  moveTip(e);
}}
function moveTip(e){{
  const t=document.getElementById('tip');
  let x=e.clientX+14, y=e.clientY+14;
  if(x+310>window.innerWidth) x=e.clientX-320;
  if(y+130>window.innerHeight) y=e.clientY-130;
  t.style.left=x+'px'; t.style.top=y+'px';
}}
function hideTip(){{ document.getElementById('tip').style.display='none'; }}

// ── Measure ───────────────────────────────────────────────────────────────
function toggleMeasure(){{
  measureMode=!measureMode;
  measureP1=null;
  document.getElementById('measure-btn').classList.toggle('active',measureMode);
  document.getElementById('measure-label').style.display='none';
  if(!measureMode){{ document.getElementById('measure-line').style.display='none'; }}
  document.getElementById('viewport').style.cursor=measureMode?'crosshair':'';
  if(measureMode) toast('לחץ נקודה ראשונה...');
}}
function handleMeasureClick(e){{
  const vp=document.getElementById('viewport');
  const rect=vp.getBoundingClientRect();
  const scrollX=vp.scrollLeft, scrollY=vp.scrollTop;
  // Click position in canvas-space (corrected for zoom+scroll)
  const px=((e.clientX-rect.left+scrollX)/zoomLevel);
  const py=((e.clientY-rect.top +scrollY)/zoomLevel);
  if(!measureP1){{
    measureP1={{x:px,y:py,cx:e.clientX,cy:e.clientY}};
    toast('לחץ נקודה שנייה...');
  }} else {{
    const dx_px=px-measureP1.x, dy_px=py-measureP1.y;
    const dx_mm=(dx_px/SCALE*MM).toFixed(1);
    const dy_mm=(dy_px/SCALE*MM).toFixed(1);
    const dist=Math.sqrt(dx_px*dx_px+dy_px*dy_px);
    const dist_mm=(dist/SCALE*MM).toFixed(1);
    const lbl=document.getElementById('measure-label');
    lbl.textContent=`↔ ${{dist_mm}}mm (dx=${{dx_mm}} dy=${{dy_mm}})`;
    lbl.style.left=(e.clientX+10)+'px';
    lbl.style.top=(e.clientY-30)+'px';
    lbl.style.display='block';
    measureP1=null;
    setTimeout(()=>{{lbl.style.display='none';toggleMeasure();}},4000);
  }}
}}

// ── Toast ──────────────────────────────────────────────────────────────────
function toast(msg){{
  const t=document.getElementById('toast');
  t.textContent=msg; t.style.opacity='1';
  setTimeout(()=>t.style.opacity='0',2000);
}}

// ── Keyboard shortcuts help ────────────────────────────────────────────────
// Ctrl+Z = undo last move
document.addEventListener('keydown', e=>{{
  if ((e.ctrlKey||e.metaKey) && e.key==='z') {{
    const keys=Object.keys(moves);
    if(keys.length){{
      delete moves[keys[keys.length-1]];
      buildOverlay();
      if(!Object.keys(moves).length) document.getElementById('export-btn').style.display='none';
      toast('↩ ביטול גרירה אחרונה');
    }}
  }}
}});
</script>
</body>
</html>"""


def main():
    print("=" * 60)
    print("  Interactive HTML Calibration Tool  v2")
    print("=" * 60)

    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    print(f"\nFields: {len(mapping['fields'])}  |  canvas: {mapping['canvas_dimensions']}")

    print(f"\nRendering blank form at {DPI} DPI...")
    imgs = {"blank": {}, "filled": {}}
    for pg in [0, 1]:
        imgs["blank"][pg] = pdf_to_b64_jpeg(str(REF_PDF), pg)
        print(f"  page {pg+1}: {len(imgs['blank'][pg])*3//4//1024} KB")

    if FILL_PDF.exists():
        print(f"\nRendering filled PDF ({FILL_PDF.name})...")
        for pg in [0, 1]:
            imgs["filled"][pg] = pdf_to_b64_jpeg(str(FILL_PDF), pg)
            print(f"  page {pg+1}: {len(imgs['filled'][pg])*3//4//1024} KB")

    print("\nBuilding HTML...")
    html = build_html(mapping, imgs)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"  ✅ {OUT_HTML.name}  ({OUT_HTML.stat().st_size//1024} KB)")

    print("\nOpening in browser...")
    os.startfile(str(OUT_HTML))
    print("\n── מקשים ─────────────────────────────────────────────────")
    print("  גרור שדה       → מזיז לכיול")
    print("  חצים           → נודג׳ 0.5mm (Shift=0.1mm)")
    print("  Ctrl+Z         → ביטול גרירה אחרונה")
    print("  Ctrl+scroll    → zoom")
    print("  📤 ייצא תיקונים → JSON לשליחה")


if __name__ == "__main__":
    main()
