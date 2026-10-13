"""Reference-scout scripts: parsers on saved real pages (offline) + live smoke tests (skipped offline)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / ".claude/skills/zamakan-reference-scout/scripts"
PAGES = REPO / "tests/fixtures/scout/pages"
FIX = REPO / "evals/fixtures/scout"
sys.path.insert(0, str(SCRIPTS))

import library as L  # noqa: E402
import score as SC  # noqa: E402
import sources as S  # noqa: E402
from verify import matches  # noqa: E402


def page(name):
    return (PAGES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------- parsers (offline, real pages)
def test_aotw_campaign_page():
    r = S.parse_aotw_campaign(page("aotw-campaign-your-2nd-half.html"), "https://www.adsoftheworld.com/campaigns/your-2nd-half")
    assert (r["brand"], r["title"], r["agency"]) == ("Half Million Coffee", "Your 2nd Half", "TTP")
    assert (r["country"], r["year"], r["month"]) == ("SA", 2023, 7)
    assert r["media"] == ["film"] and r["category"] == "Drinks (Non Alcoholic)" and r["kind"] == "professional"
    assert r["video"].endswith(".mp4") and r["thumbnail"].startswith("https://image.adsoftheworld.com/")
    assert any(c.startswith("Director: Younes Medhat") for c in r["credits"])
    assert "https://www.adsoftheworld.com/campaigns/all-the-ramadan-feels" in r["related"]
    assert "Half Million is a coffee brand" in r["description"]


@pytest.mark.parametrize("sentence,expect", [
    ("This  professional campaign titled 'Ramadan 2026 – “At the Heart of Every Moment”' was published in Qatar in February, 2026. "
     "It was created for the brand: Baladna, by ad agency: X Qatar. This 360°, Digital, and Film media campaign is related to the "
     "Food industry and contains 2 media assets. It was",
     {"brand": "Baladna", "agency": "X Qatar", "country": "QA", "year": 2026, "media": ["digital", "film", "integrated"]}),
    ("This  professional campaign titled 'Hunger Station - The Neighbor That Gets You' was published in Saudi Arabia in August, 2021. "
     "It was created for the brand: Hunger Station, . This Film, OOH Outdoor, and Print media campaign is related to the "
     "Delivery and Rideshare Services and Food industries and contains 3 media assets. It was",
     {"brand": "Hunger Station", "country": "SA", "media": ["film", "ooh", "print"], "category": "Delivery and Rideshare Services and Food"}),
])
def test_aotw_sentence_variants(sentence, expect):
    html = f"<html><body><main><p>Description</p><p>{sentence}</p></main></body></html>"
    r = S.parse_aotw_campaign(html, "https://www.adsoftheworld.com/campaigns/x")
    for k, v in expect.items():
        assert r.get(k) == v, (k, r.get(k))
    assert "agency" not in r or expect.get("agency")


def test_aotw_listing_pages():
    res = S.parse_aotw_listing(page("aotw-search-ramadan.html"))
    assert len(res["cards"]) == 60 and res["last_page"] > 1
    talabat = next(c for c in res["cards"] if c.get("brand") == "Talabat")
    assert talabat["agency"] == "az creative" and talabat["url"].startswith("https://www.adsoftheworld.com/campaigns/")
    assert all(c.get("title") and c.get("thumbnail") for c in res["cards"])
    assert len(S.parse_aotw_listing(page("aotw-country-saudi-arabia.html"))["cards"]) >= 50


def test_youtube_search_and_oembed():
    vids = S.parse_youtube_search(page("youtube-search-ramadan-coffee.html"))
    assert vids[0]["title"] == "Saudi coffee, culture in a cup" and vids[0]["views"] == 7218446
    assert all(v["url"].startswith("https://www.youtube.com/watch?v=") for v in vids)
    o = S.parse_oembed(json.loads(page("youtube-oembed-KAUJOH-uGPU.json")), "https://www.youtube.com/watch?v=KAUJOH-uGPU")
    assert o["channel"] == "Nespresso" and "Ramadan 2019" in o["title"] and o["media"] == ["film"]


def test_generic_open_graph():
    r = S.parse_generic(page("campaignme-article.html"), "https://campaignme.com/x/")
    assert r["source"] == "campaignme" and r["title"].startswith("BSA promotes") and r["year"] == 2026


def test_site_and_country_helpers():
    assert S.site_of("https://m.youtube.com/watch?v=1") == "youtube" and S.site_of("https://youtu.be/1") == "youtube"
    assert S.country_code("Saudi Arabia") == "SA" and S.country_code("UAE") == "AE" and S.country_code("Atlantis") is None


# ---------------------------------------------------------------- verify / library / score (offline)
def test_title_matching():
    ref = {"title": "Time to Savour", "brand": "Nespresso"}
    assert matches(ref, {"title": "Nespresso Ramadan 2019 | #TimeToSavour | MEA", "channel": "Nespresso"})
    assert not matches({"title": "Desert Dawn Coffee Ritual", "brand": "Almarai"},
                       {"title": "Fanous Ride - Case video", "brand": "inDrive", "url": "https://x/campaigns/fanous-ride-case-video"})
    assert matches({"title": "Your 2nd Half", "brand": "Half Million Coffee"},
                   {"title": "Your 2nd Half", "brand": "Half Million Coffee"})


def test_library_merge_dedupes_and_tracks_runs(tmp_path):
    run = json.loads((FIX / "example-run.json").read_text(encoding="utf-8"))
    lib = {}
    assert L.merge(lib, run, "rawaq") == (3, 0)
    run["run"]["id"] = "second-run"
    run["references"][0]["urls"][0]["url"] += "/"           # same page, trailing slash
    run["references"][0]["tags"] = ["pov"]
    assert L.merge(lib, run, "other-client") == (0, 3)
    rec = lib[L.canon("https://www.adsoftheworld.com/campaigns/your-2nd-half")]
    assert {s["run"] for s in rec["seen_in"]} == {"rawaq-ramadan-2027-test", "second-run"}
    assert rec["tags"] == ["pov"] and "card" not in rec
    p = tmp_path / "lib.jsonl"
    L.save(lib, p)
    assert len(L.load(p)) == 3
    assert [r["brand"] for r in L.search(L.load(p), ["heritage"])] == ["Jazean Coffee"]


def test_library_skips_rejected():
    run = json.loads((FIX / "example-run.json").read_text(encoding="utf-8"))
    run["references"][1]["status"] = "rejected"
    lib = {}
    assert L.merge(lib, run) == (2, 0)


def test_canon_youtube_variants():
    assert L.canon("https://youtu.be/KAUJOH-uGPU") == L.canon("https://www.youtube.com/watch?v=KAUJOH-uGPU&t=3")


def test_score_prefers_relevant_gcc_and_flags():
    brief = json.loads((FIX / "rawaq-ramadan-brief.json").read_text(encoding="utf-8"))
    terms = SC.brief_terms(brief)
    good = {"title": "Ramadan suhoor coffee nights", "brand": "Barn's", "country": "SA", "year": 2026}
    far = {"title": "Summer sale", "brand": "Shoe Co", "country": "US", "year": 2012}
    ai = {"title": "I Created an AI Commercial for a Saudi Coffee Brand", "channel": "someone", "year": 2026}
    s_good, s_far, s_ai = (SC.score(c, brief, terms, 2026) for c in (good, far, ai))
    assert s_good[0] > s_far[0] and s_good[1]["region"] == 5.0
    assert any("AI demo" in f for f in s_ai[2]) and s_ai[0] < s_good[0]
    lantern = SC.score({"title": "Lantern lights for Ramadan", "country": "AE"}, brief, terms, 2026)
    assert any("avoid-list" in f for f in lantern[2])


# ---------------------------------------------------------------- live (needs internet)
def online():
    if os.environ.get("ZAMAKAN_OFFLINE"):
        return False
    # curl honours the environment's proxy settings (a raw socket would not)
    r = subprocess.run(["curl", "-sS", "-m", "10", "-o", "/dev/null", "-w", "%{http_code}", "https://www.example.org/"],
                       capture_output=True, text=True)
    return r.stdout == "200"


live = pytest.mark.skipif(not online(), reason="no internet access")


@live
def test_live_fetch_and_reject_fake(tmp_path):
    from fetch_meta import fetch_one
    real = fetch_one("https://www.adsoftheworld.com/campaigns/your-2nd-half")
    assert real["brand"] == "Half Million Coffee" and real["http_status"] == 200
    fake = fetch_one("https://www.adsoftheworld.com/campaigns/zamakan-invented-campaign-404")
    assert fake.get("error") and fake["http_status"] == 404


@live
def test_live_verify_cli(tmp_path):
    run = json.loads((FIX / "example-run.json").read_text(encoding="utf-8"))
    run["references"].append({"id": "invented", "title": "Suhoor Stories", "brand": "Starbucks", "ring": "direct",
                              "status": "unverified", "provenance": {"found_via": "web-search"},
                              "card": {"idea": "Invented to test rejection.", "why_relevant": "Should be rejected."},
                              "urls": [{"url": "https://www.adsoftheworld.com/campaigns/starbucks-suhoor-stories-zz", "kind": "case"}]})
    p = tmp_path / "references.json"
    p.write_text(json.dumps(run))
    subprocess.run([sys.executable, SCRIPTS / "verify.py", p, "--write"], check=True, capture_output=True)
    out = {r["id"]: r["status"] for r in json.loads(p.read_text())["references"]}
    assert out["invented"] == "rejected"
    assert out["half-million-your-2nd-half"] == "verified"
