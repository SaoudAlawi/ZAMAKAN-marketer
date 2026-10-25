#!/usr/bin/env python3
"""From a story idea to a template shaped around it. The writer sends their general story (typed or a voice-note
transcript); Claude writes a small story_map.json (the writer's own words placed on a structure's beats, what is still
open as questions, the gaps); this builds:
  <title>-story-template.docx   the planning template around their story (Word, right to left for Arabic)
  <title>-story-map.html/.pdf   the same on one page: beats with the writer's fragments, gaps in amber

Usage:
  python story_template.py story_map.json --check                 # validate (quotes must be the writer's exact words)
  python story_template.py story_map.json --out <dir> [--no-pdf]

Colour code (also printed in the files): blue = the writer's words, grey = our questions, amber = not in the story yet.
"""
import argparse
import html
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _screenplay as S  # noqa: E402
import build_template as B  # noqa: E402

E = html.escape
BLUE, AMBER = "DBE8FB", "FDECC8"
ELEMENT = {"ar": {"hero": "البطل", "want": "ما يريده", "obstacle": "ما يقف في الطريق", "turn": "نقطة التحوّل", "ending": "النهاية",
                  "world": "العالم", "tone": "النبرة", "theme": "المعنى", "other": "أخرى"},
           "en": {"hero": "Protagonist", "want": "What they want", "obstacle": "What stands in the way", "turn": "The turn",
                  "ending": "The ending", "world": "The world", "tone": "Tone", "theme": "Meaning", "other": "Other"}}
T = {"ar": {"built": "مبني على فكرة قصتك", "yours": "قصتك بكلماتك", "yours_hint": "كما أرسلتها، دون أي تغيير.",
            "heard": "ما سمعناه، وما زال مفتوحاً", "cols": ["", "ما قلته", "ما زال مفتوحاً"], "gap": "— (لم تذكره قصتك بعد)",
            "fits": "البناء الذي يناسب قصتك", "alt": "بديل", "beats": "محطة بمحطة", "from_you": "من قصتك؟", "belongs": "هل مكانه هنا؟",
            "empty": "قصتك لا تقول هذا بعد.", "scenes": "مشاهد تقريباً", "chars": "الشخصيات التي ذكرتها", "char_cols": ["الشخصية", "تريد", "تخاف", "العيب", "كيف تتغيّر"],
            "places": "الأماكن وما يرفع الكلفة", "legend": "الألوان: الأزرق = كلماتك · الرمادي = أسئلتنا · الأصفر = ما لم تقله قصتك بعد",
            "promise": "لم نكتب شيئاً من قصتك: كل ما بالأزرق كلماتك، وكل ما أضفناه أسئلة.", "pages": "صفحات", "min": "دقيقة",
            "map": "خريطة القصة", "map_sub": "محطات البناء، وكلماتك في المكان الذي يبدو أنها تنتمي إليه، والفراغات بالأصفر."},
     "en": {"built": "Built on your story idea", "yours": "Your story, in your words", "yours_hint": "As you sent it, unchanged.",
            "heard": "What we heard, and what's still open", "cols": ["", "What you said", "Still open"], "gap": "— (not in your story yet)",
            "fits": "The structure that fits your story", "alt": "Alternative", "beats": "Beat by beat", "from_you": "From your story?", "belongs": "Does it belong here?",
            "empty": "Your story doesn't say this yet.", "scenes": "scenes, roughly", "chars": "The characters you mentioned", "char_cols": ["Character", "Wants", "Fears", "Flaw", "How they change"],
            "places": "Places and what drives cost", "legend": "Colours: blue = your words · grey = our questions · amber = not in your story yet",
            "promise": "We wrote nothing of your story: everything in blue is yours, everything we added is a question.", "pages": "pages", "min": "min",
            "map": "Story map", "map_sub": "The structure's beats, your words where they seem to belong, the gaps in amber."}}


def norm(t):
    return re.sub(r"[ً-ْـ\s«»\"'“”.,،:!?؟…\-]+", "", t or "").lower()


