#!/usr/bin/env python3
"""Pre-rank candidates against a brief, so the agent reads the promising ones first.

Usage: python score.py <candidates.jsonl> --brief brief.json [--top 40] [--out ranked.jsonl] [--sparks]

Scores (0-5, transparent heuristics; the agent's judgement comes after):
  relevance  - brief terms (category, moment, question, channels, competitors) found in the candidate
  region     - depends on brief.scope: gcc (default) GCC 5 · MENA 3.5 · elsewhere 2 · unknown 2.5;
               mena: Arab world 5 · elsewhere 2; global: 3.5 for all (award sources +0.3)
  freshness  - by year: this year/last 5 … older drops; unknown 2.5
  reach      - YouTube views on a log scale (if known)
--sparks ranks for "sparks from elsewhere" instead: far from the client's region (5) and category (4), with craft
signals (award shows, Grand Prix/Lions/Pencil in the text, professional work) and classics welcome (freshness floor 2.5).
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
    return " ".join(str(c.get(k) or "") for k in ("title", "title_from_url", "brand", "agency", "category", "description",
                                                    "channel", "country_name", "medium_label")).lower()


AWARD_RX = r"grand prix|cannes|lions|d&ad|pencil|one show|effie|clio|titanium|dubai lynx|best of show"


def spark_score(c, b, this_year):
    """Rank for sparks: work from far outside the client's region and category, judged on craft."""
    t = text_of(c)
    home = MENA if b.get("scope") == "mena" else GCC
    country = c.get("country")
    is_home = country in home or (not country and bool(re.search(GCC_WORDS, t)))
    region = 0.5 if is_home else (2.5 if country in MENA else (5.0 if country else 3.0))
    cat_terms = words(b.get("category")) | words(" ".join(b.get("competitors", [])))
    distance = 2.0 if cat_terms & words(t) else 4.0
    craft = 2.5 + 1.0 * bool(re.search(AWARD_RX, t)) + 0.5 * (c.get("kind") == "professional") + \
        0.5 * (c.get("source") in ("adsoftheworld", "lovethework", "dandad", "oneclub")) - 1.5 * (c.get("kind") == "student")
    yr = c.get("year")
    fresh = 2.5 if not yr else max(2.5, 5.0 - 0.4 * max(0, this_year - 1 - yr))
    flags = ["home region: not a spark"] if is_home else []
    if c.get("kind") == "student":
        flags.append("student work")
    parts = {"craft": round(craft, 1), "region": region, "distance": distance, "freshness": round(fresh, 1)}
    total = 0.35 * craft + 0.3 * region + 0.2 * distance + 0.15 * fresh
    return round(total, 2), parts, flags, []


def score(c, b, terms, this_year, sparks=False):
    if sparks:
        return spark_score(c, b, this_year)
    t = text_of(c)
    hits = sorted({w for w in terms if w in t})
    rel = min(5.0, 1.0 + 1.2 * len(hits))
    untitled = not c.get("title") and not c.get("title_from_url")
    if untitled:  # a hand-picked web-search URL not fetched yet: don't bury it, fetch it
        rel = 2.5
    country = c.get("country")
    is_gcc = country in GCC or (not country and bool(re.search(GCC_WORDS, t)))
    scope = b.get("scope", "gcc")
    if scope == "global":  # no regional preference: judge the work, not where it ran
        region = 3.5
    elif scope == "mena":
        region = 5.0 if (is_gcc or country in MENA) else (2.5 if not country else 2.0)
    elif is_gcc:
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
    elif c.get("source") == "youtube" and re.search(
            r"\bnews\b|news agency|updates? tv|\bvlog|reaction|review|tutorial|how to|compilation|fan ?made|\bshorts?\b|"
            r"converting|waking up|routine|explain|prayer time|right time|day in (my|the) life|travel|prank|sketch|\bsnl\b|"
            r"saturday night live|challenge|recipe|goes to|يوميات|الحياة في",
            (c.get("title", "") + " " + c.get("channel", "")).lower()):
        flags.append("probably not a campaign (news/vlog/sketch/explainer)")
    if c.get("source") == "youtube" and not any(f.startswith("probably not") for f in flags):
        chan = {w for w in words(c.get("channel")) if len(w) >= 3} - {"official", "channel", "tv", "media"}
        if chan and not chan & words(c.get("title")):
            flags.append("channel may not be the brand: check it is an official upload")
    if untitled:
        flags.append("no title yet: run fetch_meta.py on it first")
    parts = {"relevance": round(rel, 1), "region": region, "freshness": round(fresh, 1)}
    if reach is not None:
        parts["reach"] = round(reach, 1)
    award_boost = 0.3 if b.get("scope") == "global" else 0.0
    prior = award_boost * (c.get("source") in ("lovethework", "dubailynx", "dandad", "oneclub")) + {"adsoftheworld": 0.4, "lovethework": 0.4, "dubailynx": 0.4, "dandad": 0.4, "oneclub": 0.4, "campaignme": 0.3,
             "lbbonline": 0.3, "adforum": 0.3, "campaignlive": 0.2, "vimeo": 0.1}.get(c.get("source"), 0.0)
    total = 0.45 * rel + 0.25 * region + 0.2 * fresh + 0.1 * (reach if reach is not None else 2.5) + prior
    total -= 0.8 * ("student work" in flags) + 1.5 * any(f.startswith(("AI demo", "probably not")) for f in flags)
    total -= 0.7 * any(f.startswith("channel may not") for f in flags)
    return round(total, 2), parts, flags, hits


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("candidates")
    ap.add_argument("--brief", required=True)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--out")
    ap.add_argument("--sparks", action="store_true", help="rank for sparks from elsewhere (far region and category, craft)")
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
        total, parts, flags, hits = score(c, b, terms, this_year, a.sparks)
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
