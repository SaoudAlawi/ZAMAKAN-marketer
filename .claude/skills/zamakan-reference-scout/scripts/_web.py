"""HTTP helper for the scout scripts: browser-like requests, disk cache, Chromium fallback.

Pages are cached under $ZAMAKAN_SCOUT_CACHE (default ~/.cache/zamakan-scout) for 7 days, so
re-running a step or verifying a URL twice costs nothing. When a site refuses plain requests
(403/429/503 or a bot-check page) the page is fetched again with headless Chromium.
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9,ar;q=0.8"}
CACHE = Path(os.environ.get("ZAMAKAN_SCOUT_CACHE", Path.home() / ".cache" / "zamakan-scout"))
TTL = 7 * 24 * 3600
BOT_MARKERS = ("cf-chl-", "Just a moment...", "confirm you’re not a bot", "Access denied")


class Page(dict):
    """{url, final_url, status, text, via, cached}"""


def _key(url):
    return CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".json")


def _from_cache(url):
    p = _key(url)
    if p.exists() and time.time() - p.stat().st_mtime < TTL:
        d = json.loads(p.read_text(encoding="utf-8"))
        return Page(d, cached=True)
    return None


def _to_cache(page):
    CACHE.mkdir(parents=True, exist_ok=True)
    _key(page["url"]).write_text(json.dumps({k: v for k, v in page.items() if k != "cached"}), encoding="utf-8")


def _urllib(url, timeout):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(6_000_000)
            charset = r.headers.get_content_charset() or "utf-8"
            return Page(url=url, final_url=r.geturl(), status=r.status, text=raw.decode(charset, "replace"), via="http")
    except urllib.error.HTTPError as e:
        body = e.read(200_000).decode("utf-8", "replace") if e.fp else ""
        return Page(url=url, final_url=url, status=e.code, text=body, via="http")
    except Exception as e:  # noqa: BLE001 - network errors are reported, not raised
        return Page(url=url, final_url=url, status=0, text="", via="http", error=str(e)[:200])


def _chromium(url, timeout):
    from playwright.sync_api import sync_playwright
    sys_path = Path(__file__).resolve().parents[2] / "zamakan-design-system" / "scripts"
    import sys
    sys.path.insert(0, str(sys_path))
    from _common import launch_chromium
    with sync_playwright() as pw:
        b = launch_chromium(pw)
        try:
            pg = b.new_page(user_agent=UA, locale="en-US")
            r = pg.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            pg.wait_for_timeout(2500)
            return Page(url=url, final_url=pg.url, status=r.status if r else 0, text=pg.content(), via="chromium")
        except Exception as e:  # noqa: BLE001
            return Page(url=url, final_url=url, status=0, text="", via="chromium", error=str(e)[:200])
        finally:
            b.close()


def blocked(page):
    return page["status"] in (403, 429, 503) or (page["status"] == 200 and len(page["text"]) < 20000
                                                  and any(m in page["text"] for m in BOT_MARKERS))


def get(url, timeout=25, use_cache=True, browser="auto"):
    """Fetch a URL. browser: 'auto' (fallback when blocked), 'never', 'always'."""
    if use_cache:
        hit = _from_cache(url)
        if hit:
            return hit
    page = _chromium(url, timeout) if browser == "always" else _urllib(url, timeout)
    if browser == "auto" and blocked(page):
        page = _chromium(url, timeout)
    page.setdefault("cached", False)
    if page["status"] and 200 <= page["status"] < 400 and use_cache:
        _to_cache(page)
    return page


def get_json(url, timeout=20):
    page = get(url, timeout=timeout, browser="never")
    if page["status"] != 200:
        return None, page["status"]
    try:
        return json.loads(page["text"]), 200
    except json.JSONDecodeError:
        return None, page["status"]
