"""Iteration-3 fixes found by the benchmark agents (each test names the problem it guards against)."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / ".claude/skills/zamakan-reference-scout/scripts"
FIX = REPO / "evals/fixtures/scout"
sys.path.insert(0, str(SCRIPTS))

import build_outputs as B  # noqa: E402
import fetch_meta as F  # noqa: E402


def test_adsoftheworld_without_www_is_normalised():
    assert F.normalise("https://adsoftheworld.com/campaigns/x") == "https://www.adsoftheworld.com/campaigns/x"
    assert F.normalise("https://www.youtube.com/watch?v=abc") == "https://www.youtube.com/watch?v=abc"


def test_generic_thumbnails_are_detected():
    from PIL import Image
    assert F.looks_generic(Image.new("RGB", (120, 60), (10, 120, 200)))          # tiny logo: dropped
    slate = Image.new("RGB", (640, 360), (240, 240, 240))
    assert not F.looks_generic(slate) and F.looks_flat(slate)                     # flat: kept, but flagged for a look
    from PIL import ImageDraw
    photo = Image.new("RGB", (640, 360), (30, 60, 90))
    d = ImageDraw.Draw(photo)
    for i in range(0, 640, 40):
        d.rectangle((i, 0, i + 20, 360), fill=(220, 180 - i // 8, 60 + i // 5))
    assert not F.looks_flat(photo)
    assert F.GENERIC_THUMB.search("https://www.lovethework.com/images/og-image.png")


def test_letterbox_bars_are_trimmed():
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (640, 480), (0, 0, 0))
    ImageDraw.Draw(im).rectangle((0, 60, 639, 419), fill=(200, 120, 40))
    out = B.trim_bars(im)
    assert out.size == (640, 360)
    dark = Image.new("RGB", (640, 480), (5, 5, 5))  # a dark picture is left alone
    assert B.trim_bars(dark).size == (640, 480)


def test_fetch_meta_out_appends_and_replaces(tmp_path, monkeypatch):
    calls = iter([{"url": "https://a.com/1", "title": "one"}, {"url": "https://a.com/2", "title": "two"},
                  {"url": "https://a.com/1", "title": "one again"}])
    monkeypatch.setattr(F, "fetch_one", lambda u, t=False: next(calls))
    out = tmp_path / "web.jsonl"
    for urls in (["https://a.com/1", "https://a.com/2"], ["https://a.com/1"]):
        monkeypatch.setattr(sys, "argv", ["fetch_meta.py", *urls, "--out", str(out)])
        F.main()
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert [r["title"] for r in rows] == ["two", "one again"]  # nothing lost, the refetch replaced its old line


def test_cover_avoids_competitor_ads_and_honours_run_cover():
    run = json.loads((FIX / "rawaq-ramadan-sample-run.json").read_text(encoding="utf-8"))
    has = lambda r: True  # noqa: E731
    run["top"] = ["starbucks-keep-the-gathering-flowing"] + run["top"]
    c = B.cover_ref(run, has, ["Starbucks KSA", "Barn's"])
    assert "Starbucks" not in c["brand"]
    run["run"]["cover"] = "heinz-draw-ketchup"
    assert B.cover_ref(run, has, [])["id"] == "heinz-draw-ketchup"


def _sample():
    return json.loads((FIX / "rawaq-ramadan-sample-run.json").read_text(encoding="utf-8"))


def test_shared_award_source_is_allowed_but_main_url_must_be_unique():
    from validate_run import validate
    run = _sample()
    roundup = {"url": "https://campaignme.com/dubai-lynx-2025-grand-prix-winners/", "kind": "article"}
    run["references"][0]["urls"].append(dict(roundup))
    run["references"][1]["urls"].append(dict(roundup))
    errs, _ = validate(run)
    assert not errs


def test_teardown_on_thin_evidence_is_warned():
    from validate_run import validate
    run = _sample()
    top = next(r for r in run["references"] if r["id"] == run["top"][0])
    for u in top["urls"]:
        u["evidence"] = "video"
    _, warns = validate(run)
    assert any("unwatched video" in w for w in warns)


def test_same_thumbnail_on_many_references_is_warned():
    from validate_run import validate
    run = _sample()
    for r in run["references"][:2]:
        r["thumbnail"] = {"url": "https://www.lovethework.com/static/share.png"}
    _, warns = validate(run)
    assert any("same thumbnail" in w for w in warns)


def test_text_match_for_headlines_that_dont_name_the_campaign():
    from verify import text_match
    ref = {"title": "Unattainable Cup", "brand": "Nescafé"}
    assert text_match(ref, "In its Ramadan work, Nescafé created the Unattainable Cup, a mug that ...")
    assert not text_match(ref, "A roundup of the best Ramadan ads this year from several brands.")


def test_evidence_badges():
    r = {"status": "verified", "urls": [{"verified": True, "evidence": "video"}]}
    assert "not watched" in B.evidence_badge(r)
    r["urls"].append({"verified": True, "evidence": "content"})
    assert "page read" in B.evidence_badge(r)
    assert "unverified" in B.evidence_badge({"status": "unverified", "urls": []})


# ---------------------------------------------------------------- 3d competitor watch
def test_youtube_channel_uploads_parse_with_dates():
    import datetime as dt
    import sources as S
    html = (REPO / "tests/fixtures/scout/pages/youtube-channel-halfmillion.html").read_text(encoding="utf-8")
    vids = S.parse_youtube_channel(html)
    assert len(vids) == 3 and all(v["channel"] == "Half Million" and v["url"].startswith("https://www.youtube.com/watch?v=") for v in vids)
    assert all(v.get("published") and v.get("thumbnail") for v in vids)
    assert S.ago_to_date("5 days ago", dt.date(2026, 10, 13)) == "2026-10-08"
    assert S.ago_to_date("2 months ago", dt.date(2026, 10, 13)) == "2026-08-14"
    assert S.ago_to_date("no date") is None


def test_competitor_plan_and_click_list(tmp_path):
    import subprocess
    brief = {"schema_version": "1.0", "mode": "competitor-watch", "client": "rawaq", "question": "What are they doing?",
             "market": "Riyadh, Saudi Arabia", "competitors": ["Barn's", "Half Million"], "window_months": 6}
    (tmp_path / "brief.json").write_text(json.dumps(brief))
    subprocess.run([sys.executable, SCRIPTS / "competitors.py", tmp_path / "brief.json", "--out", tmp_path], check=True, capture_output=True)
    plan = (tmp_path / "competitor-plan.md").read_text()
    assert "## Barn's" in plan and "last 6 months" in plan and "Can't be read from here" in plan
    checks = json.loads((tmp_path / "manual-checks.json").read_text())
    assert any("facebook.com/ads/library" in m["url"] and "country=SA" in m["url"] for m in checks["Half Million"])


def test_competitor_watch_validation():
    from validate_run import validate
    run = _sample()
    run["run"]["mode"] = "competitor-watch"
    _, warns = validate(run, brief={"window_months": 12})
    assert any("no 'owns'" in w for w in warns) and any("manual_checks" in w for w in warns)
    assert any("older than the 12-month window" in w for w in warns)  # e.g. Nespresso 2019
    for c in run["competitor_summary"]:
        c.update(owns="x", last_seen="2026-10", manual_checks=[{"what": "Instagram", "url": "https://instagram.com/x"}])
    for r in run["references"]:
        r["tags"] = r.get("tags", []) + ["context"]
    _, warns = validate(run, brief={"window_months": 12})
    assert not any("competitor_summary/" in w or "window" in w for w in warns)


# ---------------------------------------------------------------- 3f ranking
def _score(c, **brief_over):
    import score as SC
    b = {**json.loads((FIX / "rawaq-ramadan-brief.json").read_text(encoding="utf-8")), **brief_over}
    return SC.score(c, b, SC.brief_terms(b), 2026)


def test_place_names_dont_count_as_relevance():
    import score as SC
    terms = SC.brief_terms(json.loads((FIX / "rawaq-ramadan-brief.json").read_text(encoding="utf-8")))
    assert "riyadh" not in terms and "saudi" not in terms and "ramadan" in terms
    generic = _score({"title": "Riyadh Season as never seen before", "brand": "Riyadh Season", "country": "SA", "year": 2025})
    onbrief = _score({"title": "Ramadan suhoor coffee", "brand": "Costa", "country": "EG", "year": 2024})
    assert onbrief[0] > generic[0] and any("off-topic" in f for f in generic[2])


def test_alcohol_flag_for_gulf_clients():
    s = _score({"title": "Good things come to those who wait", "brand": "Guinness", "country": "GB", "year": 1999})
    assert any(f.startswith("alcohol") for f in s[2])
    assert not any(f.startswith("alcohol") for f in _score({"title": "Ginger tea", "brand": "Lipton"})[2])


def test_award_signal_counts_more_in_pitch_mode():
    c = {"title": "Coffee night QR code", "description": "Cannes Lions Grand Prix 2022", "country": "US", "year": 2022}
    assert _score(c, mode="pitch")[0] > _score(c)[0] > _score({**c, "description": ""})[0]
