#!/usr/bin/env python3
"""Validate a scout run (references.json): JSON Schema + honesty and coverage rules.

Usage: python validate_run.py <references.json> [--json]

Errors (must fix):
  - duplicate reference ids, or the same URL on two references
  - 'verified' reference without any URL marked verified (or any 'verified' in a search-only run)
  - top / territories / patterns pointing at unknown ids
  - a top reference without a teardown, or one that is rejected
Warnings (judge):
  - a top reference that is unverified
  - a brief/pitch run missing a ring, or with fewer references than target
  - few GCC references for a GCC client
"""
import argparse
import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
GCC = {"SA", "AE", "KW", "QA", "BH", "OM"}
MENA = GCC | {"EG", "JO", "LB", "MA", "TN", "DZ", "IQ", "PS", "SY", "LY", "YE", "SD"}
REGION = {**{c: "gcc" for c in GCC}, **{c: "mena" for c in MENA - GCC},
          **{c: "europe" for c in "GB FR DE IT ES NL SE NO DK FI BE CH AT IE PT PL CZ GR".split()},
          **{c: "americas" for c in "US CA MX BR AR CL CO PE".split()},
          **{c: "asia-pacific" for c in "JP KR CN IN SG TH ID MY PH VN AU NZ HK TW PK BD".split()},
          **{c: "africa" for c in "ZA NG KE GH ET TZ UG CI SN".split()}}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def schema_errors(run):
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed: pip install jsonschema"]
    v = jsonschema.Draft202012Validator(load(SKILL / "schemas/references.schema.json"))
    return [f"schema: {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message[:200]}"
            for e in sorted(v.iter_errors(run), key=lambda e: list(e.absolute_path))]


def semantic(run, target=None, brief=None):
    E, W = [], []
    refs = run["references"]
    ids = [r["id"] for r in refs]
    for i in {i for i in ids if ids.count(i) > 1}:
        E.append(f"duplicate reference id: {i}")
    seen = {}
    for r in refs:
        for u in r["urls"]:
            key = u["url"].rstrip("/").split("#")[0].lower()
            if key in seen and seen[key] != r["id"]:
                E.append(f"same URL on '{seen[key]}' and '{r['id']}': {u['url']}")
            seen[key] = r["id"]
    byid = {r["id"]: r for r in refs}
    search_only = run["run"].get("web_access") == "search-only"
    for r in refs:
        if r["status"] == "verified":
            if search_only:
                E.append(f"{r['id']}: marked verified in a search-only run (no page could be checked)")
            elif not any(u.get("verified") for u in r["urls"]):
                E.append(f"{r['id']}: status verified but no URL has verified=true")
    for t in run.get("top", []):
        if t not in byid:
            E.append(f"top: unknown id '{t}'")
            continue
        if "teardown" not in byid[t]:
            E.append(f"top: '{t}' has no teardown")
        if byid[t]["status"] == "rejected":
            E.append(f"top: '{t}' is rejected")
        elif byid[t]["status"] == "unverified":
            W.append(f"top: '{t}' is unverified; prefer verified work for deep teardowns")
    tids = {t["id"] for t in run.get("territories", [])}
    for tid in (run.get("recommendation") or {}).get("territory_ids", []):
        if tid not in tids:
            E.append(f"recommendation: unknown territory id '{tid}'")
    for c in run.get("competitor_summary", []):
        for rid in c.get("reference_ids", []):
            if rid not in byid:
                E.append(f"competitor_summary/{c['advertiser']}: unknown reference id '{rid}'")
    for group in ("territories", "patterns"):
        for item in run.get(group, []):
            for rid in item["reference_ids"]:
                if rid not in byid:
                    E.append(f"{group}/{item.get('id', item.get('pattern', '?')[:30])}: unknown reference id '{rid}'")
    live = [r for r in refs if r["status"] != "rejected"]
    if run["run"]["mode"] in ("brief", "pitch"):
        rings = {r["ring"] for r in live}
        for ring in ("direct", "category", "adjacent", "wildcard"):
            if ring not in rings:
                W.append(f"coverage: no '{ring}' references")
        if not run.get("territories"):
            W.append("no territories: brief/pitch runs should end with 3-5 creative territories")
        if len(run.get("insights", [])) < 3:
            W.append("strategy: fewer than 3 sourced insights; the board and deck open with them")
        if not run.get("recommendation"):
            W.append("strategy: no recommendation (which territories to brief, and how they combine)")
        if not run.get("before_kickoff"):
            W.append("strategy: no before_kickoff list (what to watch/confirm before presenting)")
    if target and len(live) < target:
        W.append(f"coverage: {len(live)} references, target {target}")
    scope = run["run"].get("scope", "gcc")
    if scope == "global":
        regions = {REGION.get(r.get("country")) for r in live} - {None}
        if len(regions) < 3:
            W.append(f"coverage: global scope but only {len(regions)} region(s) {sorted(regions)}")
    else:
        pool = GCC if scope == "gcc" else MENA
        n = sum(1 for r in live if r.get("country") in pool)
        if n < 3:
            W.append(f"coverage: only {n} {scope.upper()} references")
    named = [c.lower() for c in (brief or {}).get("competitors", [])]
    checked = " ".join(c["advertiser"].lower() for c in run.get("competitor_summary", []))
    missing = [c for c in named if c.split()[0] not in checked]
    if missing and run["run"]["mode"] in ("brief", "pitch", "competitor-watch"):
        W.append(f"competitors not checked in competitor_summary: {missing}")
    return E, W


def validate(run, target=None, brief=None):
    errs = schema_errors(run)
    if errs:
        return errs, []
    return semantic(run, target, brief)


def summary(run):
    refs = [r for r in run["references"] if r["status"] != "rejected"]
    count = lambda key: {k: sum(1 for r in refs if r.get(key) == k) for k in sorted({r.get(key) for r in refs} - {None})}  # noqa: E731
    return {"references": len(refs), "status": count("status"), "ring": count("ring"),
            "gcc": sum(1 for r in refs if r.get("country") in GCC), "scope": run["run"].get("scope", "gcc"),
            "regions": sorted({REGION.get(r.get("country")) for r in refs} - {None}), "top": len(run.get("top", [])),
            "insights": len(run.get("insights", [])),
            "territories": len(run.get("territories", []))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("references")
    ap.add_argument("--target", type=int)
    ap.add_argument("--brief", help="brief.json: checks every named competitor appears in competitor_summary")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    run = load(a.references)
    brief = load(a.brief) if a.brief else None
    E, W = validate(run, a.target, brief)
    out = {"ok": not E, "errors": E, "warnings": W, "summary": summary(run) if not any(e.startswith("schema") for e in E) else None}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(("OK" if not E else "FAIL") + f": {out['summary']}; {len(E)} errors, {len(W)} warnings")
        for e in E:
            print("  ERROR", e)
        for w in W:
            print("  warn ", w)
    sys.exit(1 if E else 0)


if __name__ == "__main__":
    main()
