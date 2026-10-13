#!/usr/bin/env python3
"""Grade a design-system run against the Rawaq answer key.

Usage: python evals/grade_design_system.py <run_dir> [--client rawaq]

<run_dir>/outputs/clients/<client>/design-system/ is graded (falls back to everything under
outputs/ except input/). Works on any output format: checks are on facts, not file layout, so
with-skill and baseline runs are graded by the same rules. If a spec.json exists it is also
validated and scored field-by-field against evals/fixtures/<client>/expected-spec.json.
Writes <run_dir>/grading.json (skill-creator format) and prints a summary.
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEXT_EXT = {".md", ".json", ".css", ".html", ".txt", ".yaml", ".yml", ".csv", ".scss", ".js", ".ts"}
GARBLED = ["الرتحيب", "يف الفناء", "ب ن ي ال تمر", "أ خ ض ر", "ز عف ران", "ة يلوا ن", "التط ق ات"]


def gather(run_dir, client):
    out = Path(run_dir) / "outputs"
    ds = out / "clients" / client / "design-system"
    roots = [ds] if ds.exists() else [out]
    files = []
    for r in roots:
        for f in sorted(r.rglob("*")):
            if f.is_file() and f.suffix.lower() in TEXT_EXT and "/input/" not in str(f) and "/_work/" not in str(f):
                files.append(f)
    texts = {str(f.relative_to(out)): f.read_text(encoding="utf-8", errors="replace") for f in files}
    return out, ds, texts


def near(text, a, b, window=200, flags=re.I):
    for m in re.finditer(a, text, flags):
        seg = text[max(0, m.start() - window): m.end() + window]
        if re.search(b, seg, flags):
            return seg.replace("\n", " ")[:160]
    return None


def grade(run_dir, client="rawaq"):
    key = json.loads((REPO / f"evals/fixtures/{client}/answer-key.json").read_text(encoding="utf-8"))
    out, ds, texts = gather(run_dir, client)
    blob = "\n".join(texts.values())
    E = []

    def add(text, passed, evidence):
        E.append({"text": text, "passed": bool(passed), "evidence": evidence})

    colors = key["colors"]["primary"] + key["colors"]["secondary"]
    found = [c["name"] for c in colors if c["hex"].lower() in blob.lower()]
    add("All 8 brand colours present with correct HEX", len(found) == 8, f"found {len(found)}/8: {found}")

    ar = [c["name_ar"] for c in colors if c["name_ar"] in blob]
    add("Arabic colour names correct (≥6/8 exact)", len(ar) >= 6, f"{len(ar)}/8 exact: {ar}")

    garb = [g for g in GARBLED if g in blob]
    add("No garbled Arabic copied from PDF text extraction", not garb, f"garbled strings: {garb}" if garb else "none found")

    conf = near(blob, r"E4A23C", r"conflict|inconsisten|discrepan|mismatch|typo|differ|confirm|vs\.?|variance")
    add("Saffron HEX conflict (#E3A33B vs #E4A23C) flagged", conf, conf or "#E4A23C not mentioned as a conflict")

    sv = near(blob, r"saffron|زعفران", r"E3A33B", 70)
    wrong = near(blob, r"\"saffron\"\s*:", r"E4A23C", 80)
    add("Saffron resolved to the palette-page value #E3A33B", sv and not wrong, sv or "no saffron↔#E3A33B link")

    ch = near(blob, r"charcoal|فحمي", r"1F1B18", 70)
    add("Charcoal identified as #1F1B18 (HEX printed on a different page)", ch, ch or "not linked")

    groups = {"stretch": r"stretch|squash|distort", "rotate": r"rotat", "recolour": r"recolou?r|change (the )?colou?r|alter (the )?colou?r",
              "effects": r"shadow|effect", "background": r"low[- ]contrast|on saffron|saffron background",
              "order": r"order|swap|rearrang", "outline": r"outline", "crop": r"crop|separat"}
    misuse_txt = "\n".join(seg for seg in re.split(r"\n\s*\n", blob) if re.search(r"misuse|don.?t|do not|never|avoid|forbid", seg, re.I))
    hit = [k for k, rx in groups.items() if re.search(rx, misuse_txt, re.I)]
    add("Logo misuse rules recovered from the image-only page (≥6/8)", len(hit) >= 6, f"{len(hit)}/8: {hit}")

    sizes = {"120px": r"120\s?px|\"digital_px\":\s*120", "48px": r"48\s?px|\"digital_px\":\s*48", "32px": r"32\s?px|\"digital_px\":\s*32",
             "32mm": r"32\s?mm|\"print_mm\":\s*32", "12mm": r"12\s?mm|\"print_mm\":\s*12", "10mm": r"10\s?mm|\"print_mm\":\s*10"}
    sz = [k for k, rx in sizes.items() if re.search(rx, blob, re.I)]
    add("Logo minimum sizes captured (≥5/6)", len(sz) >= 5, f"{sz}")

    cs = near(blob, r"clear[ -]?space|exclusion zone", r"bean", 140)
    add("Clear-space rule = width of the coffee bean", cs, cs or "not found")

    nc = near(blob, r"najd[ -]?clay", r"not allowed|never|forbidden|don.?t|avoid|not on|prohibit", 120)
    add("Forbidden logo background Najd Clay captured", nc, nc or "not found")

    h1 = re.search(r"53\D{1,40}64", blob) and re.search(r"20\D{1,40}34", blob)
    add("Arabic type scale captured (e.g. H1 53/64, body 20/34)", h1, "found" if h1 else "missing")

    pf = near(blob, r"playfair", r"600|semi-?bold", 70)
    add("Playfair Display weight 600 taken from the guideline (PDF font names say Regular)", pf, pf or "not found")

    tok = [n for n, t in texts.items() if n.endswith(".json") and sum(c["hex"].lower() in t.lower() for c in colors) >= 8]
    add("Machine-readable token file containing all colours", tok, f"{tok}" if tok else "no JSON with all 8 colours")

    prop = len(re.findall(r"\bproposed\b|\bassumption\b|not specified|not defined in|suggested|\binferred\b", blob, re.I))
    add("Proposed values clearly distinguished from client-stated values (≥3 markers)", prop >= 3, f"{prop} markers")

    ph = re.search(r"warm|amber|daylight", blob, re.I) and re.search(r"cold|blue", blob, re.I)
    add("Photography direction captured (warm/amber; avoid cold/blue)", ph, "found" if ph else "missing")

    so = re.search(r"250\s?px|\"top\":\s*250|250 ?px", blob) and re.search(r"64\s?px|\"margin_px\":\s*64", blob)
    add("Social formats: 64px margin and 250px story safe zone", so, "found" if so else "missing")

    passed = sum(e["passed"] for e in E)
    result = {"expectations": E, "summary": {"passed": passed, "failed": len(E) - passed, "total": len(E),
                                             "pass_rate": round(passed / len(E), 2)},
              "files_graded": list(texts)}

    spec_path = ds / "spec.json"
    if spec_path.exists():
        result["spec_accuracy"] = spec_accuracy(spec_path, client)
    write = Path(run_dir) / "grading.json"
    # timing stays in timing.json: skill-creator's aggregator reads tokens from there
    write.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def spec_accuracy(spec_path, client):
    sys.path.insert(0, str(REPO / ".claude/skills/zamakan-design-system/scripts"))
    from validate_spec import validate
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    gold = json.loads((REPO / f"evals/fixtures/{client}/expected-spec.json").read_text(encoding="utf-8"))
    errors, warnings = validate(spec, spec_path.parents[1] / "input")
    acc = {"valid": not errors, "errors": errors[:10], "warnings": len(warnings)}
    gc = {c["hex"]: c for c in gold["colors"]}
    sc = {c["hex"]: c for c in spec.get("colors", [])}
    acc["colors_hex"] = f"{len(set(gc) & set(sc))}/{len(gc)} (+{len(set(sc) - set(gc))} extra)"
    acc["colors_name_ar"] = f"{sum(1 for h, c in gc.items() if h in sc and sc[h].get('name_ar') == c['name_ar'])}/{len(gc)}"
    acc["colors_group"] = f"{sum(1 for h, c in gc.items() if h in sc and sc[h].get('group') == c['group'])}/{len(gc)}"
    sid = {c["id"]: c["hex"] for c in spec.get("colors", [])}
    gid = {c["id"]: c["hex"] for c in gold["colors"]}
    groles = {r["role"]: gid[r["color"]] for r in gold["color_roles"]}
    sroles = {r["role"]: sid.get(r["color"]) for r in spec.get("color_roles", [])}
    acc["roles"] = f"{sum(1 for r, h in groles.items() if sroles.get(r) == h)}/{len(groles)} (spec has {sorted(sroles)})"
    gts = {(t["level"], t["script"]): (t["size_px"], t["line_height_px"], t["weight"]) for t in gold["type_scale"]}
    sts = {(t["level"], t["script"]): (t["size_px"], t["line_height_px"], t["weight"]) for t in spec.get("type_scale", [])}
    acc["type_scale_exact"] = f"{sum(1 for k, v in gts.items() if sts.get(k) == v)}/{len(gts)}"
    acc["type_scale_values_any_level"] = f"{len(set(gts.values()) & set(sts.values()))}/{len(set(gts.values()))}"
    gfam = {f["family"]: set(f["weights"]) for f in gold["fonts"]}
    sfam = {f["family"]: set(f["weights"]) for f in spec.get("fonts", [])}
    acc["fonts"] = f"{sum(1 for f, w in gfam.items() if sfam.get(f) == w)}/{len(gfam)} exact weights"
    variants = spec.get("logo", {}).get("variants", [])
    acc["logo_variants"] = len(variants)
    def bgs(vs, cmap):
        return {tuple(sorted(cmap.get(b, b) for b in v.get("approved_backgrounds", []))) for v in vs}
    acc["logo_background_sets_match"] = bgs(variants, sid) == bgs(gold["logo"]["variants"], gid)
    acc["misuse_rules"] = len(spec.get("logo", {}).get("misuse", []))
    acc["conflicts"] = [c["topic"] for c in spec.get("conflicts", [])]
    st = {}
    def walk(n):
        if isinstance(n, dict):
            if "status" in n:
                st[n["status"]] = st.get(n["status"], 0) + 1
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(spec)
    acc["status_counts"] = st
    acc["built_files"] = sorted(p.name for p in spec_path.parent.iterdir() if p.is_file())
    return acc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--client", default="rawaq")
    a = ap.parse_args()
    r = grade(a.run_dir, a.client)
    s = r["summary"]
    print(f"{s['passed']}/{s['total']} passed ({s['pass_rate']:.0%})")
    for e in r["expectations"]:
        print(f"  {'✓' if e['passed'] else '✗'} {e['text']}  [{e['evidence'][:100]}]")
    if "spec_accuracy" in r:
        print("spec accuracy:", json.dumps(r["spec_accuracy"], ensure_ascii=False))


if __name__ == "__main__":
    main()
