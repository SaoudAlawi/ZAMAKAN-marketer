"""Shot scout: film dictionary, language step, source parsing, contract rules, palettes and the board."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SHOT = REPO / ".claude/skills/zamakan-shot-scout"
SCRIPTS = SHOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _shared  # noqa: E402
import build_shot_board as BB  # noqa: E402
import discover_shots as DS  # noqa: E402
import expand as X  # noqa: E402
import palette as P  # noqa: E402
import shotstub as ST  # noqa: E402
import validate_shots as VS  # noqa: E402
import verify_shots as VF  # noqa: E402


def online():
    import _web
    try:
        return _web.get("https://eyecannndy.com/", browser="never", timeout=15).get("status") == 200
    except Exception:  # noqa: BLE001
        return False


# ---------- dictionary
def test_dictionary_is_complete_and_consistent():
    ts = _shared.techniques()
    ids = [t["id"] for t in ts]
    assert len(ids) == len(set(ids)) and len(ids) >= 60
    for t in ts:
        for k in ("name", "name_ar", "category", "feeling", "how", "method", "gear", "kit", "ai"):
            assert t[k], f"{t['id']}: {k} empty"
        assert t["budget"] in "1234" and t["method"] in ("practical", "rig", "vfx", "edit", "ai", "mixed")
        assert any("؀" <= c <= "ۿ" for c in t["name_ar"]), f"{t['id']}: Arabic name missing"
        assert t["search_terms"], t["id"]
    for m in _shared.moods():
        assert set(m["techniques"]) <= set(ids), m["id"]
        assert any(any("؀" <= c <= "ۿ" for c in w) for w in m["words"]), f"mood {m['id']} has no Arabic words"


def test_arabic_normalising():
    assert _shared.norm("الإحساس، بالوحدة") == "الاحساس بالوحده"
    assert "صحراء" in _shared.ar_variants("والصحراء") or "صحراء" in {v[:5] for v in _shared.ar_variants("والصحراء")}


# ---------- language step (answer key in evals/fixtures/shots)
@pytest.mark.parametrize("case", json.loads((REPO / "evals/fixtures/shots/requests.json").read_text(encoding="utf-8"))["requests"],
                         ids=lambda c: c["text"][:30])
def test_expand_translates_requests(case):
    p = X.plan(case["text"])
    got = {t["id"] for t in p["techniques"]}
    assert set(case["must"]) <= got, f"missing {set(case['must']) - got} in {got}"
    if case.get("subject_empty"):
        assert not p["subject"]
    if case.get("subject_has"):
        assert case["subject_has"] in p["subject"]
    assert p["searches"]["youtube"] or p["searches"]["eyecannndy_technique"]


def test_expand_keeps_named_techniques_first_and_caps_moods():
    p = X.plan("dolly zoom, lonely and epic and nostalgic and tense")
    assert p["techniques"][0]["id"] == "dolly-zoom"
    assert len(p["techniques"]) <= 8


# ---------- sources (offline, with page snippets)
EYE_GRID = """<div class="grid-item"><img hx-get="/clip_info_g/5695/?type=technique&t_id=26&q=" src="https://asset/x.gif"
 data-src="https://asset/x.webp" alt="Aminé - Charmander" title="Aminé - Charmander"></div>
