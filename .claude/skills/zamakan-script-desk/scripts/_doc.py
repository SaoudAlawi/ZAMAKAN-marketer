"""Shared pieces for documentary work: the proposal sections and the two-column picture | sound table used by the
treatment's draft section, the A/V script and the paper edit. In Arabic the picture column is on the right (first)."""
import json

import _screenplay as S

PROPOSAL = json.loads((S.SKILL / "references" / "doc_proposal.json").read_text(encoding="utf-8"))["sections"]
AV_HEAD = {"ar": ("الصورة", "الصوت"), "en": ("PICTURE", "SOUND")}


def is_doc(structure_id):
    st = next((x for x in S.STRUCTURES["structures"] if x["id"] == structure_id), None)
    return bool(st and "documentary" in st["fits"])


def _run(p, text, lang, bold=False, color=None, size=None):
    r = p.add_run(text)
    r.bold = bold or None
    if color:
        r.font.color.rgb = S.RGBColor.from_string(color)
    if size:
        r.font.size = S.Pt(size)
    if lang == "ar":
        r._r.get_or_add_rPr().append(S._el("w:rtl"))
    return r


def av_table(doc, rows, lang, head=None, widths=(2.85, 2.95), number=True, fills=None):
    """rows: [(picture text, sound text, extra)], extra = {"tc": "...", "speaker": "...", "label": "..."} (optional).
    Picture column first in reading order (right in Arabic). fills: per-row hex for the sound cell (theme tint)."""
    head = head or AV_HEAD[lang]
    cols = 3 if number else 2
    t = doc.add_table(rows=len(rows) + 1, cols=cols)
    t.style = "Table Grid"
    pr = t._tbl.tblPr
    pr.append(S._el("w:tblW", **{"w:w": 5000, "w:type": "pct"}))
    pr.append(S._el("w:tblLayout", **{"w:type": "fixed"}))
    if lang == "ar":
        pr.append(S._el("w:bidiVisual"))
    ws = ((0.45,) if number else ()) + tuple(widths)
    for gc, w in zip(t._tbl.tblGrid.findall(S.qn("w:gridCol")), ws):
        gc.set(S.qn("w:w"), str(int(w * 1440)))
    heads = (("#",) if number else ()) + tuple(head)
    for j, h in enumerate(heads):
        p = t.cell(0, j).paragraphs[0]
        if lang == "ar":
            p._p.get_or_add_pPr().append(S._el("w:bidi"))
        _run(p, h, lang, bold=True)
        t.cell(0, j)._tc.get_or_add_tcPr().append(S._el("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": "EFECE6"}))
    for i, (pic, snd, extra) in enumerate(rows, 1):
        extra = extra or {}
        cells = t.rows[i].cells
        k = 0
        if number:
            p = cells[0].paragraphs[0]
            _run(p, S.digits(i, lang), lang, bold=True)
            k = 1
        for j, (text, part) in enumerate(((pic, "pic"), (snd, "snd"))):
            cell = cells[k + j]
            p = cell.paragraphs[0]
            if lang == "ar":
                p._p.get_or_add_pPr().append(S._el("w:bidi"))
            if part == "snd" and (extra.get("speaker") or extra.get("tc")):
                _run(p, " · ".join(x for x in (extra.get("speaker"), extra.get("tc")) if x), lang, bold=True, color="5E5A53", size=9)
                p = cell.add_paragraph()
                if lang == "ar":
                    p._p.get_or_add_pPr().append(S._el("w:bidi"))
            _run(p, text or "", lang)
            if part == "snd" and extra.get("label"):
                q = cell.add_paragraph()
                if lang == "ar":
                    q._p.get_or_add_pPr().append(S._el("w:bidi"))
                _run(q, extra["label"], lang, color="5E5A53", size=9)
            if part == "snd" and fills and fills[i - 1]:
                cell._tc.get_or_add_tcPr().append(S._el("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": fills[i - 1]}))
    return t
