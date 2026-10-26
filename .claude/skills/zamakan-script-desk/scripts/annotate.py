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

LENS_FILES = {"film": "lenses.json", "documentary": "lenses_doc.json"}
LENSES, LENS = {}, {}


def use_lenses(name="film"):
    """Switch the viewpoint set (film or documentary). Updates LENSES and LENS in place, so report.py and
    side_notes.py, which import them, follow."""
    data = json.loads((S.SKILL / "references" / LENS_FILES[name]).read_text(encoding="utf-8"))
    LENSES.clear()
    LENSES.update(data)
    LENS.clear()
    LENS.update({x["id"]: x for x in data["lenses"]})


use_lenses("film")
VERDICT = LENSES["verdicts"]
UI = {"ar": {"notes": "ملاحظات القراءة", "story": "القصة كما فهمناها", "overall": "الحكم العام", "lens": "زاوية القراءة", "verdict": "الحكم",
             "summary": "الخلاصة", "next": "أولويات المسودة القادمة", "questions": "أسئلة للكاتب", "legend": "ألوان الملاحظات في الهامش", "since": "منذ المسودة السابقة", "intent": "هل يحقق النص ما تريده؟", "scene": "مشهد",
             "author": "قارئ زمكان", "kinds": {"issue": "ملاحظة", "question": "سؤال", "strength": "نقطة قوة"},
             "promise": "هذه ملاحظات وأسئلة لمساعدتك على الكتابة، لا إعادة كتابة لنصك."},
      "en": {"notes": "Reader's notes", "story": "The story as we read it", "overall": "Overall", "lens": "Viewpoint", "verdict": "Verdict",
             "summary": "Summary", "next": "Priorities for the next draft", "questions": "Questions for the writer", "legend": "Margin comment colours", "since": "Since the last draft", "intent": "Does the script do what you are going for?", "scene": "scene",
             "author": "ZAMAKAN reader", "kinds": {"issue": "Note", "question": "Question", "strength": "Strength"},
             "promise": "These are notes and questions to help you write, not a rewrite of your script."}}


def norm(t):
    return re.sub(r"[ً-ْـ\s«»\"'“”.,،:!?؟…-]+", "", t or "")


GENERIC = re.compile(r"يحتاج (إلى )?(مزيد من )?(عمق|تطوير|تحسين|عمل)|غير مقنع\s*[.؟]?$|ممل|needs? (more )?(depth|work|development|polish)|"
                     r"could be (better|stronger)|not (very )?(engaging|compelling)|feels? flat", re.I)


def quality(notes):
    """Warnings that keep notes sharp: short summaries, concrete notes that end in a question, no generic phrases,
    no repeats."""
    from difflib import SequenceMatcher
    warns = []
    for x in notes["lenses"]:
        sents = [t for t in re.split(r"(?<=[.!؟?])\s+", x["summary"].strip()) if t]
        if len(x["summary"]) > 300 or len(sents) > 3:
            warns.append(f"lens '{x['id']}': summary is {len(sents)} sentences / {len(x['summary'])} chars; keep it to two or three short sentences")
    for i, n in enumerate(notes["notes"]):
        if n["kind"] in ("issue", "question") and not re.search(r"[؟?]", n["text"]):
            warns.append(f"note {i}: an {n['kind']} should ask the writer something (end with a question)")
        if GENERIC.search(n["text"]):
            warns.append(f"note {i}: generic phrase ({GENERIC.search(n['text']).group(0)!r}); say what you saw and where")
        if len(n["text"]) > 400:
            warns.append(f"note {i}: {len(n['text'])} chars; a margin note reads best under 300")
        for j in range(i):
            m = notes["notes"][j]
            if m["scene"] == n["scene"] and m["lens"] == n["lens"] and SequenceMatcher(None, m["text"], n["text"]).ratio() > 0.75:
                warns.append(f"notes {j} and {i} say nearly the same thing in scene {n['scene']}; keep one")
    return warns


