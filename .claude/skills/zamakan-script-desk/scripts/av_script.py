#!/usr/bin/env python3
"""The documentary two-column script (picture | sound): read it from Word or text, write it back laid out, and hand it
to the reader. Arabic first: the picture column sits on the right.

Reads:
  Word   a table whose header says picture/sound («الصورة»/«الصوت», PICTURE/SOUND, VIDEO/AUDIO, VISUAL/AUDIO), with or
         without a # column; headings (or paragraphs) between tables become sections
  text   «صورة:» / «صوت:» lines (also VIS:/AUD:, VIDEO:/AUDIO:, PICTURE:/SOUND:), one row per picture line; a line
         starting with «##» or «القسم» / «SEQUENCE» starts a section
Writes av.json, a formatted Word file (+ PDF), and script.json so the reader, side comments, charts and draft
comparison work on it (each section becomes a scene; picture lines are action; sound lines are dialogue, under the
speaker when written «سالم: …», else under SOUND / «الصوت»).

Usage:
  python av_script.py draft.docx|draft.txt [--out <dir>] [--title T] [--no-pdf]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _doc as D  # noqa: E402
import _screenplay as S  # noqa: E402
import build_template as B  # noqa: E402

PIC = r"(?:صورة|الصورة|picture|vis(?:ual)?|video|image)"
SND = r"(?:صوت|الصوت|sound|aud(?:io)?)"
PIC_RE = re.compile(rf"^\s*{PIC}\s*[:：]\s*(.*)$", re.I)
SND_RE = re.compile(rf"^\s*{SND}\s*[:：]\s*(.*)$", re.I)
SEC_RE = re.compile(r"^\s*(?:#{1,3}\s*|(?:القسم|المقطع|الجزء|sequence|section|part)\b\s*[:\-–]?\s*)(.+)$", re.I)
SPEAKER_RE = re.compile(r"^([^:：«»\"]{1,25})[:：]\s*(.+)$")
WORDS_PER_SEC = {"ar": 2.0, "en": 2.5}  # spoken pace, rough
T = {"ar": {"sound": "الصوت", "spoken": "كلام منطوق", "words": "كلمة", "rough": "تقدير تقريبي لزمن الكلام وحده", "section": "القسم"},
     "en": {"sound": "SOUND", "spoken": "spoken", "words": "words", "rough": "a rough estimate of the spoken words alone", "section": "Section"}}


def from_text(lines):
    rows, section = [], None
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        m = PIC_RE.match(s)
        if m:
            rows.append({"section": section, "picture": m.group(1).strip(), "sound": ""})
            continue
        m = SND_RE.match(s)
        if m:
            if rows and rows[-1]["section"] == section and not rows[-1]["sound"]:
                rows[-1]["sound"] = m.group(1).strip()
            else:  # sound over the previous picture, or with no picture yet
                rows.append({"section": section, "picture": "", "sound": m.group(1).strip()})
            continue
        m = SEC_RE.match(s)
        if m:
            section = m.group(1).strip()
            continue
        if rows:  # a continuation line: belongs to whichever column was written last
            col = "sound" if rows[-1]["sound"] else "picture"
            rows[-1][col] = (rows[-1][col] + "\n" + s).strip()
        else:
            section = section or s  # loose text before any row: treat as a section title
    return rows


def from_docx(path):
    from docx import Document
    d = Document(path)
    body = d.element.body
    rows, section, tables = [], None, {t._tbl: t for t in d.tables}
    paras = {p._p: p for p in d.paragraphs}
    for child in body.iterchildren():
        if child in paras:
            p = paras[child]
            if p.text.strip() and (p.style.name.startswith("Heading") or SEC_RE.match(p.text)):
                m = SEC_RE.match(p.text)
                section = (m.group(1) if m and not p.style.name.startswith("Heading") else p.text).strip()
            elif p.text.strip() and (PIC_RE.match(p.text) or SND_RE.match(p.text)):
                for r in from_text([p.text]):
                    r["section"] = section
                    if r["picture"] or not rows:
                        rows.append(r)
                    else:
                        rows[-1]["sound"] = r["sound"]
            continue
        t = tables.get(child)
        if t is None or not t.rows:
            continue
        head = [c.text.strip() for c in t.rows[0].cells]
        pic = next((j for j, h in enumerate(head) if re.fullmatch(PIC, h, re.I)), None)
        snd = next((j for j, h in enumerate(head) if re.fullmatch(SND, h, re.I)), None)
        if pic is None or snd is None:
            continue
        for r in t.rows[1:]:
            cells = r.cells
            pv = "\n".join(p.text for p in cells[pic].paragraphs).strip()
            sp = [p for p in cells[snd].paragraphs if p.text.strip()]
            if len(sp) >= 2 and len(sp[0].text.strip()) <= 25 and sp[0].runs and sp[0].runs[0].bold:  # a bold name above the words
                sv = sp[0].text.strip().rstrip(":：") + ": " + "\n".join(p.text for p in sp[1:]).strip()
            else:
                sv = "\n".join(p.text for p in sp).strip()
            if pv or sv:
                rows.append({"section": section, "picture": pv, "sound": sv})
    return rows


def read(path, title=None):
    p = Path(path)
    rows = from_docx(p) if p.suffix.lower() == ".docx" else from_text(p.read_text(encoding="utf-8-sig").splitlines())
    text = " ".join(r["picture"] + " " + r["sound"] for r in rows)
    lang = "ar" if S.is_arabic(text) else "en"
    return {"schema": "zamakan-av/1", "source": str(p), "lang": lang, "title": title or p.stem,
            "rows": [{"n": i, **r} for i, r in enumerate(rows, 1)]}


def spoken(av):
    lines = [ln.strip() for r in av["rows"] for ln in r["sound"].split("\n")]
    said = [SPEAKER_RE.match(ln).group(2) for ln in lines if SPEAKER_RE.match(ln)]  # «name: words»; ambience is not speech
    words = sum(len(re.sub(r"[\(\[][^\)\]]*[\)\]]", "", x).split()) for x in said)
    return words, words / WORDS_PER_SEC[av["lang"]]


def sections(av):
    out = []
    for r in av["rows"]:
        if not out or out[-1][0] != r["section"]:
            out.append((r["section"], []))
        out[-1][1].append(r)
    return out


def _who(sound):
    """A one-line «name: words» shows the name above the words, as in the paper edit."""
    m = SPEAKER_RE.match(sound) if "\n" not in sound else None
    return (m.group(2).strip(), {"speaker": m.group(1).strip()}) if m else (sound, None)


def build_docx(av):
    lang = av["lang"]
    t = T[lang]
    doc = S.new_document(lang)
    S.add_page_numbers(doc, lang)
    B.para(doc, av["title"], lang, style="Title")
    words, sec = spoken(av)
    B.para(doc, f"{S.digits(words, lang)} {t['words']} {t['spoken']} ≈ {int(sec // 60)}:{int(sec % 60):02d} ({t['rough']})", lang, grey=True, size=10)
    n = 0
    for name, rows in sections(av):
        if name:
            B.para(doc, name, lang, style="Heading 2")
        D.av_table(doc, [(r["picture"], *_who(r["sound"])) for r in rows], lang, start=n + 1)  # numbered through, so notes can say "row 7"
        n += len(rows)
    return doc


def to_script(av):
    """av.json → script.json (zamakan-script/1) so the reader's tools work on a documentary."""
    lang = av["lang"]
    els, scenes = [], []
    for k, (name, rows) in enumerate(sections(av), 1):
        heading = name or f"{T[lang]['section']} {k}"
        start = len(els)
        els.append({"type": "scene_heading", "text": heading, "scene": k, "row": rows[0]["n"]})
        for r in rows:
            for ln in [x for x in r["picture"].split("\n") if x.strip()]:
                els.append({"type": "action", "text": ln.strip(), "scene": k, "row": r["n"]})
            for ln in [x for x in r["sound"].split("\n") if x.strip()]:
                m = SPEAKER_RE.match(ln.strip())
                if m:
                    els.append({"type": "character", "text": m.group(1).strip(), "name": m.group(1).strip(), "scene": k, "row": r["n"]})
                    els.append({"type": "dialogue", "text": m.group(2).strip(), "scene": k, "row": r["n"]})
                else:  # ambience, music, silence: in the sound column, but nobody speaks
                    els.append({"type": "action", "text": ln.strip(), "scene": k, "row": r["n"], "col": "sound"})
        scenes.append({"n": k, "heading": heading, "int_ext": "", "location": heading, "time": "", "start": start, "end": len(els) - 1})
    return {"schema": "zamakan-script/1", "source": av.get("source", ""), "lang": lang, "kind": "documentary", "form": "av",
            "title_page": {"title": av["title"]}, "scenes": scenes, "elements": els, "unsure": []}


