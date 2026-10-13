"""Benchmark tooling: scenario files, run preparation (isolation rules in prompts) and the scorecard (offline)."""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "evals"))

import bench_scout as BS  # noqa: E402
import grade_scout as GS  # noqa: E402


def test_scenarios_are_complete():
    ids = BS.scenarios()
    assert len(ids) >= 5
    kinds = {"min_links", "alive_rate", "home_refs", "global_refs", "country_refs", "region_count", "mix", "topic_ratio", "territories",
             "avoid", "visual", "deck", "written_report", "mentions", "competitors", "insights", "patterns", "recommendation",
             "limitations", "no_estimates", "on_brand"}
    modes = set()
    for sid in ids:
        sc = BS.load(sid)
        modes.add(sc["mode"])
        assert (BS.SCEN / sid / "brief.md").exists() and sc["request"] and sc["job"]
        assert {c["type"] for c in sc["checks"]} <= kinds, sid
        assert sc["checks"][0]["type"] == "min_links" and sc["checks"][1]["type"] == "alive_rate"
    assert modes == {"brief", "creative-question", "competitor-watch", "pitch"}


def test_prepare_writes_isolated_prompts(tmp_path):
    subprocess.run([sys.executable, REPO / "evals/bench_scout.py", "prepare", "--iteration", "9", "--root", tmp_path,
                    "--scenarios", "s2-global-question"], check=True, capture_output=True)
    base = tmp_path / "iteration-9/s2-global-question"
    w, wo = (base / c / "run-1/prompt.txt" for c in ("with_skill", "without_skill"))
    tw, two = w.read_text(), wo.read_text()
    assert "ZAMAKAN_LIBRARY=$W/library" in tw and "ZAMAKAN_SCOUT_CACHE=$W/.cache" in tw and "never open evals/" in tw
    assert "SKILL.md" not in two and "Do not use any skills" in two and f"Do NOT read anything in {REPO}/" in two
    assert (base / "with_skill/run-1/outputs/brief.md").exists()


def test_scorecard_renders_from_gradings(tmp_path, monkeypatch):
    monkeypatch.setattr(BS, "HIST", tmp_path / "history.json")
    for cfg, rate, secs in (("with_skill", 0.9, 600), ("without_skill", 0.6, 900)):
        run = tmp_path / f"iteration-2/s1-gcc-brief/{cfg}/run-1"
        (run / "outputs").mkdir(parents=True)
        (run / "grading.json").write_text(json.dumps({"summary": {"pass_rate": rate, "passed": 9, "total": 10},
                                                      "stats": {"alive_rate": 1.0, "ref_urls": 20},
                                                      "expectations": [{"text": "x", "passed": False}]}))
        (run / "timing.json").write_text(json.dumps({"total_tokens": 200000, "duration_seconds": secs}))
    BS.scorecard(type("A", (), {"root": tmp_path, "iteration": 2, "note": "test"})())
    h = json.loads((tmp_path / "history.json").read_text())
    assert h[-1]["summary"]["with_skill"]["quality"] == 0.9 and h[-1]["summary"]["without_skill"]["minutes"] == 15.0
    page = (tmp_path / "scorecard.html").read_text()
    assert "Reference scout scorecard" in page and "+30%" in page and "prefers-color-scheme:dark" in page


def test_grader_reads_html_outlines():
    t = {"board.html": "<h2>Key insights</h2><ul><li>People queue less when entertained (Source: Harvard 2019) https://x.org/a</li>"
                       "<li>Waiting feels shorter with music, 2021 study</li></ul><h2>Other</h2>"}
    sec = GS.sections(t, r"insight")
    assert len(sec) == 1 and len(GS.items(sec[0])) == 2
