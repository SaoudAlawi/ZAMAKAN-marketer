#!/usr/bin/env python3
"""Social video platforms (TikTok, Instagram, Vimeo, YouTube): read a post, list an account's recent posts, check an
account exists. Public routes first; the user's own login only when they choose it, on their own computer.

Learned from Agent Reach (github.com/Panniantong/agent-reach, MIT): a ladder of routes from public to logged-in,
yt-dlp as the extractor, honest error codes instead of silence, and a separate browser login the agent never types.

Routes, tried in order:
  1. oEmbed (public): Vimeo and YouTube videos, TikTok accounts. TikTok's video oEmbed carries no title from data-centre
     IPs, so it proves nothing and is skipped.
  2. yt-dlp, no login.
  3. yt-dlp with the user's login: --cookies cookies.txt or --browser chrome (or $ZAMAKAN_SOCIAL_COOKIES /
     $ZAMAKAN_SOCIAL_BROWSER). Only works where that browser lives: run the skill on the user's computer. Use a
     secondary account; never log in for the user, never store passwords, never copy cookies into the repo or a client folder.
Each failure has a code: NEED_LOGIN, PLATFORM_BLOCKED (IP or bot wall: not proof the post needs a login), RATE_LIMITED,
NOT_FOUND, UPSTREAM_BROKEN, NO_TOOL. Blocked is not dead: verify.py marks such references unverified, never rejected.

What works from a cloud server (tested November 2026): Vimeo and YouTube via oEmbed, TikTok account check via oEmbed.
TikTok videos (IP block) and Instagram (login wall) need route 3 on the user's computer, or a check by hand.

Usage:
  python social.py read <url> ... [--cookies FILE | --browser chrome] [--out candidates.jsonl]
  python social.py posts <account-url|@handle> --platform tiktok|instagram|youtube|vimeo [--limit 10] [--since-months 12] [--out ...]
  python social.py account <@handle|url> --platform tiktok        # does this account exist? (public)
  python social.py doctor [--cookies FILE | --browser chrome]     # what works from this computer, right now
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _web  # noqa: E402
import sources as S  # noqa: E402

PLATFORMS = ("tiktok", "instagram", "vimeo", "youtube")
ACCOUNT_URL = {"tiktok": "https://www.tiktok.com/@{h}", "instagram": "https://www.instagram.com/{h}/",
               "youtube": "https://www.youtube.com/@{h}/videos", "vimeo": "https://vimeo.com/{h}/videos"}
# Public test targets for `doctor` (official brand accounts, long-lived).
PROBES = {"vimeo": "https://vimeo.com/76979871", "youtube": "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
          "tiktok": "https://www.tiktok.com/@nasa", "instagram": "https://www.instagram.com/nasa/"}
HINT_LOGIN = ("Run this on your own computer with --browser chrome (a browser where a secondary account is logged in), "
              "or check it by hand. Never log in for the user.")
HINT_BLOCKED = "The platform blocked this computer (IP or bot check). This does not prove the post needs a login."


class Failed(Exception):
    def __init__(self, code, message, hint=None):
        super().__init__(message)
        self.code, self.message, self.hint = code, message, hint


def classify(stderr):
    """yt-dlp's error text → one of the codes above (patterns from Agent Reach and our own cloud tests)."""
    e = (stderr or "").lower()
    if any(s in e for s in ("ip address is blocked", "not a bot", "sign in to confirm", "captcha", "unusual traffic")):
        return Failed("PLATFORM_BLOCKED", stderr.strip()[-300:], HINT_BLOCKED)
    if "429" in e or "too many requests" in e:
        return Failed("RATE_LIMITED", stderr.strip()[-300:], "Wait and try once more later.")
    if any(s in e for s in ("only works when logged-in", "login required", "logged-in", "use --cookies", "--cookies for the authentication",
                            "account credentials", "rate-limit reached or login required")):
        return Failed("NEED_LOGIN", stderr.strip()[-300:], HINT_LOGIN)
    if any(s in e for s in ("video unavailable", "private video", "has been removed", "does not exist", "404", "not found",
                            "this post is unavailable", "no longer available")):
        return Failed("NOT_FOUND", stderr.strip()[-300:])
    return Failed("UPSTREAM_BROKEN", stderr.strip()[-300:] or "yt-dlp failed")


def ytdlp_args(cookies=None, browser=None, login=True):
    """yt-dlp ignores SSL_CERT_FILE and trusts its bundled certifi; behind a TLS-inspecting proxy (this cloud, many
    offices) every request then fails, so tell it to use the system store (Agent Reach does the same)."""
    a = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--skip-download", "--socket-timeout", "20"]
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        a += ["--compat-options", "no-certifi"]
    if not login:
        return a
    cookies = cookies or os.environ.get("ZAMAKAN_SOCIAL_COOKIES")
    browser = browser or os.environ.get("ZAMAKAN_SOCIAL_BROWSER")
    if cookies:
        a += ["--cookies", str(cookies)]
    elif browser:
        a += ["--cookies-from-browser", browser]
    return a