def check(sc, notes, intent=None):
    import jsonschema
    errs, warns = [], []
    schema = json.loads((S.SKILL / "schemas" / "notes.schema.json").read_text(encoding="utf-8"))
    for e in jsonschema.Draft202012Validator(schema).iter_errors(notes):
        errs.append(f"schema: {'/'.join(map(str, e.path))}: {e.message[:140]}")
    if errs:
        return errs, warns
    use_lenses(notes.get("lens_set", "film"))  # every tool checks the notes first, so this picks the viewpoints for all
    have = {x["id"]: x for x in notes["lenses"]}
    scope = notes.get("scope") or {"kind": "full"}
    required = list(LENS)
    if scope["kind"] == "lenses":
        required = scope.get("lenses") or []
        if not required:
            errs.append("scope lenses: name the viewpoints this pass covers")
    elif scope["kind"] == "first-pages":
        required = LENSES["first_pages"]  # what the opening pages can show
        if not scope.get("pages"):
            errs.append("scope first-pages: say how many pages were read")
    for lid in required:
        if lid not in have:
            errs.append(f"lens '{lid}' has no verdict" + (" (every viewpoint gets one, even green)" if scope["kind"] == "full" else f" (in scope for this {scope['kind']} pass)"))
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
    st = next((x for x in S.STRUCTURES["structures"] if x["id"] == notes.get("structure")), None)
    for beat, n in (notes.get("turns") or {}).items():
        if st and beat not in {b["id"] for b in st["beats"]}:
            errs.append(f"turns: '{beat}' is not a beat of {notes.get('structure')} ({', '.join(b['id'] for b in st['beats'])})")
        if not 1 <= n <= nscenes:
            errs.append(f"turns: {beat} → scene {n} does not exist")
    if notes.get("turns") and not st:
        errs.append("turns given but 'structure' is missing or unknown")
    tens = notes.get("tension") or {}
    bad = [k for k in tens if not k.isdigit() or not 1 <= int(k) <= nscenes]
    if bad:
        errs.append(f"tension: unknown scenes {bad}")
    full = (notes.get("scope") or {"kind": "full"})["kind"] == "full"
    if tens and len(tens) < nscenes and full:
        warns.append(f"tension covers {len(tens)} of {nscenes} scenes; give every scene a value for a true curve")
    if not tens and full:
        warns.append("no tension values: the report has no tension curve")
    for name, arc in (notes.get("arcs") or {}).items():
        bad = [k for k in arc["points"] if not k.isdigit() or not 1 <= int(k) <= nscenes]
        if bad:
            errs.append(f"arcs: {name} has unknown scenes {bad}")
    if intent and not notes.get("intent_check"):
        errs.append("an intent sheet was given: add intent_check (does the script do what the writer is going for?)")
    for i, it in enumerate(notes.get("intent_check") or []):
        if it.get("scene") and not 1 <= it["scene"] <= nscenes:
            errs.append(f"intent_check {i}: scene {it['scene']} does not exist")
    warns += quality(notes)
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


def scope_label(notes, lang):
    """A line saying what this reading covers, when it is not a full read."""
    sc = notes.get("scope") or {"kind": "full"}
    if sc["kind"] == "first-pages":
        return f"قراءة أول {S.digits(sc.get('pages', 10), lang)} صفحات فقط، كما يقرأها قارئ المهرجان" if lang == "ar" else \
            f"First {sc.get('pages', 10)} pages only, the way a festival reader meets the script"
    if sc["kind"] == "lenses":
        names = [(LENS[i]["name_ar"] if lang == "ar" else LENS[i]["name"]) for i in sc.get("lenses", []) if i in LENS]
        return ("قراءة مركّزة: " + "، ".join(names)) if lang == "ar" else ("Focused pass: " + ", ".join(names))
    return ""


def verdict_runs(p, v, lang):
    """● in the status colour, then icon + label in ink: the colour never carries the verdict alone."""
    for text, col in (("● ", VERDICT[v]["hex"]), (f"{VERDICT[v]['icon']} {VERDICT[v][lang]}", None)):
        r = p.add_run(text)
        r.bold = True
        if col:
            r.font.color.rgb = S.RGBColor.from_string(col.lstrip("#"))
        if lang == "ar":
            r._r.get_or_add_rPr().append(S._el("w:rtl"))


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