def script_docx(sc, pmap=None):
    """A documentary script.json laid out for reading notes: each section a heading, its rows in the picture | sound
    table (prose with no rows, as in a treatment, as plain paragraphs). pmap gets element index → paragraph, so margin
    comments land on the right line."""
    lang = sc["lang"]
    ar = lang == "ar"
    pmap = {} if pmap is None else pmap
    doc = S.new_document(lang)
    S.add_page_numbers(doc, lang)
    B.para(doc, sc.get("title_page", {}).get("title", ""), lang, style="Title")
    els = sc["elements"]
    n = 0
    for scn in sc["scenes"]:
        pmap[scn["start"]] = B.para(doc, scn["heading"], lang, style="Heading 2")
        idx = list(range(scn["start"] + 1, scn["end"] + 1))
        rows, order = {}, []
        for i in idx:
            r = els[i].get("row")
            if r is None:  # prose
                pmap[i] = B.para(doc, els[i]["text"], lang)
                continue
            if r not in rows:
                rows[r] = {"pic": [], "snd": []}
                order.append(r)
            if els[i]["type"] == "action" and els[i].get("col") != "sound":
                rows[r]["pic"].append(i)
            elif els[i]["type"] == "dialogue" or els[i].get("col") == "sound":
                rows[r]["snd"].append(i)
        if not order:
            continue
        t = D.av_table(doc, [("", "", None)] * len(order), lang, start=n + 1)
        n += len(order)
        for k, r in enumerate(order, 1):
            for col, key in ((1, "pic"), (2, "snd")):
                cell = t.cell(k, col)
                for j, i in enumerate(rows[r][key]):
                    p = cell.paragraphs[0] if j == 0 else cell.add_paragraph()
                    if j and ar:
                        p._p.get_or_add_pPr().append(S._el("w:bidi"))
                    who = els[i - 1]["name"] if key == "snd" and els[i]["type"] == "dialogue" and els[i - 1]["type"] == "character" else None
                    if who and who not in (T["ar"]["sound"], T["en"]["sound"]):
                        D._run(p, who + ": ", lang, bold=True, color="5E5A53")
                        pmap[i - 1] = p
                    D._run(p, els[i]["text"], lang)
                    pmap[i] = p
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft")
    ap.add_argument("--out", default=".")
    ap.add_argument("--title")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    av = read(a.draft, a.title)
    if not av["rows"]:
        sys.exit("no picture | sound rows found: use a two-column table with a «الصورة»/«الصوت» header, or «صورة:» / «صوت:» lines")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^\w؀-ۿ-]+", "-", av["title"]).strip("-") or "av"
    (out / f"{stem}-av.json").write_text(json.dumps(av, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"{stem}-script.json").write_text(json.dumps(to_script(av), ensure_ascii=False, indent=1), encoding="utf-8")
    docx = out / f"{stem}-av.docx"
    build_docx(av).save(docx)
    words, sec = spoken(av)
    print(f"OK: {len(av['rows'])} rows · {len(sections(av))} sections · {words} spoken words ≈ {int(sec // 60)}:{int(sec % 60):02d}")
    print(f"av → {out / (stem + '-av.json')}\nscript.json (for the reader) → {out / (stem + '-script.json')}\nWord → {docx}")
    if not a.no_pdf:
        print(f"PDF → {S.to_pdf(docx)[0]}")


if __name__ == "__main__":
    main()