def check(sm):
    import jsonschema
    errs, warns = [], []
    schema = json.loads((S.SKILL / "schemas" / "story_map.schema.json").read_text(encoding="utf-8"))
    for e in jsonschema.Draft202012Validator(schema).iter_errors(sm):
        errs.append(f"schema: {'/'.join(map(str, e.path))}: {e.message[:140]}")
    if errs:
        return errs, warns
    story = norm(sm["story"])
    st = next((x for x in S.STRUCTURES["structures"] if x["id"] == sm["structure"]), None)
    if not st:
        return [f"unknown structure {sm['structure']}"], warns
    if sm.get("alt_structure") and not any(x["id"] == sm["alt_structure"]["id"] for x in S.STRUCTURES["structures"]):
        errs.append(f"unknown alternative structure {sm['alt_structure']['id']}")
    quotes = [("heard", h.get("quote")) for h in sm["heard"]] + [(f"beat {b}", q) for b, v in sm["beats"].items() for q in v.get("fragments", [])] + \
             [("character", c.get("quote")) for c in sm.get("characters", [])] + [("place", p.get("quote")) for p in sm.get("places", [])]
    for where, q in quotes:
        if q and norm(q) not in story:
            errs.append(f"{where}: «{q[:50]}» is not the writer's words (quote exactly, or leave it out)")
    ids = {b["id"] for b in st["beats"]}
    for b in sm["beats"]:
        if b not in ids:
            errs.append(f"beat '{b}' is not in {sm['structure']} ({', '.join(ids)})")
    qs = [h["open_question"] for h in sm["heard"]] + [q for v in sm["beats"].values() for q in v.get("questions", [])]
    for q in qs:
        if not re.search(r"[؟?]\s*$", q.strip()):
            warns.append(f"not a question: «{q[:60]}» (everything we add is a question)")
    gaps = [b["id"] for b in st["beats"] if not sm["beats"].get(b["id"], {}).get("fragments")]
    if not gaps:
        warns.append("no gaps at all: check you haven't stretched the story's words to fill every beat")
    return errs, warns


def scene_counts(st, minutes, kind):
    """A rough number of scenes per beat (a short runs about one scene per 1.2 minutes, a feature one per 2)."""
    total = max(len(st["beats"]), round(minutes / (1.2 if kind == "short" else 2.0)))
    return {b["id"]: max(1, round(total * (b["end"] - b["at"]) / 100)) for b in st["beats"]}


def shade(p, hex_):
    p._p.get_or_add_pPr().append(S._el("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": hex_}))


