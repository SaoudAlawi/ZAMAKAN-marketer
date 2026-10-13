#!/usr/bin/env python3
"""Read font files: family, style, weights, variable axes, scripts covered, licence.

Usage: python fonts.py <font files or dirs...> [--out fonts.json]

Static fonts report their single weight; variable fonts report the wght axis range
and named instances. Script coverage is measured from the cmap, so "does this font
actually support Arabic?" is answered from the file, not from its name.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import write_json  # noqa: E402

FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}
# Coverage = every letter of the core alphabet is mapped (presentation forms are not
# required: modern fonts shape Arabic with OpenType GSUB instead).
ARABIC_CORE = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي" + "ءآأؤإئةى"
SCRIPTS = {
    "arabic": {ord(c) for c in ARABIC_CORE},
    "latin": set(range(0x41, 0x5B)) | set(range(0x61, 0x7B)),
    "arabic-indic-digits": set(range(0x0660, 0x066A)),
    "persian-urdu-letters": {ord(c) for c in "پچژگکی"},
}


def _name(font, *ids):
    tbl = font["name"]
    for nid in ids:
        rec = tbl.getDebugName(nid)
        if rec:
            return rec
    return None


def read_font(path):
    from fontTools.ttLib import TTFont
    font = TTFont(str(path), fontNumber=0, lazy=True)
    cmap = set(font.getBestCmap() or {})
    info = {
        "file": str(path),
        "family": _name(font, 16, 1),            # typographic family, else legacy family
        "style": _name(font, 17, 2),
        "full_name": _name(font, 4),
        "postscript": _name(font, 6),
        "version": _name(font, 5),
        "weight_class": font["OS/2"].usWeightClass if "OS/2" in font else None,
        "italic": bool(font["OS/2"].fsSelection & 1) if "OS/2" in font else None,
        "glyphs": font["maxp"].numGlyphs,
        "license": (_name(font, 13) or "")[:160] or None,
        "license_url": _name(font, 14),
    }
    info["scripts"] = [s for s, needed in SCRIPTS.items() if needed <= cmap]
    if "fvar" in font:
        axes = {a.axisTag: [a.minValue, a.defaultValue, a.maxValue] for a in font["fvar"].axes}
        info["variable_axes"] = axes
        info["named_instances"] = [
            {"name": font["name"].getDebugName(inst.subfamilyNameID), "coords": inst.coordinates}
            for inst in font["fvar"].instances]
        if "wght" in axes:
            lo, _, hi = axes["wght"]
            info["weights_available"] = [w for w in range(100, 1000, 100) if lo <= w <= hi]
    else:
        info["weights_available"] = [info["weight_class"]] if info["weight_class"] else []
    return info


def collect(paths):
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.suffix.lower() in FONT_EXT)
        elif p.suffix.lower() in FONT_EXT:
            files.append(p)
    fonts = [read_font(f) for f in files]
    families = {}
    for f in fonts:
        fam = families.setdefault(f["family"], {"family": f["family"], "files": [], "weights": set(),
                                                "scripts": set(), "variable": False, "license": f["license"]})
        fam["files"].append(f["file"])
        fam["weights"].update(f["weights_available"])
        fam["scripts"].update(f["scripts"])
        fam["variable"] |= "variable_axes" in f
    fams = [{**v, "weights": sorted(v["weights"]), "scripts": sorted(v["scripts"])} for v in families.values()]
    return {"families": fams, "files": fonts}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--out")
    a = ap.parse_args()
    r = collect(a.paths)
    if a.out:
        write_json(a.out, r)
    for f in r["families"]:
        kind = "variable" if f["variable"] else "static"
        print(f"{f['family']}: {kind}, weights {f['weights'][0]}–{f['weights'][-1]}, scripts {','.join(f['scripts'])}, "
              f"{len(f['files'])} file(s)")
    if not a.out:
        print(json.dumps(r, ensure_ascii=False, indent=1)[:2000])


if __name__ == "__main__":
    main()
