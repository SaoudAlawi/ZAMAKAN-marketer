#!/usr/bin/env python3
"""Run the full extraction pipeline on a client's brand folder.

Usage: python extract_all.py <input_dir> --out <work_dir>

Produces in <work_dir>:
  digest.md          ← READ THIS FIRST: compact overview of everything found
  pages.md           guideline text per page (Arabic masked as ⟨AR⟩)
  inventory.json, pdf_digest.json, fonts.json, logos.json   full data
  pages/sheet.png, pages/page-NN.png, logos/sheet.png      images for visual checks
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fonts as fonts_mod  # noqa: E402
import inventory as inv_mod  # noqa: E402
import logos as logos_mod  # noqa: E402
import pdf_digest as pdf_mod  # noqa: E402
from _common import write_json  # noqa: E402


def _fmt(v):
    return " ".join(str(x) for x in v) if isinstance(v, list) else (v or "")


def build_digest(input_dir, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    root = Path(input_dir)
    inv = inv_mod.inventory(root)
    write_json(out / "inventory.json", inv)
    by_kind = {}
    for f in inv["files"]:
        by_kind.setdefault(f["kind"], []).append(f["path"])

    # PDFs (guidelines first; several guideline PDFs are digested into sub-folders)
    guides = by_kind.get("guideline", [])
    pdfs = []
    for i, g in enumerate(guides):
        sub = out if len(guides) == 1 else out / f"pdf{i + 1}"
        pdfs.append(pdf_mod.digest(root / g, sub))
    palette = sorted({r["hex"] for d in pdfs for p in d["page_data"] for r in p["color_records"] if "hex" in r}
                     | {u["hex"] for d in pdfs for p in d["page_data"] for u in p["unlabelled_swatches"]})

    font_files = [root / p for p in by_kind.get("font", [])]
    fonts = fonts_mod.collect(font_files) if font_files else {"families": [], "files": []}
    write_json(out / "fonts.json", fonts)

    logo_files = [root / p for p in by_kind.get("logo", [])]
    logos = logos_mod.run(logo_files, out, palette) if logo_files else {"logos": []}

    # ---- digest.md -------------------------------------------------------
    L = [f"# Extraction digest: `{root.name}`", "",
         "Evidence only: nothing here is a decision yet. `extracted` values must come from this evidence;",
         "anything you add beyond it is `proposed`.", ""]
    L += ["## Files", "", "| kind | count | files |", "|---|---|---|"]
    for k, files in sorted(by_kind.items()):
        shown = ", ".join(Path(f).name for f in files[:6]) + (f" … +{len(files) - 6}" if len(files) > 6 else "")
        L.append(f"| {k} | {len(files)} | {shown} |")
    for f in inv["files"]:
        if f.get("note"):
            L.append(f"- ⚠ `{f['path']}`: {f['note']}")
    L.append("")

    L += ["## Look at these images", ""]
    for d in pdfs:
        L.append(f"- Guideline contact sheet: `{Path(d['sheet']).relative_to(out)}` (all {d['pages']} pages)")
        must = [p["page"] for p in d["page_data"] if any(f.startswith("image-only") for f in p["flags"])]
        if must:
            L.append(f"- **Image-only pages (no text extracted, read them visually): {must}** → `pages/page-NN.png`")
        ar = [p["page"] for p in d["page_data"] if any(f.startswith("arabic") for f in p["flags"])]
        if ar:
            L.append(f"- Arabic on pages {ar}: extracted Arabic is unreliable, so read Arabic names and labels from page images")
    if logos.get("sheet"):
        L.append(f"- Logo contact sheet: `{Path(logos['sheet']).relative_to(out)}` (each logo on light + dark)")
    L.append("")

    for d in pdfs:
        L += [f"## Colours stated in `{d['file']}`", "",
              "| HEX | name (candidates) | page | RGB | CMYK | Pantone | swatch check | notes |", "|---|---|---|---|---|---|---|---|"]
        for p in d["page_data"]:
            for r in p["color_records"]:
                chk = "✓ swatch matches" if r.get("verified_by_swatch") else (
                    f"swatch fill {r['swatch_fill']}" if r.get("swatch_fill") and "hex" not in r else "")
                note = "; ".join(r.get("checks", [])) + (" Arabic name on page" if r.get("has_arabic_name") else "")
                if not r.get("name_candidates"):
                    note += f" context: “{r['context'][:70]}”"
                L.append(f"| {r.get('hex', '—')} | {', '.join(r.get('name_candidates', [])) or '?'} | {r['page']} | "
                         f"{_fmt(r.get('rgb'))} | {_fmt(r.get('cmyk'))} | {r.get('pantone', '')} | {chk} | {note.strip()} |")
        uns = [(p["page"], u) for p in d["page_data"] for u in p["unlabelled_swatches"]]
        if uns:
            L += ["", "**Drawn swatches with no HEX printed in them** (fill colour measured from the PDF vector):"]
            for pg, u in uns:
                L.append(f"- p{pg}: `{u['hex']}`, text inside: “{u['text_inside']}”")
        if d["conflicts"]:
            L += ["", "**⚠ Possible conflicts** (near-identical values on different pages):"]
            for c in d["conflicts"]:
                where = "; ".join(f"{h} on p{','.join(str(x['page']) for x in w)} (“{w[0]['context'][:60]}”)"
                                  for h, w in c["where"].items())
                L.append(f"- {c['values'][0]} vs {c['values'][1]} (ΔE {c['delta_e']}): {where}")
        L.append("")

    L += ["## Fonts", "", "| family (from file) | type | weights | scripts | in guideline text? | files |", "|---|---|---|---|---|---|"]
    all_text = "\n".join(p["text"] for d in pdfs for p in d["page_data"]).lower()
    for f in fonts["families"]:
        mentioned = "yes" if f["family"] and f["family"].lower() in all_text else "**no**"
        L.append(f"| {f['family']} | {'variable' if f['variable'] else 'static'} | {', '.join(map(str, f['weights']))} | "
                 f"{', '.join(f['scripts'])} | {mentioned} | {len(f['files'])} |")
    names_in_files = {(f["family"] or "").lower() for f in fonts["families"]}
    for d in pdfs:
        emb = [e["name"] for e in d["embedded_fonts"]]
        L += ["", f"PDF embedded fonts: {', '.join(emb)}. *{d['embedded_fonts_note']}*"]
        missing = []
        for e in emb:
            fam = re.sub(r"[-_](Regular|Bold|Medium|Light|SemiBold|Italic|Black|Thin|ExtraBold).*$", "", e)
            spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", fam).lower()
            if spaced not in names_in_files and spaced in all_text:
                missing.append(fam)
        if missing:
            L.append(f"- ⚠ Named in guideline but no font file supplied: {', '.join(missing)}")
    L.append("")

    if logos["logos"]:
        L += ["## Logo files", "", "| file | format | size | orientation | colourway | colours → palette | bg | warnings |",
              "|---|---|---|---|---|---|---|---|"]
        for lg in logos["logos"]:
            cols = ", ".join(f"{m['measured']}" + (f"→{m['palette']}" if m["palette"] and m["palette"] != m["measured"] else "")
                             + ("" if m["palette"] else " (not in palette)") for m in lg.get("palette_match", [])) \
                or ", ".join(lg.get("colors", []))
            L.append(f"| {Path(lg['file']).relative_to(root)} | {lg['format']} | {lg.get('width')}×{lg.get('height')} | "
                     f"{lg.get('orientation')} | {lg.get('colorway')} | {cols} | {lg.get('background')} | "
                     f"{'; '.join(lg.get('warnings', []))} |")
        L.append("")

    for d in pdfs:
        L += [f"## Page index: `{d['file']}` (full text in `pages.md`)", "", "| p | title | chars | flags |", "|---|---|---|---|"]
        for p in d["page_data"]:
            flags = "; ".join(f.split(":")[0] for f in p["flags"])
            L.append(f"| {p['page']} | {mask(p['title'])[:50]} | {p['chars']} | {flags} |")
        L.append("")

    (out / "digest.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    P = []
    for d in pdfs:
        P += [f"# {d['file']}: page text", "", "Arabic runs are masked as ⟨AR⟩ (extraction is garbled); read them from the page images.", ""]
        for p in d["page_data"]:
            P += [f"## p{p['page']}: {mask(p['title'])}", ""]
            P.append(p["text"] if p["text"] else "_(no extractable text: see page image)_")
            P.append("")
    (out / "pages.md").write_text("\n".join(P) + "\n", encoding="utf-8")
    return {"digest": str(out / "digest.md"), "pages": str(out / "pages.md"), "palette": palette,
            "pdfs": len(pdfs), "fonts": len(fonts["families"]), "logos": len(logos["logos"])}


def mask(t):
    return pdf_mod.mask_arabic(t or "")[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_dir")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    r = build_digest(a.input_dir, a.out)
    size = Path(r["digest"]).stat().st_size
    print(f"digest: {r['digest']} ({size / 1024:.1f} KB) · pages: {r['pages']}")
    print(json.dumps({k: v for k, v in r.items() if k not in ("digest", "pages")}))


if __name__ == "__main__":
    main()
