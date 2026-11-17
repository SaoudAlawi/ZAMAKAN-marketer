"""social.py: TikTok / Instagram / Vimeo / YouTube routes (public first, user login opt-in) and how verify.py treats walls.
Offline: oEmbed and yt-dlp are stubbed."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / ".claude/skills/zamakan-reference-scout/scripts"))

import social as SO  # noqa: E402
import verify as V  # noqa: E402

TT = "https://www.tiktok.com/@brand/video/7372979936375770411"
IG = "https://www.instagram.com/p/C8x0d0iOq0b/"


@pytest.mark.parametrize("stderr,code", [
    ("ERROR: [TikTok] 737: Your IP address is blocked from accessing this post", "PLATFORM_BLOCKED"),
    ("ERROR: [vimeo] 7: The web client only works when logged-in. Use --cookies", "NEED_LOGIN"),
    ("ERROR: [Instagram] C8: Requested content is not available, rate-limit reached or login required. Use --cookies", "NEED_LOGIN"),
    ("ERROR: HTTP Error 429: Too Many Requests", "RATE_LIMITED"),
    ("ERROR: [youtube] x: Video unavailable", "NOT_FOUND"),
    ("ERROR: something odd", "UPSTREAM_BROKEN"),
])
def test_classify(stderr, code):
    assert SO.classify(stderr).code == code


def test_tiktok_caption_becomes_title():
    d = {"title": "", "description": "Ramadan gift guide 🌙\n#ramadan", "uploader": "Brand", "uploader_id": "brand",
         "upload_date": "20250301", "view_count": 120000, "like_count": 5000, "duration": 31, "thumbnail": "https://x/t.jpg"}
    r = SO.from_ytdlp(d, TT, "yt-dlp")
    assert r["title"].startswith("Ramadan gift guide") and r["published"] == "2025-03-01" and r["year"] == 2025
    assert r["views"] == 120000 and r["media"] == ["social"] and r["access"] == "public" and r["unwatched"]


def test_login_route_marks_access(monkeypatch):
    calls = []

    def fake(args, timeout=90, cookies=None, browser=None, login=True):
        calls.append(login)
        if not login:
            raise SO.Failed("NEED_LOGIN", "login required", SO.HINT_LOGIN)
        return json.dumps({"title": "Video by brand", "description": "New collection", "uploader": "brand"})

    monkeypatch.setattr(SO, "oembed", lambda url: None)
    monkeypatch.setattr(SO, "run_ytdlp", fake)
    r = SO.read_one(IG, browser="chrome")
    assert calls == [False, True]  # public first, then the user's login
    assert r["access"] == "logged-in" and r["via"] == "yt-dlp+login" and r["title"] == "New collection"


def test_no_login_never_tries_cookies(monkeypatch):
    monkeypatch.delenv("ZAMAKAN_SOCIAL_COOKIES", raising=False)
    monkeypatch.delenv("ZAMAKAN_SOCIAL_BROWSER", raising=False)
    calls = []

    def fake(args, timeout=90, cookies=None, browser=None, login=True):
        calls.append(login)
        raise SO.Failed("PLATFORM_BLOCKED", "IP blocked", SO.HINT_BLOCKED)

    monkeypatch.setattr(SO, "oembed", lambda url: None)
    monkeypatch.setattr(SO, "run_ytdlp", fake)
    r = SO.read_one(TT)
    assert calls == [False] and r["error_code"] == "PLATFORM_BLOCKED" and r["http_status"] == 0


def test_ytdlp_args_tls_and_login(monkeypatch):
    monkeypatch.setenv("SSL_CERT_FILE", "/etc/ssl/cert.pem")
    a = SO.ytdlp_args(browser="chrome")
    assert "no-certifi" in a and a[-2:] == ["--cookies-from-browser", "chrome"]
    assert "--cookies-from-browser" not in SO.ytdlp_args(browser="chrome", login=False)


def test_account_url():
    assert SO.account_url("@brand", "tiktok") == "https://www.tiktok.com/@brand"
    assert SO.account_url("brand", "instagram") == "https://www.instagram.com/brand/"


def test_verify_walled_is_unverified_not_rejected(monkeypatch):
    monkeypatch.setattr(V, "fetch_one", lambda url, with_text=False: {
        "url": url, "source": "tiktok", "http_status": 0, "error": "IP blocked", "error_code": "PLATFORM_BLOCKED"})
    ref = {"id": "r1", "title": "Ramadan gift guide", "brand": "Brand", "status": "unverified",
           "urls": [{"url": TT, "kind": "social-post", "source": "tiktok"}]}
    _, _, after, _ = V.check(ref)
    assert after == "unverified" and ref["urls"][0]["walled"] == "PLATFORM_BLOCKED"


def test_verify_social_post_read_is_video_evidence(monkeypatch):
    monkeypatch.setattr(V, "fetch_one", lambda url, with_text=False: {
        "url": url, "source": "tiktok", "http_status": 200, "title": "Ramadan gift guide", "channel": "Brand"})
    ref = {"id": "r1", "title": "Ramadan gift guide", "brand": "Brand", "status": "unverified",
           "urls": [{"url": TT, "kind": "social-post", "source": "tiktok"}]}
    _, _, after, urls = V.check(ref)
    assert after == "verified" and urls[0][3] == "video"


def test_gone_post_is_rejected(monkeypatch):
    monkeypatch.setattr(V, "fetch_one", lambda url, with_text=False: {
        "url": url, "source": "tiktok", "http_status": 404, "error": "removed", "error_code": "NOT_FOUND"})
    ref = {"id": "r1", "title": "x", "brand": "y", "status": "unverified", "urls": [{"url": TT, "kind": "social-post", "source": "tiktok"}]}
    assert V.check(ref)[2] == "rejected"
