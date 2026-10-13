#!/usr/bin/env python3
"""Fetch reference pages and print compact candidate records (one JSON per line).

Usage:
  python fetch_meta.py <url> [<url> ...] [--out candidates.jsonl] [--thumbs <dir>] [--workers 6]
  python fetch_meta.py --from candidates.jsonl --out detailed.jsonl      # enrich discovered cards

Ads of the World pages give brand, agency, country, year, medium, industry, credits, video and
related campaigns. YouTube/Vimeo use their public oEmbed API. Other sites: Open Graph / JSON-LD.
Each record carries fetch evidence (http_status, via, fetched_at) used later by verify.py.
--thumbs downloads a 480px JPEG thumbnail per record for boards and decks.
--text adds the readable article/case text (≤4000 chars), e.g. to write a teardown from Campaign ME or LBB.
"""
import argparse
import re
import datetime as dt
import hashlib
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _web  # noqa: E402
import sources as S  # noqa: E402


HOST_FIX = {"adsoftheworld.com": "www.adsoftheworld.com", "campaignme.com": "campaignme.com", "lbbonline.com": "lbbonline.com"}
GENERIC_THUMB = re.compile(r"logo|default|placeholder|fallback|og[-_]?image|share[-_]?image|social[-_]?share|site[-_]?image|"
                           r"/brand/|favicon|sprite|blank\.|no[-_]?image", re.I)


def normalise(url):
    """Fix address forms that web search returns but the host doesn't answer (e.g. adsoftheworld.com without www)."""
    from urllib.parse import urlsplit, urlunsplit
    u = urlsplit(url.strip())
    host = HOST_FIX.get(u.netloc.lower(), u.netloc)
    return urlunsplit((u.scheme or "https", host, u.path, u.query, u.fragment))


def youtube_id(url):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([\w-]{11})", url)
    return m.group(1) if m else None


def fetch_one(url, with_text=False):
    asked = url
    url = normalise(url)
    rec = _fetch(url, with_text)
    if url != asked:
        rec["normalised_from"] = asked
    rec["url"] = url  # the address that was asked for (the page may redirect: see final_url)
    return rec


def _fetch(url, with_text=False):
    src = S.site_of(url)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    video = re.search(r"youtube\.com/(watch|shorts/|embed/)|youtu\.be/|vimeo\.com/\d", url)
    if src in ("youtube", "vimeo") and video:  # oEmbed only knows videos; channel and playlist pages are fetched as pages
        api = ("https://www.youtube.com/oembed?format=json&url=" if src == "youtube"
               else "https://vimeo.com/api/oembed.json?url=") + quote(url, safe="")
        data, status = _web.get_json(api)
        if not data and status in (0, 429, 500, 502, 503):  # transient: one more try
            data, status = _web.get_json(api)
        rec = S.parse_oembed(data, url) if data else {"url": url, "source": src}
        vid = youtube_id(url)
        if vid and not rec.get("thumbnail") and status not in (401, 403, 404):
            rec["thumbnail"] = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"  # always exists for a public video
        if not data:
            rec["error"] = f"oEmbed HTTP {status}" + (" (private or removed video)" if status in (401, 403, 404) else "")
        rec.update(http_status=status, via="oembed", fetched_at=now)
        if src == "youtube":
            rec["unwatched"] = True  # oEmbed proves the video exists and its title, not what is in it
        return rec
    page = _web.get(url)
    if not page["text"] or page["status"] >= 400 or page["status"] == 0:
        return {"url": url, "source": src, "http_status": page["status"], "via": page.get("via"),
                "fetched_at": now, "error": page.get("error") or f"HTTP {page['status']}"}
    rec = S.parse(page["final_url"] or url, page["text"])
    rec["text_chars"] = len(S.main_text(page["text"]))  # how much readable content the page really has
    if with_text:
        rec["text"] = S.main_text(page["text"])
    rec.update(http_status=page["status"], via=page["via"] + (" (cache)" if page.get("cached") else ""), fetched_at=now)
    if page.get("final_url") and page["final_url"].rstrip("/") != url.rstrip("/"):
        rec["final_url"] = page["final_url"]
    return rec


def looks_generic(im):
    """Too small to be a campaign image (an icon or logo)."""
    return im.width < 160 or im.height < 90


def looks_flat(im):
    """Nearly one flat colour: often a site logo or an award slate, but some real ads are flat too (a QR code on black),
    so this only asks for a look; it never drops the image."""
    from PIL import ImageStat
    return max(ImageStat.Stat(im.convert("L").resize((64, 64))).stddev) < 16


def save_thumb(rec, folder):
    if not rec.get("thumbnail"):
        return rec
    from PIL import Image
    import urllib.request
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha1(rec["url"].encode()).hexdigest()[:12] + ".jpg"
    dst = folder / name
    if not dst.exists():
        err = None
        for cand in [rec["thumbnail"]] + rec.get("thumbnail_alts", []):  # first one that still exists and isn't a site logo
            if GENERIC_THUMB.search(cand):
                rec["thumbnail_generic"] = cand
                continue
            try:
                req = urllib.request.Request(cand, headers=_web.HEADERS)
                with urllib.request.urlopen(req, timeout=20) as r:
                    im = Image.open(io.BytesIO(r.read(60_000_000))).convert("RGB")
                if looks_generic(im):
                    rec["thumbnail_generic"] = cand
                    continue
                if looks_flat(im):
                    rec["thumbnail_check"] = "flat image: may be a site logo or award slate rather than the campaign; look at it"
                im.thumbnail((480, 480))
                im.save(dst, "JPEG", quality=82, optimize=True)
                rec["thumbnail"] = cand
                break
            except Exception as e:  # noqa: BLE001 - a missing thumbnail never blocks research
                err = str(e)[:120]
        else:
            rec["thumbnail_error"] = err or "only generic images (site logo or slate): find the campaign image by hand"
            rec.pop("thumbnail", None)
            return rec
    rec["thumbnail_local"] = str(dst)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--from", dest="src", help="JSONL with a 'url' per line (e.g. discover.py output)")
    ap.add_argument("--out", help="JSONL file; records are added (a URL fetched again replaces its old line)")
    ap.add_argument("--overwrite", action="store_true", help="start --out afresh instead of adding to it")
    ap.add_argument("--thumbs")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--text", action="store_true", help="add the page's readable body text (≤4000 chars): trade-press articles, case pages")
    a = ap.parse_args()
    urls = list(a.urls)
    if a.src:
        urls += [json.loads(line)["url"] for line in Path(a.src).read_text(encoding="utf-8").splitlines() if line.strip()]
    urls = list(dict.fromkeys(urls))
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        recs = list(ex.map(lambda u: fetch_one(u, a.text), urls))
    if a.thumbs:
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            recs = list(ex.map(lambda r: save_thumb(r, a.thumbs), recs))
    lines = [json.dumps(r, ensure_ascii=False) for r in recs]
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        old = [] if a.overwrite or not out.exists() else [l for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
        new_urls = {r["url"] for r in recs}
        old = [l for l in old if json.loads(l).get("url") not in new_urls]
        out.write_text("\n".join(old + lines) + "\n", encoding="utf-8")
        ok = sum(1 for r in recs if not r.get("error"))
        print(f"{ok}/{len(recs)} fetched → {a.out}")
        for r in recs:
            print(f"  {'✓' if not r.get('error') else '✗'} {r.get('brand', r.get('channel', ''))[:22]:<22} "
                  f"{(r.get('title') or r.get('error', ''))[:60]:<60} {r.get('country', '')} {r.get('year', '')}")
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
