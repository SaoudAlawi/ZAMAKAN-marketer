#!/usr/bin/env python3
"""Candidates → shot stubs for shots.json, with facts copied from the source and production notes pre-filled from
the technique dictionary (a starting point: edit them for the actual shot). Nobody retypes credits by hand.

Usage: python shotstub.py cand.jsonl [--keys keys.txt] [--list] > stubs.json
  --list   print the candidates with their keys (url, or eye:<clip id> for Eyecannndy clips) to choose from
  --keys   a file with one key per line: only those become stubs (default: all)
  --refill shots.json   after you set techniques: fill production fields still marked TODO from each shot's first technique
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared import techniques  # noqa: E402

KIND = {"wikidata": "film", "shortoftheweek": "short", "eyecannndy": "clip", "filmgrab": "stills", "shotcafe": "stills", "youtube": "clip", "vimeo": "clip",
        "directorsnotes": "short", "motionographer": "motion-design", "stash": "motion-design"}
URL_KIND = {"wikidata": "article", "shortoftheweek": "article", "eyecannndy": "video", "filmgrab": "stills", "shotcafe": "stills", "youtube": "video", "vimeo": "video",
            "directorsnotes": "article", "motionographer": "article", "stash": "article"}


def eye_to_ours():
    """Eyecannndy slug → our technique id: same id first, then the technique that lists it first, then any."""
    ts = techniques()
    m = {t["id"]: t["id"] for t in ts}
    for t in ts:
        if t["eyecannndy"]:
            m.setdefault(t["eyecannndy"][0], t["id"])
    for t in ts:
        for s in t["eyecannndy"]:
            m.setdefault(s, t["id"])
    return m


def S_of(url):
    if "ar.wikipedia" in url:
        return "Arabic Wikipedia"
    if "wikidata.org" in url:
        return "Wikidata"
    return re.sub(r"^https?://(www\.|player\.)?", "", url).split("/")[0].split(".")[0].capitalize()


def key(r):
    return f"eye:{r['clip_id']}" if r.get("clip_id") else r.get("url")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "shot").lower()).strip("-")[:50] or "shot"


def stub(r, techs, seen):
    by = {t["id"]: t for t in techniques()}
    ours = [techs[s] for s in r.get("techniques_src", []) if s in techs]
    ours = list(dict.fromkeys(ours)) or ["TODO"]
    t0 = by.get(ours[0])
    sid = slug(r.get("title"))
    while sid in seen:
        sid = f"{sid}-{len(seen)}"
    seen.add(sid)
    primary = r.get("url")
    url_kind = "article" if r.get("kind") == "article" else URL_KIND.get(r.get("source"), "video")
    if re.search(r"youtube\.com|youtu\.be|vimeo\.com", primary or ""):
        url_kind = "video"
    elif "eyecannndy.com" in (primary or ""):
        url_kind = "library"  # no original video on Eyecannndy: the technique/search page that lists the clip
    s = {"id": sid, "title": r.get("title") or "TODO", "kind": KIND.get(r.get("source"), "clip"),
         "urls": [{"url": primary, "kind": url_kind, "source": r.get("source")}], "status": "unverified",
         "techniques": ours, "why": "TODO: why this shot matters for the request",
         "production": {"method": t0["method"] if t0 else "TODO", "how": t0["how"] if t0 else "TODO", "gear": t0["gear"] if t0 else "",
                        "budget": int(t0["budget"]) if t0 else 1, "kit": t0["kit"] if t0 else "", "ai": t0["ai"] if t0 else ""},
         "provenance": {"found_via": r.get("source") if r.get("source") in ("eyecannndy", "filmgrab", "shotcafe", "youtube", "vimeo", "wikidata", "shortoftheweek") else "article",
                        "query": r.get("query", ""), "confidence": "high" if r.get("source") == "eyecannndy" else "medium"}}
    for extra in r.get("extra_urls", []):  # e.g. the playable Vimeo link of a short, the Wikidata item
        k = "video" if re.search(r"youtube\.com|youtu\.be|vimeo\.com", extra) else "article"
        s["urls"].append({"url": extra, "kind": k, "source": "wikidata" if "wikidata" in extra else S_of(extra)})
    for k in ("runtime_min", "countries", "title_ar"):
        if r.get(k):
            s[k] = r[k]
    if r.get("kind") == "documentary" or (r.get("kind") in ("film", "short") and r.get("source") in ("wikidata", "shortoftheweek")):
        s["kind"] = r["kind"]
    if r.get("found_on") and r["found_on"] != primary:
        s["found_on"] = r["found_on"]
    for k in ("year",):
        if r.get(k):
            s[k] = r[k]
    if r.get("channel"):
        s["maker"] = r["channel"]
    if r.get("credits"):
        s["credits"] = r["credits"]
        s["credits_source"] = r.get("source")
        s["maker"] = s.get("maker") or ", ".join(r["credits"].get("director", [])) or None
    if r.get("description"):
        s["shot_note"] = r["description"][:400]
    if r.get("timestamps"):
        s["timestamp"] = r["timestamps"][0]
    if r.get("thumbnail"):
        s["thumbnail"] = {"url": r["thumbnail"]}
    if r.get("stills"):
        s["stills"] = r["stills"][:6]
    return {k: v for k, v in s.items() if v not in (None, "", [], {})}


def refill(path):
    by = {t["id"]: t for t in techniques()}
    run = json.loads(Path(path).read_text(encoding="utf-8"))
    n = 0
    for s in run["shots"]:
        t = by.get((s.get("techniques") or [""])[0])
        p = s.setdefault("production", {})
        if not t:
            continue
        for k in ("method", "how", "gear", "kit", "ai"):
            if p.get(k) in (None, "", "TODO"):
                p[k] = t[k]
                n += 1
        if not isinstance(p.get("budget"), int) or p.get("budget") == 1 and t["budget"] != "1" and p.get("method") == t["method"] and p.get("how") == t["how"]:
            p["budget"] = int(t["budget"])
    Path(path).write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"filled {n} production fields from the dictionary; check them against each actual shot")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--refill":
        return refill(sys.argv[2])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("candidates")
    ap.add_argument("--keys")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    cands = [json.loads(line) for line in Path(a.candidates).read_text(encoding="utf-8").split("\n") if line.strip()]
    cands = [c for c in cands if not c.get("error")]
    if a.list:
        for c in cands:
            print(f"{key(c)}\t{c.get('source')}\t{(c.get('title') or '')[:60]}\t{','.join(c.get('techniques_src', [])[:4])}")
        return
    if a.keys:
        want = [k.strip() for k in Path(a.keys).read_text(encoding="utf-8").split("\n") if k.strip() and not k.startswith("#")]
        by = {key(c): c for c in cands}
        missing = [k for k in want if k not in by]
        if missing:
            print(f"not in candidates: {missing}", file=sys.stderr)
        cands = [by[k] for k in want if k in by]
    techs, seen = eye_to_ours(), set()
    out = [stub(c, techs, seen) for c in cands]
    print(json.dumps(out, ensure_ascii=False, indent=1))
    todo = sum(json.dumps(s).count("TODO") for s in out)
    print(f"{len(out)} stubs, {todo} TODOs to fill (why, techniques where the source had none); check every production note",
          file=sys.stderr)


if __name__ == "__main__":
    main()