def build_docx(sm):
    lang = sm["lang"]
    ar = lang == "ar"
    t = T[lang]
    st = next(x for x in S.STRUCTURES["structures"] if x["id"] == sm["structure"])
    doc = S.new_document(lang)
    for _ in range(8):
        doc.add_paragraph()
    p = B.para(doc, sm.get("title") or ("فيلمي" if ar else "MY FILM"), lang, size=22, bold=True)
    p.alignment = 1
    q = B.para(doc, f"{t['built']} · {S.digits(sm['minutes'], lang)} {t['min']}", lang, grey=True)
    q.alignment = 1
    S.page_break(doc)
    S.add_page_numbers(doc, lang)
    B.para(doc, t["promise"], lang, grey=True, italic=True, size=10)
    B.para(doc, t["legend"], lang, grey=True, size=10)
    # 1. the story, untouched
    B.para(doc, t["yours"], lang, style="Heading 1")
    B.para(doc, t["yours_hint"], lang, grey=True, size=10)
    for chunk in [c for c in sm["story"].split("\n") if c.strip()]:
        shade(B.para(doc, chunk.strip(), lang), BLUE)
    # 2. what we heard
    B.para(doc, t["heard"], lang, style="Heading 1")
    rows = [t["cols"]] + [[ELEMENT[lang][h["element"]], f"«{h['quote']}»" if h.get("quote") else t["gap"], h["open_question"]] for h in sm["heard"]]
    tb = B.table(doc, rows, lang)
    widths = (1.2, 2.1, 2.5)  # element narrow, the writer's words and the open question wide
    tb.autofit = False
    tb._tbl.tblPr.append(S._el("w:tblLayout", **{"w:type": "fixed"}))
    for gc, w in zip(tb._tbl.tblGrid.findall(S.qn("w:gridCol")), widths):
        gc.set(S.qn("w:w"), str(int(w * 1440)))
    for i, h in enumerate(sm["heard"], 1):
        tb.cell(i, 1)._tc.get_or_add_tcPr().append(S._el("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": BLUE if h.get("quote") else AMBER}))
        for r in tb.cell(i, 2).paragraphs[0].runs:
            r.font.color.rgb = B.GREY
    # 3. structure
    B.para(doc, t["fits"], lang, style="Heading 1")
    B.para(doc, st["name_ar"] if ar else st["name"], lang, bold=True, size=13)
    B.para(doc, sm["why_structure"], lang)
    if sm.get("alt_structure"):
        alt = next(x for x in S.STRUCTURES["structures"] if x["id"] == sm["alt_structure"]["id"])
        B.para(doc, f"{t['alt']}: {alt['name_ar'] if ar else alt['name']}: {sm['alt_structure']['why']}", lang, grey=True)
    counts = scene_counts(st, sm["minutes"], sm["kind"])
    trows = [B.T[lang]["tcols"][:2] + [t["scenes"]]]
    for b in st["beats"]:
        a, z = B.beat_pages(b, sm["minutes"])
        trows.append([b["name_ar"] if ar else b["name"], f"{S.digits(a, lang)}–{S.digits(z, lang)}", f"≈ {S.digits(counts[b['id']], lang)}"])
    B.table(doc, trows, lang)
    S.page_break(doc)
    # 4. beat by beat
    B.para(doc, t["beats"], lang, style="Heading 1")
    for b in st["beats"]:
        a, z = B.beat_pages(b, sm["minutes"])
        mine = sm["beats"].get(b["id"], {})
        B.para(doc, f"{b['name_ar'] if ar else b['name']}  ({t['pages']} {S.digits(a, lang)}–{S.digits(z, lang)} · ≈ {S.digits(counts[b['id']], lang)} {t['scenes']})",
               lang, style="Heading 2")
        B.para(doc, b["purpose_ar"] if ar else b["purpose"], lang, italic=True, grey=True)
        if mine.get("fragments"):
            B.para(doc, f"{t['from_you']} ({t['belongs']})", lang, bold=True, size=10)
            for f in mine["fragments"]:
                shade(B.para(doc, f"«{f}»", lang), BLUE)
        else:
            shade(B.para(doc, t["empty"], lang, bold=True), AMBER)
        for qq in mine.get("questions") or (b["questions_ar"] if ar else b["questions"]):
            B.para(doc, qq, lang, style="List Bullet", grey=True)
        B.write_box(doc, lang)
    # 5. characters and places
    B.para(doc, t["chars"], lang, style="Heading 1")
    chars = sm.get("characters") or []
    B.table(doc, [t["char_cols"]] + [[c["name"]] + [""] * 4 for c in chars] + [[""] * 5], lang)
    if sm.get("places"):
        B.para(doc, t["places"], lang, style="Heading 1")
        for pl in sm["places"]:
            pp = B.para(doc, pl["place"] + (f"  «{pl['quote']}»" if pl.get("quote") else ""), lang, bold=True)
            shade(pp, BLUE)
            if pl.get("cost_note"):
                B.para(doc, pl["cost_note"], lang, grey=True, style="List Bullet")
    # 6. draft section
    S.page_break(doc)
    B.para(doc, B.T[lang]["draft_title"], lang, style="Heading 1")
    B.para(doc, B.T[lang]["draft_hint"], lang, grey=True, italic=True)
    for kind, text in B.T[lang]["samples"]:
        S.add_element(doc, kind, text, lang)
    return doc


