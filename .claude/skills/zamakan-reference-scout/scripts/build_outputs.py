#!/usr/bin/env python3
"""Build the human outputs of a scout run from references.json (agents never hand-write these).

Usage:
  python build_outputs.py <references.json> --out <job_dir> [--formats board,deck,report] [--brief brief.json]
                          [--client-name "Rawaq Coffee Roasters"] [--no-pdf]

Always writes territories.md (for agents). Formats (ask the user which they want):
  board   board.html: self-contained visual board (thumbnails embedded, filters by ring/region/media)
  deck    deck.pptx (editable, 16:9) + deck.pdf when LibreOffice is available
  report  report.md: written analysis (patterns, white space, territories, teardowns, all references)
Refuses to build if validate_run.py reports errors. Rejected references are never shown.
"""
import argparse
import base64
import html
import io
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _web  # noqa: E402
from validate_run import GCC, validate  # noqa: E402

RING_LABEL = {"direct": "Direct · same category, GCC", "category": "Category · worldwide",
              "adjacent": "Adjacent · shared insight", "wildcard": "Wildcard · craft & ambition"}
RING_ORDER = ["direct", "category", "adjacent", "wildcard"]
E = html.escape


# ------------------------------------------------------------------ shared
def display_title(run, brief, client_name):
    """run.title, else '<Client> · <moment> references', else the question."""
    if run["run"].get("title"):
        return run["run"]["title"]
    who = client_name or (run["run"].get("client") or "").replace("-", " ").title()
    moment = (brief or {}).get("moment", "").split("(")[0].strip()
    if who and moment:
        return f"{who} · {moment} references"
    return run["run"].get("question") or run["run"]["id"]


def load_run(path):
    run = json.loads(Path(path).read_text(encoding="utf-8"))
    errors, warnings = validate(run)
    if errors:
        raise SystemExit("references.json has errors; fix them first:\n  " + "\n  ".join(errors))
    run["references"] = [r for r in run["references"] if r["status"] != "rejected"]
    return run, warnings


def thumb_bytes(ref, cache_dir):
    """JPEG bytes (max 640px) for a reference thumbnail, cached in <out>/thumbs/."""
    url = (ref.get("thumbnail") or {}).get("url")
    local = (ref.get("thumbnail") or {}).get("local")
    dst = Path(cache_dir) / f"{ref['id']}.jpg"
    if dst.exists():
        return dst.read_bytes()
    src = None
    if local and Path(local).exists():
        src = Path(local).read_bytes()
    elif url:
        try:
            req = urllib.request.Request(url, headers=_web.HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                src = r.read(60_000_000)  # some sources serve full-size originals (8 MB+ PNGs)
        except Exception:  # noqa: BLE001 - a missing image never blocks a deliverable
            return None
    if not src:
        return None
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(src)).convert("RGB")
    except Exception:  # noqa: BLE001
        return None
    im.thumbnail((640, 640))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=78, optimize=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(buf.getvalue())
    return buf.getvalue()


def meta_line(r):
    bits = [r.get("agency"), r.get("country"), str(r.get("year") or "")]
    return " · ".join(b for b in bits if b)


def primary_url(r):
    return r["urls"][0]["url"]


def link_label(r):
    return "Watch" if r["urls"][0].get("kind") == "video" or "youtube" in primary_url(r) or "vimeo" in primary_url(r) else "View case"


# ------------------------------------------------------------------ territories.md
def build_territories(run, brief=None, client_name=None):
    byid = {r["id"]: r for r in run["references"]}
    L = [f"# Creative territories: {display_title(run, brief, client_name)}", "",
         f"Run `{run['run']['id']}` · mode {run['run']['mode']} · {len(run['references'])} references "
         f"({sum(r['status'] == 'verified' for r in run['references'])} verified). Generated from references.json.", ""]
    for i, t in enumerate(run.get("territories", []), 1):
        L += [f"## {i}. {t['name']}" + (f" · {t['name_ar']}" if t.get("name_ar") else ""), "", f"**Thesis:** {t['thesis']}", ""]
        if t.get("why_this_client"):
            L += [f"**Why this client:** {t['why_this_client']}", ""]
        L.append("**Built on:**")
        for rid in t["reference_ids"]:
            r = byid.get(rid)
            if r:
                L.append(f"- {r['brand']}: *{r['title']}* ({meta_line(r)}). {r['card']['idea']} {primary_url(r)}")
        for k, lab in (("example_executions", "Example executions"), ("risks", "Risks")):
            if t.get(k):
                L += ["", f"**{lab}:**"] + [f"- {x}" for x in t[k]]
        L.append("")
    if run.get("white_space"):
        L += ["## White space", ""] + [f"- {w}" for w in run["white_space"]] + [""]
    return "\n".join(L)


