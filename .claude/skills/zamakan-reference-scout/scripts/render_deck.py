"""deck.pptx v2: an editable, on-brand 16:9 kickoff deck (called by build_outputs.py).

Same story as the board: cover → at a glance → insights → recommendation → territories → competitors →
patterns & white space → deep dives → references → before kickoff → close. Dressed in the brand kit: the approved
logo variant for each background (SVG rendered to PNG when needed), the client's fonts by name (installed for the
PDF render), colours by role, the panel radius, and the signature element (the arch) on the cover image only.
Text boxes shrink their type to fit, so nothing spills off a slide.
"""
import io
import math
import shutil
import subprocess
from pathlib import Path

from theme import mix

SLIDE_W, SLIDE_H, M = 33.867, 19.05, 1.8  # cm
RING_NAME = {"direct": "Direct", "category": "Category", "adjacent": "Adjacent", "wildcard": "Wildcard"}
RING_ORDER = ["direct", "category", "adjacent", "wildcard"]


def svg_to_png(svg, dst, height=600):
    """Render an SVG logo to a transparent PNG with the bundled Chromium (python-pptx cannot place SVG)."""
    dst = Path(dst)
    if dst.exists():
        return dst
    from playwright.sync_api import sync_playwright
    sys_path = Path(__file__).resolve().parents[2] / "zamakan-design-system" / "scripts"
    import sys
    sys.path.insert(0, str(sys_path))
    from _common import launch_chromium
    dst.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = launch_chromium(p)
        pg = b.new_page(viewport={"width": 2000, "height": height + 40})
        uri = "data:image/svg+xml;base64," + __import__("base64").b64encode(Path(svg).read_bytes()).decode()
        pg.set_content(f'<html><body style="margin:0;background:transparent"><img id="l" src="{uri}" style="height:{height}px;display:block"></body></html>')
        pg.wait_for_function("document.getElementById('l').complete && document.getElementById('l').naturalWidth > 0")
        pg.locator("#l").screenshot(path=str(dst), omit_background=True)
        b.close()
    return dst


def logo_png(logo, cache):
    if not logo:
        return None
    if logo.get("svg"):
        try:
            return svg_to_png(logo["svg"], Path(cache) / f"logo-{logo['id']}.png")
        except Exception:  # noqa: BLE001 - fall back to the client's PNG
            pass
    return logo.get("png")