def have_ytdlp():
    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        return False


def run_ytdlp(args, timeout=90, cookies=None, browser=None, login=True):
    if not have_ytdlp():
        raise Failed("NO_TOOL", "yt-dlp is not installed", "pip install yt-dlp")
    try:
        p = subprocess.run(ytdlp_args(cookies, browser, login) + args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Failed("UPSTREAM_BROKEN", f"yt-dlp timed out after {timeout}s") from None
    if p.returncode != 0:
        raise classify(p.stderr)
    return p.stdout


def logged_in(cookies=None, browser=None):
    return bool(cookies or browser or os.environ.get("ZAMAKAN_SOCIAL_COOKIES") or os.environ.get("ZAMAKAN_SOCIAL_BROWSER"))


def iso(yyyymmdd):
    s = str(yyyymmdd or "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if re.fullmatch(r"\d{8}", s) else None


def from_ytdlp(d, url, via):
    """yt-dlp info dict → the candidate record the other scout scripts read."""
    src = S.site_of(url)
    desc = (d.get("description") or "").strip()
    title = d.get("title") or ""
    if src in ("tiktok", "instagram") and (not title or re.match(r"(video|post) by ", title, re.I)):
        title = desc.split("\n")[0][:140] or title  # a TikTok/Instagram post's caption is its title
    rec = {"url": url, "source": src, "title": S._clean(title), "channel": d.get("uploader") or d.get("channel"),
           "channel_handle": d.get("uploader_id") or d.get("channel_id"), "published": iso(d.get("upload_date")),
           "duration_s": d.get("duration"), "views": d.get("view_count"), "likes": d.get("like_count"),
           "comments": d.get("comment_count"), "thumbnail": d.get("thumbnail"),
           "description": S._clean(desc, 400) or None, "media": ["social" if src in ("tiktok", "instagram") else "film"],
           "via": via, "access": "logged-in" if via.endswith("+login") else "public", "http_status": 200,
           "unwatched": True}
    if rec["published"]:
        rec["year"] = int(rec["published"][:4])
    if d.get("webpage_url") and d["webpage_url"].rstrip("/") != url.rstrip("/"):
        rec["final_url"] = d["webpage_url"]
    return {k: v for k, v in rec.items() if v not in (None, "", [])}


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def oembed(url):
    """Public route. Returns a record, or None when this platform/URL has no useful oEmbed."""
    src = S.site_of(url)
    video = re.search(r"youtube\.com/(watch|shorts/)|youtu\.be/|vimeo\.com/\d", url)
    if src == "tiktok" and re.search(r"tiktok\.com/@[\w.]+/?$", url):  # accounts only: video oEmbed is blank from servers
        api = "https://www.tiktok.com/oembed?url="
    elif src == "vimeo" and video:
        api = "https://vimeo.com/api/oembed.json?url="
    elif src == "youtube" and video:
        api = "https://www.youtube.com/oembed?format=json&url="
    else:
        return None
    data, status = _web.get_json(api + quote(url, safe=""))
    if not data or not (data.get("title") or data.get("author_name")):
        return None
    rec = S.parse_oembed(data, url)
    rec.update(via="oembed", access="public", http_status=status or 200, unwatched=True)
    if src == "tiktok":
        rec.update(media=["social"], kind="account")
    return rec


def read_one(url, cookies=None, browser=None, timeout=90):
    """Best record for one post URL, trying the routes in order. Never raises: failures come back as error records."""
    url = url.strip()
    rec = oembed(url)
    if rec:
        return {**rec, "fetched_at": now()}
    tried = []
    for login in ([False, True] if logged_in(cookies, browser) else [False]):
        try:
            out = run_ytdlp(["-J", url], timeout, cookies, browser, login=login)
            return {**from_ytdlp(json.loads(out), url, "yt-dlp+login" if login else "yt-dlp"), "fetched_at": now()}
        except Failed as f:
            tried.append(("login" if login else "public", f))
            if f.code in ("NOT_FOUND", "NO_TOOL"):
                break
    route, f = tried[-1]
    return {"url": url, "source": S.site_of(url), "http_status": 404 if f.code == "NOT_FOUND" else 0, "error": f.message,
            "error_code": f.code, "hint": f.hint, "routes_tried": [r for r, _ in tried], "fetched_at": now()}


def account_url(target, platform):
    t = target.strip()
    if "://" in t:
        return t
    return ACCOUNT_URL[platform].format(h=t.lstrip("@"))


def posts(target, platform, limit=10, since_months=None, cookies=None, browser=None, timeout=180):
    """An account's recent posts (newest first). TikTok and Instagram need route 3 from most computers."""
    url = account_url(target, platform)
    args = ["-J", "--flat-playlist", "--playlist-end", str(limit), url]
    login = logged_in(cookies, browser)
    d = json.loads(run_ytdlp(args, timeout, cookies, browser, login=login))
    via = "yt-dlp+login" if login else "yt-dlp"
    items = []
    cutoff = (dt.date.today() - dt.timedelta(days=30 * since_months)).isoformat() if since_months else None
    for e in (d.get("entries") or [])[:limit]:
        u = e.get("url") or e.get("webpage_url") or ""
        if u and not u.startswith("http"):
            u = {"youtube": "https://www.youtube.com/watch?v=", "vimeo": "https://vimeo.com/"}.get(platform, "") + u
        rec = from_ytdlp({**e, "uploader": e.get("uploader") or d.get("uploader") or d.get("channel")}, u, via)
        if cutoff and rec.get("published") and rec["published"] < cutoff:
            continue
        items.append({**rec, "fetched_at": now(), "found_via": f"social:{platform}:{target}"})
    return items


def append(path, recs):
    """Same contract as fetch_meta/discover --out: one JSON line per URL, a URL fetched again replaces its old line."""
    p = Path(path)
    old = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                old[r.get("url")] = r
    for r in recs:
        old[r["url"]] = r
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in old.values()), encoding="utf-8")