def build_map(sm):
    lang = sm["lang"]
    ar = lang == "ar"
    t = T[lang]
    st = next(x for x in S.STRUCTURES["structures"] if x["id"] == sm["structure"])
    counts = scene_counts(st, sm["minutes"], sm["kind"])
    cols = []
    for b in st["beats"]:
        a, z = B.beat_pages(b, sm["minutes"])
        mine = sm["beats"].get(b["id"], {})
        frags = "".join(f'<div class="frag">«{E(f)}»</div>' for f in mine.get("fragments", [])) or f'<div class="gap">{E(t["empty"])}</div>'
        qs = "".join(f"<li>{E(q)}</li>" for q in (mine.get("questions") or [])[:2])
        cols.append(f'<div class="beat" style="flex:{max(b["end"] - b["at"], 8)}"><div class="bh"><b>{E(b["name_ar"] if ar else b["name"])}</b>'
                    f'<span>{t["pages"]} {S.digits(a, lang)}–{S.digits(z, lang)} · ≈{S.digits(counts[b["id"]], lang)}</span></div>{frags}<ul>{qs}</ul></div>')
    title = sm.get("title") or ""
    css = """:root{--bg:#fcfcfb;--ink:#1d1b18;--muted:#5e5a53;--card:#fff;--line:#e4dfd5;--blue:#dbe8fb;--amber:#fdecc8}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme=light])){--bg:#1a1a19;--ink:#f0efec;--muted:#c3c2b7;--card:#222220;--line:#3a3935;--blue:#1f3550;--amber:#4a3a12}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.6 "IBM Plex Sans Arabic","Amiri",system-ui,sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:24px 16px 40px}h1{font-size:26px;margin:0}.sub{color:var(--muted);margin:2px 0 14px}
.story{background:var(--blue);border-radius:10px;padding:10px 14px;margin-bottom:14px}.legend{font-size:12.5px;color:var(--muted);margin-bottom:10px}
.lane{display:flex;gap:8px;align-items:stretch}.beat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 10px;min-width:0}
.bh{display:flex;flex-direction:column;margin-bottom:6px}.bh span{font-size:11.5px;color:var(--muted)}
.frag{background:var(--blue);border-radius:6px;padding:4px 7px;margin:4px 0;font-size:13px}.gap{background:var(--amber);border-radius:6px;padding:4px 7px;margin:4px 0;font-size:13px;font-weight:700}
ul{margin:4px 0 0;padding-inline-start:16px;color:var(--muted);font-size:12.5px}
@media (max-width:760px){.lane{flex-direction:column}}@page{size:A4 landscape;margin:10mm}"""
    st_name = st["name_ar"] if ar else st["name"]
    return (f'<!doctype html><html lang="{lang}" dir="{"rtl" if ar else "ltr"}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{E(title)} · {t["map"]}</title><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;700&display=swap" rel="stylesheet">'
            f'<style>{css}</style></head><body><div class="wrap"><h1>{E(title)} · {t["map"]}</h1><p class="sub">{E(st_name)} · {S.digits(sm["minutes"], lang)} {t["min"]} · {E(sm["why_structure"])}</p>'
            f'<div class="story">{E(sm["story"])}</div><div class="legend">{E(t["legend"])}</div><div class="lane">{"".join(cols)}</div></div></body></html>')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("story_map")
    ap.add_argument("--out", default=".")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    sm = json.loads(Path(a.story_map).read_text(encoding="utf-8"))
    errs, warns = check(sm)
    for w in warns:
        print("  warn ", w)
    for e in errs:
        print("  ERROR", e)
    if errs:
        sys.exit(1)
    st = next(x for x in S.STRUCTURES["structures"] if x["id"] == sm["structure"])
    gaps = [b["id"] for b in st["beats"] if not sm["beats"].get(b["id"], {}).get("fragments")]
    print(f"OK: {sm['structure']} · {len(sm['heard'])} elements heard · gaps: {', '.join(gaps) or 'none'}")
    if a.check:
        return
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^\w؀-ۿ-]+", "-", sm.get("title") or "story").strip("-") or "story"
    docx = out / f"{stem}-story-template.docx"
    build_docx(sm).save(docx)
    page = out / f"{stem}-story-map.html"
    page.write_text(build_map(sm), encoding="utf-8")
    print(f"template → {docx}\nstory map → {page}")
    if not a.no_pdf:
        from side_notes import to_pdf
        print(f"PDF → {to_pdf(page)}")


if __name__ == "__main__":
    main()
