#!/usr/bin/env python3
"""Validate a design-system spec.json: JSON Schema + semantic checks.

Usage:
  python validate_spec.py <spec.json> [--root <client_input_dir>] [--json]

Checks (beyond the schema):
  - ids are unique; every colour/font reference resolves
  - provenance: extracted/derived items cite >=1 source; proposed items give a rationale
  - stated RGB matches HEX
  - conflict 'chosen' value is one of the listed values, and the chosen colour is used
  - every type level exists for both scripts when both scripts are in use
  - fonts used in type_scale match the script
  - referenced files exist (when --root is given)
  - text/background colour roles meet WCAG contrast (warning)

Output is a compact report; exit code 1 if any errors.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import SCHEMA_PATH, contrast_ratio, hex_to_rgb, load_json, wcag_grade  # noqa: E402


def schema_errors(spec):
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed: run `pip install jsonschema`"]
    validator = jsonschema.Draft202012Validator(load_json(SCHEMA_PATH))
    out = []
    for e in sorted(validator.iter_errors(spec), key=lambda e: list(e.absolute_path)):
        path = "/".join(str(p) for p in e.absolute_path) or "(root)"
        out.append(f"schema: {path}: {e.message[:200]}")
    return out


def walk_items(node, path=""):
    """Yield (path, dict) for every dict carrying a 'status' field."""
    if isinstance(node, dict):
        if "status" in node:
            yield path, node
        for k, v in node.items():
            yield from walk_items(v, f"{path}/{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_items(v, f"{path}/{i}")


def semantic_checks(spec, root=None):
    errors, warnings = [], []

    def dupes(items, label):
        seen = set()
        for it in items:
            i = it.get("id") or it.get("role")
            if i in seen:
                errors.append(f"duplicate {label} id: {i}")
            seen.add(i)
        return seen

    colors = {c["id"]: c for c in spec.get("colors", [])}
    dupes(spec.get("colors", []), "colour")
    fonts = {f["id"]: f for f in spec.get("fonts", [])}
    dupes(spec.get("fonts", []), "font")
    dupes(spec.get("color_roles", []), "colour role")
    dupes(spec.get("logo", {}).get("variants", []), "logo variant")
    dupes(spec.get("layout", {}).get("formats", []), "format")

    def need_color(cid, where):
        if cid not in colors:
            errors.append(f"{where}: unknown colour id '{cid}'")

    for r in spec.get("color_roles", []):
        need_color(r["color"], f"color_roles/{r['role']}")
    for t in spec.get("tints", []):
        need_color(t["color"], "tints")
    for cid in spec.get("color_proportions_pct", {}):
        need_color(cid, "color_proportions_pct")
    for ts in spec.get("type_scale", []):
        where = f"type_scale/{ts['level']}/{ts['script']}"
        if ts["font"] not in fonts:
            errors.append(f"{where}: unknown font id '{ts['font']}'")
        elif fonts[ts["font"]]["script"] not in (ts["script"], "both"):
            errors.append(f"{where}: font '{ts['font']}' is {fonts[ts['font']]['script']}, not {ts['script']}")
        elif ts["weight"] not in fonts[ts["font"]]["weights"]:
            warnings.append(f"{where}: weight {ts['weight']} not in font '{ts['font']}' weights {fonts[ts['font']]['weights']}")
        if "color" in ts:
            need_color(ts["color"], where)
    for v in spec.get("logo", {}).get("variants", []):
        for cid in v.get("approved_backgrounds", []) + v.get("forbidden_backgrounds", []):
            need_color(cid, f"logo/{v['id']}")
    for g in spec.get("graphic_elements", []):
        for cid in g.get("colors", []):
            need_color(cid, f"graphic_elements/{g['id']}")
    for cid in spec.get("iconography", {}).get("colors", []):
        need_color(cid, "iconography")
    radii = {r["id"] for r in spec.get("radii", [])}
    levels = {(t["level"], t["script"]) for t in spec.get("type_scale", [])}
    dupes(spec.get("components", []), "component")
    for c in spec.get("components", []):
        where = f"components/{c['id']}"
        for k in ("background", "text", "border_color"):
            if k in c:
                need_color(c[k], where)
        if "radius" in c and c["radius"] not in radii:
            errors.append(f"{where}: unknown radius id '{c['radius']}'")
        ty = c.get("typography")
        if ty and (ty["level"], ty["script"]) not in levels:
            errors.append(f"{where}: no type_scale entry for {ty['level']}/{ty['script']}")
        if "background" in c and "text" in c:
            ratio = contrast_ratio(colors.get(c["text"], {}).get("hex", "#000000"), colors.get(c["background"], {}).get("hex", "#FFFFFF"))
            if ratio < 4.5:
                warnings.append(f"contrast: component {c['id']} text on background = {ratio:.2f}:1 ({wcag_grade(ratio)})")

    # provenance
    for path, item in walk_items(spec):
        st = item.get("status")
        if st in ("extracted", "derived") and not item.get("sources"):
            errors.append(f"{path}: status '{st}' but no sources")
        if st == "proposed" and not item.get("rationale"):
            errors.append(f"{path}: status 'proposed' but no rationale")

    # rgb vs hex
    for c in colors.values():
        if "rgb" in c:
            try:
                if tuple(c["rgb"]) != hex_to_rgb(c["hex"]):
                    errors.append(f"colors/{c['id']}: rgb {c['rgb']} != hex {c['hex']} {list(hex_to_rgb(c['hex']))}")
            except ValueError as e:
                errors.append(f"colors/{c['id']}: {e}")

    # conflicts
    for cf in spec.get("conflicts", []):
        vals = [v["value"] for v in cf["values"]]
        if cf["chosen"] not in vals:
            errors.append(f"conflict '{cf['topic']}': chosen '{cf['chosen']}' not among {vals}")
        if cf["chosen"].startswith("#") and cf["chosen"].upper() not in {c["hex"] for c in colors.values()}:
            errors.append(f"conflict '{cf['topic']}': chosen colour {cf['chosen']} is not used in colors")

    # bilingual type-scale completeness
    scale = spec.get("type_scale", [])
    scripts = {t["script"] for t in scale}
    if len(scripts) == 2:
        by = {s: {t["level"] for t in scale if t["script"] == s} for s in scripts}
        for lvl in by["latin"] ^ by["arabic"]:
            warnings.append(f"type_scale: level '{lvl}' defined for only one script")

    # files exist
    if root:
        root = Path(root)
        refs = [(f"fonts/{f['id']}", p) for f in spec.get("fonts", []) for p in f.get("files", [])]
        refs += [(f"logo/{v['id']}", p) for v in spec.get("logo", {}).get("variants", []) for p in v.get("files", [])]
        for _, item in walk_items(spec):
            refs += [("sources", s["file"]) for s in item.get("sources", [])]
        for where, p in refs:
            if not (root / p).exists():
                errors.append(f"{where}: file not found under root: {p}")

    # contrast of role pairs (warning only; rules may restrict usage)
    roles = {r["role"]: r["color"] for r in spec.get("color_roles", [])}
    # intended pairings only: normal text on light backgrounds, inverse text on inverse backgrounds
    bgs = [r for r in roles if r.startswith(("background", "surface"))]
    for t in [r for r in roles if r.startswith("text")]:
        for b in [b for b in bgs if ("inverse" in b) == ("inverse" in t)]:
            if roles[t] in colors and roles[b] in colors:
                ratio = contrast_ratio(colors[roles[t]]["hex"], colors[roles[b]]["hex"])
                if ratio < 4.5:
                    warnings.append(f"contrast: {t} on {b} = {ratio:.2f}:1 ({wcag_grade(ratio)})")

    return errors, warnings


def validate(spec, root=None):
    errs = schema_errors(spec)
    if errs:  # semantic checks assume a structurally valid spec
        return errs, []
    return semantic_checks(spec, root)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--root", help="client input dir; checks referenced files exist")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()
    spec = load_json(a.spec)
    errors, warnings = validate(spec, a.root)
    n_items = sum(1 for _ in walk_items(spec))
    status_counts = {}
    for _, it in walk_items(spec):
        status_counts[it["status"]] = status_counts.get(it["status"], 0) + 1
    if a.json:
        print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings, "items": n_items,
                          "status_counts": status_counts}, ensure_ascii=False, indent=1))
    else:
        print(f"{'OK' if not errors else 'FAIL'}: {n_items} items {status_counts}; "
              f"{len(errors)} errors, {len(warnings)} warnings")
        for e in errors:
            print("  ERROR", e)
        for w in warnings:
            print("  warn ", w)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
