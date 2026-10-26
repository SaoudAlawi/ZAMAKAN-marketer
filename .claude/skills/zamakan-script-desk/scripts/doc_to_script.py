#!/usr/bin/env python3
"""Turn documentary work into script.json, so the reader (digest, show, side comments, report, charts, draft
comparison) works on it with the documentary viewpoints (notes.json: "lens_set": "documentary").

  treatment / proposal (.docx, .txt, .md)   headings become sections, paragraphs stay prose
  two-column script (.docx table or «صورة:»/«صوت:» text)   → av_script.py does the reading
  paper edit (selects.json + bites.json)

Usage:
  python doc_to_script.py treatment.docx [--out script.json]
  python doc_to_script.py av-draft.txt --av [--out script.json]
  python doc_to_script.py selects.json --bites bites.json [--out script.json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _screenplay as S  # noqa: E402
import av_script as AV  # noqa: E402
import paper_edit as PE  # noqa: E402

HEAD_RE = re.compile(r"^\s*#{1,3}\s*(.+)$")


def treatment(path):
    """Prose → sections of paragraphs. Word headings (or #/## lines in text) start a section."""
    p = Path(path)
    blocks = []  # (is_heading, text)
    if p.suffix.lower() == ".docx":
        from docx import Document
        for para in Document(p).paragraphs:
            t = para.text.strip()
            if t:
                blocks.append((para.style.name.startswith("Heading") or para.style.name == "Title", t))
    else:
        for ln in p.read_text(encoding="utf-8-sig").splitlines():
            t = ln.strip()
            if t:
                m = HEAD_RE.match(t)
                blocks.append((bool(m), m.group(1).strip() if m else t))
    title = blocks[0][1] if blocks and blocks[0][0] else p.stem
    if blocks and blocks[0][0]:
        blocks = blocks[1:]
    lang = "ar" if S.is_arabic(" ".join(t for _, t in blocks[:200])) else "en"
    els, scenes = [], []
    for is_head, t in blocks:
        if is_head or not scenes:
            k = len(scenes) + 1
            scenes.append({"n": k, "heading": t if is_head else ("المقدمة" if lang == "ar" else "Opening"), "int_ext": "", "location": "", "time": "",
                           "start": len(els), "end": len(els)})
            els.append({"type": "scene_heading", "text": scenes[-1]["heading"], "scene": k})
            if is_head:
                continue
        els.append({"type": "action", "text": t, "scene": scenes[-1]["n"]})
        scenes[-1]["end"] = len(els) - 1
    return {"schema": "zamakan-script/1", "source": str(p), "lang": lang, "kind": "documentary", "form": "treatment",
            "title_page": {"title": title}, "scenes": scenes, "elements": els, "unsure": []}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--av", action="store_true", help="the source is a two-column (picture | sound) script")
    ap.add_argument("--bites", help="bites.json, when the source is a paper edit's selects.json")
    ap.add_argument("--title")
    ap.add_argument("--out", default="script.json")
    a = ap.parse_args()
    if a.bites:
        sel = json.loads(Path(a.source).read_text(encoding="utf-8"))
        sc = PE.to_script(sel, json.loads(Path(a.bites).read_text(encoding="utf-8"))["bites"])
    elif a.av:
        sc = AV.to_script(AV.read(a.source, a.title))
    else:
        sc = treatment(a.source)
    if a.title:
        sc["title_page"]["title"] = a.title
    Path(a.out).write_text(json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK: {sc['form']} · {len(sc['scenes'])} sections · {len(sc['elements'])} elements → {a.out}")
    print('next: digest.py, then write notes.json with "lens_set": "documentary" (references/lenses_doc.json)')


if __name__ == "__main__":
    main()
