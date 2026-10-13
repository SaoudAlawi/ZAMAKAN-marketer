"""Build tests: spec.json -> tokens.json / tokens.css / manifest / sources / DESIGN.md / preview."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / ".claude/skills/zamakan-design-system/scripts"
GOLD = REPO / "evals/fixtures/rawaq/expected-spec.json"
INPUT = REPO / "samples/rawaq/input"
sys.path.insert(0, str(SCRIPTS))

from build_design_system import build, tint  # noqa: E402

GENERATED = ["tokens.json", "tokens.css", "manifest.json", "sources.md", "DESIGN.md"]


@pytest.fixture(scope="module")
def ds(tmp_path_factory):
    out = tmp_path_factory.mktemp("ds")
    result = build(GOLD, INPUT, out, preview=True)
    return out, result


def leaves(node, path=()):
    """Yield (path, token) for every DTCG token (dict with $value)."""
    if isinstance(node, dict):
        if "$value" in node:
            yield path, node
            return
        for k, v in node.items():
            if not k.startswith("$"):
                yield from leaves(v, path + (k,))


def test_all_files_generated(ds):
    out, _ = ds
    for f in GENERATED + ["spec.json", "preview.html"]:
        assert (out / f).exists(), f


# ---------------- tokens.json
def test_tokens_have_types_and_values(ds):
    out, _ = ds
    t = json.loads((out / "tokens.json").read_text())
    for path, tok in leaves(t):
        group = t[path[0]]
        assert tok.get("$type") or group.get("$type"), path
        assert tok["$value"] is not None, path


def test_token_references_resolve(ds):
    out, _ = ds
    t = json.loads((out / "tokens.json").read_text())
    names = {".".join(p) for p, _ in leaves(t)}
    refs = re.findall(r'"\{([a-z0-9.\-]+)\}"', (out / "tokens.json").read_text())
    assert refs
    assert all(r in names for r in refs), [r for r in refs if r not in names]


def test_token_values_match_spec(ds):
    out, _ = ds
    spec = json.loads(GOLD.read_text())
    t = json.loads((out / "tokens.json").read_text())
    for c in spec["colors"]:
        assert t["color"][c["id"]]["$value"]["hex"] == c["hex"]
    assert t["color"]["date-brown-20"]["$value"]["hex"] == tint("#4A2C21", 20)
    body = t["type"]["arabic"]["body"]["$value"]
    assert body["fontSize"] == {"value": 20, "unit": "px"} and body["lineHeight"] == 1.7
    assert t["type"]["latin"]["label"]["$value"]["letterSpacing"]["value"] == pytest.approx(1.44)
    assert t["color"]["saffron"]["$extensions"]["zamakan"]["status"] == "extracted"
    assert t["space"]["$extensions"]["zamakan"]["status"] == "proposed"


def test_tint_maths():
    assert tint("#000000", 50) in ("#7F7F7F", "#808080")
    assert tint("#4A2C21", 100) == "#4A2C21"


# ---------------- tokens.css
def test_css_vars_defined_and_fonts_exist(ds):
    out, _ = ds
    css = (out / "tokens.css").read_text()
    defined = set(re.findall(r"(--[a-z0-9-]+):", css))
    used = set(re.findall(r"var\((--[a-z0-9-]+)\)", css))
    assert used <= defined, used - defined
    urls = re.findall(r"url\('([^']+)'\)", css)
    assert len(urls) == 6 and all((out / u).exists() for u in urls)


def test_css_arabic_never_tracked(ds):
    out, _ = ds
    css = (out / "tokens.css").read_text()
    for line in css.splitlines():
        if line.startswith(".z-arabic-"):
            assert "letter-spacing" not in line and "direction: rtl" in line


# ---------------- manifest
def test_manifest_assets_exist(ds):
    out, _ = ds
    m = json.loads((out / "manifest.json").read_text())
    files = [f for lg in m["logos"] for f in lg["files"]] + [f for fo in m["fonts"] for f in fo["files"]]
    assert files and all((out / f).exists() for f in files)
    assert set(m["logo_for_background"]["date-brown"]) == {"reversed", "symbol-reversed"}
    assert "saffron" not in m["logo_for_background"]


# ---------------- sources.md
def test_sources_lists_conflicts_and_proposals(ds):
    out, _ = ds
    s = (out / "sources.md").read_text()
    assert "Saffron HEX" in s and "Needs client confirmation" in s
    proposed_rows = re.findall(r"^\| `[^`]+` \|.*\|$", s.split("## Proposed values")[1].split("##")[0], re.M)
    assert len(proposed_rows) == 4
    assert "1.8 fail" in s  # saffron on sand


# ---------------- DESIGN.md
def test_design_md_front_matter(ds):
    out, _ = ds
    text = (out / "DESIGN.md").read_text()
    fm = yaml.safe_load(text.split("---")[1])
    assert fm["colors"]["primary"] == "{colors.date-brown}" and fm["colors"]["date-brown"] == "#4A2C21"
    assert "ar-body-md" in fm["typography"] and fm["typography"]["ar-body-md"]["fontFamily"] == "IBM Plex Sans Arabic"
    sections = re.findall(r"^## (.+)$", text, re.M)
    order = ["Overview", "Colors", "Typography", "Layout", "Elevation & Depth", "Shapes", "Components", "Do's and Don'ts"]
    assert [s for s in sections if s in order] == [s for s in order if s in sections]


def _designmd_cli():
    for c in (os.environ.get("ZAMAKAN_DESIGNMD"), shutil.which("design.md")):
        if c and Path(c).exists():
            return c
    return None


@pytest.mark.skipif(not _designmd_cli(), reason="DESIGN.md CLI not installed (npm i -g @google/design.md)")
def test_design_md_passes_official_linter(ds):
    out, _ = ds
    r = subprocess.run([_designmd_cli(), "lint", str(out / "DESIGN.md")], capture_output=True, text=True)
    report = json.loads(r.stdout)
    assert report["summary"]["errors"] == 0, report


# ---------------- behaviour
def test_refuses_invalid_spec(tmp_path):
    bad = json.loads(GOLD.read_text())
    bad["color_roles"][0]["color"] = "nope"
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(SystemExit, match="unknown colour id"):
        build(p, INPUT, tmp_path / "out", preview=False)


def test_build_is_deterministic(ds, tmp_path):
    out, _ = ds
    build(GOLD, INPUT, tmp_path, preview=False)
    for f in GENERATED:
        assert (out / f).read_bytes() == (tmp_path / f).read_bytes(), f


def test_preview_rendered(ds):
    out, result = ds
    assert "preview_error" not in result, result.get("preview_error")
    from PIL import Image
    w, h = Image.open(out / "preview.png").size
    assert w == 1280 and h > 1500
