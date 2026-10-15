#!/usr/bin/env python3
"""Turn fetched candidate records into reference stubs for references.json, so nobody retypes facts by hand.

Usage: python refstub.py <detail.jsonl> [--urls <url> ...] [--ids-from shortlist.txt] [--ring direct] > stubs.json

Each stub carries what the page said (title, brand, agency, country, year, category, media, URL, thumbnail) and empty
judgement fields marked TODO (card.idea, card.why_relevant, ring, scores). Paste the stubs into references.json, fill the
TODOs, then run verify.py and validate_run.py as usual.
"""
import argparse
import json
import re
import sys
from pathlib import Path


def slug(*parts):
    return re.sub(r"[^a-z0-9]+", "-", " ".join(p for p in parts if p).lower()).strip("-")[:60] or "ref"


def stub(c, ring="TODO"):
    media = c.get("media") or (["film"] if c.get("source") in ("youtube", "vimeo") else [])
    u = {"url": c["url"], "kind": "video" if c.get("source") in ("youtube", "vimeo") else "case", "source": c.get("source", "web")}
    r = {"id": slug(c.get("brand") or c.get("channel"), c.get("title")), "title": c.get("title") or "TODO",
         "brand": c.get("brand") or c.get("channel") or "TODO", "agency": c.get("agency"), "country": c.get("country"),
         "year": c.get("year"), "category": c.get("category"), "media": media, "urls": [u], "ring": ring,
         "status": "unverified", "provenance": {"found_via": c.get("found_by", "page-fetch").split(":")[0], "confidence": "medium"},
         "card": {"idea": "TODO: what they did, one sentence", "why_relevant": "TODO: why it matters for this client"},
         "tags": [], "moments": []}
    if c.get("thumbnail"):
        r["thumbnail"] = {"url": c["thumbnail"]}
    if c.get("description"):
        r["provenance"]["notes"] = c["description"][:300]
    return {k: v for k, v in r.items() if v not in (None, "")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("detail")
    ap.add_argument("--urls", nargs="*", default=[])
    ap.add_argument("--ids-from", help="text file with one URL per line (your shortlist)")
    ap.add_argument("--ring", default="TODO")
    a = ap.parse_args()
    want = set(a.urls) | ({l.strip() for l in Path(a.ids_from).read_text().splitlines() if l.strip()} if a.ids_from else set())
    recs = [json.loads(l) for l in Path(a.detail).read_text(encoding="utf-8").splitlines() if l.strip()]
    recs = [r for r in recs if not r.get("error") and (not want or r["url"] in want or r.get("final_url") in want)]
    print(json.dumps([stub(r, a.ring) for r in recs], ensure_ascii=False, indent=1))
    print(f"{len(recs)} stubs: fill every TODO, then verify.py + validate_run.py", file=sys.stderr)


if __name__ == "__main__":
    main()
