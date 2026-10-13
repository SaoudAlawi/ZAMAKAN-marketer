"""Reference-scout contract: brief + references schemas and validate_run.py rules."""
import copy
import json
import sys
from pathlib import Path

import jsonschema
import pytest

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / ".claude/skills/zamakan-reference-scout"
FIX = REPO / "evals/fixtures/scout"
sys.path.insert(0, str(SKILL / "scripts"))

from validate_run import validate  # noqa: E402


@pytest.fixture
def run():
    return json.loads((FIX / "example-run.json").read_text(encoding="utf-8"))


def test_brief_fixture_valid():
    schema = json.loads((SKILL / "schemas/brief.schema.json").read_text())
    jsonschema.validate(json.loads((FIX / "rawaq-ramadan-brief.json").read_text(encoding="utf-8")), schema)


def test_example_run_valid(run):
    errors, warnings = validate(run)
    assert errors == []
    assert any("no 'wildcard' references" in w for w in warnings)


def ref(run, i=0):
    return run["references"][i]


def m_verified_in_search_only(r):
    ref(r)["status"] = "verified"

def m_verified_without_checked_url(r):
    r["run"]["web_access"] = "full"
    ref(r)["status"] = "verified"

def m_duplicate_id(r):
    r["references"].append(copy.deepcopy(ref(r)))

def m_same_url_two_refs(r):
    ref(r, 1)["urls"] = copy.deepcopy(ref(r, 0)["urls"])

def m_top_without_teardown(r):
    r["top"] = [ref(r)["id"]]

def m_territory_unknown_ref(r):
    r["territories"][0]["reference_ids"] = ["made-up-campaign"]

def m_bad_country(r):
    ref(r)["country"] = "Saudi"

def m_card_missing(r):
    del ref(r)["card"]

def m_bad_url(r):
    ref(r)["urls"][0]["url"] = "adsoftheworld.com/x"

def m_bad_ring(r):
    ref(r)["ring"] = "local"


@pytest.mark.parametrize("mutate,expect", [
    (m_verified_in_search_only, "search-only"),
    (m_verified_without_checked_url, "no URL has verified=true"),
    (m_duplicate_id, "duplicate reference id"),
    (m_same_url_two_refs, "same URL"),
    (m_top_without_teardown, "has no teardown"),
    (m_territory_unknown_ref, "unknown reference id 'made-up-campaign'"),
    (m_bad_country, "schema"),
    (m_card_missing, "schema"),
    (m_bad_url, "schema"),
    (m_bad_ring, "schema"),
])
def test_mutations_caught(run, mutate, expect):
    mutate(run)
    errors, _ = validate(run)
    assert any(expect in e for e in errors), errors


def test_top_with_teardown_ok_but_unverified_warns(run):
    ref(run)["teardown"] = {"insight": "x", "idea": "y", "execution": "z", "transferable": ["ritual framing"],
                            "cultural_fit": {"score": 4, "notes": "Saudi brand, Saudi context"}}
    run["top"] = [ref(run)["id"]]
    errors, warnings = validate(run)
    assert errors == []
    assert any("is unverified" in w for w in warnings)


def test_target_count_warning(run):
    _, warnings = validate(run, target=25)
    assert any("3 references, target 25" in w for w in warnings)


def test_skill_run_example_is_valid_and_not_the_test_brief():
    ex = json.loads((SKILL / "references/run-example.json").read_text(encoding="utf-8"))
    errors, _ = validate(ex)
    assert errors == []
    assert all(r["status"] == "verified" for r in ex["references"])
    assert "ramadan" not in json.dumps(ex).lower()  # must not leak the Rawaq Ramadan eval answers


def test_library_path_env_override(tmp_path, monkeypatch):
    import library
    monkeypatch.setenv("ZAMAKAN_LIBRARY", str(tmp_path / "lib.jsonl"))
    assert library.default_library() == tmp_path / "lib.jsonl"
