#!/usr/bin/env python3
"""Discover candidate references (cheap: list pages only, no per-campaign fetch).

Usage:
  python discover.py aotw-search <keyword> [--pages 2]            # ONE keyword (multi-word returns nothing)
  python discover.py aotw-list <countries|industries|brands|agencies|medium_types|regions> <slug> [--pages 2]
  python discover.py aotw-related <campaign-url> [<campaign-url> ...]   # related campaigns of known references
  python discover.py youtube <query words...> [--limit 15]
Options: --out file.jsonl (append), --min-views N (youtube)

Each output line is a card {url, source, title, brand?, agency?, thumbnail?, views?, channel?, found_by}.
Pass the shortlisted URLs to fetch_meta.py for full details. Use the web-search tool for every other
site (Vimeo, award shows, Campaign ME, brand pages) and add those URLs to fetch_meta.py directly.
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _web  # noqa: E402
import sources as S  # noqa: E402

AOTW = "https://www.adsoftheworld.com"


def aotw_pages(first_url, pages):
    cards = []
    for p in range(1, pages + 1):
        url = first_url if p == 1 else first_url + ("&" if "?" in first_url else "?") + f"page={p}"
        page = _web.get(url)
        if page["status"] != 200:
            break
        res = S.parse_aotw_listing(page["text"])
        cards += res["cards"]
        if p >= res["last_page"]:
            break
    return cards


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["aotw-search", "aotw-list", "aotw-related", "youtube"])
    ap.add_argument("args", nargs="+")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--min-views", type=int, default=0)
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "aotw-search":
        kw = a.args[0]
        if len(a.args) > 1:
            print("note: Ads of the World matches one keyword; using only", repr(kw), file=sys.stderr)
        if len(kw) < 5:
            print(f"note: short keyword {kw!r} also matches inside other words (e.g. 'eid' in 'Leidos'); expect noise", file=sys.stderr)
        cards, by = aotw_pages(f"{AOTW}/campaigns?search={quote_plus(kw)}", a.pages), f"aotw-search:{kw}"
    elif a.cmd == "aotw-list":
        kind, slug = a.args[0], a.args[1]
        cards, by = aotw_pages(f"{AOTW}/{kind}/{slug}", a.pages), f"aotw-list:{kind}/{slug}"
    elif a.cmd == "aotw-related":
        cards, by = [], "aotw-related"
        for u in a.args:
            page = _web.get(u)
            rec = S.parse_aotw_campaign(page["text"], u) if page["status"] == 200 else {}
            cards += [{"url": r, "source": "adsoftheworld", "related_to": u,
                       "title_from_url": r.rsplit("/", 1)[-1].replace("-", " ")[:80]} for r in rec.get("related", [])]
    else:
        q = " ".join(a.args)
        page = _web.get(f"https://www.youtube.com/results?search_query={quote_plus(q)}", browser="never")
        cards = [c for c in S.parse_youtube_search(page["text"]) if (c.get("views") or 0) >= a.min_views][:a.limit]
        by = f"youtube:{q}"
    seen, out = set(), []
    for c in cards:
        if c["url"] not in seen:
            seen.add(c["url"])
            out.append({**c, "found_by": by})
    lines = [json.dumps(c, ensure_ascii=False) for c in out]
    if a.out:
        with open(a.out, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))
        print(f"{len(out)} cards ({by}) → {a.out}")
    for c in out[:40]:
        extra = f"{c.get('views', ''):>10}" if c.get("views") else ""
        print(f"  {(c.get('brand') or c.get('channel') or '')[:20]:<20} {(c.get('title') or c.get('title_from_url') or c['url'])[:64]:<64} {extra}")


if __name__ == "__main__":
    main()
