#!/usr/bin/env python3
"""The agency's shared reference library (one JSON record per line), deduplicated by URL.

Usage:
  python library.py add <references.json> [--client rawaq]   # merge a run's non-rejected references
  python library.py search [words...] [--country SA] [--media film] [--since 2022] [--moment ramadan]
                          [--status verified] [--limit 30] [--json]
  python library.py stats
Options: --library <path> (default: <repo>/library/references.jsonl)

Search first, before searching the web: past runs may already hold good, verified references.
Merging keeps the richest version of each field, unions tags/moments, and records every run
that used the reference in `seen_in` (run id, client, date, ring).
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RUN_SPECIFIC = {"card", "scores", "ring"}  # judged per brief; kept per run inside seen_in


def repo_root():
    p = Path(__file__).resolve()
    for d in p.parents:
        if (d / ".claude").is_dir():
            return d
    return Path.cwd()


def default_library():
    return repo_root() / "library" / "references.jsonl"


def canon(url):
    u = urlparse(url.strip())
    host = u.netloc.lower().removeprefix("www.").removeprefix("m.")
    if host in ("youtube.com", "youtu.be"):
        vid = parse_qs(u.query).get("v", [u.path.strip("/")])[0]
        return f"youtube.com/watch?v={vid}"
    return host + u.path.rstrip("/").lower()


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["key"]] = r
    return out


def save(lib, path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(lib.values(), key=lambda r: r["key"])
    p.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def richer(a, b):
    """Prefer the more informative of two values."""
    if a in (None, "", [], {}):
        return b
    if b in (None, "", [], {}):
        return a
    if isinstance(a, list) and isinstance(b, list):
        if all(isinstance(x, dict) and "url" in x for x in a + b):  # urls: merge by URL, newer fields win
            merged = {x["url"]: x for x in a}
            for x in b:
                merged[x["url"]] = {**merged.get(x["url"], {}), **x}
            return list(merged.values())
        out = {}
        for x in a + b:
            out.setdefault(json.dumps(x, sort_keys=True, ensure_ascii=False), x)
        return list(out.values())
    if isinstance(a, dict) and isinstance(b, dict):
        return {**a, **{k: richer(a.get(k), v) for k, v in b.items()}}
    if isinstance(a, str) and isinstance(b, str):
        return b if len(b) > len(a) else a
    return b


def merge(lib, run, client=None):
    rid = run["run"]["id"]
    when = run["run"].get("created") or dt.date.today().isoformat()
    added = updated = 0
    for ref in run["references"]:
        if ref["status"] == "rejected":
            continue
        key = canon(ref["urls"][0]["url"])
        rec = {k: v for k, v in ref.items() if k not in RUN_SPECIFIC}
        seen = {"run": rid, "client": client or run["run"].get("client"), "date": when, "ring": ref.get("ring"),
                "card": ref.get("card"), "scores": ref.get("scores")}
        if key in lib:
            old = lib[key]
            new = {k: richer(old.get(k), rec.get(k)) for k in set(old) | set(rec) if k not in ("seen_in", "key")}
            if old.get("status") == "verified" or rec.get("status") == "verified":
                new["status"] = "verified"
            new["seen_in"] = [s for s in old.get("seen_in", []) if s["run"] != rid] + [seen]
            new["key"] = key
            lib[key] = new
            updated += 1
        else:
            lib[key] = {**rec, "key": key, "seen_in": [seen]}
            added += 1
    return added, updated


def text_of(r):
    parts = [r.get(k) for k in ("title", "brand", "brand_ar", "agency", "category", "country")]
    parts += r.get("tags", []) + r.get("moments", []) + r.get("media", [])
    parts += [(r.get("card") or {}).get("idea")] + [(s.get("card") or {}).get("idea") for s in r.get("seen_in", [])]
    parts += [(r.get("teardown") or {}).get(k) for k in ("insight", "idea")]
    return " ".join(str(p) for p in parts if p).lower()


def search(lib, words=(), country=None, media=None, since=None, moment=None, status=None, limit=30):
    hits = []
    for r in lib.values():
        if country and r.get("country") != country.upper():
            continue
        if media and media not in r.get("media", []):
            continue
        if since and (r.get("year") or 0) < since:
            continue
        if moment and moment.lower() not in " ".join(r.get("moments", []) + r.get("tags", [])).lower() + text_of(r):
            continue
        if status and r.get("status") != status:
            continue
        t = text_of(r)
        score = sum(1 for w in words if re.search(rf"\b{re.escape(w.lower())}", t))
        if words and not score:
            continue
        hits.append((score, r.get("status") == "verified", r.get("year") or 0, r))
    hits.sort(key=lambda h: (-h[0], -h[1], -h[2]))
    return [h[3] for h in hits[:limit]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["add", "search", "stats"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--library", default=str(default_library()))
    ap.add_argument("--client")
    ap.add_argument("--country")
    ap.add_argument("--media")
    ap.add_argument("--since", type=int)
    ap.add_argument("--moment")
    ap.add_argument("--status")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    lib = load(a.library)
    if a.cmd == "add":
        if not a.args:
            sys.exit("usage: library.py add <references.json>")
        run = json.loads(Path(a.args[0]).read_text(encoding="utf-8"))
        added, updated = merge(lib, run, a.client)
        save(lib, a.library)
        print(f"library: +{added} new, {updated} updated → {len(lib)} references in {a.library}")
    elif a.cmd == "search":
        hits = search(lib, a.args, a.country, a.media, a.since, a.moment, a.status, a.limit)
        if a.json:
            print(json.dumps(hits, ensure_ascii=False, indent=1))
            return
        print(f"{len(hits)} match(es) in library ({len(lib)} total)")
        for r in hits:
            runs = ", ".join(sorted({s.get("client") or "?" for s in r.get("seen_in", [])}))
            print(f"  [{r.get('status', '?')[:5]}] {r.get('brand', '')[:20]:<20} {r.get('title', '')[:52]:<52} "
                  f"{r.get('country', ''):<2} {r.get('year', '')}  used by: {runs}  {r['urls'][0]['url']}")
    else:
        by = lambda k: {v: sum(1 for r in lib.values() if r.get(k) == v) for v in sorted({r.get(k) for r in lib.values()} - {None})}  # noqa: E731
        print(json.dumps({"total": len(lib), "status": by("status"), "country": by("country"),
                          "clients": sorted({s.get("client") for r in lib.values() for s in r.get("seen_in", []) if s.get("client")})},
                         ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
