import streamlit as st
import zipfile
import io
import math
import re
from collections import Counter
from datetime import datetime

st.set_page_config(
    page_title="PPTX Brand Checker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.block-container { padding-top: 2rem; }
.metric-box { background:#f8f9fa; border-radius:10px; padding:1rem; text-align:center; }
.pill-err  { background:#fce8e8; color:#9b1c1c; border-radius:20px; padding:2px 10px; font-size:12px; font-weight:600; }
.pill-warn { background:#fef3c7; color:#92400e; border-radius:20px; padding:2px 10px; font-size:12px; font-weight:600; }
.pill-ok   { background:#d1fae5; color:#065f46; border-radius:20px; padding:2px 10px; font-size:12px; font-weight:600; }
.slide-header { font-weight:600; font-size:15px; margin-bottom:4px; }
</style>
""", unsafe_allow_html=True)


# ── Color utilities ───────────────────────────────────────────────────────────
def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_lab(r, g, b):
    R, G, B = r/255, g/255, b/255
    def lin(c): return ((c+0.055)/1.055)**2.4 if c > 0.04045 else c/12.92
    R, G, B = lin(R), lin(G), lin(B)
    X = (R*0.4124 + G*0.3576 + B*0.1805) / 0.95047
    Y = (R*0.2126 + G*0.7152 + B*0.0722) / 1.00000
    Z = (R*0.0193 + G*0.1192 + B*0.9505) / 1.08883
    def f(t): return t**(1/3) if t > 0.008856 else 7.787*t + 16/116
    return 116*f(Y)-16, 500*(f(X)-f(Y)), 200*(f(Y)-f(Z))

def delta_e(h1, h2):
    l1,a1,b1 = rgb_to_lab(*hex_to_rgb(h1))
    l2,a2,b2 = rgb_to_lab(*hex_to_rgb(h2))
    return math.sqrt((l1-l2)**2 + (a1-a2)**2 + (b1-b2)**2)

def is_brand_color(hex_val, brand_colors, tolerance):
    return any(delta_e(hex_val, bc) <= tolerance for bc in brand_colors)


# ── PPTX parser ───────────────────────────────────────────────────────────────
def parse_pptx(file_bytes):
    """Return list of slide XMLs and presentation width/height in EMUs."""
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


def check_slide(xml, slide_num, cfg):
    issues = []

    shapes = re.findall(r"<p:sp[\s\S]*?</p:sp>", xml)
    all_fonts, all_sizes, all_colors = [], [], []
    has_content = False
    total_bullets = 0

    for sp in shapes:
        is_title = bool(re.search(r'ph type="title"|ph type="ctrTitle"', sp))
        text = re.sub(r"<[^>]+>", "", sp).strip()
        if text:
            has_content = True

        # bullets
        paras = re.findall(r"<a:p>([\s\S]*?)</a:p>", sp)
        total_bullets += sum(1 for p in paras if "<a:buChar" in p or "<a:buAutoNum" in p)

        for rpr_m in re.finditer(r"<a:rPr([^>]*)>([\s\S]*?)</a:rPr>", sp):
            attrs, inner = rpr_m.group(1), rpr_m.group(2)
            # font
            lm = re.search(r'<a:latin typeface="([^"]+)"', inner)
            if lm and lm.group(1) not in ("+mj-lt", "+mn-lt"):
                all_fonts.append((lm.group(1), is_title))
            # size
            sm = re.search(r'sz="(\d+)"', attrs)
            if sm:
                all_sizes.append((int(sm.group(1)) / 100, is_title))
            # color
            cm = re.search(r'<a:srgbClr val="([0-9A-Fa-f]{6})"', inner)
            if cm:
                all_colors.append("#" + cm.group(1).upper())

        for fm in re.finditer(r'<a:srgbClr val="([0-9A-Fa-f]{6})"', sp):
            all_colors.append("#" + fm.group(1).upper())

    # bg color
    bg = re.search(r"<p:bg>[\s\S]*?<a:srgbClr val=\"([0-9A-Fa-f]{6})\"", xml)
    if bg:
        all_colors.append("#" + bg.group(1).upper())

    # — Run checks —
    if cfg["chk_empty"] and not has_content:
        issues.append(("error", "Slide has no text content"))

    if cfg["chk_fonts"] and cfg["allowed_fonts"]:
        bad = list({f for f, _ in all_fonts if f.lower() not in cfg["allowed_fonts"]})
        if bad:
            issues.append(("error", f"Non-brand fonts: {', '.join(bad[:3])}{'…' if len(bad)>3 else ''}"))

    if cfg["chk_sizes"]:
        for sz, is_t in all_sizes:
            if is_t:
                if sz < cfg["min_title"]:
                    issues.append(("error", f"Title font {sz}pt below min {cfg['min_title']}pt"))
                if sz > cfg["max_title"]:
                    issues.append(("warning", f"Title font {sz}pt above max {cfg['max_title']}pt"))
            else:
                if sz < cfg["min_body"]:
                    issues.append(("error", f"Body font {sz}pt below min {cfg['min_body']}pt"))
                if sz > cfg["max_body"]:
                    issues.append(("warning", f"Body font {sz}pt above max {cfg['max_body']}pt"))

    if cfg["chk_colors"] and cfg["brand_colors"]:
        unique = list(set(all_colors))
        off = [c for c in unique if not is_brand_color(c, cfg["brand_colors"], cfg["tolerance"])]
        if off:
            issues.append(("warning", f"Off-brand colors: {', '.join(off[:3])}{'…' if len(off)>3 else ''}"))

    if cfg["chk_bullets"] and total_bullets > 7:
        issues.append(("warning", f"{total_bullets} bullets — consider visual alternatives"))

    return {
        "num": slide_num,
        "issues": issues,
        "sig": f"{len(shapes)}-{sorted([s for s,_ in all_sizes])}",
    }


def run_checks(slides_xml, pres_w, pres_h, cfg):
    results = []
    progress = st.progress(0, text="Analysing slides…")
    for i, xml in enumerate(slides_xml):
        results.append(check_slide(xml, i+1, cfg))
        progress.progress((i+1)/len(slides_xml), text=f"Slide {i+1} / {len(slides_xml)}")

    # Layout consistency
    if cfg["chk_layout"] and len(slides_xml) > 2:
        sigs = [r["sig"] for r in results]
        most_common, count = Counter(sigs).most_common(1)[0]
        if count > len(slides_xml) * 0.4:
            for r in results:
                if r["sig"] != most_common:
                    r["issues"].append(("warning", "Layout differs from majority of slides"))

    # Slide size
    if cfg["slide_size"] != "any":
        exp_w = 12192000 if cfg["slide_size"] == "widescreen" else 9144000
        exp_h = 6858000
        if abs(pres_w - exp_w) > 50000 or abs(pres_h - exp_h) > 50000:
            results[0]["issues"].insert(0, (
                "warning",
                f"Deck size ({pres_w/914400:.2f}×{pres_h/914400:.2f} in) ≠ expected {cfg['slide_size']}"
            ))

    progress.empty()
    return results


def build_html_report(results, filename, score):
    rows = ""
    for r in results:
        rows += f"<tr><td>Slide {r['num']}</td>"
        if r["issues"]:
            rows += "<td>" + "<br>".join(
                f"<span style='color:{'#9b1c1c' if t=='error' else '#92400e'}'>{'✖' if t=='error' else '⚠'} {m}</span>"
                for t, m in r["issues"]
            ) + "</td></tr>"
        else:
            rows += "<td><span style='color:#065f46'>✔ Pass</span></td></tr>"

    color = "#065f46" if score >= 80 else "#92400e" if score >= 60 else "#9b1c1c"
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>Brand Report — {filename}</title>
<style>
  body{{font-family:Arial,sans-serif;max-width:860px;margin:40px auto;padding:0 20px;color:#111}}
  h1{{font-size:22px}} h2{{font-size:14px;color:#555;margin-bottom:24px}}
  .score{{font-size:48px;font-weight:700;color:{color}}}
  table{{width:100%;border-collapse:collapse;margin-top:20px}}
  th{{background:#f3f4f6;text-align:left;padding:8px 12px;font-size:13px}}
  td{{padding:8px 12px;border-top:1px solid #e5e7eb;font-size:13px;vertical-align:top}}
</style></head><body>
<h1>Brand Compliance Report</h1>
<h2>{filename} &nbsp;·&nbsp; Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</h2>
<div class='score'>{score}%</div><p style='color:#555'>compliance score</p>
<table><thead><tr><th>Slide</th><th>Result</th></tr></thead><tbody>{rows}</tbody></table>
</body></html>"""


# ── Sidebar: Brand Guidelines ─────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Brand Guidelines")

    fonts_raw = st.text_input("Allowed font families (comma-separated)", "Calibri, Arial")
    allowed_fonts = [f.strip().lower() for f in fonts_raw.split(",") if f.strip()]

    st.markdown("**Slide dimensions**")
    slide_size = st.selectbox("Expected size", ["widescreen", "standard", "any"],
                               format_func=lambda x: {"widescreen":"Widescreen (13.33×7.5 in)",
                                                       "standard":"Standard (10×7.5 in)",
                                                       "any":"Any / skip check"}[x])

    st.markdown("**Font size limits (pt)**")
    c1, c2 = st.columns(2)
    min_title = c1.number_input("Min title", 8, 72, 24)
    max_title = c2.number_input("Max title", 12, 96, 48)
    min_body  = c1.number_input("Min body",  6, 48, 14)
    max_body  = c2.number_input("Max body",  6, 60, 20)

    st.markdown("**Brand colors**")
    default_colors = ["#003087", "#FFFFFF", "#000000"]
    color_input = st.text_input("Add hex color (press Enter)", placeholder="#FF5733")
    if "brand_colors" not in st.session_state:
        st.session_state.brand_colors = default_colors.copy()
    if color_input:
        v = color_input.strip().upper()
        if not v.startswith("#"): v = "#" + v
        if re.match(r"^#[0-9A-F]{6}$", v) and v not in st.session_state.brand_colors:
            st.session_state.brand_colors.append(v)
            st.rerun()

    cols = st.columns(4)
    to_remove = None
    for i, c in enumerate(st.session_state.brand_colors):
        with cols[i % 4]:
            st.color_picker(f"", c, key=f"cp_{i}", disabled=True, label_visibility="collapsed")
            if st.button("✕", key=f"rm_{i}"):
                to_remove = i
    if to_remove is not None:
        st.session_state.brand_colors.pop(to_remove)
        st.rerun()

    tolerance = st.slider("Color tolerance (ΔE)", 0, 60, 20,
                           help="Higher = more lenient. ~10 is strict, ~25 is lenient.")

    st.markdown("**Checks to run**")
    chk_fonts   = st.checkbox("Fonts",               True)
    chk_colors  = st.checkbox("Colors",              True)
    chk_sizes   = st.checkbox("Font sizes",          True)
    chk_layout  = st.checkbox("Layout consistency",  True)
    chk_empty   = st.checkbox("Empty slides",        True)
    chk_bullets = st.checkbox("Excessive bullets",   True)


# ── Main area ─────────────────────────────────────────────────────────────────
st.title("📊 PowerPoint Brand Checker")
st.caption("Upload a .pptx file and verify it meets your brand guidelines.")

uploaded = st.file_uploader("Drop your .pptx file here", type=["pptx"])

if uploaded:
    cfg = dict(
        allowed_fonts=allowed_fonts, slide_size=slide_size,
        min_title=min_title, max_title=max_title,
        min_body=min_body, max_body=max_body,
        brand_colors=st.session_state.brand_colors, tolerance=tolerance,
        chk_fonts=chk_fonts, chk_colors=chk_colors, chk_sizes=chk_sizes,
        chk_layout=chk_layout, chk_empty=chk_empty, chk_bullets=chk_bullets,
    )

    file_bytes = uploaded.read()
    slides_xml, pres_w, pres_h = parse_pptx(file_bytes)
    results = run_checks(slides_xml, pres_w, pres_h, cfg)

    # ── Summary metrics ──
    total   = len(results)
    errors  = sum(1 for r in results for t,_ in r["issues"] if t == "error")
    warnings= sum(1 for r in results for t,_ in r["issues"] if t == "warning")
    clean   = sum(1 for r in results if not r["issues"])
    score   = round(clean / total * 100)

    color = "normal" if score >= 80 else "inverse"
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Compliance score", f"{score}%")
    m2.metric("Total slides", total)
    m3.metric("Errors", errors, delta=None)
    m4.metric("Warnings", warnings, delta=None)

    st.divider()

    # ── Slide-by-slide report ──
    st.subheader("Slide-by-slide results")
    for r in results:
        errs  = [(t,m) for t,m in r["issues"] if t == "error"]
        warns = [(t,m) for t,m in r["issues"] if t == "warning"]
        label = f"Slide {r['num']}"
        if not r["issues"]:
            with st.expander(f"✅ {label} — Pass"):
                st.success("No issues found.")
        else:
            icon = "🔴" if errs else "🟡"
            with st.expander(f"{icon} {label} — {len(errs)} error(s), {len(warns)} warning(s)"):
                for _, msg in errs:
                    st.error(msg)
                for _, msg in warns:
                    st.warning(msg)

    st.divider()

    # ── Download report ──
    html = build_html_report(results, uploaded.name, score)
    st.download_button(
        "⬇️ Download HTML report",
        data=html.encode(),
        file_name="brand-compliance-report.html",
        mime="text/html",
    )

else:
    st.info("👈 Configure your brand guidelines in the sidebar, then upload a .pptx file above.")
