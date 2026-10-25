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
    errs, warns = A.check(sc, notes())
    assert errs == [] and any("tension" in w for w in warns)
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


# ---- v0.2: charts, side notes, voices, draft comparison ----
import charts as C  # noqa: E402
import compare as CMP  # noqa: E402
import side_notes as SN  # noqa: E402

SAMPLE2 = ROOT / "samples" / "script-desk" / "al-mirsah-draft2.txt"


def full_notes():
    n = notes()
    n["structure"] = "short-one-moment"
    n["lenses"][2]["verdict"] = "red"  # character
    n["notes"] += [{"scene": 8, "lens": "character", "kind": "issue", "text": "القرار قرار سالم. ماذا تختار مريم؟", "quote": "مريم بتطلع مع حمد"},
                   {"scene": 4, "lens": "structure", "kind": "question", "text": "ما دور البوصلة؟"}]
    n["lenses"][1]["verdict"] = "amber"
    n["turns"] = {"hook": 1, "turn": 8, "after": 13}
    n["tension"] = {str(i): (5 if i == 7 else 2) for i in range(1, 14)}
    return n


def test_turns_and_tension_are_checked(sc):
    n = full_notes()
    assert A.check(sc, n)[0] == []
    n["turns"]["midpoint"] = 5  # not a beat of short-one-moment
    n["tension"]["40"] = 3
    errs = A.check(sc, n)[0]
    assert any("not a beat" in e for e in errs) and any("unknown scenes" in e for e in errs)


def test_scene_marks_worst_wins(sc):
    m = SN.scene_marks(sc, full_notes())
    assert m[8] == "red" and m[4] == "question" and m[1] == "green"


def test_side_notes_place_cards_beside_their_lines(sc):
    page = SN.build(sc, full_notes(), "ar")
    assert page.count('class="card') == 3 and 'dir="rtl"' in page
    i = page.index("مريم بتطلع مع حمد")  # the quoted line, then its card in the same row
    assert page.index("القرار قرار سالم", i) - i < 400


def test_charts_render_for_arabic(sc):
    d = D.digest(sc, "short-one-moment")
    st = next(s for s in S.STRUCTURES["structures"] if s["id"] == "short-one-moment")
    frags = C.all_charts(d, full_notes(), st, SN.scene_marks(sc, full_notes()), "ar")
    assert len(frags) == 6
    html = "".join(frags)
    assert "خريطة المحطات" in html and "منحنى التوتر" in html and "خريطة اللهجات" in html and "لوحة التصوير" in html
    assert "#d03b3b" in html  # the red scene in the health strip
    assert C.strip_kind({"int_ext": "خارجي", "time": "ليل"}) == "ext_night" and C.strip_kind({"int_ext": "داخلي", "time": "فجر"}) == "dawn_dusk"


def test_voice_profiles(sc):
    d = D.digest(sc)
    v = {x["name"]: x for x in d["voices"]}
    assert v["الجدة"]["avg_words"] > v["مريم"]["avg_words"] * 2
    assert all("،" not in w and "؟" not in w for x in d["voices"] for w in x["own_words"])


def test_compare_drafts(sc):
    sc2 = P.parse(SAMPLE2)
    c = CMP.compare(sc, full_notes(), sc2)
    assert c["cut"] == [5, 7, 9] and c["scene_map"]["1"]["status"] == "same"
    assert 1 not in c["reread"] and 7 in c["reread"]
    by = {it["old_scene"]: it for it in c["previous_notes"]}
    assert by[8]["new_scene"] == 7 and by[8]["start"].startswith("re-read")
    assert by[4]["start"].startswith("probably open")  # compass scene unchanged: Claude must still check elsewhere


def test_previous_section_in_outputs(sc):
    n = full_notes()
    n["previous"] = {"draft": "1", "items": [{"id": 0, "status": "resolved", "text": "قرار مريم", "scene": 7},
                                             {"id": 1, "status": "open", "text": "سطر الأفكار في المشهد ١", "scene": 1}]}
    assert A.check(sc, n)[0] == []
    import report as R
    page = R.build(sc, n, D.digest(sc, "short-one-moment"), "ar")
    assert "منذ المسودة 1" in page and "حُلّت" in page and "ما زالت قائمة" in page


# ---- v0.3: intent sheet, margin conversation, scene cards, arcs ----
import cards as CARDS  # noqa: E402
import intent as INT  # noqa: E402
import replies as REP  # noqa: E402


