#!/usr/bin/env python3
"""Check every shot against its live page, with the reference scout's verify.py (same rules, same evidence levels).

Usage: python verify_shots.py <shots.json> [--write]

  content - page read and it matches · title - page exists, details unconfirmed · video - the video exists, nobody watched it
A shot is verified when one link is live and matches its title (or maker); rejected when every link is dead.
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shared  # noqa: E402,F401
import verify as V  # noqa: E402


def in_library(shot, u):
    """A library page (Eyecannndy technique/search page) lists many clips: check this clip's title is on it."""
    import datetime as dt
    import html as H
    import _web
    page = _web.get(u["url"], browser="never")
    raw = H.unescape(page.get("text") or "")
    ok = page.get("status") == 200 and shot["title"] in raw
    u.update(http_status=page.get("status") or 0, checked_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             verified=ok, title_match=ok)
    if ok:
        u["evidence"] = "title"  # the library lists it; the film itself wasn't opened
    return ok, page.get("status") or 0


def check(shot):
    lib = [u for u in shot["urls"] if u["kind"] == "library"]
    if lib and len(lib) == len(shot["urls"]):
        res = [in_library(shot, u) for u in lib]
        shot["status"] = "verified" if any(ok for ok, _ in res) else ("unverified" if any(200 <= st < 400 for _, st in res) else "rejected")
        return shot["id"], shot["status"], [(u["url"], u["http_status"], u["verified"], u.get("evidence")) for u in lib]

    ref = {"id": shot["id"], "title": shot["title"], "brand": shot.get("maker", ""), "urls": shot["urls"], "status": shot["status"]}
    if shot.get("kind") == "stills":  # film-still pages are titled with the film; the maker (director) isn't on the page
        ref["brand"] = ""
    _, _, after, urls = V.check(ref)
    shot["status"] = after
    return shot["id"], after, urls


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shots")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    path = Path(a.shots)
    run = json.loads(path.read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(check, run["shots"]))
    levels = {"content": 0, "title": 0, "video": 0}
    counts = {}
    for sid, after, urls in res:
        counts[after] = counts.get(after, 0) + 1
        if after != "verified":
            print(f"  {after:<10} {sid}: " + "; ".join(f"{s} {'match' if m else 'no-match'} {u}" for u, s, m, _ in urls))
            continue
        best = max(urls, key=lambda x: V.EVIDENCE_RANK.get(x[3], 0))[3]
        levels[best or "content"] = levels.get(best or "content", 0) + 1
        if best == "video":
            print(f"  video      {sid}: exists, not watched: describe only what the source says; add it to watch_list")
    print(f"verified {counts.get('verified', 0)} (page read {levels['content']} · page exists {levels['title']} · video, not watched "
          f"{levels['video']}) · unverified {counts.get('unverified', 0)} · rejected {counts.get('rejected', 0)} of {len(res)}")
    if a.write:
        run["run"]["web_access"] = "full"
        path.write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"updated {path}")


if __name__ == "__main__":
    main()
