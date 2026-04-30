import streamlit as st
import zipfile
import io
import math
import re
from collections import Counter
from datetime import datetime

st.set_page_config(
    page_title="PPTX Brand Checker",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Amber theme CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
:root {
    --amber-50:  #fffbeb;
    --amber-100: #fef3c7;
    --amber-200: #fde68a;
    --amber-400: #fbbf24;
    --amber-600: #d97706;
    --amber-800: #92400e;
    --orange:    #ED7D31;
}
.stApp { background-color: var(--amber-50); }
[data-testid="stSidebar"] {
    background-color: var(--amber-100) !important;
    border-right: 1px solid var(--amber-200);
}
[data-testid="stSidebar"] label { color: var(--amber-800) !important; }
h1 { color: var(--amber-800) !important; }
h2, h3 { color: #78350f !important; }
[data-testid="metric-container"] {
    background: var(--amber-100);
    border: 1px solid var(--amber-200);
    border-radius: 10px;
    padding: 0.75rem 1rem;
}
[data-testid="stExpander"] {
    border: 1px solid var(--amber-200) !important;
    border-radius: 8px !important;
    background: white !important;
}
.stButton > button {
    background-color: var(--orange) !important;
    color: white !important; border: none !important;
    border-radius: 8px !important; font-weight: 600 !important;
}
.stButton > button:hover { background-color: #C55A11 !important; }
.stDownloadButton > button {
    background-color: var(--amber-800) !important;
    color: white !important; border: none !important; border-radius: 8px !important;
}
[data-testid="stFileUploadDropzone"] {
    background-color: var(--amber-50) !important;
    border: 2px dashed var(--amber-400) !important; border-radius: 10px !important;
}
.stProgress > div > div { background-color: var(--orange) !important; }
.stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid var(--amber-200); }
.stTabs [aria-selected="true"] {
    color: var(--orange) !important;
    border-bottom: 2px solid var(--orange) !important;
}
hr { border-color: var(--amber-200) !important; }

/* Swatches */
.swatch-row { display:flex; gap:8px; flex-wrap:wrap; margin:6px 0; }
.swatch {
    display:inline-flex; align-items:center; gap:6px;
    background:#fff; border:1px solid #fde68a;
    border-radius:20px; padding:3px 10px; font-size:12px;
}
.swatch-dot { width:14px; height:14px; border-radius:50%; border:1px solid #ccc; flex-shrink:0; }

/* Role table */
.role-table { width:100%; border-collapse:collapse; font-size:13px; }
.role-table th {
    background:var(--amber-100); padding:6px 10px; text-align:left;
    border-bottom:2px solid var(--amber-200); color:#78350f;
}
.role-table td { padding:6px 10px; border-bottom:1px solid var(--amber-100); vertical-align:top; }
.role-table tr:hover td { background:var(--amber-50); }

/* Role badges */
.badge { display:inline-block; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:600; white-space:nowrap; }
.badge-title     { background:#fde68a; color:#78350f; }
.badge-header    { background:#fed7aa; color:#9a3412; }
.badge-subheader { background:#fef3c7; color:#92400e; }
.badge-body      { background:#f3f4f6; color:#374151; }

/* Issue cards */
.issue-card {
    border-radius: 8px;
    padding: 10px 14px;
    margin: 6px 0;
    font-size: 13px;
    line-height: 1.5;
}
.issue-card.err  { background:#fef2f2; border-left:4px solid #ef4444; }
.issue-card.warn { background:#fffbeb; border-left:4px solid #f59e0b; }
.issue-card .issue-title { font-weight:600; margin-bottom:4px; }
.issue-card .issue-title.err  { color:#991b1b; }
.issue-card .issue-title.warn { color:#78350f; }
.snippet {
    display:inline-block;
    background:#1e1e1e; color:#d4d4d4;
    font-family:monospace; font-size:11px;
    border-radius:4px; padding:2px 8px;
    margin-top:4px; max-width:100%;
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.color-chip-row { display:flex; gap:6px; flex-wrap:wrap; margin-top:6px; }
.color-chip {
    display:inline-flex; align-items:center; gap:5px;
    background:#fff; border:1px solid #e5e7eb;
    border-radius:20px; padding:2px 8px; font-size:11px;
    font-family:monospace;
}
.chip-dot { width:12px; height:12px; border-radius:50%; border:1px solid #ccc; flex-shrink:0; }
.detail-meta {
    font-size:11px; color:#6b7280; margin-top:3px;
}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
ORANGE_PALETTE = {
    "#ED7D31": "Orange, Accent 1",
    "#FBE5D6": "Lighter 80%",
    "#F8CBAD": "Lighter 60%",
    "#F4B183": "Lighter 40%",
    "#C55A11": "Darker 25%",
    "#843C0B": "Darker 50%",
    "#303C41": "Dark Slate",
    "#F5F5F6": "Light Grey",
}
DEFAULT_BRAND_COLORS = list(ORANGE_PALETTE.keys())

ROLE_DEFAULTS = {
    "slide_title": {"font": "Plus Jakarta Sans", "weight": "Medium", "size": 40},
    "header":      {"font": "Plus Jakarta Sans", "weight": "Normal", "size": 16},
    "subheader":   {"font": "Plus Jakarta Sans", "weight": "Normal", "size": 12},
    "body":        {"font": "Plus Jakarta Sans", "weight": "Light",  "size": 10},
}
ROLE_LABELS = {
    "slide_title": "Slide Title",
    "header":      "Header",
    "subheader":   "Subheader",
    "body":        "Body Text",
}

SNIPPET_MAX = 60  # characters before truncation

# All accepted variants of the brand font family (lowercase for matching)
ACCEPTED_FONTS = {
    "plus jakarta sans",
    "plus jakarta sans medium",
    "plus jakarta sans normal",
    "plus jakarta sans light",
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def trunc(text, n=SNIPPET_MAX):
    text = " ".join(text.split())  # collapse whitespace
    return text[:n] + "…" if len(text) > n else text

def extract_text(xml_fragment):
    """Pull plain text from an XML shape or run fragment."""
    return re.sub(r"<[^>]+>", "", xml_fragment).strip()

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_lab(r, g, b):
    R, G, B = r/255, g/255, b/255
    def lin(c): return ((c+0.055)/1.055)**2.4 if c > 0.04045 else c/12.92
    R, G, B = lin(R), lin(G), lin(B)
    X = (R*0.4124 + G*0.3576 + B*0.1805)/0.95047
    Y = (R*0.2126 + G*0.7152 + B*0.0722)/1.00000
    Z = (R*0.0193 + G*0.1192 + B*0.9505)/1.08883
    def f(t): return t**(1/3) if t > 0.008856 else 7.787*t+16/116
    return 116*f(Y)-16, 500*(f(X)-f(Y)), 200*(f(Y)-f(Z))

def delta_e(h1, h2):
    l1,a1,b1 = rgb_to_lab(*hex_to_rgb(h1))
    l2,a2,b2 = rgb_to_lab(*hex_to_rgb(h2))
    return math.sqrt((l1-l2)**2+(a1-a2)**2+(b1-b2)**2)

def is_brand_color(hex_val, brand_colors, tolerance):
    return any(delta_e(hex_val, bc) <= tolerance for bc in brand_colors)

def infer_role(size_pt, is_title_ph, cfg):
    if is_title_ph:
        return "slide_title", "explicit"
    if not cfg.get("smart_roles"):
        return "body", "explicit"
    ts = cfg["role_sizes"]["slide_title"]
    hs = cfg["role_sizes"]["header"]
    ss = cfg["role_sizes"]["subheader"]
    if size_pt >= ts * 0.85:   return "slide_title", "heuristic"
    elif size_pt >= hs * 0.85: return "header",      "heuristic"
    elif size_pt >= ss * 0.85: return "subheader",   "heuristic"
    else:                       return "body",        "heuristic"


# ── PPTX parser ───────────────────────────────────────────────────────────────
def parse_pptx(file_bytes):
    zf = zipfile.ZipFile(io.BytesIO(file_bytes))
    slide_files = sorted(
        [n for n in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)],
        key=lambda x: int(re.search(r"\d+", x).group())
    )
    slides_xml = [zf.read(n).decode("utf-8") for n in slide_files]
    pres_w, pres_h = 12192000, 6858000
    try:
        pres_xml = zf.read("ppt/presentation.xml").decode("utf-8")
        wm = re.search(r'cx="(\d+)"', pres_xml)
        hm = re.search(r'cy="(\d+)"', pres_xml)
        if wm: pres_w = int(wm.group(1))
        if hm: pres_h = int(hm.group(1))
    except Exception:
        pass
    return slides_xml, pres_w, pres_h


# ── Core checker ─────────────────────────────────────────────────────────────
def check_slide(xml, slide_num, cfg):
    """
    Returns dict with:
      issues: list of {type, message, snippet, detail, colors}
      role_findings: list of {role, method, font, size, snippet}
      sig: layout signature string
    """
    issues = []
    role_findings = []
    all_colors_with_ctx = []   # list of (hex, snippet)
    has_content = False
    total_bullets = 0
    shapes = re.findall(r"<p:sp[\s\S]*?</p:sp>", xml)

    for sp in shapes:
        is_title_ph = bool(re.search(r'ph type="title"|ph type="ctrTitle"', sp))
        shape_text  = trunc(extract_text(sp))

        raw_text = extract_text(sp)
        if raw_text:
            has_content = True

        # Count bullets
        paras = re.findall(r"<a:p>([\s\S]*?)</a:p>", sp)
        bullet_paras = [p for p in paras if "<a:buChar" in p or "<a:buAutoNum" in p]
        total_bullets += len(bullet_paras)

        # Collect all srgbClr in this shape for color context
        shape_colors = re.findall(r'<a:srgbClr val="([0-9A-Fa-f]{6})"', sp)

        # Track checked combos to avoid duplicate issues per shape
        checked_font_issues = set()
        checked_size_issues = set()

        for rpr_m in re.finditer(r"<a:rPr([^>]*)>([\s\S]*?)</a:rPr>", sp):
            attrs, inner = rpr_m.group(1), rpr_m.group(2)

            font_name = None
            lm = re.search(r'<a:latin typeface="([^"]+)"', inner)
            if lm and lm.group(1) not in ("+mj-lt", "+mn-lt"):
                font_name = lm.group(1)

            size_pt = None
            sm = re.search(r'sz="(\d+)"', attrs)
            if sm:
                size_pt = int(sm.group(1)) / 100

            run_color = None
            cm = re.search(r'<a:srgbClr val="([0-9A-Fa-f]{6})"', inner)
            if cm:
                run_color = "#" + cm.group(1).upper()
                all_colors_with_ctx.append((run_color, shape_text))

            if size_pt or font_name:
                role, method = infer_role(size_pt or 0, is_title_ph, cfg)
                role_findings.append({
                    "role": role, "method": method,
                    "font": font_name, "size": size_pt,
                    "snippet": shape_text,
                })

                spec     = cfg["role_specs"].get(role, {})
                exp_font = spec.get("font", "").lower()
                exp_size = spec.get("size")

                # Font check — accept any variant in ACCEPTED_FONTS
                if cfg["chk_fonts"] and font_name:
                    fn_lower = font_name.lower()
                    font_ok = any(fn_lower == af or fn_lower.startswith(af) for af in ACCEPTED_FONTS)
                    if not font_ok:
                        key = (role, font_name)
                        if key not in checked_font_issues:
                            checked_font_issues.add(key)
                            accepted_list = ", ".join(sorted(ACCEPTED_FONTS))
                            issues.append({
                                "type":    "error",
                                "message": f"{ROLE_LABELS[role]}: wrong font",
                                "detail":  f"Found '{font_name}' — accepted: {accepted_list}",
                                "snippet": shape_text,
                                "colors":  [],
                            })

                # Size check
                if cfg["chk_sizes"] and size_pt and exp_size:
                    diff = abs(size_pt - exp_size)
                    if diff > cfg.get("size_tolerance", 2):
                        key = (role, size_pt)
                        if key not in checked_size_issues:
                            checked_size_issues.add(key)
                            sev = "error" if diff > 4 else "warning"
                            issues.append({
                                "type":    sev,
                                "message": f"{ROLE_LABELS[role]}: wrong font size",
                                "detail":  f"Found {size_pt}pt, expected {exp_size}pt",
                                "snippet": shape_text,
                                "colors":  [],
                            })

        # Collect shape-level fill/outline colors
        for fc in shape_colors:
            all_colors_with_ctx.append(("#" + fc.upper(), shape_text))

    # Background color
    bg = re.search(r"<p:bg>[\s\S]*?<a:srgbClr val=\"([0-9A-Fa-f]{6})\"", xml)
    if bg:
        all_colors_with_ctx.append(("#" + bg.group(1).upper(), "slide background"))

    # ── Whole-slide checks ──────────────────────────────────────────────────
    if cfg["chk_empty"] and not has_content:
        issues.append({
            "type":    "error",
            "message": "Empty slide — no text content",
            "detail":  "This slide contains no readable text in any shape.",
            "snippet": "",
            "colors":  [],
        })

    # Color check — group off-brand colors with their context snippets
    if cfg["chk_colors"] and cfg["brand_colors"]:
        off_brand = {}  # hex -> list of snippets
        for color_hex, ctx in all_colors_with_ctx:
            if not is_brand_color(color_hex, cfg["brand_colors"], cfg["tolerance"]):
                off_brand.setdefault(color_hex, [])
                if ctx not in off_brand[color_hex]:
                    off_brand[color_hex].append(ctx)
        if off_brand:
            # one issue per off-brand color, showing where it appears
            for color_hex, contexts in list(off_brand.items())[:6]:
                ctx_str = " / ".join(c for c in contexts[:2] if c)
                issues.append({
                    "type":    "warning",
                    "message": "Off-brand color used",
                    "detail":  f"In: {ctx_str}" if ctx_str else "Found in slide elements",
                    "snippet": ctx_str,
                    "colors":  [color_hex],
                })

    # Bullet check — show first bullet text as snippet
    if cfg["chk_bullets"] and total_bullets > 7:
        # find first shape with bullets to get snippet
        bullet_snippet = ""
        for sp in shapes:
            paras = re.findall(r"<a:p>([\s\S]*?)</a:p>", sp)
            if any("<a:buChar" in p or "<a:buAutoNum" in p for p in paras):
                bullet_snippet = trunc(extract_text(sp))
                break
        issues.append({
            "type":    "warning",
            "message": f"Excessive bullet points ({total_bullets} total)",
            "detail":  "Consider replacing some bullets with visuals or concise prose.",
            "snippet": bullet_snippet,
            "colors":  [],
        })

    sig = f"{len(shapes)}-{sorted([rf['size'] for rf in role_findings if rf['size']])}"
    return {"num": slide_num, "issues": issues, "role_findings": role_findings, "sig": sig}


def run_checks(slides_xml, pres_w, pres_h, cfg):
    results = []
    bar = st.progress(0, text="Analysing slides…")
    for i, xml in enumerate(slides_xml):
        results.append(check_slide(xml, i+1, cfg))
        bar.progress((i+1)/len(slides_xml), text=f"Slide {i+1} / {len(slides_xml)}")

    if cfg["chk_layout"] and len(slides_xml) > 2:
        sigs = [r["sig"] for r in results]
        most_common, count = Counter(sigs).most_common(1)[0]
        if count > len(slides_xml) * 0.4:
            for r in results:
                if r["sig"] != most_common:
                    r["issues"].append({
                        "type":    "warning",
                        "message": "Layout differs from majority of slides",
                        "detail":  "This slide's structure (number of shapes / sizes) is unusual.",
                        "snippet": "",
                        "colors":  [],
                    })

    if cfg["slide_size"] != "any":
        exp_w = 12192000 if cfg["slide_size"] == "widescreen" else 9144000
        if abs(pres_w - exp_w) > 50000 or abs(pres_h - 6858000) > 50000:
            results[0]["issues"].insert(0, {
                "type":    "warning",
                "message": "Unexpected slide dimensions",
                "detail":  f"Deck is {pres_w/914400:.2f}×{pres_h/914400:.2f} in, expected {cfg['slide_size']}.",
                "snippet": "",
                "colors":  [],
            })
    bar.empty()
    return results


# ── Issue card renderer ───────────────────────────────────────────────────────
def render_issue_card(issue):
    t     = issue["type"]
    cls   = "err" if t == "error" else "warn"
    icon  = "✖" if t == "error" else "⚠"
    snip  = issue.get("snippet", "")
    detail = issue.get("detail", "")
    colors = issue.get("colors", [])

    snippet_html = ""
    if snip:
        escaped = snip.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        snippet_html = f'<div class="snippet">"{escaped}"</div>'

    color_html = ""
    if colors:
        chips = "".join(
            f'<div class="color-chip">'
            f'<div class="chip-dot" style="background:{c}"></div>{c}'
            f'</div>'
            for c in colors
        )
        color_html = f'<div class="color-chip-row">{chips}</div>'

    detail_html = f'<div class="detail-meta">{detail}</div>' if detail else ""

    return f"""
    <div class="issue-card {cls}">
      <div class="issue-title {cls}">{icon} {issue['message']}</div>
      {detail_html}
      {snippet_html}
      {color_html}
    </div>"""


# ── HTML report ───────────────────────────────────────────────────────────────
def build_html_report(results, filename, score, cfg):
    score_color = "#065f46" if score >= 80 else "#92400e" if score >= 60 else "#9b1c1c"
    total  = len(results)
    errs   = sum(1 for r in results for i in r["issues"] if i["type"]=="error")
    warns  = sum(1 for r in results for i in r["issues"] if i["type"]=="warning")

    swatches = "".join(
        f"<span style='display:inline-flex;align-items:center;gap:5px;"
        f"background:#fff;border:1px solid #fde68a;border-radius:20px;"
        f"padding:3px 9px;font-size:12px;margin:3px'>"
        f"<span style='width:12px;height:12px;border-radius:50%;"
        f"background:{h};border:1px solid #ccc;flex-shrink:0'></span>"
        f"{ORANGE_PALETTE.get(h,h)}</span>"
        for h in cfg["brand_colors"]
    )

    slide_rows = ""
    for r in results:
        if not r["issues"]:
            slide_rows += f"""
            <div class='slide-block pass'>
              <div class='slide-num'>✔ Slide {r['num']}</div>
              <div class='pass-label'>No issues</div>
            </div>"""
        else:
            issue_html = ""
            for iss in r["issues"]:
                t   = iss["type"]
                cls = "err" if t=="error" else "warn"
                icon= "✖" if t=="error" else "⚠"
                snip = iss.get("snippet","")
                det  = iss.get("detail","")
                cols = iss.get("colors",[])
                snip_html = (
                    f"<div style='font-family:monospace;font-size:11px;"
                    f"background:#1e1e1e;color:#d4d4d4;border-radius:4px;"
                    f"padding:2px 8px;display:inline-block;margin-top:4px;"
                    f"max-width:100%;overflow:hidden;text-overflow:ellipsis;"
                    f"white-space:nowrap'>\"{snip}\"</div>"
                    if snip else ""
                )
                chip_html = "".join(
                    f"<span style='display:inline-flex;align-items:center;gap:4px;"
                    f"background:#fff;border:1px solid #e5e7eb;border-radius:20px;"
                    f"padding:2px 7px;font-size:11px;font-family:monospace;margin:2px'>"
                    f"<span style='width:10px;height:10px;border-radius:50%;"
                    f"background:{c};border:1px solid #ccc'></span>{c}</span>"
                    for c in cols
                )
                issue_html += f"""
                <div style='border-left:4px solid {"#ef4444" if cls=="err" else "#f59e0b"};
                     background:{"#fef2f2" if cls=="err" else "#fffbeb"};
                     border-radius:6px;padding:8px 12px;margin:5px 0;font-size:13px'>
                  <strong style='color:{"#991b1b" if cls=="err" else "#78350f"}'>{icon} {iss["message"]}</strong>
                  {"<div style='color:#6b7280;font-size:11px;margin-top:2px'>"+det+"</div>" if det else ""}
                  {snip_html}
                  {"<div style='margin-top:4px'>"+chip_html+"</div>" if chip_html else ""}
                </div>"""
            slide_rows += f"""
            <div class='slide-block'>
              <div class='slide-num'>Slide {r['num']}</div>
              {issue_html}
            </div>"""

    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>Brand Report — {filename}</title>
<style>
  body{{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;
        padding:0 20px;background:#fffbeb;color:#111}}
  h1{{font-size:22px;color:#92400e}}
  h2{{font-size:14px;color:#777;margin-bottom:20px}}
  .score{{font-size:48px;font-weight:700;color:{score_color}}}
  .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:20px 0}}
  .metric{{background:#fef3c7;border-radius:10px;padding:14px;text-align:center}}
  .metric-val{{font-size:28px;font-weight:700}}
  .metric-lbl{{font-size:12px;color:#777;margin-top:4px}}
  .palette{{margin:16px 0}}
  .slide-block{{background:white;border:1px solid #fde68a;border-radius:10px;
                padding:14px 18px;margin:10px 0}}
  .slide-block.pass{{border-color:#bbf7d0}}
  .slide-num{{font-weight:700;font-size:14px;color:#92400e;margin-bottom:6px}}
  .pass-label{{color:#065f46;font-size:13px}}
</style></head><body>
<h1>📊 Brand Compliance Report</h1>
<h2>{filename} &nbsp;·&nbsp; {datetime.now().strftime('%Y-%m-%d %H:%M')}</h2>
<div class='score'>{score}%</div>
<p style='color:#777;margin-top:4px'>compliance score</p>
<div class='grid'>
  <div class='metric'><div class='metric-val'>{total}</div><div class='metric-lbl'>total slides</div></div>
  <div class='metric'><div class='metric-val' style='color:#9b1c1c'>{errs}</div><div class='metric-lbl'>errors</div></div>
  <div class='metric'><div class='metric-val' style='color:#92400e'>{warns}</div><div class='metric-lbl'>warnings</div></div>
</div>
<div class='palette'><strong style='color:#92400e'>Brand palette:</strong><br>{swatches}</div>
<hr style='border-color:#fde68a;margin:20px 0'>
{slide_rows}
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("⚙️ Brand Guidelines")

    st.markdown("### 🔤 Text roles")
    smart_roles    = st.toggle("Smart role detection", value=True,
        help="Infer Header/Subheader/Body by font size when no explicit XML placeholder exists")
    size_tolerance = st.slider("Size tolerance (±pt)", 0, 6, 2)

    role_specs = {}
    for rk, rd in ROLE_DEFAULTS.items():
        with st.expander(f"{ROLE_LABELS[rk]}  —  default {rd['size']}pt"):
            c1, c2 = st.columns(2)
            font = c1.text_input("Font", rd["font"], key=f"f_{rk}")
            size = c2.number_input("pt",  6, 96, rd["size"], key=f"s_{rk}")
            role_specs[rk] = {"font": font, "size": size}

    st.divider()
    st.markdown("### 🎨 Brand colors")
    st.caption("Default: Office Orange Accent 1 family")

    if "brand_colors" not in st.session_state:
        st.session_state.brand_colors = DEFAULT_BRAND_COLORS.copy()

    st.markdown(
        '<div class="swatch-row">' +
        "".join(
            f'<div class="swatch"><div class="swatch-dot" style="background:{h}"></div>'
            f'<span style="font-size:11px">{ORANGE_PALETTE.get(h,h)}</span></div>'
            for h in st.session_state.brand_colors
        ) + '</div>', unsafe_allow_html=True
    )

    color_input = st.text_input("Add hex color", placeholder="#FF5733")
    if color_input:
        v = color_input.strip().upper()
        if not v.startswith("#"): v = "#" + v
        if re.match(r"^#[0-9A-F]{6}$", v) and v not in st.session_state.brand_colors:
            st.session_state.brand_colors.append(v)
            st.rerun()

    rm_cols = st.columns(6)
    to_remove = None
    for i, c in enumerate(st.session_state.brand_colors):
        with rm_cols[i % 6]:
            if st.button("✕", key=f"rm_{i}", help=f"Remove {c}"):
                to_remove = i
    if to_remove is not None:
        st.session_state.brand_colors.pop(to_remove)
        st.rerun()

    if st.button("↺ Reset to Orange defaults"):
        st.session_state.brand_colors = DEFAULT_BRAND_COLORS.copy()
        st.rerun()

    tolerance = st.slider("Color tolerance (ΔE)", 0, 60, 20,
        help="~10 = strict, ~25 = lenient")

    st.divider()
    st.markdown("### 📐 Structural checks")
    slide_size = st.selectbox("Slide dimensions", ["widescreen","standard","any"],
        format_func=lambda x: {
            "widescreen": "Widescreen (13.33×7.5 in)",
            "standard":   "Standard (10×7.5 in)",
            "any":        "Any / skip check",
        }[x])
    chk_fonts   = st.checkbox("Font families",      True)
    chk_colors  = st.checkbox("Colors",             True)
    chk_sizes   = st.checkbox("Font sizes",         True)
    chk_layout  = st.checkbox("Layout consistency", True)
    chk_empty   = st.checkbox("Empty slides",       True)
    chk_bullets = st.checkbox("Excessive bullets",  True)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="display:flex;align-items:center;gap:18px;margin-bottom:6px">
  <div style="font-size:64px;line-height:1">🔍</div>
  <div>
    <div style="font-size:28px;font-weight:700;color:#92400e;line-height:1.2">PowerPoint Brand Checker</div>
    <div style="font-size:13px;color:#b45309;font-style:italic;margin-top:4px">Powered by JoAI</div>
     <div style="font-size:13px;color:#b45309;font-style:italic;margin-top:4px">AI may contain errors; verify important information</div>
  </div>
</div>
<p style="color:#6b7280;font-size:14px;margin-top:10">Upload a .pptx — verify fonts, colors, text roles, and layout against your brand guidelines.</p>
""", unsafe_allow_html=True)

uploaded = st.file_uploader("Drop your .pptx file here", type=["pptx"])

if uploaded:
    cfg = dict(
        smart_roles=smart_roles,
        size_tolerance=size_tolerance,
        role_specs=role_specs,
        role_sizes={k: v["size"] for k, v in role_specs.items()},
        brand_colors=st.session_state.brand_colors,
        tolerance=tolerance,
        slide_size=slide_size,
        chk_fonts=chk_fonts, chk_colors=chk_colors, chk_sizes=chk_sizes,
        chk_layout=chk_layout, chk_empty=chk_empty, chk_bullets=chk_bullets,
    )

    file_bytes = uploaded.read()
    slides_xml, pres_w, pres_h = parse_pptx(file_bytes)
    results = run_checks(slides_xml, pres_w, pres_h, cfg)

    total    = len(results)
    errors   = sum(1 for r in results for i in r["issues"] if i["type"]=="error")
    warnings = sum(1 for r in results for i in r["issues"] if i["type"]=="warning")
    clean    = sum(1 for r in results if not r["issues"])
    score    = round(clean/total*100)

    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Compliance score", f"{score}%")
    m2.metric("Slides", total)
    m3.metric("Errors", errors)
    m4.metric("Warnings", warnings)

    st.divider()

    tab1, tab2 = st.tabs(["📋 Slide issues", "🔤 Role detection map"])

    # ── Tab 1: Issues with snippets ──────────────────────────────────────────
    with tab1:
        for r in results:
            errs  = [i for i in r["issues"] if i["type"]=="error"]
            warns = [i for i in r["issues"] if i["type"]=="warning"]

            if not r["issues"]:
                with st.expander(f"✅ Slide {r['num']} — Pass"):
                    st.success("No issues found.")
            else:
                icon = "🔴" if errs else "🟡"
                label = f"{icon} Slide {r['num']} — {len(errs)} error(s), {len(warns)} warning(s)"
                with st.expander(label):
                    cards_html = "".join(render_issue_card(i) for i in r["issues"])
                    st.markdown(cards_html, unsafe_allow_html=True)

    # ── Tab 2: Role detection map ────────────────────────────────────────────
    with tab2:
        if smart_roles:
            st.info("⚠️ **Smart role detection on** — Header/Subheader/Body inferred by font size. "
                    "Rows marked *heuristic* may not always be accurate.")
        else:
            st.info("Smart role detection **off** — only explicit title placeholders are tagged.")

        badge_html = {
            "slide_title": '<span class="badge badge-title">Slide Title</span>',
            "header":      '<span class="badge badge-header">Header</span>',
            "subheader":   '<span class="badge badge-subheader">Subheader</span>',
            "body":        '<span class="badge badge-body">Body</span>',
        }

        for r in results:
            with st.expander(f"Slide {r['num']}"):
                if not r["role_findings"]:
                    st.caption("No text runs detected.")
                    continue
                seen, rows_html = set(), ""
                for rf in r["role_findings"]:
                    key = (rf["role"], rf["font"], rf["size"])
                    if key in seen: continue
                    seen.add(key)
                    badge   = badge_html.get(rf["role"], "")
                    method  = "✓ explicit" if rf["method"]=="explicit" else "~ heuristic"
                    font_d  = rf["font"] or "—"
                    size_d  = f"{rf['size']}pt" if rf["size"] else "—"
                    snip_d  = rf.get("snippet","") or "—"
                    esc_snip = snip_d.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                    rows_html += (
                        f"<tr>"
                        f"<td>{badge}</td>"
                        f"<td>{font_d}</td>"
                        f"<td>{size_d}</td>"
                        f"<td style='max-width:200px;overflow:hidden;text-overflow:ellipsis;"
                        f"white-space:nowrap;color:#6b7280;font-size:11px'>{esc_snip}</td>"
                        f"<td style='color:#9ca3af;font-size:11px'>{method}</td>"
                        f"</tr>"
                    )
                st.markdown(
                    f"<table class='role-table'><thead><tr>"
                    f"<th>Role</th><th>Font</th><th>Size</th><th>Text snippet</th><th>Method</th>"
                    f"</tr></thead><tbody>{rows_html}</tbody></table>",
                    unsafe_allow_html=True
                )

    st.divider()
    html = build_html_report(results, uploaded.name, score, cfg)
    st.download_button("⬇️ Download HTML report", data=html.encode(),
                       file_name="brand-report.html", mime="text/html")

else:
    st.info("👈 Set your brand guidelines in the sidebar, then upload a .pptx file.")

    st.markdown("#### Default brand palette — Office Orange Accent 1")
    st.markdown(
        '<div class="swatch-row">' +
        "".join(
            f'<div class="swatch"><div class="swatch-dot" style="background:{h}"></div>{name}</div>'
            for h,name in ORANGE_PALETTE.items()
        ) + '</div>',
        unsafe_allow_html=True
    )

    st.markdown("#### Default text role specs")
    rows = "".join(
        f"<tr><td>{ROLE_LABELS[k]}</td><td>{v['font']}</td>"
        f"<td>{v['weight']}</td><td>{v['size']}pt</td></tr>"
        for k,v in ROLE_DEFAULTS.items()
    )
    st.markdown(
        f"<table class='role-table'><thead><tr>"
        f"<th>Role</th><th>Font</th><th>Weight</th><th>Size</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>",
        unsafe_allow_html=True
    )
