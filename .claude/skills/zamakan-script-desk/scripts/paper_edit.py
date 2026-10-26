#!/usr/bin/env python3
"""A documentary paper edit from chosen bites. Claude (or the editor) writes selects.json naming bites by id only
(bites.json from transcripts.py), so every quote is verbatim by construction; this builds:
  <title>-paper-edit.docx   two columns (picture | sound), each bite with speaker, timecode and theme, sections with
                            their running time, a summary of minutes per section and per speaker (Word, right to left)
  <title>-paper-edit.csv    the same cut list for the editor (file, in, out, seconds, theme, text)

selects.json:
  {"schema": "zamakan-selects/1", "lang": "ar", "title": "...", "target_minutes": 52,
   "themes": {"craft": {"label": "الصنعة في الرأس"}},
   "sections": [{"name": "...", "purpose": "what this section does",
     "items": [{"bite": "A005", "theme": "craft", "picture": "what we see (optional)", "note": "why (optional)"},
               {"picture": "the hull at dawn", "sound": "hammer, sea"},     # a moment with no words
               {"gap": "we have nothing yet of the son: film him?"}]}]}   # still to find or film

Usage:
  python paper_edit.py selects.json bites.json [--out <dir>] [--check] [--pdf]
Checks: every bite exists; interviewer lines and bites used twice are flagged; two bites of one speaker cut together
that were not said together are flagged (a joined quote must keep its meaning true); running time against the target.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _doc as D  # noqa: E402
import _screenplay as S  # noqa: E402
import build_template as B  # noqa: E402

TINTS = ["DBE8FB", "FBE3D6", "D3F1E5", "E6DDF5", "F8EEC9", "F6DCE8", "E2EEF0", "ECEAE6"]
AMBER = "FDECC8"
T = {"ar": {"paper": "المونتاج الورقي", "legend": "المحاور", "silence": "دون كلام", "gap": "ينقصنا", "summary": "الزمن",
            "cols": ["القسم", "المقاطع", "المدة (د:ث)"], "speakers": "من يتكلم وكم", "scols": ["المتحدث", "المقاطع", "المدة (د:ث)", "النسبة"],
            "total": "المجموع", "target": "المدة المستهدفة", "min": "دقيقة", "promise": "كل ما بين «» كلام قيل فعلاً، كما هو، بتوقيته في الملف.", "howto": "اكتب ما تريد تغييره كتعليق أو مباشرة في عمود الصورة، وأرسل الملف: لا تكتب كلاماً جديداً في عمود الصوت، فالاقتباسات تأتي من التفريغ. الصفوف الصفراء ما ينقص.",
            "joined": "قطع يجمع كلاماً لم يُقل متتالياً: تأكّد أن المعنى بقي صادقاً"},
     "en": {"paper": "Paper edit", "legend": "Themes", "silence": "no words", "gap": "Still missing", "summary": "Running time",
            "cols": ["Section", "Bites", "Time (m:ss)"], "speakers": "Who speaks, and how much", "scols": ["Speaker", "Bites", "Time (m:ss)", "Share"],
            "total": "Total", "target": "Target", "min": "min", "promise": "Everything in quotes was really said, word for word, with its timecode.", "howto": "Write changes as comments or straight into the picture column, and send the file back; don't type new words in the sound column, quotes come from the transcripts. Amber rows are what's missing.",
            "joined": "This cut joins words not said one after the other: make sure the meaning stays true"}}


def load(sel_path, bites_path):
    sel = json.loads(Path(sel_path).read_text(encoding="utf-8"))
    bites = json.loads(Path(bites_path).read_text(encoding="utf-8"))["bites"]
    return sel, bites


def check(sel, bites):
    import jsonschema
    errs, warns = [], []
    schema = json.loads((S.SKILL / "schemas" / "selects.schema.json").read_text(encoding="utf-8"))
    for e in jsonschema.Draft202012Validator(schema).iter_errors(sel):
        errs.append(f"schema: {'/'.join(map(str, e.path))}: {e.message[:140]}")
    if errs:
        return errs, warns
    by = {b["id"]: b for b in bites}
    order = {b["id"]: i for i, b in enumerate(bites)}
    themes = sel.get("themes", {})
    used, joins = {}, []
    for s in sel.get("sections", []):
        prev = None  # joins only count inside a section: across sections a cut is expected
        if not s.get("name"):
            errs.append("a section has no name")
        for it in s.get("items", []):
            if "bite" in it:
                if "sound" in it:
                    errs.append(f"{it['bite']}: a bite row takes its sound from the transcript; remove 'sound'")
                b = by.get(it["bite"])
                if not b:
                    errs.append(f"{s.get('name')}: no bite {it['bite']} in bites.json")
                    prev = None
                    continue
                if b.get("interviewer"):
                    warns.append(f"{it['bite']} is the interviewer's question; keep it only if the film hears the question")
                if it["bite"] in used:
                    warns.append(f"{it['bite']} is used twice ({used[it['bite']]} and {s['name']})")
                used[it["bite"]] = s.get("name")
                if prev and prev["speaker"] == b["speaker"] and prev["file"] == b["file"] and order[b["id"]] != order[prev["id"]] + 1:
                    joins.append(f"{prev['id']}→{b['id']}")
                prev = b
            else:
                prev = None
            if it.get("theme") and it["theme"] not in themes:
                errs.append(f"theme '{it['theme']}' is not in themes")
            if not any(k in it for k in ("bite", "picture", "sound", "gap")):
                errs.append(f"{s.get('name')}: an empty row")
    if joins:
        warns.append(f"{len(joins)} cut(s) join one speaker's words from different moments ({', '.join(joins)}; marked ✂ in the paper edit): "
                     "check each keeps what they meant")
    total = runtime(sel, bites)[1]
    if sel.get("target_minutes") and total > sel["target_minutes"] * 60:
        warns.append(f"the bites alone run {total / 60:.1f} min, over the {sel['target_minutes']} min target")
    elif sel.get("target_minutes") and total < sel["target_minutes"] * 30:
        warns.append(f"the bites run {total / 60:.1f} min, under half the {sel['target_minutes']} min target: say what still has to be filmed (gap rows)")
    return errs, warns


def mmss(sec):
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}"


def runtime(sel, bites):
    by = {b["id"]: b for b in bites}
    per = []
    for s in sel["sections"]:
        sec = [by[i["bite"]] for i in s["items"] if i.get("bite") in by]
        per.append((s["name"], len(sec), sum(max(0, (b["out"] or 0) - (b["in"] or 0)) for b in sec if b["text"])))  # a silence isn't speech
    return per, sum(x[2] for x in per)


def build_docx(sel, bites):
    lang = sel["lang"]
    ar = lang == "ar"
    t = T[lang]
    by = {b["id"]: b for b in bites}
    tint = {k: TINTS[i % len(TINTS)] for i, k in enumerate(sel.get("themes", {}))}
    order = {b["id"]: i for i, b in enumerate(bites)}
    doc = S.new_document(lang)
    S.add_page_numbers(doc, lang)
    B.para(doc, f"{sel.get('title', '')} · {t['paper']}", lang, style="Title")
    B.para(doc, t["promise"], lang, grey=True, italic=True, size=10)
    B.para(doc, t["howto"], lang, grey=True, size=10)
    if sel.get("themes"):
        B.para(doc, t["legend"], lang, style="Heading 3")
        for k, th in sel["themes"].items():
            p = B.para(doc, th["label"], lang, size=10)
            p._p.get_or_add_pPr().append(S._el("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": tint[k]}))
    per, total = runtime(sel, bites)
    for s, (_, n, sec) in zip(sel["sections"], per):
        B.para(doc, f"{s['name']}  ({mmss(sec)})", lang, style="Heading 2")
        if s.get("purpose"):
            B.para(doc, s["purpose"], lang, grey=True, italic=True)
        rows, fills, prev = [], [], None
        for it in s["items"]:
            th = sel.get("themes", {}).get(it.get("theme"), {}).get("label")
            if "bite" in it and it["bite"] in by:
                b = by[it["bite"]]
                text = f"«{b['text']}»" if b["text"] else f"({'; '.join(b.get('direction', []))})"
                label = " · ".join(x for x in (th, it.get("note")) if x)
                if prev and prev["speaker"] == b["speaker"] and prev["file"] == b["file"] and order[b["id"]] != order[prev["id"]] + 1:
                    label = " · ".join(x for x in (label, "✂ " + t["joined"]) if x)
                rows.append((it.get("picture", ""), text, {"speaker": b["speaker"], "tc": f"{b['id']} · {b['tc_in']}–{b['tc_out']}", "label": label}))
                fills.append(tint.get(it.get("theme")))
                prev = b
            elif "gap" in it:
                rows.append(("", f"{t['gap']}: {it['gap']}", {"label": th} if th else None))
                fills.append(AMBER)
                prev = None
            else:
                rows.append((it.get("picture", ""), f"({it.get('sound') or t['silence']})", {"label": th} if th else None))
                fills.append(tint.get(it.get("theme")))
                prev = None
        if rows:
            D.av_table(doc, rows, lang, fills=fills)
    # summary: time per section, time per speaker
    B.para(doc, t["summary"], lang, style="Heading 1")
    rows = [t["cols"]] + [[name, S.digits(n, lang), mmss(sec)] for name, n, sec in per]
    rows.append([t["total"], S.digits(sum(x[1] for x in per), lang), mmss(total)])
    if sel.get("target_minutes"):
        rows.append([t["target"], "", f"{sel['target_minutes']}:00"])
    B.table(doc, rows, lang)
    sp = {}
    for s in sel["sections"]:
        for it in s["items"]:
            b = by.get(it.get("bite"))
            if b and b["text"]:
                n, sec = sp.get(b["speaker"], (0, 0))
                sp[b["speaker"]] = (n + 1, sec + max(0, (b["out"] or 0) - (b["in"] or 0)))
    B.para(doc, t["speakers"], lang, style="Heading 2")
    B.table(doc, [t["scols"]] + [[k, S.digits(n, lang), mmss(sec), S.digits(f"{100 * sec / max(total, 1):.0f}", lang) + "٪" if ar else f"{100 * sec / max(total, 1):.0f}%"]
                                  for k, (n, sec) in sorted(sp.items(), key=lambda x: -x[1][1])], lang)
    return doc


def write_csv(sel, bites, path):
    by = {b["id"]: b for b in bites}
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel shows Arabic
        w = csv.writer(f)
        w.writerow(["order", "section", "bite", "file", "speaker", "tc_in", "tc_out", "seconds", "theme", "picture", "sound"])
        n = 0
        for s in sel["sections"]:
            for it in s["items"]:
                n += 1
                b = by.get(it.get("bite"))
                th = sel.get("themes", {}).get(it.get("theme"), {}).get("label", "")
                if b:
                    w.writerow([n, s["name"], b["id"], b["file"], b["speaker"], b["tc_in"], b["tc_out"],
                                round((b["out"] or 0) - (b["in"] or 0), 1), th, it.get("picture", ""), b["text"]])
                else:
                    w.writerow([n, s["name"], "", "", "", "", "", "", th, it.get("picture", ""), it.get("sound") or ("GAP: " + it["gap"] if "gap" in it else "")])


def to_script(sel, bites):
    """Paper edit → script.json (zamakan-script/1) so the documentary reader can comment on it: sections are scenes,
    pictures are action, each bite is its speaker's line (with id and timecode), gaps are marked."""
    lang = sel["lang"]
    by = {b["id"]: b for b in bites}
    els, scenes, row = [], [], 0
    for k, s in enumerate(sel["sections"], 1):
        start = len(els)
        els.append({"type": "scene_heading", "text": s["name"], "scene": k})
        for it in s["items"]:
            row += 1
            if it.get("picture"):
                els.append({"type": "action", "text": it["picture"], "scene": k, "row": row})
            b = by.get(it.get("bite"))
            if b:
                said = b["text"] or f"({'; '.join(b.get('direction', []))})"
                els.append({"type": "character", "text": b["speaker"], "name": b["speaker"], "scene": k, "row": row, "bite": b["id"], "tc": b["tc_in"]})
                els.append({"type": "dialogue", "text": said, "scene": k, "row": row, "bite": b["id"]})
            elif "gap" in it:
                els.append({"type": "action", "text": f"[{T[lang]['gap']}: {it['gap']}]", "scene": k, "row": row})
            elif it.get("sound"):
                els.append({"type": "action", "text": f"({it['sound']})", "scene": k, "row": row, "col": "sound"})
        scenes.append({"n": k, "heading": s["name"], "int_ext": "", "location": s["name"], "time": "", "start": start, "end": len(els) - 1})
    return {"schema": "zamakan-script/1", "source": "paper edit", "lang": lang, "kind": "documentary", "form": "paper-edit",
            "title_page": {"title": sel.get("title", "")}, "scenes": scenes, "elements": els, "unsure": []}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("selects")
    ap.add_argument("bites")
    ap.add_argument("--out", default=".")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--csv", action="store_true", help="also the cut list for the editor (CSV)")
    a = ap.parse_args()
    sel, bites = load(a.selects, a.bites)
    errs, warns = check(sel, bites)
    for w in warns:
        print("  warn ", w)
    for e in errs:
        print("  ERROR", e)
    if errs:
        sys.exit(1)
    per, total = runtime(sel, bites)
    print(f"OK: {len(per)} sections · {sum(x[1] for x in per)} bites · {total / 60:.1f} min of words")
    if a.check:
        return
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^\w؀-ۿ-]+", "-", sel.get("title") or "film").strip("-") or "film"
    docx = out / f"{stem}-paper-edit.docx"
    build_docx(sel, bites).save(docx)
    print(f"paper edit → {docx}")
    if a.csv:
        write_csv(sel, bites, out / f"{stem}-paper-edit.csv")
        print(f"cut list → {out / (stem + '-paper-edit.csv')}")
    if a.pdf:
        print(f"PDF → {S.to_pdf(docx)[0]}")


if __name__ == "__main__":
    main()