def show(r):
    if r.get("error_code"):
        return f"  ✗ {r['error_code']:<16} {r['url']}\n      {r.get('hint') or r['error'][:160]}"
    bits = [r.get("channel") or "", (r.get("title") or "")[:60], r.get("published") or "",
            f"{r['views']:,} views" if r.get("views") else "", f"[{r['via']}]"]
    return "  ✓ " + " · ".join(b for b in bits if b)


def doctor(cookies=None, browser=None):
    print(f"yt-dlp: {'installed' if have_ytdlp() else 'MISSING (pip install yt-dlp)'} · "
          f"login: {'yes (' + (cookies or browser or os.environ.get('ZAMAKAN_SOCIAL_COOKIES') or os.environ.get('ZAMAKAN_SOCIAL_BROWSER')) + ')' if logged_in(cookies, browser) else 'none (public routes only)'}")
    for plat, url in PROBES.items():
        r = read_one(url, cookies, browser, timeout=60) if not url.endswith("/nasa/") else _account_probe(url, cookies, browser)
        print(f"{plat:<10}" + show(r).strip())


def _account_probe(url, cookies, browser):
    try:
        items = posts(url, "instagram", limit=1, cookies=cookies, browser=browser, timeout=60)
        return items[0] if items else {"url": url, "error_code": "NOT_FOUND", "error": "no posts"}
    except Failed as f:
        return {"url": url, "error_code": f.code, "error": f.message, "hint": f.hint}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def login_opts(p):
        g = p.add_mutually_exclusive_group()
        g.add_argument("--cookies", help="cookies.txt exported from a browser (secondary account)")
        g.add_argument("--browser", help="read the login from this browser on this computer: chrome, firefox, safari, edge (opt. :profile)")

    a1 = sub.add_parser("read")
    a1.add_argument("urls", nargs="+")
    a1.add_argument("--out")
    login_opts(a1)
    a2 = sub.add_parser("posts")
    a2.add_argument("target")
    a2.add_argument("--platform", required=True, choices=PLATFORMS)
    a2.add_argument("--limit", type=int, default=10)
    a2.add_argument("--since-months", type=int)
    a2.add_argument("--out")
    login_opts(a2)
    a3 = sub.add_parser("account")
    a3.add_argument("target")
    a3.add_argument("--platform", default="tiktok", choices=("tiktok",))
    a4 = sub.add_parser("doctor")
    login_opts(a4)
    a = ap.parse_args()

    if a.cmd == "doctor":
        doctor(a.cookies, a.browser)
        return
    if a.cmd == "account":
        r = oembed(account_url(a.target, a.platform)) or {"url": account_url(a.target, a.platform), "error_code": "NOT_FOUND",
                                                           "error": "no such account (or the platform refused)"}
        print(show(r))
        return
    if a.cmd == "read":
        recs = [read_one(u, a.cookies, a.browser) for u in a.urls]
    else:
        try:
            recs = posts(a.target, a.platform, a.limit, a.since_months, a.cookies, a.browser)
        except Failed as f:
            print(f"  ✗ {f.code}: {f.message[:200]}\n      {f.hint or ''}")
            sys.exit(2)
    for r in recs:
        print(show(r))
    ok = [r for r in recs if not r.get("error_code")]
    if a.out and ok:
        append(a.out, ok)
    print(f"{len(ok)}/{len(recs)} read" + (f" → {a.out}" if a.out and ok else ""))
    if len(ok) < len(recs):
        print("  blocked ≠ gone: list these under before_kickoff / manual checks, or rerun on your computer with --browser")


if __name__ == "__main__":
    main()
