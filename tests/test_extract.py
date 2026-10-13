"""Extraction pipeline tests: run on the Rawaq sample and grade against the answer key."""
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / ".claude/skills/zamakan-design-system/scripts"
INPUT = REPO / "samples/rawaq/input"
KEY = json.loads((REPO / "evals/fixtures/rawaq/answer-key.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(SCRIPTS))

import extract_all  # noqa: E402
import logos as logos_mod  # noqa: E402
from pdf_digest import find_values, mask_arabic  # noqa: E402

ALL_COLORS = KEY["colors"]["primary"] + KEY["colors"]["secondary"]


@pytest.fixture(scope="module")
def work(tmp_path_factory):
    out = tmp_path_factory.mktemp("work")
    summary = extract_all.build_digest(INPUT, out)
    load = lambda n: json.loads((out / n).read_text(encoding="utf-8"))  # noqa: E731
    return {"out": out, "summary": summary, "pdf": load("pdf_digest.json"), "fonts": load("fonts.json"),
            "logos": load("logos.json"), "inv": load("inventory.json"),
            "digest": (out / "digest.md").read_text(encoding="utf-8"),
            "pages_md": (out / "pages.md").read_text(encoding="utf-8")}


def records(work):
    return [r for p in work["pdf"]["page_data"] for r in p["color_records"]]


# --- unit-level -------------------------------------------------------------

def test_mask_arabic():
    masked, n = mask_arabic("Brand Essence جوهر العلامة")
    assert n == 1 and masked == "Brand Essence ⟨AR⟩"
    assert mask_arabic("no arabic")[1] == 0


@pytest.mark.parametrize("text,kind,value", [
    ("HEX #4a2c21", "hex", "#4A2C21"),
    ("HEX 4A2C21", "hex", "#4A2C21"),
    ("Web: 4a2c21", "hex", "#4A2C21"),
    ("RGB: 74, 44, 33", "rgb", [74, 44, 33]),
    ("RGB 74/44/33", "rgb", [74, 44, 33]),
    ("R74 G44 B33", "rgb", [74, 44, 33]),
    ("CMYK 35 75 80 65", "cmyk", [35, 75, 80, 65]),
    ("C35 M75 Y80 K65", "cmyk", [35, 75, 80, 65]),
    ("PMS 4625C", "pantone", "4625C"),
    ("Pantone 7409 C", "pantone", "7409 C"),
])
def test_colour_notations(text, kind, value):
    found = [(k, v) for k, v, _ in find_values(text)]
    assert found == [(kind, value)], found


def test_hex_pattern_ignores_longer_tokens():
    assert not list(find_values("id #4A2C21FF"))


def test_no_double_count_hex_with_label():
    assert len(list(find_values("HEX #4A2C21"))) == 1


# --- inventory ----------------------------------------------------------------

def test_inventory_counts(work):
    assert work["inv"]["counts"] == {"font": 6, "guideline": 1, "license": 1, "logo": 10}


# --- colours vs answer key -----------------------------------------------------

def test_every_brand_colour_found(work):
    found = set(work["summary"]["palette"])
    missing = [c["name"] for c in ALL_COLORS if c["hex"] not in found]
    assert not missing


@pytest.mark.parametrize("c", [c for c in ALL_COLORS if c["name"] != "Charcoal"], ids=lambda c: c["name"])
def test_stated_colours_named_and_swatch_verified(work, c):
    rec = next(r for r in records(work) if r.get("hex") == c["hex"] and r["page"] == c["page"])
    assert c["name"] in rec.get("name_candidates", [])
    assert rec.get("verified_by_swatch")
    if "rgb" in c:
        assert rec["rgb"] == c["rgb"]
    if "cmyk" in c:
        assert rec["cmyk"] == c["cmyk"]
    if "pantone" in c:
        assert rec["pantone"] == c["pantone"]


def test_charcoal_trap(work):
    p10 = work["pdf"]["page_data"][9]
    assert any(u["hex"] == "#1F1B18" and "Charcoal" in u["text_inside"] for u in p10["unlabelled_swatches"])
    assert any(r.get("hex") == "#1F1B18" and r["page"] == 13 for r in records(work))


def test_saffron_conflict_trap(work):
    pairs = [set(c["values"]) for c in work["pdf"]["conflicts"]]
    assert {"#E3A33B", "#E4A23C"} in pairs
    assert "#E3A33B vs #E4A23C" in work["digest"]


def test_no_false_conflicts(work):
    assert len(work["pdf"]["conflicts"]) == 1


# --- pages -------------------------------------------------------------------------

def test_flattened_page_flagged(work):
    p7 = work["pdf"]["page_data"][6]
    assert p7["chars"] == 0 and any(f.startswith("image-only") for f in p7["flags"])
    assert "[7]" in work["digest"]


def test_arabic_never_leaks_garbled(work):
    assert not re.search(r"[؀-ۿ]", work["pages_md"])


def test_page_titles(work):
    titles = {p["page"]: p["title"] for p in work["pdf"]["page_data"]}
    assert titles[9] == "Primary Colour Palette" and titles[13] == "Type Hierarchy" and titles[12] == "Typefaces"


def test_renders_exist(work):
    assert (work["out"] / "pages/sheet.png").exists()
    assert len(list((work["out"] / "pages").glob("page-*.png"))) == 19


def test_digest_is_compact(work):
    assert len(work["digest"].encode()) < 12_000


# --- fonts ---------------------------------------------------------------------------

def test_font_families_and_scripts(work):
    fams = {f["family"]: f for f in work["fonts"]["families"]}
    for f in KEY["typography"]["families"]:
        fam = fams[f["family"]]
        assert set(f["weights"]) <= set(fam["weights"]), f["family"]
        assert ("arabic" in fam["scripts"]) == ("Arabic" in f["role"]), f["family"]


# --- logos ---------------------------------------------------------------------------

def logo(work, name):
    return next(lg for lg in work["logos"]["logos"] if lg["file"].endswith(name))


@pytest.mark.parametrize("name,orientation,colorway", [
    ("Rawaq_Logo_Primary_Stacked.svg", "stacked", "full-color"),
    ("Rawaq_Logo_Horizontal.svg", "horizontal", "full-color"),
    ("Rawaq_Symbol.svg", "square", "full-color"),
    ("Rawaq_Logo_Primary_Stacked_Reversed.svg", "stacked", "reversed"),
    ("Rawaq_Symbol_Reversed.svg", "square", "reversed"),
    ("Rawaq_Logo_Mono_Black.svg", "stacked", "mono-dark"),
    ("Rawaq_Logo_Primary_Stacked.png", "stacked", "full-color"),
    ("Rawaq_Logo_Primary_Stacked_Reversed_on_DateBrown.png", "stacked", "reversed"),
])
def test_logo_classification(work, name, orientation, colorway):
    lg = logo(work, name)
    assert (lg["orientation"], lg["colorway"]) == (orientation, colorway)


def test_logo_colours_snap_to_palette(work):
    for lg in work["logos"]["logos"]:
        if "Mono" in lg["file"]:
            continue
        assert all(m["palette"] for m in lg["palette_match"]), (lg["file"], lg["palette_match"])


def test_raster_background_detected(work):
    assert logo(work, "Reversed_on_DateBrown.png")["background"] == "#4A2C21"


def test_live_text_svg_warns(tmp_path):
    svg = tmp_path / "logo-text.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 50">'
                   '<text x="0" y="40" fill="#112233">ACME</text></svg>')
    info = logos_mod.analyse(svg)
    assert any("live <text>" in w for w in info["warnings"])
    assert info["colors"] == ["#112233"]
