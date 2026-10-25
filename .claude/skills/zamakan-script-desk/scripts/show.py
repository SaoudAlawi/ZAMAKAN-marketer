#!/usr/bin/env python3
"""Print only the scenes you need from script.json, compactly (one line per element), so the reader never loads the
whole script to check a few scenes.

Usage: python show.py script.json 3 5 7-9        # scene numbers or ranges; --all for everything (short films)
"""
import json
import re
import sys
from pathlib import Path

TAG = {"scene_heading": "##", "action": "", "character": "@", "parenthetical": "  ", "dialogue": "  > ", "transition": "→ ",
       "centered": "<>", "section": "#", "synopsis": "=", "note": "[[]]"}


def wanted(args, total):
    if "--all" in args:
        return set(range(1, total + 1))
    out = set()
    for a in args:
        if "-" in a:
            x, y = a.split("-", 1)
            out.update(range(int(x), int(y) + 1))
        elif a.isdigit():
            out.add(int(a))
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    sc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    keep = wanted(sys.argv[2:], len(sc["scenes"]))
    cue = None
    for i, e in enumerate(sc["elements"]):
        if e.get("scene") not in keep:
            continue
        t = e["type"]
        if t == "scene_heading":
            print(f"\n## S{e['scene']} " + re.sub(r"^\s*(?:(?:مشهد|م)\s*[\d٠-٩]+|[\d٠-٩]+)\s*[:.\-–)]?\s*", "", e["text"]))
        elif t == "character":
            cue = e.get("name", e["text"])
        elif t == "dialogue":
            print(f"{cue}: {e['text']}  [{i}]")
        elif t == "parenthetical":
            print(f"{cue} {e['text']}")
        else:
            print(f"{TAG.get(t, '')}{e['text']}  [{i}]".strip())


if __name__ == "__main__":
    main()
