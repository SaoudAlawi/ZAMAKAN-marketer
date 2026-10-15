#!/usr/bin/env python3
"""The agency's reference library: shared campaign pages + private client notes.

Usage:
  python library.py add <references.json> --client <slug> [--client-name "Rawaq Coffee Roasters"]
  python library.py search [words...] [--country SA] [--media film] [--since 2022] [--moment ramadan]
                          [--status verified] [--client <slug>] [--limit 30] [--json]
  python library.py export          # rebuild the pages from references.jsonl (add does this automatically)
  python library.py stats
Options: --library <path> (default: $ZAMAKAN_LIBRARY, else <repo>/library/references.jsonl)

Two layers, kept apart on purpose:
  SHARED (committed, client-neutral)   library/references.jsonl     one record per campaign (machine index)
                                        library/README.md            browsable index by moment, category, market
                                        library/campaigns/<slug>/REFERENCE.md   one page per campaign
     facts, links, the idea, insight, execution, craft, sourced results, awards; how often it was used (counts only).
  PRIVATE (clients/<slug>/library/, git-ignored)
                                        notes.jsonl, README.md       why it mattered for that client, ring, scores,
                                                                     what to borrow, cultural-fit notes, risks, run ids.
Anything in a shared field that names the client is moved to the client's notes instead (and reported).
Search the library before searching the web: past runs may already hold good, verified references.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SHARED_FACTS = ["id", "title", "brand", "brand_ar", "agency", "country", "year", "month", "category", "media", "channels",
                "language", "urls", "thumbnail", "awards", "results", "moments", "tags", "live_ad", "status"]
SHARED_TEARDOWN = ["insight", "idea", "execution", "channels", "tone", "visual_devices", "results"]
CLIENT_TEARDOWN = ["transferable", "cultural_fit", "risks"]
REGION_NAME = {"gcc": "GCC", "mena": "Wider MENA", "europe": "Europe", "americas": "Americas", "asia-pacific": "Asia-Pacific",
               "africa": "Africa", None: "Other"}


def repo_root():
    p = Path(__file__).resolve()
    for d in p.parents:
        if (d / ".claude").is_dir():
            return d
    return Path.cwd()


def default_library():
    """$ZAMAKAN_LIBRARY overrides (isolated test runs, other teams); else <repo>/library/references.jsonl."""
    env = os.environ.get("ZAMAKAN_LIBRARY")
    return Path(env) if env else repo_root() / "library" / "references.jsonl"


def clients_root():
    env = os.environ.get("ZAMAKAN_CLIENTS")
    return Path(env) if env else repo_root() / "clients"


def canon(url):
    u = urlparse(url.strip())
    host = u.netloc.lower().removeprefix("www.").removeprefix("m.")
    if host in ("youtube.com", "youtu.be"):
        vid = parse_qs(u.query).get("v", [u.path.strip("/")])[0]
        return f"youtube.com/watch?v={vid}"
    return host + u.path.rstrip("/").lower()


def slugify(*parts):
    s = re.sub(r"[^a-z0-9]+", "-", " ".join(p for p in parts if p).lower()).strip("-")
    return s[:70].rstrip("-") or "campaign"


# tags that only mean something relative to one client ("this is our client's own ad", "a rival of our client"): shared,
# they would reveal who the client is, so they stay in the client's private notes
CLIENT_RELATIVE_TAGS = {"client-own-work", "own-work", "competitor", "competitor-brand", "rival", "contrast", "benchmark"}


def neutral(rec):
    """Shared, client-neutral view of a record (also migrates the old format that stored per-client cards)."""
    out = {k: rec[k] for k in SHARED_FACTS + ["key", "slug", "used", "summary", "teardown", "provenance"] if rec.get(k) not in (None, "", [], {})}
    if out.get("tags"):
        out["tags"] = [t for t in out["tags"] if t not in CLIENT_RELATIVE_TAGS]
        if not out["tags"]:
            out.pop("tags")
    if not out.get("summary"):
        idea = (rec.get("card") or {}).get("idea") or next(((s.get("card") or {}).get("idea") for s in rec.get("seen_in", []) if s.get("card")), None)
        if idea:
            out["summary"] = idea
    if rec.get("teardown"):
        td = {k: rec["teardown"][k] for k in SHARED_TEARDOWN if rec["teardown"].get(k)}
        if td:
            out["teardown"] = td
        else:
            out.pop("teardown", None)
    if rec.get("provenance"):
        out["provenance"] = {k: v for k, v in rec["provenance"].items() if k in ("found_via", "confidence")}
    if isinstance(out.get("thumbnail"), dict):  # a local path would name the client's job folder: keep the web address only
        out["thumbnail"] = {"url": out["thumbnail"]["url"]} if out["thumbnail"].get("url") else None
        if not out["thumbnail"]:
            out.pop("thumbnail")
    if "seen_in" in rec and "used" not in out:
        dates = sorted(s.get("date") for s in rec["seen_in"] if s.get("date"))
        ids = sorted({run_hash(s["run"]) for s in rec["seen_in"] if s.get("run")})
        out["used"] = {"runs": len(ids), "run_ids": ids, "first": dates[0] if dates else None, "last": dates[-1] if dates else None}
    return out


def run_hash(run_id):
    """An anonymous, stable fingerprint of a run id: counts repeat runs without naming the client."""
    return hashlib.sha1(run_id.encode()).hexdigest()[:10]


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = neutral(json.loads(line))
            out[r["key"]] = r
    return assign_slugs(out)


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


def client_terms(slug, client_name=None):
    terms = {t for t in [slug, (slug or "").replace("-", " ")] if t and len(t) >= 3}
    if client_name:
        terms |= {client_name} | {w for w in client_name.split() if len(w) >= 4}
    ds = clients_root() / (slug or "_") / "design-system" / "spec.json"
    if ds.exists():
        c = json.loads(ds.read_text(encoding="utf-8")).get("client", {})
        terms |= {x for x in (c.get("name"), c.get("name_ar")) if x}
        terms |= {w for w in (c.get("name") or "").split() if len(w) >= 4}
    generic = {"coffee", "roasters", "company", "group", "bank", "arabia", "saudi"}
    return {t for t in terms if t.lower() not in generic}


def scrub(rec, terms):
    """Move any shared text that names the client out of the shared record. Returns (clean_rec, moved_fields)."""
    if not terms:
        return rec, {}
    rx = re.compile("|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)), re.I)
    moved = {}
    for k in ("summary",):
        if rec.get(k) and rx.search(rec[k]):
            moved[k] = rec.pop(k)
    for k in list((rec.get("teardown") or {})):
        v = rec["teardown"][k]
        if rx.search(json.dumps(v, ensure_ascii=False)):
            moved[f"teardown.{k}"] = rec["teardown"].pop(k)
    if rec.get("teardown") == {}:
        rec.pop("teardown")
    return rec, moved


def merge(lib, run, client=None, client_name=None):
    """Merge a run into the shared library; returns (added, updated, notes, moved) where notes are the client's private notes."""
    rid = run["run"]["id"]
    when = run["run"].get("created") or dt.date.today().isoformat()
    client = client or run["run"].get("client")
    terms = client_terms(client, client_name)
    terr_of = {}
    for t in run.get("territories", []):
        for i in t["reference_ids"]:
            terr_of.setdefault(i, []).append(t["name"])
    added = updated = 0
    notes, moved_all = [], {}
    for ref in run["references"]:
        if ref["status"] == "rejected":
            continue
        key = canon(ref["urls"][0]["url"])
        rec, moved = scrub(neutral({**ref, "summary": (ref.get("card") or {}).get("idea")}), terms)
        if moved:
            moved_all[ref["id"]] = sorted(moved)
        td = ref.get("teardown") or {}
        notes.append({"key": key, "run": rid, "date": when, "id": ref["id"], "ring": ref.get("ring"),
                      "why_relevant": (ref.get("card") or {}).get("why_relevant"), "scores": ref.get("scores"),
                      **{k: td[k] for k in CLIENT_TEARDOWN if td.get(k)}, "territories": terr_of.get(ref["id"], []),
                      "top": ref["id"] in run.get("top", []), **({"moved_from_shared": moved} if moved else {})})
        if key in lib:
            old = lib[key]
            new = {k: richer(old.get(k), rec.get(k)) for k in set(old) | set(rec) if k not in ("used", "key", "slug")}
            if old.get("status") == "verified" or rec.get("status") == "verified":
                new["status"] = "verified"
            u = old.get("used") or {}
            ids = sorted(set(u.get("run_ids", [])) | {run_hash(rid)})
            new["used"] = {"runs": len(ids), "run_ids": ids, "first": min(filter(None, [u.get("first"), when])),
                           "last": max(filter(None, [u.get("last"), when]))}
            new["key"], new["slug"] = key, old.get("slug") or slugify(rec.get("brand"), rec.get("title"))
            lib[key] = new
            updated += 1
        else:
            lib[key] = {**rec, "key": key, "used": {"runs": 1, "run_ids": [run_hash(rid)], "first": when, "last": when}}
            added += 1
    assign_slugs(lib)
    return added, updated, notes, moved_all


