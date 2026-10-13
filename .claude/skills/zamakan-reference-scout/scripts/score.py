#!/usr/bin/env python3
"""Pre-rank candidates against a brief, so the agent reads the promising ones first.

Usage: python score.py <candidates.jsonl> --brief brief.json [--top 40] [--out ranked.jsonl]

Scores (0-5, transparent heuristics; the agent's judgement comes after):
  relevance  - brief terms (category, moment, question, channels, competitors) found in the candidate
  region     - GCC 5 · wider MENA 3.5 · elsewhere 2 · unknown 2.5 (country, or Arabic/GCC words)
  freshness  - by year: this year/last 5 … older drops; unknown 2.5
  reach      - YouTube views on a log scale (if known)
Penalties: student work, the brief's `avoid` terms (flagged, not dropped), near-duplicate titles.
Output keeps every input field and adds `pre_score`, `pre_scores` and `flags`; duplicates are removed.
"""
import argparse
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path

GCC = {"SA", "AE", "KW", "QA", "BH", "OM"}
MENA = GCC | {"EG", "JO", "LB", "MA", "TN", "DZ", "IQ", "PS", "SY", "LY", "YE", "SD", "TR"}
GCC_WORDS = r"saudi|ksa|riyadh|jeddah|dammam|uae|dubai|abu dhabi|qatar|doha|kuwait|bahrain|oman|muscat|gcc|السعودية|الرياض"
MOMENT_SYNONYMS = {
    "ramadan": ["ramadan", "ramadhan", "iftar", "suhoor", "sohour", "taraweeh", "رمضان", "سحور", "إفطار", "افطار", "fanous", "fawanees"],
    "eid": ["eid", "عيد", "eidiya", "eidiyah"],
    "national day": ["national day", "اليوم الوطني", "founding day", "يوم التأسيس"],
}
STOP = set("the a an of and or for to in on by with at from is are be as this that our their its campaign brand"
           " brief references creative territories make own run after".split())


def words(text):
    return {w for w in re.findall(r"[\w؀-ۿ]{3,}", (text or "").lower()) if w not in STOP}


def brief_terms(b):
    terms = set()
    for k in ("category", "question", "audience"):
        terms |= words(b.get(k))
    moment = (b.get("moment") or "").lower()
    for key, syn in MOMENT_SYNONYMS.items():
        if key in moment or any(s in moment for s in syn):
            terms |= set(syn)
    terms |= {c.lower() for c in b.get("competitors", [])}
    return terms


def text_of(c):
    return " ".join(str(c.get(k) or "") for k in ("title", "brand", "agency", "category", "description", "channel",
                                                    "country_name", "medium_label")).lower()


def score(c, b, terms, this_year):
    t = text_of(c)
    hits = sorted({w for w in terms if w in t})
    rel = min(5.0, 1.0 + 1.2 * len(hits))
    country = c.get("country")
    if country in GCC or (not country and re.search(GCC_WORDS, t)):
        region = 5.0
    elif country in MENA:
        region = 3.5
    else:
        region = 2.0 if country else 2.5
    yr = c.get("year")
    fresh = 2.5 if not yr else max(0.0, 5.0 - 0.6 * max(0, this_year - 1 - yr))
    reach = min(5.0, math.log10(c["views"]) - 1) if c.get("views") else None
    flags = []
    if c.get("kind") == "student":
        flags.append("student work")
    stem = lambda w: w[:-1] if len(w) > 4 and w.endswith("s") else w  # noqa: E731 - lanterns ~ lantern
    avoid_hits = [a for a in b.get("avoid", []) if any(stem(w) in t for w in words(a) - {"generic", "anything", "feels"})]
    if avoid_hits:
        flags.append("touches avoid-list: " + ", ".join(avoid_hits))
    if re.search(r"\bai (ad|commercial|generated)|i created an ai", t):
        flags.append("AI demo / not a real campaign?")
    parts = {"relevance": round(rel, 1), "region": region, "freshness": round(fresh, 1)}
    if reach is not None:
        parts["reach"] = round(reach, 1)
    total = 0.45 * rel + 0.25 * region + 0.2 * fresh + 0.1 * (reach if reach is not None else 2.5)
    total -= 0.8 * ("student work" in flags) + 1.5 * any(f.startswith("AI demo") for f in flags)
    return round(total, 2), parts, flags, hits


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("candidates")
    ap.add_argument("--brief", required=True)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--out")
    a = ap.parse_args()
    b = json.loads(Path(a.brief).read_text(encoding="utf-8"))
    terms = brief_terms(b)
    this_year = dt.date.today().year
    seen_url, kept, out = set(), [], []
    for line in Path(a.candidates).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        if c.get("error") or c["url"] in seen_url:
            continue
        # near-duplicate: same brand/channel and ≥70% of title words shared (re-uploads, cut-downs)
        who = (c.get("brand") or c.get("channel") or "").lower()
        tw = words(c.get("title"))
        if any(who == w and tw and len(tw & t2) / max(1, min(len(tw), len(t2))) >= 0.7 for w, t2 in kept):
            continue
        seen_url.add(c["url"])
        kept.append((who, tw))
        total, parts, flags, hits = score(c, b, terms, this_year)
        out.append({**c, "pre_score": total, "pre_scores": parts, "flags": flags, "matched": hits})
    out.sort(key=lambda c: -c["pre_score"])
    top = out[:a.top]
    if a.out:
        Path(a.out).write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in top), encoding="utf-8")
    print(f"{len(out)} unique candidates, showing top {len(top)}" + (f" → {a.out}" if a.out else ""))
    for c in top:
        f = f"  ⚑ {'; '.join(c['flags'])}" if c["flags"] else ""
        print(f"  {c['pre_score']:>4} {(c.get('brand') or c.get('channel') or '')[:18]:<18} {(c.get('title') or '')[:54]:<54} "
              f"{c.get('country') or '':<2} {c.get('year') or '':<4}{f}")


if __name__ == "__main__":
    main()
