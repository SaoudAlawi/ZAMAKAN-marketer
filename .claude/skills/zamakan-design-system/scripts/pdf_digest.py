#!/usr/bin/env python3
"""Digest a brand-guideline PDF into compact, agent-friendly evidence.

Usage: python pdf_digest.py <guideline.pdf> --out <work_dir> [--dpi 110]

Writes to <work_dir>:
  pdf_digest.json     full per-page data (text, colour mentions, swatch fills, flags, fonts)
  pages/page-NN.png   page renders for visual checks
  pages/sheet.png     contact sheet of all pages (one image = whole document at a glance)
Prints a short summary.

Why: the agent should not read a raw PDF. This gives it per-page text with Arabic runs
masked (PDF Arabic extraction is usually garbled; read Arabic from the page image instead),
every colour value with its location, the exact fill colour of drawn swatches, and flags
for pages that need a visual check (image-only pages, Arabic content).
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import cmyk_to_hex, delta_e, hex_to_rgb, rgb_to_hex, write_json  # noqa: E402

ARABIC = r"؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿"
ARABIC_RUN = re.compile(rf"[{ARABIC}][{ARABIC}\s‌-‏،؛؟.,:،؛؟ـ]*")
HAS_ARABIC = re.compile(rf"[{ARABIC}]")
N = r"(\d{1,3}(?:\.\d+)?)"
SEP = r"[\s,/;]+"
PATTERNS = {  # several notations per kind, as found in real guidelines
    "hex": [re.compile(r"(?<![0-9A-Za-z])#([0-9A-Fa-f]{6})(?![0-9A-Fa-f])"),
            re.compile(r"\b(?:HEX|Hex|hex|HTML|Web)\b[:\s]*([0-9A-Fa-f]{6})\b")],
    "rgb": [re.compile(rf"\bRGB\b[:\s]*\(?{N}{SEP}{N}{SEP}{N}", re.I),
            re.compile(r"\bR\s?(\d{1,3})\s+G\s?(\d{1,3})\s+B\s?(\d{1,3})\b")],
    "cmyk": [re.compile(rf"\bCMYK\b[:\s]*\(?{N}{SEP}{N}{SEP}{N}{SEP}{N}", re.I),
             re.compile(r"\bC\s?(\d{1,3})\s+M\s?(\d{1,3})\s+Y\s?(\d{1,3})\s+K\s?(\d{1,3})\b")],
    "pantone": [re.compile(r"\b(?:Pantone|PMS)\b[:\s®]*([0-9]{3,5}\s?[A-Z]{0,2}|[A-Za-z]+(?:\s[A-Za-z]+)?\s?[CU])\b")],
}


def find_values(text):
    """Yield (kind, normalised value, match) for every colour value in text, without double counting."""
    taken = []
    for kind, rxs in PATTERNS.items():
        for rx in rxs:
            for m in rx.finditer(text):
                if any(a < m.end() and m.start() < b for a, b in taken):
                    continue
                taken.append(m.span())
                if kind == "hex":
                    val = "#" + m.group(1).upper()
                elif kind == "pantone":
                    val = m.group(1).strip()
                else:
                    val = [round(float(g)) for g in m.groups()]
                yield kind, val, m


def mask_arabic(text):
    """Replace Arabic runs with ⟨AR⟩ (garbled in extraction); returns (masked, n_runs)."""
    n = len(ARABIC_RUN.findall(text))
    return ARABIC_RUN.sub("⟨AR⟩ ", text).replace("⟨AR⟩  ", "⟨AR⟩ ").strip(), n


def rect_contains(outer, inner, pad=1.0):
    return (outer[0] - pad <= inner[0] and outer[1] - pad <= inner[1]
            and outer[2] + pad >= inner[2] and outer[3] + pad >= inner[3])


def area(r):
    return max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])


def page_fills(page, page_area):
    """Filled vector rectangles/shapes: candidate colour swatches."""
    fills = []
    for d in page.get_drawings():
        f = d.get("fill")
        if not f or d.get("type") not in ("f", "fs"):
            continue
        r = d["rect"]
        a = r.width * r.height
        if a < 150:  # icons, dots, hairlines
            continue
        fills.append({"hex": rgb_to_hex([c * 255 for c in f[:3]]), "rect": [r.x0, r.y0, r.x1, r.y1],
                      "area_pct": round(100 * a / page_area, 2), "opacity": round(d.get("fill_opacity") or 1, 2)})
    return fills


def container_fill(fills, bbox, page_area):
    """Smallest filled shape (not page background) that contains bbox."""
    best = None
    for f in fills:
        if f["area_pct"] > 60 or f["opacity"] < 1:
            continue
        if rect_contains(f["rect"], bbox) and (best is None or area(f["rect"]) < area(best["rect"])):
            best = f
    return best


def digest_page(page, pno):
    W, H = page.rect.width, page.rect.height
    page_area = W * H
    fills = page_fills(page, page_area)
    d = page.get_text("dict")
    lines = []
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            txt = "".join(s["text"] for s in ln["spans"]).strip()
            if not txt:
                continue
            size = max(s["size"] for s in ln["spans"])
            lines.append({"text": txt, "bbox": list(ln["bbox"]), "size": round(size, 1)})
    # title = largest non-Arabic line in the top quarter of the page (page headers), else anywhere
    latin = [{**ln, "text": mask_arabic(ln["text"])[0].replace("⟨AR⟩", "").strip()} for ln in lines]
    latin = [ln for ln in latin if len(ln["text"]) > 1]
    top = [ln for ln in latin if ln["bbox"][1] < H * 0.25] or latin
    title = max(top, key=lambda ln: (ln["size"], -ln["bbox"][1]))["text"] if top else ""

    # colour mentions
    mentions = []
    for ln in lines:
        for kind, val, _ in find_values(ln["text"]):
            mentions.append({"kind": kind, "value": val, "bbox": ln["bbox"], "line": ln["text"]})

    # group mentions into swatch records: by container fill, else by column proximity
    groups = []
    for mt in sorted(mentions, key=lambda m: (round(m["bbox"][0] / 40), m["bbox"][1])):
        cont = container_fill(fills, mt["bbox"], page_area)
        key = tuple(round(v) for v in cont["rect"]) if cont else None
        g = next((g for g in groups if key and g["key"] == key), None)
        if g is None and not key:
            g = next((g for g in groups if g["key"] is None and abs(g["x0"] - mt["bbox"][0]) < 20
                      and 0 <= mt["bbox"][1] - g["y1"] < 30), None)
        if g is None:
            g = {"key": key, "x0": mt["bbox"][0], "y0": mt["bbox"][1], "y1": mt["bbox"][3], "items": [],
                 "swatch": cont["hex"] if cont else None, "rect": cont["rect"] if cont else None}
            groups.append(g)
        g["items"].append(mt)
        g["y1"] = max(g["y1"], mt["bbox"][3])

    mention_lines = {id(m["line"]) for m in mentions}
    records = []
    for g in groups:
        rec = {"page": pno}
        for it in g["items"]:
            rec.setdefault(it["kind"], it["value"])
        # name: Latin non-value line inside the swatch, else nearest line above in the same column
        if g["rect"]:
            cands = [ln for ln in lines if rect_contains(g["rect"], ln["bbox"]) and id(ln["text"]) not in mention_lines]
        else:
            cands = [ln for ln in lines if abs(ln["bbox"][0] - g["x0"]) < 30 and 0 < g["y0"] - ln["bbox"][3] < 50]
            cands.sort(key=lambda ln: g["y0"] - ln["bbox"][3])
        names = []
        for ln in cands:
            if next(find_values(ln["text"]), None):
                continue
            t, n_ar = mask_arabic(ln["text"])
            t = t.replace("⟨AR⟩", "").strip()
            if t and len(t.split()) <= 4:
                names.append(t)
            elif n_ar:
                rec["has_arabic_name"] = True
        if names:
            rec["name_candidates"] = names[:2]
        if g["swatch"]:
            rec["swatch_fill"] = g["swatch"]
        checks = []
        if "hex" in rec and "rgb" in rec and hex_to_rgb(rec["hex"]) != tuple(rec["rgb"]):
            checks.append(f"rgb {rec['rgb']} != hex {rec['hex']}")
        if "hex" in rec and g["swatch"] and rec["hex"] != g["swatch"]:
            checks.append(f"stated {rec['hex']} but swatch is filled {g['swatch']} (ΔE {delta_e(rec['hex'], g['swatch']):.1f})")
        if "hex" in rec and g["swatch"] and rec["hex"] == g["swatch"]:
            rec["verified_by_swatch"] = True
        if "cmyk" in rec and "hex" in rec:
            de = delta_e(rec["hex"], cmyk_to_hex(*rec["cmyk"]))
            if de > 35:
                checks.append(f"CMYK looks far from HEX (naive ΔE {de:.0f}); usually fine, CMYK is profile-dependent")
        if checks:
            rec["checks"] = checks
        rec["context"] = mask_arabic(" | ".join(it["line"] for it in g["items"]))[0][:160]
        records.append(rec)

    # swatches that carry no stated HEX (e.g. a colour whose HEX is printed elsewhere)
    stated = {r["hex"] for r in records if "hex" in r}
    unlabelled = []
    for f in fills:
        if f["area_pct"] > 60 or f["area_pct"] < 1 or f["opacity"] < 1:
            continue
        if any(delta_e(f["hex"], h) < 1 for h in stated) or f["hex"] in ("#FFFFFF",):
            continue
        inside = [mask_arabic(ln["text"])[0] for ln in lines if rect_contains(f["rect"], ln["bbox"])]
        inside = [t for t in inside if t.replace("⟨AR⟩", "").strip()]
        if inside and not any(u["hex"] == f["hex"] for u in unlabelled):
            unlabelled.append({"hex": f["hex"], "area_pct": f["area_pct"], "text_inside": " | ".join(inside)[:120]})

    full_text = "\n".join(ln["text"] for ln in lines)
    masked, n_ar = mask_arabic(full_text)
    img_cov = 0.0
    for info in page.get_image_info():
        img_cov += area(info["bbox"]) / page_area
    flags = []
    if len(full_text) < 30 and img_cov > 0.5:
        flags.append("image-only: no extractable text, read this page from its image")
    elif img_cov > 0.3:
        flags.append(f"large image ({img_cov:.0%} of page): check visually")
    if n_ar:
        flags.append(f"arabic: {n_ar} runs masked as ⟨AR⟩, read Arabic from the page image")

    # fills summary (distinct colours, total area)
    agg = {}
    for f in fills:
        if f["opacity"] < 1:
            continue
        agg[f["hex"]] = round(agg.get(f["hex"], 0) + f["area_pct"], 2)
    return {
        "page": pno, "title": title, "chars": len(full_text), "image_coverage": round(img_cov, 2),
        "flags": flags, "text": masked, "color_records": records, "unlabelled_swatches": unlabelled,
        "fills": dict(sorted(agg.items(), key=lambda kv: -kv[1])[:10]),
        "tinted_fills": sorted({f"{f['hex']}@{f['opacity']}" for f in fills if f["opacity"] < 1}),
    }


def cross_page_checks(pages):
    """Near-identical HEX values stated on different pages → probable conflict/typo."""
    seen = {}
    for p in pages:
        for r in p["color_records"]:
            if "hex" in r:
                seen.setdefault(r["hex"], []).append({"page": p["page"], "name": (r.get("name_candidates") or [""])[0],
                                                       "context": r["context"][:80]})
        for m in re.finditer(r"#([0-9A-F]{6})", p["text"]):  # hexes in prose (e.g. notes)
            h = "#" + m.group(1)
            if not any(x["page"] == p["page"] for x in seen.get(h, [])):
                i = p["text"].find(m.group(0))
                seen.setdefault(h, []).append({"page": p["page"], "name": "", "context": p["text"][max(0, i - 60):i + 20]})
    conflicts, hexes = [], sorted(seen)
    for i, a in enumerate(hexes):
        for b in hexes[i + 1:]:
            de = delta_e(a, b)
            if de < 6:
                conflicts.append({"values": [a, b], "delta_e": round(de, 2), "where": {a: seen[a], b: seen[b]},
                                  "hint": "near-identical colours: likely the same brand colour stated inconsistently"})
    return conflicts, {h: [x["page"] for x in v] for h, v in seen.items()}


def _font_name(doc, xref, basefont):
    """Real font name: BaseFont, else FontDescriptor/FontName (Type3 fonts hide it there)."""
    name = basefont
    if not name:
        fd = doc.xref_get_key(xref, "FontDescriptor")
        if fd[0] == "xref":
            fn = doc.xref_get_key(int(fd[1].split()[0]), "FontName")
            if fn[0] == "name":
                name = fn[1].lstrip("/")
    return re.sub(r"^[A-Z]{6}\+", "", name or "") or None


def pdf_fonts(doc):
    names = {}
    for pno in range(doc.page_count):
        for f in doc[pno].get_fonts():
            base = _font_name(doc, f[0], f[3])
            if base:
                names.setdefault(base, {"type": f[2], "pages": set()})["pages"].add(pno + 1)
    return [{"name": n, "type": v["type"], "pages": sorted(v["pages"])} for n, v in sorted(names.items())]


def render(doc, out_dir, dpi):
    from PIL import Image
    pages_dir = Path(out_dir) / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    thumbs = []
    for pno in range(doc.page_count):
        pix = doc[pno].get_pixmap(dpi=dpi)
        path = pages_dir / f"page-{pno + 1:02d}.png"
        pix.save(str(path))
        im = Image.open(path).convert("RGB")
        im.thumbnail((360, 360))
        thumbs.append(im)
    cols = 4
    tw = max(t.width for t in thumbs)
    th = max(t.height for t in thumbs) + 18
    rows = -(-len(thumbs) // cols)
    sheet = Image.new("RGB", (cols * (tw + 8) + 8, rows * (th + 8) + 8), "white")
    from PIL import ImageDraw
    dr = ImageDraw.Draw(sheet)
    for i, t in enumerate(thumbs):
        x, y = 8 + (i % cols) * (tw + 8), 8 + (i // cols) * (th + 8)
        sheet.paste(t, (x, y + 18))
        dr.text((x, y + 2), f"p{i + 1}", fill="black")
    sheet.save(pages_dir / "sheet.png")
    return str(pages_dir / "sheet.png")


def digest(pdf_path, out_dir, dpi=110, render_pages=True):
    import pymupdf
    doc = pymupdf.open(pdf_path)
    pages = [digest_page(doc[i], i + 1) for i in range(doc.page_count)]
    conflicts, hex_pages = cross_page_checks(pages)
    result = {
        "file": Path(pdf_path).name, "pages": doc.page_count,
        "page_size_pt": [round(doc[0].rect.width), round(doc[0].rect.height)],
        "metadata": {k: v for k, v in (doc.metadata or {}).items() if v},
        "embedded_fonts": pdf_fonts(doc),
        "embedded_fonts_note": "PDF font names often hide real weights (variable fonts, subsets); take weights from the text.",
        "hex_pages": hex_pages, "conflicts": conflicts, "page_data": pages,
    }
    if render_pages:
        result["sheet"] = render(doc, out_dir, dpi)
    write_json(Path(out_dir) / "pdf_digest.json", result)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    r = digest(a.pdf, a.out, a.dpi, not a.no_render)
    n_rec = sum(len(p["color_records"]) for p in r["page_data"])
    print(f"{r['file']}: {r['pages']} pages, {n_rec} colour records, {len(r['conflicts'])} possible conflicts")
    for p in r["page_data"]:
        if p["flags"]:
            print(f"  p{p['page']}: " + "; ".join(p["flags"]))
    print(json.dumps({"out": a.out}))


if __name__ == "__main__":
    main()