def assign_slugs(lib):
    """Unique, stable page names (brand-title); a clash gets a short hash of the URL."""
    taken = {}
    for r in sorted(lib.values(), key=lambda r: r["key"]):
        s = r.get("slug") or slugify(r.get("brand"), r.get("title"))
        if taken.get(s, r["key"]) != r["key"]:
            s = f"{s[:62]}-{hashlib.sha1(r['key'].encode()).hexdigest()[:6]}"
        taken[s] = r["key"]
        r["slug"] = s
    return lib


# ------------------------------------------------------------------ pages
def region_of(cc):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from validate_run import REGION
    return REGION.get(cc)


def country_name(cc):
    try:
        import pycountry
        c = pycountry.countries.get(alpha_2=cc)
        return getattr(c, "common_name", None) or c.name if c else cc
    except Exception:  # noqa: BLE001
        return cc or ""


def md(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def reference_md(r):
    import yaml
    fm = {k: r[k] for k in ("id", "title", "brand", "brand_ar", "agency", "country", "year", "category", "media", "moments", "tags", "status") if r.get(k)}
    fm["region"] = REGION_NAME.get(region_of(r.get("country")), "Other")
    fm["links"] = [{k: u[k] for k in ("url", "kind", "source", "verified", "checked_at") if k in u} for u in r["urls"]]
    if (r.get("thumbnail") or {}).get("url"):
        fm["thumbnail"] = r["thumbnail"]["url"]
    fm["used_in_runs"] = (r.get("used") or {}).get("runs", 0)
    td = r.get("teardown") or {}
    head = f"# {r.get('brand', '')}: {r.get('title', '')}"
    L = ["---", yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=200).strip(), "---", "", head, ""]
    if r.get("summary"):
        L += [f"> {r['summary']}", ""]
    if fm.get("thumbnail"):
        L += [f'<img src="{fm["thumbnail"]}" alt="{md(r.get("brand", ""))}: {md(r.get("title", ""))}" width="480">', ""]
    L += ["## Overview", "", "| | |", "|---|---|"]
    rows = [("Brand", r.get("brand", "") + (f" ({r['brand_ar']})" if r.get("brand_ar") else "")), ("Agency", r.get("agency")),
            ("Market", f"{country_name(r.get('country'))} · {fm['region']}" if r.get("country") else None), ("Year", r.get("year")),
            ("Category", r.get("category")), ("Media", ", ".join(r.get("media", []))), ("Moments", ", ".join(r.get("moments", []))),
            ("Tags", ", ".join(r.get("tags", [])))]
    L += [f"| {k} | {md(v)} |" for k, v in rows if v] + [""]
    sections = [("Insight", td.get("insight")), ("The idea", td.get("idea")), ("Execution", td.get("execution")),
                ("Channels", td.get("channels")), ("Tone", td.get("tone")),
                ("Visual devices", "\n".join(f"- {x}" for x in td.get("visual_devices", [])) or None)]
    for title, body in sections:
        if body:
            L += [f"## {title}", "", body, ""]
    res = [x for x in (r.get("results") or []) if isinstance(x, dict) and x.get("claim")]
    if res or td.get("results"):
        L += ["## Results", ""] + [f"- {x['claim']} ([source]({x['source_url']}))" if x.get("source_url") else f"- {x['claim']}" for x in res]
        if td.get("results") and not res:
            L.append(f"- {td['results']}")
        L.append("")
    if r.get("awards"):
        L += ["## Awards", ""] + [f"- {a if isinstance(a, str) else ' '.join(str(v) for v in a.values())}" for a in r["awards"]] + [""]
    L += ["## Links", ""]
    for u in r["urls"]:
        chk = f" · checked live {u['checked_at'][:10]}" if u.get("verified") and u.get("checked_at") else (" · not verified" if not u.get("verified") else "")
        L.append(f"- [{u.get('kind', 'link')} on {u.get('source') or urlparse(u['url']).netloc}]({u['url']}){chk}")
    L += ["", "---", f"*Status: {r.get('status', 'unverified')}. Used in {fm['used_in_runs']} scout run(s). Client-specific notes "
          "(why it mattered, what to borrow, fit) live in each client's private folder, not here. Generated by "
          "`library.py` from `references.jsonl`; edit the data, not this page.*", ""]
    return "\n".join(L)