# ------------------------------------------------------------------ report.md
def build_report(run, brief, client_name):
    refs = run["references"]
    byid = {r["id"]: r for r in refs}
    L = [f"# Reference scout report: {display_title(run, brief, client_name)}", "",
         f"**Question:** {run['run'].get('question', '')}", ""]
    if brief:
        L += ["| Brief | |", "|---|---|"] + [f"| {k.title()} | {brief[k] if isinstance(brief[k], str) else ', '.join(brief[k])} |"
                                             for k in ("objective", "audience", "moment", "channels", "competitors", "avoid") if brief.get(k)] + [""]
    rings = {k: sum(r["ring"] == k for r in refs) for k in RING_ORDER}
    L += ["## Summary", "",
          f"{len(refs)} references ({sum(r['status'] == 'verified' for r in refs)} verified against their live pages), "
          f"{sum(r.get('country') in GCC for r in refs)} from the GCC. Rings: "
          + ", ".join(f"{k} {v}" for k, v in rings.items()) + ".", ""]
    if run.get("patterns"):
        L += ["## Patterns", ""] + [f"- {p['pattern']} ({', '.join(byid[i]['brand'] for i in p['reference_ids'] if i in byid)})"
                                    for p in run["patterns"]] + [""]
    if run.get("white_space"):
        L += ["## White space", ""] + [f"- {w}" for w in run["white_space"]] + [""]
    L += ["## Creative territories", "", build_territories(run, brief, client_name).split("\n", 4)[-1].replace("\n## ", "\n### "), ""]
    if run.get("top"):
        L += ["## Deep dives", ""]
        for rid in run["top"]:
            r, td = byid[rid], byid[rid]["teardown"]
            L += [f"### {r['brand']}: {r['title']}", "", f"{meta_line(r)} · [{link_label(r)}]({primary_url(r)})", "",
                  f"- **Insight:** {td['insight']}", f"- **Idea:** {td['idea']}", f"- **Execution:** {td['execution']}"]
            for k in ("channels", "tone", "results"):
                if td.get(k):
                    L.append(f"- **{k.title()}:** {td[k]}")
            L += [f"- **What we can borrow:** " + "; ".join(td["transferable"]),
                  f"- **Saudi cultural fit ({td['cultural_fit']['score']}/5):** {td['cultural_fit']['notes']}"]
            if td.get("risks"):
                L.append("- **Risks:** " + "; ".join(td["risks"]))
            L.append("")
    L += ["## All references", ""]
    for ring in RING_ORDER:
        rs = [r for r in refs if r["ring"] == ring]
        if not rs:
            continue
        L += [f"### {RING_LABEL[ring]}", "", "| Brand | Campaign | Agency · country · year | Idea | Link |", "|---|---|---|---|---|"]
        L += [f"| {r['brand']} | {r['title']} | {meta_line(r)} | {r['card']['idea']} | [{link_label(r)}]({primary_url(r)}) |" for r in rs]
        L.append("")
    if run.get("open_questions"):
        L += ["## Open questions", ""] + [f"- {q}" for q in run["open_questions"]] + [""]
    L += ["---", f"*Method: searched {', '.join(run['run'].get('queries', [])[:8])}. Every link was checked against its live page.*"]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ board.html
