"""Tests for the design-system spec contract (schema + validate_spec.py)."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / ".claude/skills/zamakan-design-system/scripts"
GOLD = REPO / "evals/fixtures/rawaq/expected-spec.json"
ROOT = REPO / "samples/rawaq/input"
sys.path.insert(0, str(SCRIPTS))

from _common import contrast_ratio, hex_to_rgb, rgb_to_hex, wcag_grade  # noqa: E402
from validate_spec import validate  # noqa: E402


@pytest.fixture
def gold():
    return json.loads(GOLD.read_text(encoding="utf-8"))


def color(spec, cid):
    return next(c for c in spec["colors"] if c["id"] == cid)


# --- colour maths ---------------------------------------------------------

def test_hex_roundtrip():
    assert hex_to_rgb("#4A2C21") == (74, 44, 33)
    assert rgb_to_hex((74, 44, 33)) == "#4A2C21"


def test_contrast_known_values():
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert wcag_grade(contrast_ratio("#E3A33B", "#F3E7D3")) == "fail"  # Saffron on Sand
    assert wcag_grade(contrast_ratio("#1F1B18", "#F3E7D3")) == "AAA"   # Charcoal on Sand


# --- gold spec ---------------------------------------------------------------

def test_gold_spec_is_valid(gold):
    errors, warnings = validate(gold, ROOT)
    assert errors == []
    assert warnings == []


def test_cli_ok_exit_code():
    r = subprocess.run([sys.executable, SCRIPTS / "validate_spec.py", GOLD, "--root", ROOT, "--json"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["ok"] and out["status_counts"]["proposed"] >= 1


# --- each mutation must be caught -------------------------------------------

def mutate_missing_sources(s):
    del color(s, "date-brown")["sources"]

def mutate_proposed_without_rationale(s):
    del s["spacing"]["rationale"]

def mutate_unknown_color_ref(s):
    s["color_roles"][0]["color"] = "midnight-blue"

def mutate_rgb_mismatch(s):
    color(s, "saffron")["rgb"] = [228, 162, 60]

def mutate_lowercase_hex(s):
    color(s, "sand")["hex"] = "#f3e7d3"

def mutate_conflict_chosen_unused(s):
    s["conflicts"][0]["chosen"] = "#E4A23C"

def mutate_unknown_field(s):
    color(s, "sand")["colour"] = "typo"

def mutate_font_script_mismatch(s):
    s["type_scale"][0]["font"] = "reem-kufi"  # latin display set in an Arabic font

def mutate_duplicate_id(s):
    s["colors"].append(copy.deepcopy(color(s, "sand")))

def mutate_missing_file(s):
    s["logo"]["variants"][0]["files"].append("Logos/does-not-exist.svg")

def mutate_bad_status(s):
    color(s, "sand")["status"] = "guessed"


@pytest.mark.parametrize("mutate,expect", [
    (mutate_missing_sources, "no sources"),
    (mutate_proposed_without_rationale, "no rationale"),
    (mutate_unknown_color_ref, "unknown colour id"),
    (mutate_rgb_mismatch, "rgb"),
    (mutate_lowercase_hex, "schema"),
    (mutate_conflict_chosen_unused, "not used in colors"),
    (mutate_unknown_field, "schema"),
    (mutate_font_script_mismatch, "is arabic, not latin"),
    (mutate_duplicate_id, "duplicate colour id"),
    (mutate_missing_file, "file not found"),
    (mutate_bad_status, "schema"),
])
def test_mutations_are_caught(gold, mutate, expect):
    mutate(gold)
    errors, _ = validate(gold, ROOT)
    assert any(expect in e for e in errors), errors


def test_low_contrast_role_warns(gold):
    next(r for r in gold["color_roles"] if r["role"] == "text-primary")["color"] = "saffron"
    errors, warnings = validate(gold, ROOT)
    assert errors == []
    assert any("contrast: text-primary on background" in w for w in warnings)


def test_one_sided_type_level_warns(gold):
    gold["type_scale"] = [t for t in gold["type_scale"] if not (t["level"] == "h3" and t["script"] == "arabic")]
    _, warnings = validate(gold, ROOT)
    assert any("'h3' defined for only one script" in w for w in warnings)


def test_spec_guide_example_is_valid():
    """The worked example in references/spec-guide.md must itself pass the schema + semantic checks."""
    guide = (REPO / ".claude/skills/zamakan-design-system/references/spec-guide.md").read_text(encoding="utf-8")
    block = guide.split("```json", 1)[1].split("```", 1)[0]
    errors, _ = validate(json.loads(block))  # no --root: example files don't exist on disk
    assert errors == []