def readme_md(lib):
    recs = sorted(lib.values(), key=lambda r: (-(r.get("year") or 0), r.get("brand", "").lower()))
    link = lambda r: f"[{md(r.get('brand', ''))}: {md(r.get('title', ''))}](campaigns/{r['slug']}/REFERENCE.md)"  # noqa: E731
    ver = sum(r.get("status") == "verified" for r in recs)
    L = ["# ZAMAKAN reference library", "",
         f"{len(recs)} campaigns ({ver} checked live), collected by the reference scout across client jobs. One page per campaign in "
         "`campaigns/<name>/REFERENCE.md` (facts, links, idea, insight, execution, results); `references.jsonl` is the same data for agents.",
         "Client-specific judgement (why a campaign mattered for a client, what to borrow) is kept in that client's private folder.", "",
         "Search from the command line: `python3 .claude/skills/zamakan-reference-scout/scripts/library.py search ramadan --country SA`", "",
         "**Browse:** [by moment](#by-moment) · [by category](#by-category) · [by market](#by-market) · [all campaigns](#all-campaigns)", ""]

    def group(title, keyfn, order=None):
        groups = {}
        for r in recs:
            for g in keyfn(r) or ["Other"]:
                groups.setdefault(g, []).append(r)
        L.extend([f"## {title}", ""])
        for g in (order or sorted(groups, key=lambda g: (g == "Other", -len(groups[g]), str(g)))):
            if g in groups:
                L.append(f"**{g}** ({len(groups[g])}): " + " · ".join(link(r) for r in groups[g]))
                L.append("")
    group("By moment", lambda r: [m.replace("-", " ").title() for m in r.get("moments", [])])
    group("By category", lambda r: [r.get("category") or "Other"])
    group("By market", lambda r: [REGION_NAME.get(region_of(r.get("country")), "Other")],
          order=[REGION_NAME[k] for k in ("gcc", "mena", "europe", "americas", "asia-pacific", "africa", None)])
    L += ["## All campaigns", "", "| | Campaign | Market | Year | Media | Status |", "|---|---|---|---|---|---|"]
    for r in recs:
        th = (r.get("thumbnail") or {}).get("url")
        img = f'<img src="{th}" width="120" alt="">' if th else ""
        L.append(f"| {img} | {link(r)}<br><sub>{md(r.get('summary', ''))[:140]}</sub> | {country_name(r.get('country'))} | "
                 f"{r.get('year', '')} | {', '.join(r.get('media', []))} | {'✓' if r.get('status') == 'verified' else '?'} |")
    L += ["", "*Generated by `library.py export`; do not edit by hand.*", ""]
    return "\n".join(L)