BOARD_CSS = """
:root{--bg:#F6F4EF;--panel:#FFFFFF;--ink:#1E1C19;--muted:#6E675E;--line:#E4DED3;--accent:#9B4F1E;--chip:#EFEAE1;
--direct:#9B4F1E;--category:#2F6F62;--adjacent:#5B4B8A;--wildcard:#A3762A;--ok:#2F7D4F;
--disp:'Fraunces',Georgia,serif;--body:'IBM Plex Sans','IBM Plex Sans Arabic',system-ui,sans-serif;--ar:'IBM Plex Sans Arabic','IBM Plex Sans',sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161513;--panel:#201E1B;--ink:#EDE8E0;--muted:#A79F94;--line:#36322C;--accent:#E0965F;--chip:#2A2724;
--direct:#E0965F;--category:#79C2AF;--adjacent:#ABA0DD;--wildcard:#E2B663;--ok:#6CC08E;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#161513;--panel:#201E1B;--ink:#EDE8E0;--muted:#A79F94;--line:#36322C;--accent:#E0965F;--chip:#2A2724;
--direct:#E0965F;--category:#79C2AF;--adjacent:#ABA0DD;--wildcard:#E2B663;--ok:#6CC08E;color-scheme:dark}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 var(--body)}
.wrap{max-width:1240px;margin:0 auto;padding-inline:20px;padding-block:36px 64px;display:grid;gap:44px}
h1{font:600 clamp(26px,3.6vw,38px)/1.15 var(--disp);margin:0;text-wrap:balance} h2{font:600 22px/1.25 var(--disp);margin:0 0 14px}
.eyebrow{font:600 11px/1 var(--body);letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:10px}
.lede{color:var(--muted);max-width:75ch;margin:8px 0 0} .ar{font-family:var(--ar);direction:rtl}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px} .stat{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px 14px}
.stat b{font-size:20px;font-variant-numeric:tabular-nums;display:block}.stat span{color:var(--muted);font-size:12px}
.terr{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.tcard{background:var(--panel);border:1px solid var(--line);border-top:3px solid var(--accent);border-radius:6px;padding:18px;display:grid;gap:10px;align-content:start}
.tcard h3{margin:0;font:600 19px/1.25 var(--disp)} .tcard .ar{color:var(--muted);font-size:15px}
.tcard p{margin:0} .tcard small{color:var(--muted)} .strip{display:flex;gap:6px;flex-wrap:wrap}
.strip a{display:block;width:72px;aspect-ratio:4/3;border-radius:3px;overflow:hidden;background:var(--chip)} .strip img{width:100%;height:100%;object-fit:cover}
ul.tight{margin:0;padding-left:18px;display:grid;gap:4px;font-size:14px}
.dive{display:grid;grid-template-columns:minmax(0,320px) minmax(0,1fr);gap:20px;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:18px}
.dive img{width:100%;border-radius:4px;display:block} .dive dl{margin:0;display:grid;grid-template-columns:130px 1fr;gap:6px 14px;font-size:14px}
.dive dt{color:var(--muted);font-weight:600}.dive dd{margin:0} .dives{display:grid;gap:14px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px} .box{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:16px}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px} .filters button{font:500 13px var(--body);border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:20px;padding:5px 12px;cursor:pointer}
.filters button[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)} .filters button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:6px;overflow:hidden;display:flex;flex-direction:column}
.card .img{aspect-ratio:16/10;background:var(--chip)} .card .img img{width:100%;height:100%;object-fit:cover;display:block}
.card .body{padding:12px 14px 14px;display:grid;gap:6px;flex:1;align-content:start} .card h4{margin:0;font-size:15px;line-height:1.3}
.card .brand{font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)} .card .meta{font-size:12px;color:var(--muted)}
.card p{margin:0;font-size:14px} .card .why{color:var(--muted);font-size:13px} .card a.go{font-size:13px;font-weight:600;color:var(--accent);text-decoration:none;margin-top:4px}
.badges{display:flex;gap:6px;flex-wrap:wrap} .badge{font-size:11px;font-weight:600;padding:2px 8px;border-radius:10px;background:var(--chip);color:var(--ink)}
.badge.ring{color:#fff} .ring-direct{background:var(--direct)}.ring-category{background:var(--category)}.ring-adjacent{background:var(--adjacent)}.ring-wildcard{background:var(--wildcard)}
.badge.ok{color:var(--ok)} .card[hidden]{display:none!important}
footer{color:var(--muted);font-size:13px;border-top:1px solid var(--line);padding-top:16px}
@media (max-width:760px){.dive{grid-template-columns:1fr}.two{grid-template-columns:1fr}.dive dl{grid-template-columns:1fr}}
"""

