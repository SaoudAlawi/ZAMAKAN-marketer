#!/usr/bin/env python3
"""Compare a new draft with the previous one and its notes, so the reader re-reads only what changed: scenes are
matched (same, changed, new, cut), and every previous note gets a starting status from what happened to its scene
(scene unchanged → probably still open; changed → re-read; cut → check). Claude confirms each status after reading
the changed scenes and writes them into the new notes.json as "previous".

Usage:
  python compare.py old/script.json old/notes.json new/script.json --out compare.json
Prints the scene map, the scenes to re-read, and the previous notes with their starting status (each with its id).
"""
import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _screenplay as S  # noqa: E402


def scene_texts(sc):
    out = {}
    for e in sc["elements"]:
        if e.get("scene") and e["type"] != "scene_heading":
            out.setdefault(e["scene"], []).append(e["text"])
    return {s["n"]: {"heading": f'{s.get("int_ext") or ""} {s.get("place") or ""} {s.get("time") or ""}'.strip(),
                     "text": " ".join(out.get(s["n"], []))} for s in sc["scenes"]}


def sim(a, b):
    return SequenceMatcher(None, re.sub(r"\s+", " ", a), re.sub(r"\s+", " ", b), autojunk=False).ratio()


def match(old, new):
    """Greedy best match by text similarity, nudged by matching headings."""
    o, n = scene_texts(old), scene_texts(new)
    pairs = []
    for a, oa in o.items():
        for b, nb in n.items():
            score = sim(oa["text"], nb["text"]) + (0.15 if oa["heading"] == nb["heading"] else 0)
            pairs.append((score, a, b))
    pairs.sort(reverse=True)
    used_o, used_n, m = set(), set(), {}
    for score, a, b in pairs:
        if a in used_o or b in used_n or score < 0.35:
            continue
        used_o.add(a)
        used_n.add(b)
        raw = sim(o[a]["text"], n[b]["text"])
        m[b] = {"old": a, "similarity": round(raw, 2), "status": "same" if raw > 0.93 else "changed"}
    for b in n:
        m.setdefault(b, {"old": None, "similarity": 0, "status": "new"})
    cut = sorted(set(o) - used_o)
    return m, cut


def compare(old, old_notes, new):
    m, cut = match(old, new)
    old_to_new = {v["old"]: b for b, v in m.items() if v["old"]}
    items = []
    for i, n in enumerate(old_notes["notes"]):
        if n["kind"] == "strength":
            continue
        now = old_to_new.get(n["scene"])
        if now is None:
            start = "check: scene cut"
        elif m[now]["status"] == "same":
            start = "probably open: scene unchanged"
        else:
            start = "re-read: scene changed"
        items.append({"id": i, "old_scene": n["scene"], "new_scene": now, "lens": n["lens"], "start": start, "text": n["text"][:160]})
    reread = sorted(b for b, v in m.items() if v["status"] != "same")
    return {"scene_map": {str(k): v for k, v in sorted(m.items())}, "cut": cut, "reread": reread, "previous_notes": items,
            "old_scenes": len(old["scenes"]), "new_scenes": len(new["scenes"])}


def show(c, new_path="new/script.json"):
    out = [f"# draft comparison: {c['old_scenes']} → {c['new_scenes']} scenes · cut {c['cut'] or '-'}",
           "scene map (new ← old, similarity): " + " · ".join(
               f"S{k}←{('S' + str(v['old'])) if v['old'] else 'new'}" + (f" {v['similarity']}" if v["old"] else "") + ("" if v["status"] == "same" else f" [{v['status']}]")
               for k, v in c["scene_map"].items()),
           f"re-read only: {', '.join('S' + str(s) for s in c['reread']) or 'nothing changed'}  (python3 show.py {new_path} {' '.join(map(str, c['reread']))})",
           "", "## previous notes (id · old scene → new scene · starting status); strengths are left out, so ids skip them"]
    for it in c["previous_notes"]:
        out.append(f"[{it['id']}] S{it['old_scene']} → {('S' + str(it['new_scene'])) if it['new_scene'] else 'cut'} · {it['lens']} · {it['start']} · {it['text'][:90]}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old_script")
    ap.add_argument("old_notes")
    ap.add_argument("new_script")
    ap.add_argument("--out")
    a = ap.parse_args()
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    c = compare(load(a.old_script), load(a.old_notes), load(a.new_script))
    if a.out:
        Path(a.out).write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    print(show(c, a.new_script))


if __name__ == "__main__":
    main()
