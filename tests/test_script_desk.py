"""Script desk: templates, parser, formatter, digest and the reader's outputs (no network; LibreOffice tests skip
when it is missing)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / ".claude" / "skills" / "zamakan-script-desk"
sys.path.insert(0, str(DESK / "scripts"))
import _screenplay as S  # noqa: E402
import annotate as A  # noqa: E402
import build_template as B  # noqa: E402
import digest as D  # noqa: E402
import format_script as F  # noqa: E402
import parse_script as P  # noqa: E402

SAMPLE = ROOT / "samples" / "script-desk" / "al-mirsah-draft.txt"
SOFFICE = shutil.which("soffice") or shutil.which("libreoffice")


@pytest.fixture(scope="module")
def sc():
    s = P.parse(SAMPLE, fixes={"56": "character"})
    return s


def test_structures_are_well_formed():
    for st in S.STRUCTURES["structures"]:
        assert st["name_ar"] and st["source"] and st["fits"]
        for b in st["beats"]:
            assert 0 <= b["at"] < b["end"] <= 100, (st["id"], b["id"])
            assert b["questions"] and len(b["questions"]) == len(b["questions_ar"]), (st["id"], b["id"])


def test_beat_pages_cover_the_film():
    st = next(s for s in S.STRUCTURES["structures"] if s["id"] == "short-one-moment")
    pages = [B.beat_pages(b, 12) for b in st["beats"]]
    assert pages[0][0] == 1 and pages[-1][1] == 12
    assert all(a <= b for a, b in pages)


def test_template_has_styles_and_rtl(tmp_path):
    doc = B.build("three-act", 90, "ar", "اختبار")
    names = {s.name for s in doc.styles}
    assert {"Scene Heading", "Action", "Character", "Dialogue", "Parenthetical", "Transition"} <= names
    assert doc.sections[0]._sectPr.find(S.qn("w:bidi")) is not None
    assert doc.sections[0].right_margin > doc.sections[0].left_margin  # binding margin on the right in Arabic
    out = tmp_path / "t.docx"
    doc.save(out)
    back = P.parse(out)  # the template's sample draft lines read back by style
    assert len(back["scenes"]) == 1 and any(e["type"] == "character" for e in back["elements"])


def test_parse_arabic_sample(sc):
    assert sc["lang"] == "ar" and len(sc["scenes"]) == 13
    assert sc["title_page"]["title"] == "المرساة"
    s4 = [e for e in sc["elements"] if e.get("scene") == 4]
    assert [e["type"] for e in s4[:4]] == ["scene_heading", "action", "character", "dialogue"]  # «الجدة: …» split
    assert sc["scenes"][6]["int_ext"] == "خارجي" and sc["scenes"][6]["time"] == "ليل"
    assert not sc["unsure"]


def test_unsure_one_off_cue_is_listed_not_guessed():
    s = P.parse(SAMPLE)
    assert [u["text"] for u in s["unsure"]] == ["صياد"]


def test_parse_english_fountain(tmp_path):
    f = tmp_path / "x.fountain"
    f.write_text("INT. KITCHEN - NIGHT\n\nA kettle.\n\nSARA\n(quietly)\nNot tonight.\n\nJOHN (O.S.)\nSara?\n\nCUT TO:\n\n.ROOFTOP\n\nRain.\n", encoding="utf-8")
    s = P.parse(f)
    types = [e["type"] for e in s["elements"]]
    assert s["lang"] == "en" and len(s["scenes"]) == 2
    assert types.count("character") == 2 and "parenthetical" in types and "transition" in types
    john = next(e for e in s["elements"] if e.get("name") == "JOHN")
    assert john["ext"] == "O.S."


def test_heading_parts_any_order():
    assert P.heading_parts("مشهد ٣: ليل - داخلي - بيت سالم") == {"int_ext": "داخلي", "place": "بيت سالم", "time": "ليل"}
    assert P.heading_parts("EXT. STREET - DAY")["int_ext"].startswith("EXT")


def test_format_round_trip(sc, tmp_path):
    doc = F.build_docx(sc)
    out = tmp_path / "f.docx"
    doc.save(out)
    back = P.parse(out)
    assert len(back["scenes"]) == 13 and back["title_page"]["title"] == "المرساة"
    assert [e["type"] for e in back["elements"]] == [e["type"] for e in sc["elements"] if e["type"] not in ("note", "synopsis", "section")]
    assert "@صياد" in F.to_fountain(sc) and ".خارجي - شاطئ صور - فجر #1#" in F.to_fountain(sc)


@pytest.mark.skipif(not SOFFICE, reason="LibreOffice not installed")
def test_pdf_embeds_fonts_and_mirrors(sc, tmp_path):
    import pymupdf
    out = tmp_path / "f.docx"
    F.build_docx(sc).save(out)
    pdf, err = S.to_pdf(out, tmp_path)
    assert pdf, err
    with pymupdf.open(pdf) as d:
        fonts = {f[3] for p in d for f in p.get_fonts()}
        assert any("NotoNaskhArabic" in f for f in fonts)
        page = d[1]
        x1 = max(l["bbox"][2] for b in page.get_text("dict")["blocks"] for l in b.get("lines", []))
        assert abs(page.rect.width - x1 - 1.5 * 72) < 12  # text ends at the 1.5" binding margin on the right


def test_digest_flags(sc):
    d = D.digest(sc, "short-one-moment")
    assert d["protagonist_guess"] == "مريم"
    assert [3, 5] in d["same_place_same_people"]
    assert any(m["character"] == "الجدة" for m in d["dialect_mix"])
    assert any(t["scene"] == 1 for t in d["telling_lines"])
    assert 7 in d["production"]["night exterior"] and 6 in d["silent_scenes"]
    assert len(D.show(d)) < 6000  # stays a compact read


def notes(**over):
    n = {"schema": "zamakan-script-notes/1", "lang": "ar", "logline_read": "x", "overall": {"verdict": "amber", "summary": "x"},
         "lenses": [{"id": lid, "verdict": "green", "summary": "x"} for lid in A.LENS],
         "notes": [{"scene": 1, "lens": "visual", "kind": "strength", "text": "صورة افتتاحية قوية."}], "next_draft": ["x"]}
    n.update(over)
    return n


def test_notes_checker(sc):
    assert A.check(sc, notes()) == ([], [])
    bad = notes()
    bad["lenses"][1]["verdict"] = "red"  # red with no note
    bad["notes"].append({"scene": 99, "lens": "structure", "kind": "issue", "text": "x"})
    bad["notes"].append({"scene": 2, "lens": "dialogue", "kind": "issue", "text": "x", "quote": "كلام غير موجود"})
    errs, _ = A.check(sc, bad)
    assert any("scene 99" in e for e in errs) and any("quote not found" in e for e in errs)
    missing = notes(lenses=[{"id": "premise", "verdict": "green", "summary": "x"}])
    assert any("has no verdict" in e for e in A.check(sc, missing)[0])
    rewrite = notes(notes=[{"scene": 2, "lens": "dialogue", "kind": "issue", "text": "اكتبها هكذا: «أنا خايفة عليك يا بنتي من البحر ومن كل شي فيه وما أقدر أشوفك تروحين»"}])
    assert any("rewriting" in w for w in A.check(sc, rewrite)[1])


def test_annotated_docx_has_comments_and_notes_page(sc, tmp_path):
    n = notes()
    n["lenses"][1]["verdict"] = "amber"
    n["notes"].append({"scene": 3, "lens": "structure", "kind": "question", "text": "ما الجديد هنا؟", "quote": "خلاص. قلت لا."})
    doc = A.annotate(sc, n, "ar")
    out = tmp_path / "n.docx"
    doc.save(out)
    from docx import Document
    d = Document(out)
    assert len(d.comments) == 2
    texts = [p.text for p in d.paragraphs]
    assert texts.index("ملاحظات القراءة") < next(i for i, t in enumerate(texts) if "خارجي - شاطئ صور" in t)


def test_cli_end_to_end(tmp_path):
    js = tmp_path / "s.json"
    r = subprocess.run([sys.executable, str(DESK / "scripts" / "parse_script.py"), str(SAMPLE), "--out", str(js)], capture_output=True, text=True)
    assert r.returncode == 0 and "unsure" in r.stdout
    r = subprocess.run([sys.executable, str(DESK / "scripts" / "show.py"), str(js), "9"], capture_output=True, text=True)
    assert "الجدة:" in r.stdout and "S9" in r.stdout