def shaped(img_bytes, w, h, arch=False, radius_frac=0.0):
    """Crop an image to w×h (cover) and mask it to an arch (semicircle top) or rounded rectangle; returns PNG bytes."""
    from PIL import Image, ImageDraw
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    W = 1100 if w > 12 else 640  # enough for a projector, small enough to mail
    H = int(W * h / w)
    s = max(W / im.width, H / im.height)
    im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)))
    l, t = (im.width - W) // 2, int((im.height - H) * (0.3 if arch else 0.5))  # arches favour the top (faces)
    im = im.crop((l, t, l + W, t + H)).convert("RGBA")
    if arch or radius_frac:
        mask = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(mask)
        if arch:
            d.ellipse((0, 0, W, W), fill=255)
            d.rectangle((0, W // 2, W, H), fill=255)
        else:
            d.rounded_rectangle((0, 0, W, H), radius=int(radius_frac * W), fill=255)
        im.putalpha(mask)
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        return buf.getvalue()
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=82, optimize=True)
    return buf.getvalue()


def install_fonts(kit):
    """Make the client's font files visible to LibreOffice for the PDF render (user font dir)."""
    if not kit["font_files"]:
        return
    d = Path.home() / ".fonts" / "zamakan"
    d.mkdir(parents=True, exist_ok=True)
    new = False
    for f in kit["font_files"]:
        dst = d / Path(f["path"]).name
        if not dst.exists():
            shutil.copy(f["path"], dst)
            new = True
    if new and shutil.which("fc-cache"):
        subprocess.run(["fc-cache", "-f", str(d)], capture_output=True)


def build(run, brief, client_name, kit, thumb, codes, h, path, cache):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.util import Emu, Pt

    th = kit["theme"]
    rgb = lambda x: RGBColor.from_string(x.lstrip("#").upper())  # noqa: E731
    C = {k: rgb(th[k]) for k in ("ink", "heading", "muted", "accent", "accent_text", "on_accent", "bg", "panel", "dark", "on_dark", "chip", "line")}
    C["on_dark_muted"] = rgb(mix(th["on_dark"], th["dark"], 0.3))
    deco = rgb((__import__("re").search(r"#[0-9A-Fa-f]{6}", kit["divider"] or "") or [th["accent"]])[0])
    DISP, BODY, AR, AR_BODY = th["display_font"], th["body_font"], th["ar_display_font"], th["ar_body_font"]
    radius_frac = 0.0 if kit["radius"] in ("0px", "0") else 0.03
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
    blank = prs.slide_layouts[6]
    refs = run["references"]
    byid = {r["id"]: r for r in refs}
    cm = lambda v: Emu(int(v * 360000))  # noqa: E731
    who = (client_name or kit.get("client_name") or "").split(" ")[0] or "the client"
    logos = {k: logo_png(v, cache) for k, v in kit["logos"].items()}
    page = [0]

    def fit(lines, w, h, size, min_size):
        """Largest size ≤ size whose estimated wrapped height fits the box."""
        while size > min_size:
            cpl = max(8, w / (size * 0.0353 * 0.52))
            n = sum(max(1, math.ceil(len(l) / cpl)) for l in lines)
            if n * size * 0.0353 * 1.28 <= h:
                break
            size -= 1
        return size

    def text(s, x, y, w, hgt, t, size=16, bold=False, color=None, font=None, align=None, rtl=False, min_size=9, anchor=None, spacing=None):
        lines = t if isinstance(t, list) else [t]
        size = fit(lines, w, hgt, size, min_size)
        tb = s.shapes.add_textbox(cm(x), cm(y), cm(w), cm(hgt))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        if anchor:
            tf.vertical_anchor = anchor
        for i, line in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            r = p.add_run()
            r.text = line
            r.font.size, r.font.bold, r.font.name = Pt(size), bold, font or (AR_BODY if rtl else BODY)
            r.font.color.rgb = color or C["ink"]
            if spacing:
                p.space_after = Pt(spacing)
            if align or rtl:
                p.alignment = PP_ALIGN.RIGHT if rtl else align
        return tb

    def rect(s, x, y, w, hgt, fill, rounded=False):
        shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if rounded and radius_frac else MSO_SHAPE.RECTANGLE, cm(x), cm(y), cm(w), cm(hgt))
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
        shp.line.fill.background()
        shp.shadow.inherit = False
        if rounded and radius_frac:
            shp.adjustments[0] = 0.06
        return shp

    def picture(s, r, x, y, w, hgt, arch=False, code=True):
        b = thumb(r)
        if not b:
            ph = rect(s, x, y, w, hgt, C["chip"], True)
            tf = ph.text_frame
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            for k, line in enumerate((r["brand"], "no preview image · open the link")):
                p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                p.alignment = PP_ALIGN.CENTER
                rr = p.add_run()
                rr.text = line
                rr.font.size, rr.font.bold, rr.font.name, rr.font.color.rgb = Pt(9 if w < 10 else 12), k == 0, BODY, C["muted"]
        else:
            s.shapes.add_picture(io.BytesIO(shaped(b, w, hgt, arch, radius_frac)), cm(x), cm(y), cm(w), cm(hgt))
        if code:
            lab = rect(s, x + 0.25, y + (w / 2 if arch else 0.25), 1.25, 0.6, C["dark"])
            tf = lab.text_frame
            tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            rr = p.add_run()
            rr.text = codes[r["id"]]
            rr.font.size, rr.font.bold, rr.font.name, rr.font.color.rgb = Pt(9), True, BODY, C["on_dark"]

    def link(s, x, y, r, size=11):
        tb = text(s, x, y, 7, 0.7, f"{h.link_label(r)} ↗", size, True, C["accent_text"])
        run_ = tb.text_frame.paragraphs[0].runs[0]
        run_.hyperlink.address = h.primary_url(r)
        run_.font.color.rgb = C["accent_text"]
        run_.font.underline = False

    def slide(eyebrow=None, title=None, bg=None):
        s = prs.slides.add_slide(blank)
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = bg or C["bg"]
        page[0] += 1
        if eyebrow is not None:
            text(s, M, 1.2, 20, 0.6, eyebrow.upper(), 10, True, C["accent_text"])
            if kit["divider"]:
                ln = s.shapes.add_connector(1, cm(M), cm(1.95), cm(M + 2.4), cm(1.95))
                ln.line.color.rgb, ln.line.width = deco, Pt(1.5)
        if title:
            text(s, M, 2.25, SLIDE_W - 2 * M - 4, 2.2, title, 30, False, C["heading"], DISP, min_size=20)
        # footer: page number, client, brand mark bottom-right
        text(s, M, SLIDE_H - 1.2, 12, 0.5, f"{page[0]:02d}   {client_name or ''}", 9, False, C["on_dark_muted"] if bg else C["muted"])
        mark = logos.get("mark_light") if bg is None else logos.get("mark_dark")
        if mark:
            s.shapes.add_picture(str(mark), cm(SLIDE_W - M - 0.9), cm(SLIDE_H - 1.55), height=cm(0.95))
        return s

    # 1 cover
    s = prs.slides.add_slide(blank)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = C["dark"]
    page[0] += 1
    if logos.get("on_dark"):
        s.shapes.add_picture(str(logos["on_dark"]), cm(M), cm(1.4), height=cm(3.4))
    else:
        text(s, M, 1.4, 14, 1, (client_name or th["name"]).upper(), 14, True, C["on_dark"], DISP)
    text(s, M, 6.4, 18.5, 1, f"REFERENCE SCOUT · {run['run']['mode'].upper()} · {run['run'].get('scope', 'gcc').upper()} SCOPE", 11, True, C["on_dark_muted"])
    text(s, M, 7.4, 18.5, 5.4, h.display_title(run, brief, client_name), 44, False, C["on_dark"], DISP, min_size=28)
    lede = " · ".join(brief[k] for k in ("moment", "objective") if brief and brief.get(k)) or run["run"].get("question", "")
    text(s, M, 13.2, 18, 2.4, lede, 15, False, C["on_dark_muted"])
    text(s, M, SLIDE_H - 1.6, 18, 0.6, run["run"].get("created", ""), 11, False, C["on_dark_muted"])
    hero = h.cover_ref(run, lambda r: bool(thumb(r)), h.competitor_names(run, brief))
    if hero:
        picture(s, hero, 22.2, 2.2, 9.9, SLIDE_H - 2.2, arch=kit["arch"], code=False)

    # 2 at a glance
    s = slide("At a glance", "What we looked at")
    scope = run["run"].get("scope", "gcc")
    stats = [(len(refs), "references"), (sum(r["status"] == "verified" for r in refs), "checked live"),
             (sum(h.region_of(r) == "gcc" for r in refs), "from the GCC") if scope != "global" else (len({h.region_of(r) for r in refs}), "regions"),
             (len(run.get("territories", [])), "territories")]
    for i, (n, lab) in enumerate(stats):
        x = M + i * 7.6
        text(s, x, 5.4, 7, 2.4, str(n), 54, False, C["heading"], DISP)
        text(s, x, 8.1, 7, 0.8, lab, 13, False, C["muted"])
    rows = [f"{k.title()}: {brief[k] if isinstance(brief[k], str) else ', '.join(brief[k])}"
            for k in ("objective", "audience", "moment", "channels", "competitors", "avoid") if brief and brief.get(k)]
    text(s, M, 10.2, 16.5, 6.6, rows or [run["run"].get("question", "")], 13, color=C["ink"], spacing=4)
    ring_lines = [f"{RING_NAME[k]}: {sum(r['ring'] == k for r in refs)}" for k in RING_ORDER]
    text(s, 19.6, 10.2, 12.4, 0.7, "How we searched", 12, True, C["accent_text"])
    text(s, 19.6, 11.1, 12.4, 5.6, ring_lines + ["", "Sources: " + ", ".join(sorted({q.split(':')[0] for q in run['run'].get('queries', [])}))], 12, color=C["ink"])

    # 3 insights
    if run.get("insights"):
        s = slide("What we learned", "Insights")
        ins = run["insights"][:3]
        cw = (SLIDE_W - 2 * M - 2 * 0.8) / len(ins)
        for i, x in enumerate(ins):
            cx = M + i * (cw + 0.8)
            rect(s, cx, 5.0, cw, 9.2, C["panel"], True)
            rect(s, cx, 5.0, cw, 0.12, C["accent"])
            text(s, cx + 0.7, 5.7, cw - 1.4, 1.6, f"{i + 1:02d}", 30, False, C["accent_text"], DISP)
            text(s, cx + 0.7, 7.6, cw - 1.4, 4.9, x["text"], 18, False, C["ink"], min_size=11)
            src = " · ".join(v for v in (x.get("source_name"), x.get("date")) if v)
            tb = text(s, cx + 0.7, 12.9, cw - 1.4, 1.0, src + " ↗", 10, True, C["accent_text"])
            tb.text_frame.paragraphs[0].runs[0].hyperlink.address = x["source_url"]
            tb.text_frame.paragraphs[0].runs[0].font.color.rgb = C["accent_text"]

    # 4 recommendation
    rec = run.get("recommendation")
    tname = {t["id"]: t["name"] for t in run.get("territories", [])}
    if rec:
        s = slide("Our recommendation")
        rect(s, M, 2.6, 0.22, 9.4, C["accent"])
        text(s, M + 1.0, 2.6, 21, 9.4, rec["summary"], 30, False, C["heading"], DISP, min_size=18)
        x = M + 1.0
        for tid in rec.get("territory_ids", []):
            w = min(10.5, 0.7 + len(tname.get(tid, tid)) * 0.24)
            chip = rect(s, x, 12.7, w, 1.0, C["accent"], True)
            tf = chip.text_frame
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            rr = p.add_run()
            rr.text = tname.get(tid, tid)
            rr.font.size, rr.font.bold, rr.font.name, rr.font.color.rgb = Pt(11), True, BODY, C["on_accent"]
            x += w + 0.4
        text(s, 24.0, 2.6, 8.1, 0.7, "WHY", 10, True, C["accent_text"])
        text(s, 24.0, 3.4, 8.1, 8.6, rec.get("rationale", ""), 15, False, C["ink"])

    # territories
    recd = set((rec or {}).get("territory_ids", []))
    leads = h.lead_order(run, {r["id"]: thumb(r) for r in refs}, h.competitor_names(run, brief))
    for i, t in enumerate(run.get("territories", []), 1):
        s = slide(f"Territory {i:02d}" + ("  ·  recommended" if t["id"] in recd else ""))
        text(s, M, 2.25, 15.4, 1.8, t["name"], 32, False, C["heading"], DISP, min_size=22)
        if t.get("name_ar"):
            text(s, M, 4.1, 15.4, 1.3, t["name_ar"], 22, False, C["muted"], AR, rtl=True, min_size=16)
        text(s, M, 5.8, 15.4, 3.6, t["thesis"], 17, False, C["ink"], min_size=12)
        body = ([f"Why {who}: {t['why_this_client']}"] if t.get("why_this_client") else [])
        text(s, M, 9.6, 15.4, 1.9, body, 12, False, C["muted"])
        ex, risks = t.get("example_executions", []), t.get("risks", [])
        if ex:
            text(s, M, 11.7, 7.4, 0.6, "EXECUTIONS", 9, True, C["accent_text"])
            text(s, M, 12.4, 7.4, 4.8, [f"• {x}" for x in ex], 11, spacing=3)
        if risks:
            text(s, M + 8.0, 11.7, 7.4, 0.6, "WATCH-OUTS", 9, True, C["accent_text"])
            text(s, M + 8.0, 12.4, 7.4, 4.8, [f"• {x}" for x in risks], 11, spacing=3)
        rs = leads[t["id"]]
        X, Y, W = 18.4, 1.2, SLIDE_W - 18.4 - M
        if rs:
            picture(s, rs[0], X, Y, W, 8.2)
        for j, r in enumerate(rs[1:3]):
            picture(s, r, X + j * (W / 2 + 0.15), Y + 8.5, W / 2 - 0.15, 5.4)
        cap = "   ".join(f"{codes[r['id']]} {r['brand']}" for r in rs)
        text(s, X, Y + 14.2, W, 1.6, cap, 9, False, C["muted"])

    # sparks from elsewhere
    sparks = [r for r in refs if r.get("spark")][:4]
    if sparks:
        s = slide(bg=C["dark"])
        text(s, M, 1.2, 20, 0.6, "SPARKS FROM ELSEWHERE", 10, True, C["on_dark_muted"])
        text(s, M, 2.0, 26, 1.6, f"What if {who}…", 30, False, C["on_dark"], DISP)
        text(s, M + 14, 2.55, SLIDE_W - 2 * M - 14, 1.2, "Work from far outside the category and the region: provocations, not references to copy.",
             11, False, C["on_dark_muted"], align=PP_ALIGN.RIGHT)
        n = len(sparks)
        cw = (SLIDE_W - 2 * M - (n - 1) * 0.8) / n
        for j, r in enumerate(sparks):
            x = M + j * (cw + 0.8)
            picture(s, r, x, 4.4, cw, cw * 0.58)
            y = 4.4 + cw * 0.58 + 0.5
            text(s, x, y, cw, 4.0, r["spark"], 16 if n < 4 else 14, False, C["on_dark"], DISP, min_size=10)
            text(s, x, y + 4.2, cw, 1.4, f"From {r['brand']}: {r['title']} · {r.get('country', '')} {r.get('year', '')}", 9, False, C["on_dark_muted"], min_size=8)
    # competitors
    comp = run.get("competitor_summary") or []
    if comp:
        s = slide("The competition", "What competitors run")
        rows_n = min(len(comp), 7)
        tbl = s.shapes.add_table(rows_n + 1, 4, cm(M), cm(5.0), cm(SLIDE_W - 2 * M), cm(1.2 * (rows_n + 1))).table
        widths = [6.0, 3.6, 15.0, SLIDE_W - 2 * M - 24.6]
        for c, w in enumerate(widths):
            tbl.columns[c].width = cm(w)
        hdr = ["Competitor", "Campaign found", "What they own", "References"]
        for r_i in range(rows_n + 1):
            for c_i in range(4):
                cell = tbl.cell(r_i, c_i)
                cell.fill.solid()
                cell.fill.fore_color.rgb = C["dark"] if r_i == 0 else (C["panel"] if r_i % 2 else C["bg"])
                if r_i == 0:
                    val = hdr[c_i]
                else:
                    cc = comp[r_i - 1]
                    val = [cc["advertiser"], "Yes" if cc.get("found_campaign") else "None found",
                           cc.get("notes", "") + (f" ({', '.join(cc['messaging_pillars'])})" if cc.get("messaging_pillars") else ""),
                           ", ".join(codes[x] for x in cc.get("reference_ids", []) if x in codes) or "–"][c_i]
                tf = cell.text_frame
                tf.text = ""
                rr = tf.paragraphs[0].add_run()
                rr.text = val
                rr.font.size, rr.font.name = Pt(10 if r_i else 9), BODY
                rr.font.bold = r_i == 0 or c_i == 0
                rr.font.color.rgb = C["on_dark"] if r_i == 0 else C["ink"]
        text(s, M, SLIDE_H - 2.2, 26, 0.6, "Every named competitor was checked; 'none found' means searched, not ignored.", 10, False, C["muted"])

    # patterns & white space
    if run.get("patterns") or run.get("white_space"):
        s = slide("Patterns & white space", "What everyone does, and what nobody does")
        half = (SLIDE_W - 2 * M - 1.2) / 2
        for k, (lab, items) in enumerate((("PATTERNS", [p["pattern"] + "  " + ", ".join(codes[x] for x in p["reference_ids"] if x in codes)
                                                         for p in run.get("patterns", [])]),
                                          ("WHITE SPACE", run.get("white_space", [])))):
            x = M + k * (half + 1.2)
            rect(s, x, 5.0, half, 10.2, C["panel"], True)
            text(s, x + 0.7, 5.6, half - 1.4, 0.6, lab, 10, True, C["accent_text"])
            text(s, x + 0.7, 6.6, half - 1.4, 8.2, [f"{n}.  {v}" for n, v in enumerate(items, 1)], 14, spacing=8, min_size=10)

    # deep dives
    for rid in run.get("top", []):
        r, td = byid[rid], byid[rid]["teardown"]
        s = slide(f"Deep dive · {codes[rid]}")
        text(s, M, 2.25, 17.5, 2.0, f"{r['brand']}: {r['title']}", 26, False, C["heading"], DISP, min_size=18)
        text(s, M, 4.3, 17.5, 0.6, h.meta_line(r), 11, False, C["muted"])
        rows = [f"Insight: {td['insight']}", f"Idea: {td['idea']}", f"Execution: {td['execution']}",
                "Borrow: " + "; ".join(td["transferable"]), f"Cultural fit {td['cultural_fit']['score']}/5: {td['cultural_fit']['notes']}"]
        text(s, M, 5.4, 17.5, 11.6, rows, 13, spacing=6, min_size=9)
        picture(s, r, 20.6, 2.2, SLIDE_W - 20.6 - M, 7.6, code=False)
        link(s, 20.6, 10.1, r)

    # reference grid, 8 per slide
    ordered = sorted(refs, key=lambda r: codes[r["id"]])
    per, cols = 8, 4
    cw = (SLIDE_W - 2 * M - (cols - 1) * 0.6) / cols
    for i in range(0, len(ordered), per):
        s = slide("The evidence", "All references" + (f" ({i // per + 1}/{math.ceil(len(ordered) / per)})" if len(ordered) > per else ""))
        for j, r in enumerate(ordered[i:i + per]):
            x, y = M + (j % cols) * (cw + 0.6), 4.7 + (j // cols) * 6.9
            picture(s, r, x, y, cw, 3.6)
            text(s, x, y + 3.8, cw, 1.4, [r["brand"], r["title"]], 10, False, C["ink"], min_size=8)
            text(s, x, y + 5.2, cw, 0.5, f"{RING_NAME[r['ring']]} · {h.meta_line(r)}", 8, False, C["muted"], min_size=7)
            link(s, x, y + 5.75, r, 9)

    # before kickoff
    if run.get("before_kickoff") or run.get("open_questions"):
        s = slide("Next", "Before kickoff")
        half = (SLIDE_W - 2 * M - 1.2) / 2
        for k, (lab, items) in enumerate((("CHECK THESE FIRST", run.get("before_kickoff", [])), ("OPEN QUESTIONS", run.get("open_questions", [])))):
            x = M + k * (half + 1.2)
            text(s, x, 5.0, half, 0.6, lab, 10, True, C["accent_text"])
            text(s, x, 6.0, half, 10.6, [f"☐  {v}" for v in items], 14, spacing=10, min_size=10)

    # close
    s = prs.slides.add_slide(blank)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = C["dark"]
    if logos.get("on_dark"):
        from PIL import Image
        iw, ih = Image.open(logos["on_dark"]).size
        hh = 4.0
        ww = hh * iw / ih
        s.shapes.add_picture(str(logos["on_dark"]), cm((SLIDE_W - ww) / 2), cm((SLIDE_H - hh) / 2 - 1), height=cm(hh))
    text(s, M, SLIDE_H - 3.0, SLIDE_W - 2 * M, 0.8, "Every reference links to its original page and was checked live. Thumbnails © their owners; internal reference use only.",
         10, False, C["on_dark_muted"], align=PP_ALIGN.CENTER)
    set_link_colour(prs, th["accent_text"])
    prs.save(path)
    return path


def set_link_colour(prs, hex_):
    """Viewers (LibreOffice, Keynote) draw links in the theme's hyperlink colour, not the run colour: set it to the brand's."""
    import re as _re
    master = prs.slide_masters[0]
    for rel in master.part.rels.values():
        if rel.reltype.endswith("/theme"):
            part = rel.target_part
            xml = part.blob.decode("utf-8")
            for tag in ("hlink", "folHlink"):
                xml = _re.sub(rf"<a:{tag}>.*?</a:{tag}>", f'<a:{tag}><a:srgbClr val="{hex_.lstrip("#").upper()}"/></a:{tag}>', xml, flags=_re.S)
            part._blob = xml.encode("utf-8")