def filled_intent(tmp_path, sc):
    from docx import Document
    path = tmp_path / "intent.docx"
    INT.form("ar", "المرساة", sc).save(path)
    d = Document(path)
    t = d.tables[0]
    t.cell(0, 1).paragraphs[0].add_run("عن الحزن حين يتحول إلى فعل")
    t.cell(4, 1).paragraphs[0].add_run("الجدة تبارك بالفصحى عمداً")
    t.cell(4, 1).add_paragraph("النهاية مفتوحة عمداً")
    t.cell(6, 1).paragraphs[0].add_run("١٢ دقيقة")
    for row in d.tables[1].rows[1:]:
        name = row.cells[0].text.strip()
        row.cells[1].paragraphs[0].add_run({"الجدة": "يتنقل", "الأم": "خليجي"}.get(name, ""))
    d.save(path)
    return INT.read(path)


def test_intent_round_trip_and_declared_dialects(tmp_path, sc):
    it = filled_intent(tmp_path, sc)
    assert it["about"].startswith("عن الحزن") and it["intentional"] == ["الجدة تبارك بالفصحى عمداً", "النهاية مفتوحة عمداً"]
    assert it["minutes"] == 12 and {c["name"]: c["dialect"] for c in it["characters"]}["الجدة"] == "mixed"
    d = D.digest(sc, intent=it)
    flagged = {m["character"]: m for m in d["dialect_mix"]}
    assert "الجدة" not in flagged  # declared as switching on purpose
    assert flagged["الأم"]["declared"] == "gulf" and "2" in flagged["الأم"]["by_scene"]
    assert "writer's intent" in D.show(d)


def test_intent_check_required_when_intent_given(sc):
    n = full_notes()
    assert any("intent_check" in e for e in A.check(sc, n, intent={"about": "x"})[0])
    n["intent_check"] = [{"intent": "x", "lands": "partly", "note": "y", "scene": 8}]
    assert A.check(sc, n, intent={"about": "x"})[0] == []


def test_replies_read_back_from_word(tmp_path, sc):
    n = full_notes()
    doc = A.annotate(sc, n, "ar")
    target = next(p for p in doc.paragraphs if "مريم بتطلع مع حمد" in p.text)
    doc.add_comment(target.runs, text="معك حق، بغيّرها.", author="الكاتب", initials="K")
    out = tmp_path / "back.docx"
    doc.save(out)
    items = REP.read(out, n)
    by = {i["id"]: i for i in items}
    k = next(i for i, x in enumerate(n["notes"]) if x.get("quote") == "مريم بتطلع مع حمد")
    assert by[k]["replies"][0]["text"] == "معك حق، بغيّرها." and by[k]["scene"] == 8
    sc2 = P.parse(SAMPLE2)
    c = CMP.compare(sc, n, sc2, {i["id"]: i for i in items})
    assert next(x for x in c["previous_notes"] if x["id"] == k)["writer"]["replies"] == ["معك حق، بغيّرها."]


def test_cards_board_table_and_reorder(tmp_path, sc):
    stats = D.digest(sc, "short-one-moment")
    page = CARDS.board(sc, stats, full_notes(), "ar")
    assert page.count('class="c"') == 13 and "الضغط" in page
    path = tmp_path / "cards.docx"
    CARDS.table(sc, full_notes(), "ar").save(path)
    from docx import Document
    d = Document(path)
    for row in d.tables[0].rows[1:]:
        n = int(row.cells[0].text)
        row.cells[1].paragraphs[0].add_run({6: "7", 7: "6", 9: "x"}.get(n, str(n)))
    d.save(path)
    order, dropped = CARDS.read_order(path, 13)
    assert order[5:7] == [7, 6] and dropped == [9] and len(order) == 12
    new = CARDS.reorder(sc, order)
    assert len(new["scenes"]) == 12 and new["scenes"][5]["was"] == 7 and new["scenes"][5]["place"] == "البحر المفتوح"


def test_arc_chart(sc):
    n = full_notes()
    n["arcs"] = {"مريم": {"start": "تنتظر", "end": "تبحر", "points": {"1": {"value": -1}, "13": {"value": 2, "want": "أن تبحر"}}}}
    assert A.check(sc, n)[0] == []
    html = C.arc_chart(D.digest(sc), n, "ar")
    assert "أقواس الشخصيات" in html and "تنتظر" in html and "#2a78d6" in html
    n["arcs"]["مريم"]["points"]["99"] = {"value": 0}
    assert any("unknown scenes" in e for e in A.check(sc, n)[0])
