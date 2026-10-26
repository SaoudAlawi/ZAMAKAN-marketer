#!/usr/bin/env python3
"""Validate shots.json: schema + the skill's rules. Exit 1 on errors.

Usage: python validate_shots.py <shots.json> [--target 15]

Errors: schema problems; techniques not in the dictionary; rejected or unverified shots; groups pointing at missing shots;
mode rules (frame-match needs run.frame, who needs ≥3 people with shots); TODOs left; a cover that isn't a shot.
Warnings: shots in no group; unwatched videos missing from watch_list; credits with no credits_source; few techniques
covered; one source dominating; below target; timestamps without a video link.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared import SKILL, tech_by_id  # noqa: E402


def listed(shot, line):
    """The watch-list line names this shot (most of the title's words, or its id)."""
    import re
    words = {w for w in re.findall(r"\w{3,}", shot["title"].lower())}
    return shot["id"] in line or (words and len(words & set(re.findall(r"\w{3,}", line.lower()))) / len(words) >= 0.5)


def validate(run, target=None):
    import jsonschema
    E, W = [], []
    schema = json.loads((SKILL / "schemas/shots.schema.json").read_text(encoding="utf-8"))
    for e in sorted(jsonschema.Draft202012Validator(schema).iter_errors(run), key=lambda e: list(e.path)):
        E.append(f"schema: {'/'.join(map(str, e.path))}: {e.message[:160]}")
    if E:
        return E, W, {}
    techs = tech_by_id()
    shots = {s["id"]: s for s in run["shots"]}
    if "TODO" in json.dumps(run):
        E.append("TODOs left in the file (fill or delete them)")
    mode = run["run"]["mode"]
    roles = run["run"].get("roles") or []
    for s in run["shots"]:
        if mode != "inspire" and not s.get("production"):
            E.append(f"{s['id']}: production notes missing (required outside inspire mode)")
        if mode == "inspire":
            missing = [r for r in roles if r not in (s.get("watch_for") or {})]
            if s["kind"] not in ("essay", "interview", "breakdown") and missing:
                E.append(f"{s['id']}: watch_for missing for {', '.join(missing)}")
            if s.get("pairs_with") and s["pairs_with"] not in shots:
                E.append(f"{s['id']}: pairs_with '{s['pairs_with']}' is not a shot id")
            if s["kind"] in ("film", "short") and not s.get("credits"):
                W.append(f"{s['id']}: no credits: look them up with film_facts.py")
        for t in s["techniques"]:
            if t not in techs:
                E.append(f"{s['id']}: technique '{t}' is not in techniques.json (use an id from it, or add the technique there)")
        if s["status"] == "rejected":
            E.append(f"{s['id']}: rejected (dead link): remove it")
        elif s["status"] == "unverified":
            E.append(f"{s['id']}: unverified: run verify_shots.py, fix the title/maker or drop it")
        if s.get("credits") and not s.get("credits_source"):
            W.append(f"{s['id']}: credits without credits_source: say where they come from")
        evid = {u.get("evidence") for u in s["urls"]}
        if evid == {"video"} and not any(listed(s, w) for w in run.get("watch_list", [])):
            W.append(f"{s['id']}: video nobody has watched: add it to watch_list")
        if s.get("timestamp") and not any(u["kind"] == "video" for u in s["urls"]):
            W.append(f"{s['id']}: timestamp but no video link")
    grouped = set()
    for g in run.get("groups", []):
        if not g.get("technique") and not g.get("title"):
            E.append("a group needs a technique id or a title")
        elif g.get("technique") and g["technique"] not in techs:
            E.append(f"group '{g['technique']}' is not a technique id")
        for sid in g["shot_ids"]:
            if sid not in shots:
                E.append(f"group '{g.get('technique') or g.get('title')}' points at missing shot '{sid}'")
            grouped.add(sid)
    loose = [s for s in shots if s not in grouped]
    if run.get("groups") and loose:
        W.append(f"shots in no group: {', '.join(loose[:6])}")
    if not run.get("groups"):
        W.append("no groups: the board will group by each shot's first technique")
    if mode == "inspire":
        if not roles:
            E.append("inspire mode needs run.roles (writer, dop, director, editor)")
        kinds = Counter(s["kind"] for s in run["shots"])
        if kinds.get("film", 0) < 2:
            W.append("fewer than 2 feature films: the programme needs at least a couple of evenings")
        if not kinds.get("short"):
            W.append("no short film: add one that can be watched free tonight (shortoftheweek)")
        if not any(k in kinds for k in ("essay", "interview", "breakdown")):
            W.append("no essay or breakdown: add one way into how it was made")
        countries = Counter(c for s in run["shots"] for c in (s.get("countries") or [])[:1])
        if len(countries) < 3 and len(run["shots"]) >= 5:
            W.append("few countries: mix world, Arab and Omani/Gulf cinema (see references/oman-cinema.md)")
        no_ex = [s["id"] for s in run["shots"] if s["kind"] in ("film", "short", "scene") and not s.get("exercise")]
        if no_ex:
            W.append(f"no exercise for: {', '.join(no_ex[:5])}")
    if mode == "frame-match" and not run["run"].get("frame"):
        E.append("frame-match mode needs run.frame (the frame described in film terms)")
    if mode == "who":
        ppl = [p for p in run.get("people", []) if p["shot_ids"]]
        if len(ppl) < 3:
            E.append("who mode needs at least 3 people, each with shots that show their work")
        for p in run.get("people", []):
            for sid in p["shot_ids"]:
                if sid not in shots:
                    E.append(f"person '{p['name']}' points at missing shot '{sid}'")
    cover = run["run"].get("cover")
    if cover and cover not in shots:
        E.append(f"run.cover '{cover}' is not a shot id")
    src = Counter(s["provenance"]["found_via"] for s in run["shots"])
    if run["shots"] and src.most_common(1)[0][1] / len(run["shots"]) > 0.7 and len(run["shots"]) >= 8:
        W.append(f"{src.most_common(1)[0][0]} supplies most shots: add other sources for range")
    covered = Counter(t for s in run["shots"] for t in s["techniques"][:1])
    if mode in ("subject", "frame-match") and len(covered) < 3 and len(run["shots"]) >= 6:
        W.append("fewer than 3 lead techniques: a subject board needs a range of ways to shoot it")
    if target and len(run["shots"]) < target:
        W.append(f"{len(run['shots'])} shots, target {target}")
    stats = {"shots": len(run["shots"]), "status": dict(Counter(s["status"] for s in run["shots"])), "sources": dict(src),
             "techniques": len({t for s in run["shots"] for t in s["techniques"]}), "groups": len(run.get("groups", [])),
             "people": len(run.get("people", [])), "mode": mode}
    return E, W, stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shots")
    ap.add_argument("--target", type=int)
    a = ap.parse_args()
    run = json.loads(Path(a.shots).read_text(encoding="utf-8"))
    E, W, stats = validate(run, a.target)
    print(f"{'OK' if not E else 'FAIL'}: {stats}; {len(E)} errors, {len(W)} warnings")
    for e in E:
        print(f"  ERROR {e}")
    for w in W:
        print(f"  warn  {w}")
    sys.exit(1 if E else 0)


if __name__ == "__main__":
    main()