BOARD_JS = """
const state={ring:'all',region:'all'};
function apply(){document.querySelectorAll('.card').forEach(c=>{
 const okR=state.ring==='all'||c.dataset.ring===state.ring; const okG=state.region==='all'||c.dataset.region===state.region;
 c.hidden=!(okR&&okG);});
 const n=[...document.querySelectorAll('.card')].filter(c=>!c.hidden).length; document.getElementById('count').textContent=n;}
document.querySelectorAll('.filters button').forEach(b=>b.addEventListener('click',()=>{
 const k=b.dataset.k; state[k]=b.dataset.v; document.querySelectorAll(`.filters button[data-k="${k}"]`).forEach(x=>x.setAttribute('aria-pressed',x===b));apply();}));
apply();
"""


def build_board(run, brief, client_name, thumbs_dir):
    refs = run["references"]
    byid = {r["id"]: r for r in refs}
    img = {}
    for r in refs:
        b = thumb_bytes(r, thumbs_dir)
        img[r["id"]] = "data:image/jpeg;base64," + base64.b64encode(b).decode() if b else ""

    def pic(r, cls=""):
        return f'<img src="{img[r["id"]]}" alt="{E(r["brand"])}: {E(r["title"])}" loading="lazy"{cls}>' if img[r["id"]] else ""

    terr = ""
    for t in run.get("territories", []):
        strip = "".join(f'<a href="#ref-{rid}" title="{E(byid[rid]["brand"])}: {E(byid[rid]["title"])}">{pic(byid[rid])}</a>'
                        for rid in t["reference_ids"] if rid in byid)
        extra = "".join(f'<div><small>{lab}</small><ul class="tight">{"".join(f"<li>{E(x)}</li>" for x in t[k])}</ul></div>'
                        for k, lab in (("example_executions", "Example executions"), ("risks", "Watch-outs")) if t.get(k))
        terr += (f'<article class="tcard"><div><h3>{E(t["name"])}</h3>'
                 + (f'<div class="ar">{E(t["name_ar"])}</div>' if t.get("name_ar") else "")
                 + f'</div><p>{E(t["thesis"])}</p>' + (f'<p><small>Why Rawaq: </small>{E(t["why_this_client"])}</p>'.replace("Rawaq", E(client_name.split()[0]) if client_name else "this client") if t.get("why_this_client") else "")
                 + f'<div class="strip">{strip}</div>{extra}</article>')
    dives = ""
    for rid in run.get("top", []):
        r, td = byid[rid], byid[rid]["teardown"]
        rows = [("Insight", td["insight"]), ("Idea", td["idea"]), ("Execution", td["execution"])]
        rows += [(k.title(), td[k]) for k in ("channels", "tone", "results") if td.get(k)]
        rows += [("Borrow", "; ".join(td["transferable"])), (f"Saudi fit {td['cultural_fit']['score']}/5", td["cultural_fit"]["notes"])]
        if td.get("risks"):
            rows.append(("Risks", "; ".join(td["risks"])))
        dives += (f'<article class="dive" id="dive-{rid}"><div>{pic(r)}<p class="meta" style="margin:8px 0 0">'
                  f'<b>{E(r["brand"])}</b>: {E(r["title"])}<br><small>{E(meta_line(r))}</small><br>'
                  f'<a href="{E(primary_url(r))}" target="_blank" rel="noopener">{link_label(r)} ↗</a></p></div>'
                  f'<dl>{"".join(f"<dt>{E(k)}</dt><dd>{E(v)}</dd>" for k, v in rows)}</dl></article>')
    cards = ""
    for ring in RING_ORDER:
        for r in [x for x in refs if x["ring"] == ring]:
            region = "gcc" if r.get("country") in GCC else "other"
            cards += (f'<article class="card" id="ref-{r["id"]}" data-ring="{ring}" data-region="{region}">'
                      f'<div class="img">{pic(r)}</div><div class="body"><div class="badges"><span class="badge ring ring-{ring}">{ring}</span>'
                      + ('<span class="badge ok">✓ verified</span>' if r["status"] == "verified" else '<span class="badge">unverified</span>')
                      + (f'<span class="badge">top pick</span>' if r["id"] in run.get("top", []) else "")
                      + f'</div><div class="brand">{E(r["brand"])}</div><h4>{E(r["title"])}</h4><div class="meta">{E(meta_line(r))}</div>'
                      f'<p>{E(r["card"]["idea"])}</p><p class="why">{E(r["card"]["why_relevant"])}</p>'
                      f'<a class="go" href="{E(primary_url(r))}" target="_blank" rel="noopener">{link_label(r)} ↗</a></div></article>')
    ring_btns = "".join(f'<button data-k="ring" data-v="{k}" aria-pressed="false">{k.title()} ({sum(r["ring"] == k for r in refs)})</button>'
                        for k in RING_ORDER if any(r["ring"] == k for r in refs))
    patterns = "".join(f"<li>{E(p['pattern'])}</li>" for p in run.get("patterns", []))
    white = "".join(f"<li>{E(w)}</li>" for w in run.get("white_space", []))
    brief_bits = " · ".join(E(brief[k]) for k in ("moment", "objective", "audience") if brief and brief.get(k))
    n_ver = sum(r["status"] == "verified" for r in refs)
    title = display_title(run, brief, client_name)
    return f"""<title>{E(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Sans+Arabic:wght@400;600&display=swap">
<style>{BOARD_CSS}</style>
<div class="wrap">
<header><div class="eyebrow">Reference scout · {E(run['run']['mode'])} · {E(run['run'].get('created', ''))}</div>
<h1>{E(display_title(run, brief, client_name))}</h1><p class="lede">{brief_bits}</p>
<div class="stats"><div class="stat"><b>{len(refs)}</b><span>references</span></div><div class="stat"><b>{n_ver}</b><span>verified live</span></div>
<div class="stat"><b>{sum(r.get('country') in GCC for r in refs)}</b><span>from the GCC</span></div><div class="stat"><b>{len(run.get('territories', []))}</b><span>territories</span></div></div></header>
<section><h2>Creative territories</h2><div class="terr">{terr}</div></section>
<section class="two"><div class="box"><h2>Patterns</h2><ul class="tight">{patterns}</ul></div><div class="box"><h2>White space</h2><ul class="tight">{white}</ul></div></section>
{f'<section><h2>Deep dives</h2><div class="dives">{dives}</div></section>' if dives else ''}
<section><h2>All references (<span id="count">{len(refs)}</span>)</h2>
<div class="filters" role="toolbar" aria-label="Filter references"><button data-k="ring" data-v="all" aria-pressed="true">All rings</button>{ring_btns}
<span style="width:12px"></span><button data-k="region" data-v="all" aria-pressed="true">All regions</button><button data-k="region" data-v="gcc" aria-pressed="false">GCC</button><button data-k="region" data-v="other" aria-pressed="false">Rest of world</button></div>
<div class="grid">{cards}</div></section>
<footer>{''.join(f'<p>Open question: {E(q)}</p>' for q in run.get('open_questions', []))}
<p>Every reference links to its original page and was checked live. Thumbnails © their owners, internal reference use only. Generated by zamakan-reference-scout.</p></footer>
</div><script>{BOARD_JS}</script>"""


