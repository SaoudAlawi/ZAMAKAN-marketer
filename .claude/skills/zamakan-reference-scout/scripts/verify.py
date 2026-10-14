#!/usr/bin/env python3
"""Verify every reference in references.json against its live page (no invented campaigns).

Usage: python verify.py <references.json> [--write] [--workers 6]

For each reference URL: fetch it (YouTube/Vimeo via oEmbed), record http_status and checked_at,
and compare the page with the reference's title/brand: the page title first, then (for articles whose headline doesn't
name the campaign) the page's readable text. Each URL gets an `evidence` level:
  content  - the page was read and it matches (title, or campaign + brand in the body text)
  title    - the title matches but there is almost no readable text (login wall, award entry, empty shell):
             the page exists; details such as award level are NOT confirmed by it
  video    - a YouTube/Vimeo video exists with this title; nobody has watched it
Then per reference:
  verified    - at least one URL is reachable AND matches (see `evidence` for how strongly)
  unverified  - reachable but no match (check by hand, fix the title, or drop it)
  rejected    - every URL is gone (404/410) or unreachable: never show it as a reference
Run it again after every edit of references.json (rebuilding the file resets statuses).
--write updates the file in place (and sets run.web_access = "full"); otherwise it only reports.
"""
import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_meta import fetch_one  # noqa: E402

STOP = {"the", "a", "an", "of", "and", "for", "to", "in", "on", "by", "with", "at", "from", "is", "as", "our", "your", "its", "campaign", "ad", "ads", "film",
        "official", "video", "case", "study", "tvc", "commercial", "ramadan", "kareem", "mubarak", "ads", "world"}


def tokens(text):
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = re.sub(r"[^\w؀-ۿ]+", " ", t)
    return {w for w in t.split() if len(w) > 1 and w not in STOP}


def matches(ref, page):
    """True if the fetched page plausibly is this reference (a bilingual title is tried in each language)."""
    title = ref.get("title") or ""
    parts = [p for p in re.split(r"[()\[\]|/]", title) if p.strip()]
    if len(parts) > 1:
        return any(_matches({**ref, "title": p}, page) for p in [title] + parts)
    return _matches(ref, page)


def _matches(ref, page):
    claimed = tokens(ref.get("title"))
    found = tokens(page.get("title")) | tokens(page.get("final_url", "")) | tokens(page.get("url", "").rsplit("/", 1)[-1])
    brand_ok = bool(tokens(ref.get("brand")) & (found | tokens(page.get("brand")) | tokens(page.get("channel"))
                                                 | tokens(page.get("description"))))
    if not claimed:
        return brand_ok
    # substring match on the squashed page title too, so "#TimeToSavour" matches "Time to Savour"
    squashed = re.sub(r"[^\w\u0600-\u06FF]", "", " ".join(str(page.get(k) or "") for k in ("title", "final_url", "url")).lower())
    overlap = sum(1 for w in claimed if w in found or w in squashed) / len(claimed)
    return overlap >= 0.6 or (overlap >= 0.3 and brand_ok)


def text_match(ref, text):
    """For articles whose headline doesn't name the campaign: the campaign words and the brand appear in the body."""
    body = tokens(text)
    claimed, brand = tokens(ref.get("title")), tokens(ref.get("brand"))
    return bool(claimed) and len(claimed & body) / len(claimed) >= 0.6 and bool(brand & body)


EVIDENCE_RANK = {"content": 3, "title": 2, "video": 1}


def check(ref):
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    any_ok, any_alive = False, False
    for u in ref["urls"]:
        page = fetch_one(u["url"])
        status = page.get("http_status") or 0
        alive = 200 <= status < 400 and not page.get("error")
        m = alive and matches(ref, page)
        evidence = None
        if alive and page.get("source") in ("youtube", "vimeo"):
            evidence = "video" if m else None
        elif alive:
            full = fetch_one(u["url"], with_text=True) if not m or page.get("text_chars") is None else page
            if not m and text_match(ref, full.get("text", "")):
                m = True
            if m:
                evidence = "content" if (full.get("text_chars") or page.get("text_chars") or 0) >= 400 else "title"
        u.update(http_status=status, checked_at=now, verified=bool(m), title_match=bool(m))
        if evidence:
            u["evidence"] = evidence
        else:
            u.pop("evidence", None)
        any_alive |= alive
        any_ok |= m
    before = ref["status"]
    ref["status"] = "verified" if any_ok else ("unverified" if any_alive else "rejected")
    return ref["id"], before, ref["status"], [(u["url"], u["http_status"], u["title_match"], u.get("evidence")) for u in ref["urls"]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("references")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    path = Path(a.references)
    run = json.loads(path.read_text(encoding="utf-8"))
    refs = [r for r in run["references"]]
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        results = list(ex.map(check, refs))
    counts = {}
    for rid, before, after, urls in results:
        counts[after] = counts.get(after, 0) + 1
        if after != "verified":
            detail = "; ".join(f"{s} {'match' if m else 'no-match'} {u}" for u, s, m, _ in urls)
            print(f"  {after:<10} {rid}: {detail}")
            continue
        best = max((EVIDENCE_RANK.get(e, 0) for *_, e in urls), default=0)
        if best == 2:
            print(f"  thin       {rid}: page exists but has almost no readable text (login wall?): details not confirmed by it")
        elif best == 1:
            print(f"  video      {rid}: the video exists; nobody has watched it: say so before quoting what happens in it")
        if any(not m for _, _, m, _ in urls):
            extra = "; ".join(f"{s} {u}" for u, s, m, _ in urls if not m)
            print(f"  note       {rid}: verified, but extra link(s) don't match the title (fine for press coverage; check): {extra}")
    best = {}
    for rid, _, after, urls in results:
        if after == "verified":
            ev = max((EVIDENCE_RANK.get(e, 0) for *_, e in urls), default=3)
            best[ev] = best.get(ev, 0) + 1
    print(f"verified {counts.get('verified', 0)} (page read {best.get(3, 0) + best.get(0, 0)} · page exists, details unconfirmed "
          f"{best.get(2, 0)} · video, not watched {best.get(1, 0)}) · unverified {counts.get('unverified', 0)} · "
          f"rejected {counts.get('rejected', 0)} of {len(refs)}")
    if a.write:
        run["run"]["web_access"] = "full"
        path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"updated {path}")


if __name__ == "__main__":
    main()