def notes_page(doc, sc, notes, lang, images=()):
    u = UI[lang]
    # insert the notes page before the script body: build it at the end, then move its elements to the front
    body = doc.element.body
    start = len(body) - (1 if body[-1].tag == S.qn("w:sectPr") else 0)  # new paragraphs go in before sectPr
    para(doc, u["notes"], lang, style="Heading 1")
    para(doc, u["promise"], lang, color="#777777", size=10)
    if scope_label(notes, lang):
        para(doc, scope_label(notes, lang), lang, bold=True)
    para(doc, u["story"], lang, style="Heading 3")
    para(doc, notes["logline_read"], lang)
    v = notes["overall"]["verdict"]
    pv = para(doc, f"{u['overall']}: ", lang, bold=True)
    verdict_runs(pv, v, lang)
    para(doc, notes["overall"]["summary"], lang)
    t = doc.add_table(rows=1, cols=3)
    t.style = "Table Grid"
    pr = t._tbl.tblPr
    pr.append(S._el("w:tblW", **{"w:w": 5000, "w:type": "pct"}))
    if lang == "ar":
        pr.append(S._el("w:bidiVisual"))
    for c, h in zip(t.rows[0].cells, (u["lens"], u["verdict"], u["summary"])):
        cell_text(c, h, lang, bold=True)
    use_lenses(notes.get("lens_set", "film"))  # every tool checks the notes first, so this picks the viewpoints for all
    have = {x["id"]: x for x in notes["lenses"]}
    for lid, L in LENS.items():
        x = have.get(lid)
        if not x:
            continue
        row = t.add_row().cells
        cell_text(row[0], "", lang)
        for text, col in (("■ ", L["hex"]), (L["name_ar"] if lang == "ar" else L["name"], None)):
            rr = row[0].paragraphs[0].add_run(text)
            rr.bold = True
            if col:
                rr.font.color.rgb = S.RGBColor.from_string(col.lstrip("#"))
            if lang == "ar":
                rr._r.get_or_add_rPr().append(S._el("w:rtl"))
        cell_text(row[1], "", lang)
        verdict_runs(row[1].paragraphs[0], x["verdict"], lang)
        cell_text(row[2], x["summary"], lang)
    for img in images:  # the charts, as pictures
        doc.add_paragraph()
        doc.add_picture(str(img), width=S.Inches(5.9))
    widths = (1.35, 1.15, 3.3)  # viewpoint and verdict narrow, summary wide
    t.autofit = False
    pr.append(S._el("w:tblLayout", **{"w:type": "fixed"}))
    for gc, w in zip(t._tbl.tblGrid.findall(S.qn("w:gridCol")), widths):
        gc.set(S.qn("w:w"), str(int(w * 1440)))
    for row in t.rows:
        for cell, w in zip(row.cells, widths):
            cell.width = S.Inches(w)
    ic = notes.get("intent_check") or []
    if ic:
        lands = {"yes": ("✓", "#0ca30c"), "partly": ("◐", "#fab219"), "no": ("✕", "#d03b3b")}
        para(doc, u["intent"], lang, style="Heading 3")
        for it in ic:
            pp = para(doc, "", lang)
            for text, col, bold in ((lands[it["lands"]][0] + " ", lands[it["lands"]][1], True), (it["intent"] + ": ", None, True),
                                    (it["note"] + (f" ({u['scene']} {S.digits(it['scene'], lang)})" if it.get("scene") else ""), None, False)):
                r = pp.add_run(text)
                r.bold = bold or None
                if col:
                    r.font.color.rgb = S.RGBColor.from_string(col.lstrip("#"))
                if lang == "ar":
                    r._r.get_or_add_rPr().append(S._el("w:rtl"))
    prev = (notes.get("previous") or {}).get("items") or []
    if prev:
        icons = {"resolved": ("✓", "#0ca30c"), "partly": ("◐", "#fab219"), "open": ("!", "#d03b3b"), "dropped": ("–", "#8a8984")}
        labels = {"ar": {"resolved": "حُلّت", "partly": "جزئياً", "open": "قائمة", "dropped": "لم تعد تنطبق"},
                  "en": {"resolved": "resolved", "partly": "partly", "open": "open", "dropped": "no longer applies"}}
        para(doc, u["since"], lang, style="Heading 3")
        for it in sorted(prev, key=lambda x: list(icons).index(x["status"])):
            pp = para(doc, "", lang)
            for text, col in ((icons[it["status"]][0] + " ", icons[it["status"]][1]),
                              (f"{labels[lang][it['status']]}: {it['text']}" + (f" — {it['comment']}" if it.get("comment") else ""), None)):
                r = pp.add_run(text)
                if col:
                    r.font.color.rgb = S.RGBColor.from_string(col.lstrip("#"))
                    r.bold = True
                if lang == "ar":
                    r._r.get_or_add_rPr().append(S._el("w:rtl"))
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
        for text, col in (("■ ", L["hex"]), (f"{L['name_ar'] if lang == 'ar' else L['name']}    ", None)):
            r = lg.add_run(text)
            if col:
                r.font.color.rgb = S.RGBColor.from_string(col.lstrip("#"))
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


