#!/usr/bin/env python3
"""Lay out a parsed script (script.json from parse_script.py) as a properly formatted screenplay: Word file, PDF
(LibreOffice, bundled fonts embedded) and a Fountain text file for screenwriting apps. Arabic scripts are right to
left with the binding margin on the right; scene headings are rebuilt consistently (داخلي - المكان - ليل) and
numbered; the page count gives a running-time estimate.

Usage:
  python format_script.py script.json --out <dir> [--name my-film] [--paper a4|letter] [--font "Simplified Arabic"]
                          [--latin-digits] [--no-numbers] [--no-pdf]

Writes <name>.docx, <name>.pdf, <name>.fountain (and <name>.fdx for English scripts) and adds {"format": {pages, est_minutes}} to script.json.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _screenplay as S  # noqa: E402

TITLE_LABELS = {"ar": {"author": "تأليف", "draft": "المسودة", "draft_date": "التاريخ", "contact": "للتواصل", "credit": "عن قصة"},
                "en": {"author": "Written by", "draft": "Draft", "draft_date": "Date", "contact": "Contact", "credit": "Based on"}}


def clean_heading(scene, lang):
    """One consistent heading: INT/EXT - PLACE - TIME (numbers are added by the layout)."""
    parts = [scene.get("int_ext"), scene.get("place"), scene.get("time")]
    if not scene.get("int_ext"):
        return re.sub(r"^\s*(?:(?:مشهد|م)\s*[\d٠-٩]+\s*[:.\-–]?\s*)", "", scene["heading"]).strip()
    if lang == "en":
        ie = scene["int_ext"].upper().rstrip(".")
        ie = {"INT": "INT.", "EXT": "EXT.", "INT/EXT": "INT./EXT.", "I/E": "INT./EXT."}.get(ie, scene["int_ext"].upper())
        return " - ".join(p for p in [ie + (" " + scene["place"] if scene.get("place") else "")] + [scene.get("time")] if p).upper()
    ie = re.sub(r"\s*/\s*", "/", scene["int_ext"]).replace("داخلى", "داخلي").replace("خارجى", "خارجي").replace("د/خ", "داخلي/خارجي")
    return " - ".join(p for p in [ie, scene.get("place"), scene.get("time")] if p)


def clean_transition(text, lang):
    t = text.strip(" -–—")
    if lang == "ar" and not t.endswith((":", ".")) and not t.startswith(("تلاشي", "النهاية")):
        t += ":"
    return t


def build_docx(sc, paper=None, font=S.ARABIC_FONT, arabic_digits=True, numbers=True, pmap=None):
    """pmap (a dict) collects element index → paragraph, for annotate.py."""
    lang = sc["lang"]
    doc = S.new_document(lang, paper, arabic_font=font)
    meta = sc.get("title_page") or {}
    if meta:
        for _ in range(9):
            doc.add_paragraph()
        p = doc.add_paragraph(style="Centered")
        r = p.add_run(meta.get("title", "").upper() if lang == "en" else meta.get("title", ""))
        r.bold = True
        r.font.size = S.Pt(16)
        if lang == "ar":
            r._r.get_or_add_rPr().append(S._el("w:rtl"))
            r._r.get_or_add_rPr().append(S._el("w:szCs", **{"w:val": 40}))
        for k in ("credit", "author", "draft", "draft_date", "contact"):
            if meta.get(k):
                q = doc.add_paragraph(style="Centered")
                rr = q.add_run(f"{TITLE_LABELS[lang][k]}: {meta[k]}")
                if lang == "ar":
                    rr._r.get_or_add_rPr().append(S._el("w:rtl"))
        S.page_break(doc)
    S.add_page_numbers(doc, lang)
    scenes = {s["n"]: s for s in sc["scenes"]}
    first = True
    for idx, e in enumerate(sc["elements"]):
        t = e["type"]
        if t in ("note", "synopsis"):
            continue
        if t == "section":
            continue  # acts/beats stay in the source and the reader's notes, not on the page
        text = e["text"]
        if t == "scene_heading":
            text = clean_heading(scenes[e["scene"]], lang)
        elif t == "transition":
            text = clean_transition(text, lang)
        elif t == "character":
            text = e.get("name", text) + (f" ({e['ext']})" if e.get("ext") else "")
        p = S.add_element(doc, t if t in S.STYLE_NAMES else "action", text, lang,
                          scene_no=e.get("scene") if (t == "scene_heading" and numbers) else None, arabic_digits=arabic_digits)
        if first:
            p.paragraph_format.space_before = 0
            first = False
        if pmap is not None:
            pmap[idx] = p
    return doc


def to_fountain(sc):
    """Fountain text (Arabic lines forced with . @ > so any Fountain app reads them right)."""
    lang, out = sc["lang"], []
    meta = sc.get("title_page") or {}
    keys = {"title": "Title", "author": "Author", "draft": "Draft", "draft_date": "Draft date", "contact": "Contact", "credit": "Credit"}
    for k, v in meta.items():
        out.append(f"{keys.get(k, k)}: {v}")
    if meta:
        out.append("")
    scenes = {s["n"]: s for s in sc["scenes"]}
    prev = None
    for e in sc["elements"]:
        t, text = e["type"], e["text"]
        if t == "scene_heading":
            out += ["", "." + clean_heading(scenes[e["scene"]], lang) + f" #{e['scene']}#"]
        elif t == "character":
            out += ["", ("@" if lang == "ar" else "") + e.get("name", text) + (f" ({e['ext']})" if e.get("ext") else "")]
        elif t in ("dialogue", "parenthetical"):
            out.append(text)
        elif t == "transition":
            out += ["", "> " + clean_transition(text, lang)]
        elif t == "centered":
            out += ["", f"> {text} <"]
        elif t == "section":
            out += ["", "#" * e.get("level", 1) + " " + text]
        elif t == "synopsis":
            out.append("= " + text)
        elif t == "note":
            out.append(f"[[{text}]]")
        else:
            out += ["", ("!" if lang == "ar" else "") + text]
        prev = t
    return "\n".join(out).strip() + "\n"


FDX_TYPE = {"scene_heading": "Scene Heading", "action": "Action", "character": "Character", "parenthetical": "Parenthetical",
            "dialogue": "Dialogue", "transition": "Transition", "centered": "Action"}


def to_fdx(sc):
    """Final Draft file (English scripts; Final Draft does not support right-to-left text)."""
    from xml.sax.saxutils import escape
    scenes = {s["n"]: s for s in sc["scenes"]}
    paras = []
    for e in sc["elements"]:
        t = FDX_TYPE.get(e["type"])
        if not t:
            continue
        text = clean_heading(scenes[e["scene"]], sc["lang"]) if e["type"] == "scene_heading" else \
            (e.get("name", e["text"]) + (f" ({e['ext']})" if e.get("ext") else "")) if e["type"] == "character" else e["text"]
        num = f' Number="{e["scene"]}"' if e["type"] == "scene_heading" else ""
        paras.append(f'    <Paragraph Type="{t}"{num}><Text>{escape(text)}</Text></Paragraph>')
    meta = sc.get("title_page") or {}
    title = "".join(f'      <Paragraph Type="Action" Alignment="Center"><Text>{escape(v)}</Text></Paragraph>\n' for v in
                    [meta.get("title", ""), meta.get("author", "")] if v)
    return ('<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n<FinalDraft DocumentType="Script" Template="No" Version="5">\n'
            "  <Content>\n" + "\n".join(paras) + "\n  </Content>\n  <TitlePage>\n    <Content>\n" + title + "    </Content>\n  </TitlePage>\n</FinalDraft>\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script")
    ap.add_argument("--out", required=True)
    ap.add_argument("--name")
    ap.add_argument("--paper", choices=["a4", "letter"])
    ap.add_argument("--font", default=S.ARABIC_FONT, help="Arabic font named in the Word file (PDF always embeds Amiri)")
    ap.add_argument("--latin-digits", action="store_true", help="scene numbers 1 2 3 instead of ١ ٢ ٣ in Arabic")
    ap.add_argument("--no-numbers", action="store_true")
    ap.add_argument("--no-pdf", action="store_true", help="skip the page count too (it needs a PDF rendering)")
    ap.add_argument("--also", default="", help="extra formats on request, comma-separated: pdf,fountain,fdx (Word is always made)")
    a = ap.parse_args()
    sc = json.loads(Path(a.script).read_text(encoding="utf-8"))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = a.name or re.sub(r"[^\w؀-ۿ-]+", "-", (sc.get("title_page") or {}).get("title") or Path(sc["source"]).stem).strip("-") or "script"
    docx = out / f"{name}.docx"
    build_docx(sc, a.paper, a.font, not a.latin_digits, not a.no_numbers).save(docx)
    also = {x.strip() for x in a.also.split(",") if x.strip()}
    msg = [f"Word → {docx}"]
    if "fountain" in also:
        (out / f"{name}.fountain").write_text(to_fountain(sc), encoding="utf-8")
        msg.append(f"Fountain → {out / (name + '.fountain')}")
    if "fdx" in also:
        if sc["lang"] == "en":
            (out / f"{name}.fdx").write_text(to_fdx(sc), encoding="utf-8")
            msg.append(f"Final Draft → {out / (name + '.fdx')}")
        else:
            msg.append("Final Draft: English scripts only (Final Draft's right-to-left support is unreliable)")
    pages = None
    if not a.no_pdf:
        if a.font != S.ARABIC_FONT:  # PDF uses the bundled font so it always renders
            tmp = out / f".{name}-pdf.docx"
            build_docx(sc, a.paper, S.ARABIC_FONT, not a.latin_digits, not a.no_numbers).save(tmp)
            pdf, err = S.to_pdf(tmp, out)
            if pdf:
                pdf = pdf.rename(out / f"{name}.pdf")
            tmp.unlink(missing_ok=True)
        else:
            pdf, err = S.to_pdf(docx, out)
        if pdf:
            pages = S.pdf_pages(pdf)
            body = pages - (1 if sc.get("title_page") else 0) if pages else None
            msg.append((f"PDF → {pdf} · " if "pdf" in also else "") + f"{body} script pages ≈ {body} min at one page a minute")
            sc["format"] = {"pages": body, "est_minutes": body, "paper": a.paper or ("a4" if sc["lang"] == "ar" else "letter"),
                            "note": "one page ≈ one minute is the English convention; for Arabic it is unverified, so time a read-through"}
            Path(a.script).write_text(json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8")
            if "pdf" not in also:  # rendered only to count pages; Word is the deliverable
                pdf.unlink(missing_ok=True)
        else:
            msg.append(err)
    print("\n".join(msg))


if __name__ == "__main__":
    main()
