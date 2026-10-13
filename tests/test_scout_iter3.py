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