def anchor_index(sc, note):
    """The element a note belongs to: the line holding its quote, else the scene heading."""
    head = next(s["start"] for s in sc["scenes"] if s["n"] == note["scene"])
    q = norm(note.get("quote"))
    if q:
        for i, e in enumerate(sc["elements"]):
            if e.get("scene") == note["scene"] and q in norm(e["text"]):
                return i
    return head


def annotate(sc, notes, lang, images=()):
    pmap = {}
    if sc.get("kind") == "documentary":  # a treatment, A/V script or paper edit keeps its own layout
        from av_script import script_docx
        doc = script_docx(sc, pmap)
    else:
        doc = F.build_docx(sc, pmap=pmap)
    u = UI[lang]
    heading_of = {s["n"]: s["start"] for s in sc["scenes"]}
    for k, n in enumerate(notes["notes"]):
        L = LENS[n["lens"]]
        target = anchor_index(sc, n)
        p = pmap.get(target) or pmap.get(heading_of[n["scene"]])
        if not p or not p.runs:
            continue
        shade_runs(p, L["hex"])
        tag = f"■ {L['name_ar'] if lang == 'ar' else L['name']} · {u['kinds'][n['kind']]} · #{k}"  # #k lets replies.py find the note
        # one reviewer per viewpoint: Word gives each its own margin colour and lets the writer show or hide it
        who = L["name_ar"] if lang == "ar" else L["name"]
        doc.add_comment(p.runs, text=f"{tag}\n{n['text']}", author=who, initials=L["id"][:2].upper())
    notes_page(doc, sc, notes, lang, images)
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script")
    ap.add_argument("notes")
    ap.add_argument("--out")
    ap.add_argument("--name")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--stats", help="stats.json from digest.py: adds the charts to the notes page")
    ap.add_argument("--intent", help="intent.json: requires an intent_check in the notes")
    a = ap.parse_args()
    sc = json.loads(Path(a.script).read_text(encoding="utf-8"))
    notes = json.loads(Path(a.notes).read_text(encoding="utf-8"))
    intent = json.loads(Path(a.intent).read_text(encoding="utf-8")) if a.intent else None
    errs, warns = check(sc, notes, intent)
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
    images = []
    if a.stats:
        import charts as C
        from side_notes import scene_marks
        stats = C.in_scope(json.loads(Path(a.stats).read_text(encoding="utf-8")), notes)
        st = next((x for x in S.STRUCTURES["structures"] if x["id"] == notes.get("structure")), None)
        frags = [C.beat_map(stats, notes, st, scene_marks(sc, notes), lang), C.tension_curve(stats, notes, st, lang), C.arc_chart(stats, notes, lang),
                 C.presence(stats, lang), C.dialect_map(stats, lang)]
        images = C.to_pngs([f for f in frags if f], out / ".charts", lang)
    annotate(sc, notes, lang, images).save(path)
    print(f"annotated script → {path}")


if __name__ == "__main__":
    main()