def export(lib, path):
    root = Path(path).parent
    pages = root / "campaigns"
    keep = set()
    for r in lib.values():
        d = pages / r["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "REFERENCE.md").write_text(reference_md(r), encoding="utf-8")
        keep.add(d.name)
    if pages.exists():  # pages of records that no longer exist
        for d in pages.iterdir():
            if d.is_dir() and d.name not in keep and (d / "REFERENCE.md").exists():
                (d / "REFERENCE.md").unlink()
                d.rmdir()
    (root / "README.md").write_text(readme_md(lib), encoding="utf-8")
    return len(keep)


# ------------------------------------------------------------------ client notes (private)
def client_dir(slug):
    return clients_root() / slug / "library"


def load_notes(slug):
    p = client_dir(slug) / "notes.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def save_notes(slug, notes, lib, lib_path):
    d = client_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    old = [n for n in load_notes(slug) if (n["run"], n["key"]) not in {(x["run"], x["key"]) for x in notes}]
    allnotes = sorted(old + notes, key=lambda n: (n["date"], n["run"], n["key"]))
    (d / "notes.jsonl").write_text("".join(json.dumps(n, ensure_ascii=False, sort_keys=True) + "\n" for n in allnotes), encoding="utf-8")
    rel = os.path.relpath(Path(lib_path).parent / "campaigns", d)
    L = [f"# {slug}: references and what they meant for this client", "",
         "Private (git-ignored). The campaign facts are in the shared library; this file keeps the client-specific judgement.", ""]
    for run in sorted({n["run"] for n in allnotes}, reverse=True):
        ns = [n for n in allnotes if n["run"] == run]
        L += [f"## {run} ({ns[0]['date']})", "", "| Campaign | Ring | Why it mattered | Borrow | Fit | Territories |", "|---|---|---|---|---|---|"]
        for n in ns:
            r = lib.get(n["key"], {})
            name = f"[{md(r.get('brand', n['id']))}: {md(r.get('title', ''))}]({rel}/{r['slug']}/REFERENCE.md)" if r.get("slug") else n["id"]
            fit = n.get("cultural_fit") or {}
            L.append(f"| {name}{' ★' if n.get('top') else ''} | {n.get('ring', '')} | {md(n.get('why_relevant') or '')} | "
                     f"{md('; '.join(n.get('transferable', [])))} | {fit.get('score', '')} {md(fit.get('notes', ''))} | {md(', '.join(n.get('territories', [])))} |")
        L.append("")
    (d / "README.md").write_text("\n".join(L), encoding="utf-8")
    return d


# ------------------------------------------------------------------ search
def text_of(r):
    parts = [r.get(k) for k in ("title", "brand", "brand_ar", "agency", "category", "country", "summary")]
    parts += r.get("tags", []) + r.get("moments", []) + r.get("media", [])
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
    ap.add_argument("cmd", choices=["add", "search", "export", "stats"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--library", default=str(default_library()))
    ap.add_argument("--client")
    ap.add_argument("--client-name")
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
            sys.exit("usage: library.py add <references.json> --client <slug>")
        run = json.loads(Path(a.args[0]).read_text(encoding="utf-8"))
        client = a.client or run["run"].get("client")
        added, updated, notes, moved = merge(lib, run, client, a.client_name)
        save(lib, a.library)
        n = export(lib, a.library)
        print(f"library: +{added} new, {updated} updated → {len(lib)} campaigns, {n} pages in {Path(a.library).parent}")
        if client:
            d = save_notes(client, notes, lib, a.library)
            print(f"client notes (private): {len(notes)} → {d}")
        for rid, fields in moved.items():
            print(f"  kept out of the shared library (names the client): {rid}: {', '.join(fields)}")
    elif a.cmd == "export":
        save(lib, a.library)  # also migrates old-format records
        print(f"exported {export(lib, a.library)} pages + README.md in {Path(a.library).parent}")
    elif a.cmd == "search":
        hits = search(lib, a.args, a.country, a.media, a.since, a.moment, a.status, a.limit)
        mine = {n["key"]: n for n in load_notes(a.client)} if a.client else {}
        if a.json:
            print(json.dumps([{**h, **({"client_note": mine[h["key"]]} if h["key"] in mine else {})} for h in hits], ensure_ascii=False, indent=1))
            return
        print(f"{len(hits)} match(es) in library ({len(lib)} total)")
        for r in hits:
            note = f"  [{a.client}: {mine[r['key']].get('ring')}]" if r["key"] in mine else ""
            print(f"  [{r.get('status', '?')[:5]}] {r.get('brand', '')[:20]:<20} {r.get('title', '')[:52]:<52} "
                  f"{r.get('country', ''):<2} {r.get('year', '')}  runs:{(r.get('used') or {}).get('runs', 0)}{note}  "
                  f"library/campaigns/{r['slug']}/REFERENCE.md")
    else:
        by = lambda k: {v: sum(1 for r in lib.values() if r.get(k) == v) for v in sorted({r.get(k) for r in lib.values()} - {None})}  # noqa: E731
        print(json.dumps({"total": len(lib), "status": by("status"), "country": by("country")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
