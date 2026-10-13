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


def fetch_one(url, with_text=False):
    src = S.site_of(url)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if src in ("youtube", "vimeo"):
        api = ("https://www.youtube.com/oembed?format=json&url=" if src == "youtube"
               else "https://vimeo.com/api/oembed.json?url=") + quote(url, safe="")
        data, status = _web.get_json(api)
        rec = S.parse_oembed(data, url) if data else {"url": url, "source": src}
        rec.update(http_status=status, via="oembed", fetched_at=now)
        return rec
    page = _web.get(url)
    if not page["text"] or page["status"] >= 400 or page["status"] == 0:
        return {"url": url, "source": src, "http_status": page["status"], "via": page.get("via"),
                "fetched_at": now, "error": page.get("error") or f"HTTP {page['status']}"}
    rec = S.parse(page["final_url"] or url, page["text"])
    if with_text:
        rec["text"] = S.main_text(page["text"])
    rec.update(http_status=page["status"], via=page["via"] + (" (cache)" if page.get("cached") else ""), fetched_at=now)
    if page.get("final_url") and page["final_url"].rstrip("/") != url.rstrip("/"):
        rec["final_url"] = page["final_url"]
    return rec


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
        for cand in [rec["thumbnail"]] + rec.get("thumbnail_alts", []):  # first one that still exists
            try:
                req = urllib.request.Request(cand, headers=_web.HEADERS)
                with urllib.request.urlopen(req, timeout=20) as r:
                    im = Image.open(io.BytesIO(r.read(60_000_000))).convert("RGB")
                im.thumbnail((480, 480))
                im.save(dst, "JPEG", quality=82, optimize=True)
                rec["thumbnail"] = cand
                break
            except Exception as e:  # noqa: BLE001 - a missing thumbnail never blocks research
                err = str(e)[:120]
        else:
            rec["thumbnail_error"] = err
            return rec
    rec["thumbnail_local"] = str(dst)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--from", dest="src", help="JSONL with a 'url' per line (e.g. discover.py output)")
    ap.add_argument("--out")
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
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok = sum(1 for r in recs if not r.get("error"))
        print(f"{ok}/{len(recs)} fetched → {a.out}")
        for r in recs:
            print(f"  {'✓' if not r.get('error') else '✗'} {r.get('brand', r.get('channel', ''))[:22]:<22} "
                  f"{(r.get('title') or r.get('error', ''))[:60]:<60} {r.get('country', '')} {r.get('year', '')}")
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
