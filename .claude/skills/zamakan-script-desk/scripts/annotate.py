#!/usr/bin/env python3
"""Check the reader's notes, then write the writer's copy: the formatted script in Word with a notes page up front
(overall verdict, one coloured row per viewpoint, priorities, questions) and a margin comment on each note's scene,
the anchored text shaded in that viewpoint's colour. Notes are questions and observations, never rewrites.

Usage:
  python annotate.py script.json notes.json --out <dir> [--name my-film-notes] [--stats stats.json]
  python annotate.py script.json notes.json --check        # validate only

Checks (exit 1 on errors): schema; every viewpoint in references/lenses.json has a verdict; every amber/red viewpoint
has at least one note; note scenes exist; quotes are found in their scene; notes that look like rewritten dialogue
(long quoted lines not in the script) are flagged.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _screenplay as S  # noqa: E402
import format_script as F  # noqa: E402

LENSES = json.loads((S.SKILL / "references" / "lenses.json").read_text(encoding="utf-8"))
LENS = {x["id"]: x for x in LENSES["lenses"]}
VERDICT = LENSES["verdicts"]
UI = {"ar": {"notes": "ملاحظات القراءة", "story": "القصة كما فهمناها", "overall": "الحكم العام", "lens": "زاوية القراءة", "verdict": "الحكم",
             "summary": "الخلاصة", "next": "أولويات المسودة القادمة", "questions": "أسئلة للكاتب", "legend": "ألوان الملاحظات في الهامش",
             "author": "قارئ زمكان", "kinds": {"issue": "ملاحظة", "question": "سؤال", "strength": "نقطة قوة"},
             "promise": "هذه ملاحظات وأسئلة لمساعدتك على الكتابة، لا إعادة كتابة لنصك."},
      "en": {"notes": "Reader's notes", "story": "The story as we read it", "overall": "Overall", "lens": "Viewpoint", "verdict": "Verdict",
             "summary": "Summary", "next": "Priorities for the next draft", "questions": "Questions for the writer", "legend": "Margin comment colours",
             "author": "ZAMAKAN reader", "kinds": {"issue": "Note", "question": "Question", "strength": "Strength"},
             "promise": "These are notes and questions to help you write, not a rewrite of your script."}}


def norm(t):
    return re.sub(r"[ً-ْـ\s«»\"'“”.,،:!?؟…-]+", "", t or "")


def check(sc, notes):
    import jsonschema
    errs, warns = [], []
    schema = json.loads((S.SKILL / "schemas" / "notes.schema.json").read_text(encoding="utf-8"))
    for e in jsonschema.Draft202012Validator(schema).iter_errors(notes):
        errs.append(f"schema: {'/'.join(map(str, e.path))}: {e.message[:140]}")
    if errs:
        return errs, warns
    have = {x["id"]: x for x in notes["lenses"]}
    for lid in LENS:
        if lid not in have:
            errs.append(f"lens '{lid}' has no verdict (every viewpoint gets one, even green)")
    for lid in have:
        if lid not in LENS:
            errs.append(f"unknown lens '{lid}' (use: {', '.join(LENS)})")
    nscenes = len(sc["scenes"])
    scene_text = {}
    for e in sc["elements"]:
        if e.get("scene"):
            scene_text[e["scene"]] = scene_text.get(e["scene"], "") + " " + e["text"]
    for i, n in enumerate(notes["notes"]):
        if n["lens"] not in LENS:
            errs.append(f"note {i}: unknown lens '{n['lens']}'")
        if not 1 <= n["scene"] <= nscenes:
            errs.append(f"note {i}: scene {n['scene']} does not exist (1-{nscenes})")
            continue
        if n.get("quote") and norm(n["quote"]) not in norm(scene_text.get(n["scene"], "")):
            errs.append(f"note {i}: quote not found in scene {n['scene']}: {n['quote'][:50]!r}")
        for q in re.findall(r"[«\"“]([^»\"”]{40,})[»\"”]", n["text"]):
            if norm(q) not in norm(" ".join(scene_text.values())):
                warns.append(f"note {i}: quotes a long line that is not in the script; ask a question instead of rewriting: {q[:50]!r}")
    for lid, x in have.items():
        if x["verdict"] in ("amber", "red") and not any(n["lens"] == lid and n["kind"] != "strength" for n in notes["notes"]):
            errs.append(f"lens '{lid}' is {x['verdict']} but has no note pointing to a scene")
    if not any(n["kind"] == "strength" for n in notes["notes"]) and not any(x.get("strengths") for x in notes["lenses"]):
        warns.append("no strengths noted: say what works, too")
    return errs, warns


def tint(hex_, k=0.78):
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "{:02X}{:02X}{:02X}".format(*(round(c + (255 - c) * k) for c in (r, g, b)))


def shade_runs(p, hex_):
    for r in p.runs:
        rpr = r._r.get_or_add_rPr()
        rpr.append(S._el("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": tint(hex_)}))


def cell_text(cell, text, lang, bold=False, fill=None, color=None):
    p = cell.paragraphs[0]
    if lang == "ar":
        p._p.get_or_add_pPr().append(S._el("w:bidi"))
    r = p.add_run(text)
    r.bold = bold or None
    if color:
        r.font.color.rgb = S.RGBColor.from_string(color.lstrip("#"))
    if lang == "ar":
        r._r.get_or_add_rPr().append(S._el("w:rtl"))
    if fill:
        cell._tc.get_or_add_tcPr().append(S._el("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": fill.lstrip("#")}))


def para(doc, text, lang, style=None, bold=False, color=None, size=None):
    p = doc.add_paragraph(style=style)
    r = p.add_run(text)
    r.bold = bold or None
    if color:
        r.font.color.rgb = S.RGBColor.from_string(color.lstrip("#"))
    if size:
        r.font.size = S.Pt(size)
    if lang == "ar":
        p._p.get_or_add_pPr().append(S._el("w:bidi"))
        r._r.get_or_add_rPr().append(S._el("w:rtl"))
    return p


def notes_page(doc, sc, notes, lang):
    u = UI[lang]
    # insert the notes page before the script body: build it at the end, then move its elements to the front
    body = doc.element.body
    start = len(body) - (1 if body[-1].tag == S.qn("w:sectPr") else 0)  # new paragraphs go in before sectPr
    para(doc, u["notes"], lang, style="Heading 1")
    para(doc, u["promise"], lang, color="#777777", size=10)
    para(doc, u["story"], lang, style="Heading 3")
    para(doc, notes["logline_read"], lang)
    v = notes["overall"]["verdict"]
    para(doc, f"{u['overall']}: ● {VERDICT[v][lang]}", lang, bold=True, color=VERDICT[v]["hex"])
    para(doc, notes["overall"]["summary"], lang)
    t = doc.add_table(rows=1, cols=3)
    t.style = "Table Grid"
    pr = t._tbl.tblPr
    pr.append(S._el("w:tblW", **{"w:w": 5000, "w:type": "pct"}))
    if lang == "ar":
        pr.append(S._el("w:bidiVisual"))
    for c, h in zip(t.rows[0].cells, (u["lens"], u["verdict"], u["summary"])):
        cell_text(c, h, lang, bold=True)
    have = {x["id"]: x for x in notes["lenses"]}
    for lid, L in LENS.items():
        x = have.get(lid)
        if not x:
            continue
        row = t.add_row().cells
        cell_text(row[0], "■ " + (L["name_ar"] if lang == "ar" else L["name"]), lang, bold=True, color=L["hex"])
        cell_text(row[1], "● " + VERDICT[x["verdict"]][lang], lang, bold=True, color=VERDICT[x["verdict"]]["hex"])
        cell_text(row[2], x["summary"], lang)
    para(doc, u["next"], lang, style="Heading 3")
    for i, item in enumerate(notes["next_draft"], 1):
        para(doc, f"{S.digits(i, lang)}. {item}", lang)
    if notes.get("questions_for_writer"):
        para(doc, u["questions"], lang, style="Heading 3")
        for q in notes["questions_for_writer"]:
            para(doc, f"؟ {q}" if lang == "ar" else f"? {q}", lang)
    para(doc, u["legend"], lang, style="Heading 3")
    lg = para(doc, "", lang, size=9)
    for L in LENS.values():
        r = lg.add_run(f"■ {L['name_ar'] if lang == 'ar' else L['name']}    ")
        r.font.color.rgb = S.RGBColor.from_string(L["hex"].lstrip("#"))
        r.font.size = S.Pt(9)
        if lang == "ar":
            r._r.get_or_add_rPr().append(S._el("w:rtl"))
    pb = doc.add_paragraph()
    pb.add_run().add_break(S.WD_BREAK.PAGE)
    added = list(body)[start:]
    sect = body[-1] if body[-1].tag == S.qn("w:sectPr") else None
    for el in added:
        if el is sect:
            continue
        body.remove(el)
    # after the title page (if any): find the first page-break paragraph
    anchor = 0
    if sc.get("title_page"):
        for i, el in enumerate(body):
            if el.tag == S.qn("w:p") and el.findall(".//" + S.qn("w:br")):
                anchor = i + 1
                break
    for k, el in enumerate([e for e in added if e is not sect]):
        body.insert(anchor + k, el)


def annotate(sc, notes, lang):
    pmap = {}
    doc = F.build_docx(sc, pmap=pmap)
    u = UI[lang]
    by_scene = {}
    for idx, e in enumerate(sc["elements"]):
        if e.get("scene"):
            by_scene.setdefault(e["scene"], []).append(idx)
    heading_of = {s["n"]: s["start"] for s in sc["scenes"]}
    for n in notes["notes"]:
        L = LENS[n["lens"]]
        target = heading_of[n["scene"]]
        if n.get("quote"):
            q = norm(n["quote"])
            target = next((i for i in by_scene.get(n["scene"], []) if q and q in norm(sc["elements"][i]["text"])), target)
        p = pmap.get(target) or pmap.get(heading_of[n["scene"]])
        if not p or not p.runs:
            continue
        shade_runs(p, L["hex"])
        tag = f"■ {L['name_ar'] if lang == 'ar' else L['name']} · {u['kinds'][n['kind']]}"
        doc.add_comment(p.runs, text=f"{tag}\n{n['text']}", author=u["author"], initials="ZR")
    notes_page(doc, sc, notes, lang)
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script")
    ap.add_argument("notes")
    ap.add_argument("--out")
    ap.add_argument("--name")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    sc = json.loads(Path(a.script).read_text(encoding="utf-8"))
    notes = json.loads(Path(a.notes).read_text(encoding="utf-8"))
    errs, warns = check(sc, notes)
    for w in warns:
        print("  warn ", w)
    for e in errs:
        print("  ERROR", e)
    if errs:
        sys.exit(1)
    by = {}
    for n in notes["notes"]:
        by[n["lens"]] = by.get(n["lens"], 0) + 1
    print(f"OK: {len(notes['notes'])} notes · " + ", ".join(f"{x['id']} {x['verdict']}" for x in notes["lenses"]))
    if a.check:
        return
    out = Path(a.out or ".")
    out.mkdir(parents=True, exist_ok=True)
    lang = notes.get("lang") or sc["lang"]
    name = a.name or (re.sub(r"[^\w؀-ۿ-]+", "-", (sc.get("title_page") or {}).get("title") or "script").strip("-") + "-notes")
    path = out / f"{name}.docx"
    annotate(sc, notes, lang).save(path)
    print(f"annotated script → {path}")


if __name__ == "__main__":
    main()
