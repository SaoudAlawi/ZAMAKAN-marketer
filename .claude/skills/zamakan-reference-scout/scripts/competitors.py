#!/usr/bin/env python3
"""Competitor-watch plan: what to search, what the scripts can pull, and what only a person can check.

Usage: python competitors.py <brief.json> --out <job_dir> [--youtube] [--handles "Barn's=@barnsofficial,Half Million=@HalfMillionKSA"]

Writes <job_dir>/competitor-plan.md and <job_dir>/manual-checks.json. With --youtube it also lists each competitor's
recent uploads (within brief.window_months, default 12) into <job_dir>/candidates.jsonl, from the handles given here or in
brief.competitor_handles, and suggests candidate channels for competitors without a handle (confirm they are official).

Why: from this environment, Instagram, TikTok, Snapchat, X and the Meta Ad Library can't be read (login walls, 403s,
empty shells). Trade press, brand sites, YouTube channels and award archives can. So the plan spends web searches on
what search can find, pulls YouTube directly (no search budget needed), and hands the person a click-list for the rest.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _web  # noqa: E402
import sources as S  # noqa: E402

HERE = Path(__file__).resolve().parent


def manual_links(name, country="SA"):
    q = quote_plus(name)
    return [
        {"what": "Meta Ad Library: active ads", "url": f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country={country}&q={q}&search_type=keyword_unordered"},
        {"what": "Instagram: profile and recent posts", "url": f"https://www.instagram.com/explore/search/keyword/?q={q}"},
        {"what": "TikTok: account and recent videos", "url": f"https://www.tiktok.com/search?q={q}"},
        {"what": "X: latest posts", "url": f"https://x.com/search?q={q}&f=live"},
        {"what": "TikTok Creative Center: top ads in the country", "url": f"https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en?region={country}"},
    ]


def search_queries(name, year, category="", moment="", name_ar=None):
    ar = name_ar or name  # Arabic searches need the Arabic brand name; the English one returns unrelated results
    qs = [f'"{name}" campaign {year}', f'"{name}" campaign {year - 1}', f'"{name}" new ad {year}',
          f'"{ar}" حملة إعلانية', f'"{ar}" إعلان جديد',
          f'site:campaignme.com "{name}"', f'site:arabnews.com "{name}"', f'"{name}" agency appointed OR "account win"',
          f'"{name}" partnership OR sponsor {year}']
    if moment:
        qs.append(f'"{name}" {moment.split("(")[0].strip()}')
    return qs


def suggest_channels(name, hint=""):
    page = _web.get(f"https://www.youtube.com/results?search_query={quote_plus(f'{name} {hint}'.strip())}", browser="never")
    seen = {}
    for c in S.parse_youtube_search(page.get("text") or ""):
        if c.get("channel_url") and c["channel_url"] not in seen:
            seen[c["channel_url"]] = c.get("channel")
    first = name.split()[0].lower().rstrip("'s")
    ranked = sorted(seen.items(), key=lambda kv: first not in (kv[1] or "").lower().replace("'", ""))
    return [{"channel": ch, "url": u} for u, ch in ranked[:4]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brief")
    ap.add_argument("--out", required=True)
    ap.add_argument("--youtube", action="store_true")
    ap.add_argument("--handles", default="")
    a = ap.parse_args()
    b = json.loads(Path(a.brief).read_text(encoding="utf-8"))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    year = dt.date.today().year
    months = b.get("window_months", 12)
    handles = dict(b.get("competitor_handles", {}))
    for pair in filter(None, a.handles.split(",")):
        k, _, v = pair.partition("=")
        handles[k.strip()] = v.strip()
    country = "SA" if "saudi" in (b.get("market") or "saudi").lower() else (S.country_code(b.get("market") or "") or "SA")
    names = b.get("competitors") or []
    L = [f"# Competitor-watch plan: {b.get('client', '')}", "",
         f"Window: the last {months} months (since {S.months_ago(months).isoformat()}). "
         "Older work is context only: tag it `context` and say so.", "",
         "**Can be read from here:** trade press, brand websites and newsrooms, YouTube channels, award archives, Ads of the World.",
         "**Can't be read from here:** Instagram, TikTok, Snapchat, X, the Meta Ad Library. Don't spend searches on them; "
         "put the click-list below in the report so a person can check them in a logged-in browser (about 5 minutes per brand).", "",
         "**Search budget:** web searches are shared with other work and run out. Plan about 5 per competitor, newest first; "
         "YouTube uploads come from `discover.py youtube-channel` and cost no searches.", ""]
    manual = {}
    for name in names:
        L += [f"## {name}", "", "Web searches (in this order, stop when the picture is clear):"]
        L += [f"- `{q}`" for q in search_queries(name, year, b.get("category", ""), b.get("moment", ""), (b.get("competitor_names_ar") or {}).get(name))]
        if not (b.get("competitor_names_ar") or {}).get(name):
            L.append("- (add the Arabic name in brief.competitor_names_ar for better Arabic searches, e.g. `discover.py youtube <Arabic name> اعلان`)")
        h = handles.get(name)
        if h:
            L += ["", f"YouTube: `discover.py youtube-channel {h} --since-months {months}`"]
        elif a.youtube:
            word = (b.get("category") or "").split("/")[0].split()[-1:] or [""]
            ar = (b.get("competitor_names_ar") or {}).get(name)
            sug = (suggest_channels(ar, "اعلان") if ar else []) + suggest_channels(name, f"{word[0]} {(b.get('market') or '').split(',')[-1].strip()}")
            sug = list({c["url"]: c for c in sug}.values())[:5]
            L += ["", "YouTube channel not given. Candidates from search (confirm which is the brand's own before using):"]
            L += [f"- {c['channel']}: {c['url']}" for c in sug] or ["- none found: search `\"<brand>\" youtube channel`"]
        manual[name] = manual_links(name, country)
        L += ["", "Check by hand (put these in the report):"] + [f"- {m['what']}: {m['url']}" for m in manual[name]] + [""]
    (out / "competitor-plan.md").write_text("\n".join(L), encoding="utf-8")
    (out / "manual-checks.json").write_text(json.dumps(manual, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"plan → {out / 'competitor-plan.md'}; click-list → {out / 'manual-checks.json'}")
    if a.youtube:
        for name in names:
            if handles.get(name):
                subprocess.run([sys.executable, HERE / "discover.py", "youtube-channel", handles[name], "--since-months", str(months),
                                "--out", str(out / "candidates.jsonl")], check=False)


if __name__ == "__main__":
    main()