<div class="grid-item"><img hx-get="/clip_info_g/1848/?type=technique&t_id=26&q=" src="https://asset/y.gif" title="Jaws"></div>"""
EYE_INFO = """<div>Aminé - Charmander (2021) | In the 2021 music video "Charmander" by Aminé, the artist retreats to a secluded cabin
in the woods, with a warm, earthy colour palette. | Technique - <a href="/technique/dolly-zoom">Dolly Zoom</a>
<a href="/technique/close-up#medium-close-up">Close-up</a> Director - <a href="/director/adam-daniel/">Adam Daniel</a>
DOP - <a href="/dop/ben-mullen/">Ben Mullen</a> <a href="https://www.youtube.com/watch?v=uAIa-JMriag">Original</a></div>"""


def test_eyecannndy_parsing(monkeypatch):
    clips = DS.eye_clip_ids(EYE_GRID)
    assert [c["id"] for c in clips] == ["5695", "1848"] and clips[0]["still"] == "https://asset/x.webp"
    monkeypatch.setattr(DS._web, "get", lambda url, **kw: {"text": EYE_INFO, "status": 200})
    r = DS.eye_clip(clips[0], "https://eyecannndy.com/technique/dolly-zoom")
    assert r["year"] == 2021 and r["url"].startswith("https://www.youtube.com/")
    assert r["techniques_src"] == ["dolly-zoom", "close-up"]  # sub-labels (#medium-close-up) dropped
    assert r["credits"] == {"director": ["Adam Daniel"], "dop": ["Ben Mullen"]}
    assert r["found_on"].endswith("/technique/dolly-zoom") and r["clip_id"] == "5695"


def test_timestamps_from_descriptions():
    assert DS.timestamps("Sandstorm at 00:32, again at 1:02:15; not 2011-04-15 or 3:4") == ["00:32", "1:02:15"]


def test_candidates_file_survives_unicode_line_separators(tmp_path):
    out = tmp_path / "c.jsonl"
    DS.write([{"url": "https://a", "title": "A", "description": "line one line two"}], out)
    DS.write([{"source": "eyecannndy", "clip_id": "1", "url": "https://v", "title": "B"},
              {"source": "eyecannndy", "clip_id": "2", "url": "https://v", "title": "C"}], out)  # two shots, same video
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").split("\n") if x.strip()]
    assert len(rows) == 3


def test_eyecannndy_slugs_map_to_the_right_technique():
    m = ST.eye_to_ours()
    assert m["hard-light"] == "hard-light" and m["halation"] == "halation"
    assert m["fixed-camera"] == "static-frame" and m["arc-movement"] == "orbit" and m["speed-ramping"] == "speed-ramp"


# ---------- contract
def shot(i="s1", **kw):
    s = {"id": i, "title": "Moonlight", "kind": "film", "status": "verified", "techniques": ["hard-light"],
         "urls": [{"url": "https://www.youtube.com/watch?v=abc", "kind": "video", "evidence": "video"}],
         "why": "Warm light on faces at close range.", "provenance": {"found_via": "eyecannndy"},
         "production": {"method": "practical", "how": "Hard warm sources close to the face.", "budget": 2}}
    s.update(kw)
    return s


def run_of(shots, mode="subject", **kw):
    r = {"schema_version": "1.0", "run": {"id": "t", "mode": mode, "created": "2026-10-18", "request": "warm faces"},
         "shots": shots, "groups": [{"technique": "hard-light", "shot_ids": [s["id"] for s in shots]}],
         "watch_list": ["Watch Moonlight"]}
    r.update(kw)
    return r


def test_valid_run_passes():
    E, W, stats = VS.validate(run_of([shot()]))
    assert not E, E
    assert stats["shots"] == 1


@pytest.mark.parametrize("bad,expect", [
    ({"techniques": ["not-a-technique"]}, "not in techniques.json"),
    ({"status": "rejected"}, "rejected"),
    ({"status": "unverified"}, "unverified"),
    ({"why": "TODO: why"}, "TODO"),
])
def test_validator_catches(bad, expect):
    E, _, _ = VS.validate(run_of([shot(**bad)]))
    assert any(expect in e for e in E), E


def test_mode_rules():
    E, _, _ = VS.validate(run_of([shot()], mode="who"))
    assert any("at least 3 people" in e for e in E)
    E, _, _ = VS.validate(run_of([shot()], mode="frame-match"))
    assert any("run.frame" in e for e in E)


def test_unwatched_video_must_be_on_watch_list():
    _, W, _ = VS.validate(run_of([shot()], watch_list=[]))
    assert any("watch_list" in w for w in W)
    _, W, _ = VS.validate(run_of([shot(title="Oblé Reed - WESTON.")], watch_list=["Watch Oblé Reed 'WESTON.' on YouTube"]))
    assert not any("watch_list" in w for w in W)


def test_library_listing_is_checked_for_the_clip(monkeypatch):
    import _web
    monkeypatch.setattr(_web, "get", lambda url, **kw: {"status": 200, "text": '<img alt="Dune: Part Two" title="Dune: Part Two">'})
    s = shot(title="Dune: Part Two", urls=[{"url": "https://eyecannndy.com/technique/haze", "kind": "library"}], status="unverified")
    VF.check(s)
    assert s["status"] == "verified" and s["urls"][0]["evidence"] == "title"
    s = shot(title="Not Listed", urls=[{"url": "https://eyecannndy.com/technique/haze", "kind": "library"}], status="unverified")
    VF.check(s)
    assert s["status"] == "unverified"


# ---------- palette
def test_palette_finds_colours_and_ignores_letterbox(tmp_path):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (400, 300), "black")
    d = ImageDraw.Draw(im)
    d.rectangle((0, 40, 199, 259), fill=(200, 80, 20))
    d.rectangle((200, 40, 399, 259), fill=(30, 90, 160))
    f = tmp_path / "f.png"
    im.save(f)
    pal = P.palette(f)
    assert "#000000" not in pal[:2]
    assert any(abs(int(h[1:3], 16) - 200) < 20 and abs(int(h[3:5], 16) - 80) < 20 for h in pal)
    assert any(abs(int(h[5:7], 16) - 160) < 20 for h in pal)
    assert "#010101" not in P.overall([["#010101", "#C45113"], ["#010101", "#AAB4BD"]])


# ---------- board
def test_timestamp_links():
    assert BB.at_time("https://www.youtube.com/watch?v=abc", "1:05") == "https://www.youtube.com/watch?v=abc&t=65s"
    assert BB.at_time("https://vimeo.com/22439234", "00:32") == "https://vimeo.com/22439234#t=32s"


@pytest.fixture
def board_job(tmp_path):
    from PIL import Image
    (tmp_path / "thumbs").mkdir()
    Image.new("RGB", (640, 360), (196, 81, 19)).save(tmp_path / "thumbs/a.jpg")
    s1 = shot(timestamp="00:32", thumbnail={"url": "https://x/a.jpg", "local": "thumbs/a.jpg"}, palette=["#C45113", "#602714"],
              credits={"director": ["Barry Jenkins"], "dop": ["James Laxton"]}, credits_source="eyecannndy")
    s2 = shot("s2", title="Dune: Part Two", techniques=["silhouette"], urls=[{"url": "https://eyecannndy.com/technique/silhouette", "kind": "library", "evidence": "title"}])
    run = run_of([s1, s2], groups=[{"technique": "hard-light", "note": "Warm faces.", "shot_ids": ["s1"]},
                                   {"technique": "silhouette", "shot_ids": ["s2"]}],
                 look={"summary": "Warm low sun.", "summary_ar": "شمس منخفضة دافئة.", "traits": ["Warm"], "palette": ["#C45113"]},
                 people=[{"name": "James Laxton", "role": "dop", "known_for": "Warm portraits", "shot_ids": ["s1"]}],
                 production_summary={"gear": ["Fast primes"], "ksa_notes": ["Permits"], "ai_notes": ["Mock-ups"], "budget": "Cheap."})
    run["run"]["cover"] = "s1"
    (tmp_path / "shots.json").write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_board_builds_with_every_section(board_job):
    r = subprocess.run([sys.executable, SCRIPTS / "build_shot_board.py", board_job / "shots.json", "--out", board_job],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    h = (board_job / "board.html").read_text(encoding="utf-8")
    for needle in ("In film language", "How it's done", "People to brief or bid", "How to shoot it", "Watch before the meeting",
                   "t=32s", "data:image/jpeg;base64", 'lang="ar"', "James Laxton", "page exists"):
        assert needle in h, needle
    assert "color-mix" not in h  # the contrast check can't read it
    assert (board_job / "shots.md").exists()


def test_board_passes_the_visual_check(board_job):
    subprocess.run([sys.executable, SCRIPTS / "build_shot_board.py", board_job / "shots.json", "--out", board_job], check=True,
                   capture_output=True)
    sys.path.insert(0, str(REPO / ".claude/skills/zamakan-reference-scout/scripts"))
    import check_outputs
    out = check_outputs.run_checks(board_job)
    assert out["ok"], out["errors"]


# ---------- live
@pytest.mark.skipif(not online(), reason="offline")
def test_live_eyecannndy_technique():
    recs = DS.eyecannndy("https://eyecannndy.com/technique/dolly-zoom", 2, "technique:dolly-zoom")
    assert recs and all(r["title"] for r in recs)
    assert any(r.get("credits") for r in recs)


# ---------- inspire mode
import film_facts as FF  # noqa: E402


def test_film_search_never_returns_a_person(monkeypatch):
    hits = {"search": [{"id": "Q1", "label": "Nora Ephron", "description": "American film director and writer (1941–2012)"},
                       {"id": "Q2", "label": "Norah", "description": "2023 Saudi Arabian film"}]}
    monkeypatch.setattr(FF, "get_json", lambda url, tries=5: (hits, 200))
    hit, how = FF.search("Norah", 2024)
    assert hit["id"] == "Q2"
    hits["search"] = hits["search"][:1]
    hit, how = FF.search("Norah", 2024)
    assert hit is None and "no film from 2024" in how


def test_craft_sentences_are_extracted(monkeypatch):
    html_ = ("<div class='mw-parser-output'><section><p>Sophie records the holiday on a MiniDV camera, the footage of which is "
             "interspersed throughout the film. The film premiered at Cannes in May.</p><p>Ozu often had key scenes take place off camera, "
             "with the viewer learning about them through dialogue.<sup>[3]</sup></p></section></div>")

    class R:
        def __init__(self, b):
            self.b = b

        def read(self):
            return self.b.encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=25: R(html_))
    notes = FF.craft_notes("https://en.wikipedia.org/wiki/X")
    assert any("MiniDV camera" in n for n in notes) and any("off camera" in n for n in notes)
    assert not any("premiered at Cannes" in n for n in notes)


def test_roles_and_inspire_mode_are_detected():
    p = X.plan("I'm a writer and cinematographer, inspire me: films about silence and what's left unsaid")
    assert p["mode_hint"] == "inspire" and p["roles"] == ["writer", "dop"]
    assert "silence" in p["subject"] and "i'm" not in p["subject"] and "films" not in p["subject"]
    assert "static-frame" in {t["id"] for t in p["techniques"]}
    p = X.plan("أنا مخرج، أبغى أشاهد أفلام عن الصحراء والوحدة")
    assert p["mode_hint"] == "inspire" and p["roles"] == ["director"] and "الصحراء" in p["subject"]


def test_shortoftheweek_parsing(monkeypatch):
    data = {"data": [{"post_title": "Father and Daughter", "post_date": "2008-02-10 10:00:00", "post_name": "father-and-daughter",
                      "filmmaker": "Michael Dudok de Wit", "duration": "8", "country": {"display_name": "Netherlands"},
                      "play_link": "https://player.vimeo.com/video/123456", "post_excerpt": "<p>A moving tale</p>",
                      "background_image": "//static.x/still.jpg"},
                     {"post_title": "Oscars guide", "post_date": "2026-01-01 10:00:00", "post_name": "guide", "filmmaker": ""},
                     {"post_title": "Acrobats", "post_date": "2024-01-01", "post_name": "acrobats", "filmmaker": "Ana A &amp; Bo B"}]}
    monkeypatch.setattr(DS._web, "get_json", lambda url, timeout=20: (data, 200))
    recs = DS.shortoftheweek("father", 5)
    assert [r["title"] for r in recs] == ["Father and Daughter", "Acrobats"]  # articles without a filmmaker skipped
    r = recs[0]
    assert r["url"] == "https://www.shortoftheweek.com/2008/02/10/father-and-daughter/" and r["runtime_min"] == 8
    assert r["extra_urls"] == ["https://vimeo.com/123456"] and r["thumbnail"].startswith("https://")
    assert recs[1]["credits"]["director"] == ["Ana A", "Bo B"]


def inspire_run(**kw):
    s1 = shot("f1", kind="film", countries=["Japan"], credits={"director": ["Yasujirō Ozu"]}, credits_source="wikidata",
              watch_for={"writer": "Key scenes happen off camera; you learn them through dialogue.", "dop": "Low camera, like sitting on a tatami mat."},
              exercise="Write a scene whose main event happens off screen.", runtime_min=136)
    s1.pop("production")
    s2 = shot("s2", kind="short", countries=["Netherlands"], credits={"director": ["Michael Dudok de Wit"]}, credits_source="shortoftheweek",
              watch_for={"writer": "A whole life told without a word of dialogue.", "dop": "Long shadows and silhouettes carry the time of day."},
              exercise="Tell a 30-year story in five wordless images.", pairs_with="f1")
    r = run_of([s1, s2], mode="inspire", groups=[{"title": "Tonight, free", "shot_ids": ["s2"]}, {"title": "An evening", "shot_ids": ["f1"]}])
    r["run"].update(roles=["writer", "dop"], theme="silence and the unsaid")
    r.update(kw)
    return r


def test_inspire_run_validates_and_needs_watch_for_per_role():
    E, W, _ = VS.validate(inspire_run())
    assert not E, E
    r = inspire_run()
    del r["shots"][0]["watch_for"]["dop"]
    E, _, _ = VS.validate(r)
    assert any("watch_for missing for dop" in e for e in E)
    r = inspire_run()
    r["run"]["roles"] = []
    E, _, _ = VS.validate(r)
    assert any("run.roles" in e for e in E)
    r = inspire_run()
    r["shots"][0].pop("production", None)
    r["run"]["mode"] = "subject"
    r["run"].pop("roles")
    E, _, _ = VS.validate(r)
    assert any("production notes missing" in e for e in E)


def test_inspire_board_shows_programme(tmp_path):
    (tmp_path / "shots.json").write_text(json.dumps(inspire_run(), ensure_ascii=False), encoding="utf-8")
    subprocess.run([sys.executable, SCRIPTS / "build_shot_board.py", tmp_path / "shots.json", "--out", tmp_path], check=True, capture_output=True)
    h = (tmp_path / "board.html").read_text(encoding="utf-8")
    for needle in ("A viewing programme", "Tonight, free", "After watching:", "Double bill with", "Cinematographer", "مدير تصوير",
                   ">01<", ">02<", "136 min", "hours of cinema"):
        assert needle in h, needle


# ---------- documentaries
def test_documentary_techniques_and_mood():
    ts = _shared.tech_by_id()
    for t in ("talking-head", "direct-address", "observational", "archival", "reenactment", "animated-doc", "diary-film", "essay-film"):
        assert ts[t]["category"] == "documentary"
    p = X.plan("documentaries about borderline personality disorder")
    assert "borderline" in p["subject"]  # a diagnosis stays the subject, not a mood
    assert {"observational", "talking-head"} <= {t["id"] for t in p["techniques"]}
    assert p["searches"]["docs"] == [p["subject"]]


def test_channel_search_drops_unrelated_uploads(monkeypatch):
    fake = [{"url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "title": "Living With Borderline Personality Disorder"},
            {"url": "https://www.youtube.com/watch?v=bbbbbbbbbbb", "title": "Extreme Heat Is the New Normal | Op-Docs"}]
    monkeypatch.setattr(DS._web, "get", lambda url, **kw: {"text": "", "status": 200})
    monkeypatch.setattr(DS.S, "parse_youtube_search", lambda h: fake)
    recs = DS.channel_search("@nytopinion", "borderline personality")
    assert [r["title"] for r in recs] == ["Living With Borderline Personality Disorder"]
    assert recs[0]["kind"] == "documentary"


def test_documentaries_are_a_kind(tmp_path):
    s = shot("d1", kind="documentary", title="Border", urls=[{"url": "https://www.youtube.com/watch?v=abc", "kind": "video", "evidence": "video"}])
    E, _, _ = VS.validate(run_of([s], watch_list=["Watch Border (d1)"]))
    assert not E, E
    assert BB.KIND["documentary"] == "Documentary"