# ------------------------------------------------------------------ deck.pptx
def build_deck(run, brief, client_name, thumbs_dir, path):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Emu, Pt
    INK, MUTED, ACCENT, BG, PAPER = RGBColor(0x1E, 0x1C, 0x19), RGBColor(0x6E, 0x67, 0x5E), RGBColor(0x9B, 0x4F, 0x1E), \
        RGBColor(0xF6, 0xF4, 0xEF), RGBColor(0xFF, 0xFF, 0xFF)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
    W, H = prs.slide_width, prs.slide_height
    blank = prs.slide_layouts[6]
    refs = run["references"]
    byid = {r["id"]: r for r in refs}
    cm = lambda v: Emu(int(v * 360000))  # noqa: E731

    def slide(bg=BG):
        s = prs.slides.add_slide(blank)
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = bg
        return s

    def text(s, x, y, w, h, t, size=16, bold=False, color=INK, align=None, rtl=False, font="Arial"):
        tb = s.shapes.add_textbox(cm(x), cm(y), cm(w), cm(h))
        tf = tb.text_frame
        tf.word_wrap = True
        lines = t if isinstance(t, list) else [t]
        for i, line in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = line
            p.font.size, p.font.bold, p.font.color.rgb, p.font.name = Pt(size), bold, color, font
            if align or rtl:
                p.alignment = PP_ALIGN.RIGHT if rtl else align
        return tb

    def picture(s, r, x, y, w, h):
        b = thumb_bytes(r, thumbs_dir)
        if not b:
            box = s.shapes.add_shape(1, cm(x), cm(y), cm(w), cm(h))
            box.fill.solid()
            box.fill.fore_color.rgb = RGBColor(0xEF, 0xEA, 0xE1)
            box.line.fill.background()
            return
        from PIL import Image
        iw, ih = Image.open(io.BytesIO(b)).size
        scale = min(w / iw, h / ih)
        pw, ph = iw * scale, ih * scale
        s.shapes.add_picture(io.BytesIO(b), cm(x + (w - pw) / 2), cm(y + (h - ph) / 2), cm(pw), cm(ph))

    def link(s, x, y, r):
        tb = text(s, x, y, 12, 0.8, f"{link_label(r)} ↗", 11, True, ACCENT)
        tb.text_frame.paragraphs[0].runs[0].hyperlink.address = primary_url(r)

    # 1 title
    s = slide(INK)
    text(s, 2, 1.6, 26, 1, "REFERENCE SCOUT", 12, True, RGBColor(0xC9, 0xBF, 0xB2))
    text(s, 2, 2.6, 28, 6, display_title(run, brief, client_name), 34, True, PAPER)
    text(s, 2, 15.5, 28, 1.5, f"{client_name or ''} · {run['run'].get('created', '')}", 14, False, RGBColor(0xC9, 0xBF, 0xB2))
    # 2 brief + method
    s = slide()
    text(s, 2, 1.4, 28, 1.2, "The brief", 28, True)
    rows = [f"{k.title()}: {brief[k] if isinstance(brief[k], str) else ', '.join(brief[k])}"
            for k in ("objective", "audience", "moment", "channels", "competitors", "avoid") if brief and brief.get(k)]
    text(s, 2, 3.2, 16, 12, rows or [run["run"].get("question", "")], 14)
    n_ver = sum(r["status"] == "verified" for r in refs)
    rings = [f"{RING_LABEL[k]}: {sum(r['ring'] == k for r in refs)}" for k in RING_ORDER]
    text(s, 19.5, 3.2, 12, 1, "How we searched", 14, True, ACCENT)
    text(s, 19.5, 4.2, 12, 11, [f"{len(refs)} references, {n_ver} verified live", f"{sum(r.get('country') in GCC for r in refs)} from the GCC", ""] + rings, 13)
    # 3 patterns & white space
    s = slide()
    text(s, 2, 1.4, 28, 1.2, "What the category does, and what nobody does", 26, True)
    text(s, 2, 3.4, 14, 1, "Patterns", 14, True, ACCENT)
    text(s, 2, 4.4, 14, 12, [f"• {p['pattern']}" for p in run.get("patterns", [])], 14)
    text(s, 17.5, 3.4, 14, 1, "White space", 14, True, ACCENT)
    text(s, 17.5, 4.4, 14, 12, [f"• {w}" for w in run.get("white_space", [])], 14)
    # territories
    for i, t in enumerate(run.get("territories", []), 1):
        s = slide()
        text(s, 2, 1.2, 20, 0.8, f"TERRITORY {i}", 11, True, ACCENT)
        text(s, 2, 2.0, 16.5, 1.6, t["name"], 30, True)
        if t.get("name_ar"):
            text(s, 2, 3.5, 16.5, 1.4, t["name_ar"], 22, True, MUTED, rtl=True)
        text(s, 2, 5.2, 16, 3.4, t["thesis"], 18)
        body = []
        if t.get("why_this_client"):
            body += [f"Why: {t['why_this_client']}", ""]
        body += [f"• {x}" for x in t.get("example_executions", [])]
        body += [f"⚠ {x}" for x in t.get("risks", [])]
        text(s, 2, 9.0, 16, 8.5, body, 13, color=MUTED)
        rs = [byid[rid] for rid in t["reference_ids"] if rid in byid][:3]
        for j, r in enumerate(rs):
            y = 1.4 + j * 5.6
            picture(s, r, 19.5, y, 6.6, 4.4)
            text(s, 26.4, y, 5.6, 3.2, [r["brand"], r["title"]], 11, False, INK)
            link(s, 26.4, y + 3.4, r)
    # deep dives
    for rid in run.get("top", []):
        r, td = byid[rid], byid[rid]["teardown"]
        s = slide()
        text(s, 2, 1.2, 18, 0.8, "DEEP DIVE", 11, True, ACCENT)
        text(s, 2, 2.0, 18, 2.2, f"{r['brand']}: {r['title']}", 24, True)
        text(s, 2, 4.0, 18, 0.8, meta_line(r), 12, False, MUTED)
        rows = [f"Insight: {td['insight']}", f"Idea: {td['idea']}", f"Execution: {td['execution']}",
                "Borrow: " + "; ".join(td["transferable"]), f"Saudi fit {td['cultural_fit']['score']}/5: {td['cultural_fit']['notes']}"]
        text(s, 2, 5.2, 17.5, 13, rows, 13)
        picture(s, r, 20.5, 2.0, 11.5, 8.5)
        link(s, 20.5, 10.8, r)
    # reference grid (6 per slide)
    ordered = [r for k in RING_ORDER for r in refs if r["ring"] == k]
    for i in range(0, len(ordered), 6):
        s = slide()
        text(s, 2, 1.0, 28, 1.2, "All references" + (f" ({i // 6 + 1})" if len(ordered) > 6 else ""), 22, True)
        for j, r in enumerate(ordered[i:i + 6]):
            x, y = 2 + (j % 3) * 10.2, 3.0 + (j // 3) * 7.6
            picture(s, r, x, y, 9.4, 4.2)
            text(s, x, y + 4.3, 9.4, 2.4, [f"{r['brand']}: {r['title']}", f"{r['ring']} · {meta_line(r)}"], 10)
            link(s, x, y + 6.5, r)
    if run.get("open_questions"):
        s = slide()
        text(s, 2, 1.4, 28, 1.2, "Open questions", 26, True)
        text(s, 2, 3.4, 28, 12, [f"• {q}" for q in run["open_questions"]], 16)
    prs.save(path)
    return path


def to_pdf(pptx_path):
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return None
    out = Path(pptx_path).parent
    r = subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", str(out), str(pptx_path)],
                       capture_output=True, text=True, timeout=180)
    pdf = out / (Path(pptx_path).stem + ".pdf")
    return str(pdf) if r.returncode == 0 and pdf.exists() else None


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("references")
    ap.add_argument("--out", required=True)
    ap.add_argument("--formats", default="board")
    ap.add_argument("--brief")
    ap.add_argument("--client-name")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    run, warnings = load_run(a.references)
    brief = json.loads(Path(a.brief).read_text(encoding="utf-8")) if a.brief else None
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    thumbs = out / "thumbs"
    made = []
    (out / "territories.md").write_text(build_territories(run, brief, a.client_name), encoding="utf-8")
    made.append("territories.md")
    fmts = {f.strip() for f in a.formats.split(",") if f.strip()}
    if "report" in fmts:
        (out / "report.md").write_text(build_report(run, brief, a.client_name), encoding="utf-8")
        made.append("report.md")
    if "board" in fmts:
        (out / "board.html").write_text(build_board(run, brief, a.client_name, thumbs), encoding="utf-8")
        made.append("board.html")
    if "deck" in fmts:
        build_deck(run, brief, a.client_name, thumbs, out / "deck.pptx")
        made.append("deck.pptx")
        if not a.no_pdf:
            pdf = to_pdf(out / "deck.pptx")
            made.append("deck.pdf" if pdf else "(deck.pdf skipped: LibreOffice not available)")
    print(f"built in {out}: {', '.join(made)}")
    for w in warnings:
        print("  warn", w)


if __name__ == "__main__":
    main()
