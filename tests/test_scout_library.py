"""Reference library: client-neutral shared pages (awesome-design-md style) + private client notes."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / ".claude/skills/zamakan-reference-scout/scripts"
FIX = REPO / "evals/fixtures/scout"
sys.path.insert(0, str(SCRIPTS))

import library as L  # noqa: E402


@pytest.fixture
def added(tmp_path, monkeypatch):
    lib = tmp_path / "shared/library/references.jsonl"
    monkeypatch.setenv("ZAMAKAN_CLIENTS", str(tmp_path / "clients"))
    run = json.loads((FIX / "rawaq-ramadan-sample-run.json").read_text(encoding="utf-8"))
    run["references"][0]["card"]["idea"] += " Rawaq could own this."              # a leak the guard must stop
    run["references"][0]["teardown"]["execution"] += " Perfect for Rawaq Coffee Roasters."
    src = tmp_path / "references.json"
    src.write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, SCRIPTS / "library.py", "add", src,
                        "--client", "rawaq", "--client-name", "Rawaq Coffee Roasters", "--library", lib],
                       capture_output=True, text=True, check=True, env={**__import__("os").environ, "ZAMAKAN_CLIENTS": str(tmp_path / "clients")})
    return lib, tmp_path / "clients/rawaq/library", r.stdout


def test_shared_library_is_client_neutral(added):
    lib, _, out = added
    shared = "\n".join(p.read_text(encoding="utf-8") for p in lib.parent.rglob("*") if p.is_file())
    assert "rawaq" not in shared.lower() and "رواق" not in shared  # no client name anywhere in the shared layer
    for word in ("why_relevant", "transferable", "cultural_fit", "scores", "ring"):
        assert f'"{word}"' not in lib.read_text(encoding="utf-8")
    assert "kept out of the shared library" in out and "summary, teardown.execution" in out  # moved, and said so


def test_one_page_per_campaign_with_front_matter(added):
    import yaml
    lib, _, _ = added
    run = json.loads((FIX / "rawaq-ramadan-sample-run.json").read_text(encoding="utf-8"))
    live = [r for r in run["references"] if r["status"] != "rejected"]
    pages = sorted(lib.parent.glob("campaigns/*/REFERENCE.md"))
    assert len(pages) == len(live)
    alj = (lib.parent / "campaigns/abdul-latif-jameel-motors-iftar-is-always-better-together/REFERENCE.md").read_text(encoding="utf-8")
    fm = yaml.safe_load(alj.split("---")[1])
    assert fm["country"] == "SA" and fm["region"] == "GCC" and fm["links"][0]["verified"] is True
    for section in ("## Overview", "## Insight", "## The idea", "## Tone", "## Links"):
        assert section in alj
    assert "Al Khobar" not in alj  # the planted execution line named the client, so it stayed private


def test_index_by_moment_category_market(added):
    lib, _, _ = added
    idx = (lib.parent / "README.md").read_text(encoding="utf-8")
    for h in ("## By moment", "## By category", "## By market", "## All campaigns", "**GCC**", "**Ramadan**"):
        assert h in idx
    for link in __import__("re").findall(r"\]\((campaigns/[^)]+)\)", idx):
        assert (lib.parent / link).exists(), link


def test_private_client_notes(added):
    _, notes_dir, _ = added
    notes = [json.loads(l) for l in (notes_dir / "notes.jsonl").read_text(encoding="utf-8").splitlines()]
    alj = next(n for n in notes if n["id"] == "alj-toyota-iftar-better-together")
    assert alj["ring"] == "direct" and "Rawaq" in alj["why_relevant"] and alj["transferable"] and alj["top"]
    assert "Who hosts tonight?" in alj["territories"]
    assert "Rawaq could own this." in alj["moved_from_shared"]["summary"]  # the leaked text is kept privately, not lost
    readme = (notes_dir / "README.md").read_text(encoding="utf-8")
    assert "rawaq-ramadan-2027-sample" in readme and "REFERENCE.md" in readme


def test_clients_folder_is_git_ignored():
    r = subprocess.run(["git", "check-ignore", "clients/rawaq/library/notes.jsonl"], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0


def test_old_format_records_migrate():
    old = {"key": "x.com/a", "id": "a", "title": "T", "brand": "B", "urls": [{"url": "https://x.com/a"}], "status": "verified",
           "seen_in": [{"run": "acme-run", "client": "acme", "date": "2026-01-01", "card": {"idea": "An idea.", "why_relevant": "For Acme."}}],
           "teardown": {"insight": "I", "transferable": ["Do it for Acme"], "cultural_fit": {"score": 4, "notes": "n"}}}
    new = L.neutral(old)
    assert new["summary"] == "An idea." and new["used"]["runs"] == 1 and new["teardown"] == {"insight": "I"}
    assert "seen_in" not in new and "acme" not in json.dumps(new).lower()


def test_same_run_twice_counts_once(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAMAKAN_CLIENTS", str(tmp_path / "clients"))
    run = json.loads((FIX / "rawaq-ramadan-sample-run.json").read_text(encoding="utf-8"))
    lib = {}
    L.merge(lib, run, "rawaq")
    L.merge(lib, run, "rawaq")
    assert {r["used"]["runs"] for r in lib.values()} == {1}
    assert "rawaq" not in json.dumps(lib).lower()


def test_local_paths_never_reach_the_shared_library():
    """Found by a benchmark agent: thumbnail.local held /…/clients/<client>/jobs/… in the shared library."""
    rec = {"key": "x.com/a", "id": "a", "title": "T", "urls": [{"url": "https://x.com/a"}], "status": "verified",
           "thumbnail": {"url": "https://img.x.com/a.jpg", "local": "/w/clients/acme/jobs/2026-scout/thumbs/a.jpg"}}
    assert L.neutral(rec)["thumbnail"] == {"url": "https://img.x.com/a.jpg"}
    assert "thumbnail" not in L.neutral({**rec, "thumbnail": {"local": "/w/clients/acme/x.jpg"}})


def test_client_relative_tags_stay_private():
    """'client-own-work' or 'competitor' only make sense for one client: shared, they'd reveal who the client is."""
    rec = {"key": "k", "title": "T", "brand": "B", "tags": ["client-own-work", "competitor", "csr"]}
    assert L.neutral(rec)["tags"] == ["csr"]
    assert "tags" not in L.neutral({"key": "k", "title": "T", "brand": "B", "tags": ["competitor"]})
