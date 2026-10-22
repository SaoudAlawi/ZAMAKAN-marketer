#!/usr/bin/env python3
"""Analyse logo files and render one contact sheet for visual review.

Usage: python logos.py <logo files or dirs...> --out <work_dir> [--palette #HEX,#HEX,...]

Per file: format, size/aspect, orientation guess, colours used (SVG fills/strokes or
dominant PNG/JPG colours), background (transparent/opaque), colourway guess, warnings
(live <text> instead of outlines, embedded raster in SVG, low resolution).
Writes <work_dir>/logos.json and <work_dir>/logos/sheet.png (each logo on light and dark tiles).
"""
import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import delta_e, hex_to_rgb, launch_chromium, relative_luminance, rgb_to_hex, write_json  # noqa: E402

LOGO_EXT = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".pdf"}
NAMED = {"black": "#000000", "white": "#FFFFFF"}
HINTS = {
    "colorway": [("reversed", r"revers|white|neg|inverse|on[-_ ]?dark"), ("mono-dark", r"mono|black|1c|one[-_ ]?col"),
                 ("full-color", r"primary|full|colou?r|main")],
    "kind": [("symbol", r"symbol|icon|mark|monogram|avatar|favicon"), ("wordmark", r"wordmark|logotype|type"),
             ("lockup", r"logo|lockup|primary|horizontal|stacked|vertical")],
    "orientation": [("horizontal", r"horiz|landscape|wide|inline"), ("stacked", r"stack|vertical|portrait|centered")],
}


def norm_color(v):
    v = (v or "").strip()
    if v in NAMED:
        return NAMED[v]
    m = re.fullmatch(r"#([0-9a-fA-F]{3})", v)
    if m:
        return "#" + "".join(c * 2 for c in m.group(1)).upper()
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", v)
    if m:
        return "#" + m.group(1).upper()
    m = re.fullmatch(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", v)
    if m:
        return rgb_to_hex([int(x) for x in m.groups()])
    return None


def analyse_svg(path):
    tree = ET.parse(path)
    root = tree.getroot()
    vb = root.get("viewBox")
    if vb:
        _, _, w, h = (float(x) for x in re.split(r"[\s,]+", vb.strip()))
    else:
        w = float(re.sub(r"[^\d.]", "", root.get("width", "0")) or 0)
        h = float(re.sub(r"[^\d.]", "", root.get("height", "0")) or 0)
    colors, warnings, bg = {}, [], None
    n_text = n_image = n_shapes = 0
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag == "text":
            n_text += 1
        elif tag == "image":
            n_image += 1
        elif tag in ("path", "rect", "circle", "ellipse", "polygon", "polyline", "line"):
            n_shapes += 1
        style = dict(kv.split(":", 1) for kv in (el.get("style") or "").split(";") if ":" in kv)
        for attr in ("fill", "stroke"):
            c = norm_color(style.get(attr, el.get(attr)))
            if not c:
                continue
            # full-canvas rect = background, not artwork
            if tag == "rect" and attr == "fill" and el.get("width") in ("100%", str(int(w))) and el.get("height") in ("100%", str(int(h))):
                bg = c
                continue
            colors[c] = colors.get(c, 0) + 1
    if n_text:
        warnings.append(f"{n_text} live <text> element(s): fonts may not render; ask for outlined artwork")
    if n_image:
        warnings.append("embedded raster image inside SVG: not true vector")
    return {"width": round(w, 1), "height": round(h, 1), "colors": sorted(colors, key=lambda c: -colors[c]),
            "background": bg or "transparent", "shapes": n_shapes, "warnings": warnings}


def analyse_raster(path):
    from PIL import Image
    im = Image.open(path)
    w, h = im.size
    warnings = []
    rgba = im.convert("RGBA")
    corners = [rgba.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    transparent = all(c[3] < 16 for c in corners)
    bg = "transparent" if transparent else rgb_to_hex(corners[0][:3])
    small = rgba.copy()
    small.thumbnail((640, 640))
    data = small.get_flattened_data() if hasattr(small, "get_flattened_data") else small.getdata()
    px = [p for p in data if p[3] > 200]
    if not transparent:
        bgc = hex_to_rgb(bg)
        px = [p for p in px if sum(abs(a - b) for a, b in zip(p[:3], bgc)) > 30]
    colors = []
    if px:
        q = Image.new("RGB", (len(px), 1))
        q.putdata([p[:3] for p in px])
        pal = q.quantize(colors=12, method=Image.Quantize.MEDIANCUT)
        palette = pal.getpalette()
        raw = [(n / len(px), rgb_to_hex(palette[i * 3: i * 3 + 3])) for n, i in sorted(pal.getcolors(), reverse=True)]
        # merge anti-aliasing near-duplicates into the dominant neighbour (ΔE < 6)
        merged = []
        for share, hx in raw:
            near = next((m for m in merged if delta_e(m["hex"], hx) < 6), None)
            if near:
                near["share"] += share
            else:
                merged.append({"hex": hx, "share": share})
        # drop edge blends: small clusters lying between two bigger colours
        anchors = [] if transparent else [{"hex": bg, "share": 1.0}]

        def is_blend(c):
            big = [m for m in merged if m["share"] > c["share"] * 3] + anchors
            return any(delta_e(a["hex"], c["hex"]) + delta_e(c["hex"], b["hex"]) < delta_e(a["hex"], b["hex"]) * 1.15
                       for a in big for b in big if a is not b)
        colors = [{"hex": m["hex"], "share": round(m["share"], 3)} for m in merged
                  if m["share"] >= 0.01 and not is_blend(m)]
    if max(w, h) < 500:
        warnings.append(f"low resolution ({w}×{h}px): fine for digital thumbnails only")
    return {"width": w, "height": h, "colors": [c["hex"] for c in colors], "color_shares": colors,
            "background": bg, "warnings": warnings}


def guess(name, key):
    for label, rx in HINTS[key]:
        if re.search(rx, name, re.I):
            return label
    return None


def colorway(colors, bg):
    if not colors:
        return None
    lums = [relative_luminance(hex_to_rgb(c)) for c in colors]
    if len(colors) == 1 or all(delta_e(colors[0], c) < 8 for c in colors):
        return "mono-light" if lums[0] > 0.6 else "mono-dark"
    if all(l > 0.35 for l in lums) or (bg != "transparent" and relative_luminance(hex_to_rgb(bg)) < 0.2):
        return "reversed"
    return "full-color"


def snap(colors, palette):
    """Map measured colours to the nearest palette colour (ΔE<6); raster AA makes exact matches rare."""
    out = []
    for c in colors:
        best = min(palette, key=lambda p: delta_e(c, p)) if palette else None
        out.append({"measured": c, "palette": best if best and delta_e(c, best) < 6 else None})
    return out


def _orientation(ar, kind):
    if ar >= 1.6:
        return "horizontal"
    if kind == "symbol":
        return "square"
    return "stacked" if ar <= 1.3 else "square"


def analyse(path, palette=()):
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".svg":
        info = analyse_svg(p)
    elif ext in (".png", ".jpg", ".jpeg", ".webp"):
        info = analyse_raster(p)
    else:
        return {"file": str(p), "format": ext[1:], "warnings": ["not analysed (render the PDF page instead)"]}
    w, h = info["width"], info["height"]
    ar = w / h if h else 0
    info.update({
        "file": str(p), "format": ext[1:], "aspect": round(ar, 2),
        "orientation": guess(p.stem, "orientation") or _orientation(ar, guess(p.stem, "kind")),
        "kind_hint": guess(p.stem, "kind"),
        "colorway": colorway(info["colors"], info["background"]),
        "colorway_hint_from_name": guess(p.stem, "colorway"),
    })
    if palette:
        info["palette_match"] = snap(info["colors"], palette)
    if info["colorway_hint_from_name"] and info["colorway"] and \
            info["colorway_hint_from_name"].split("-")[0] != info["colorway"].split("-")[0]:
        info["warnings"].append(f"name suggests {info['colorway_hint_from_name']} but colours look {info['colorway']}")
    return info


def contact_sheet(files, out_png):
    """Each logo on a light and a dark tile, labelled, in one PNG."""
    from playwright.sync_api import sync_playwright
    cells = "".join(
        f'<div class="c"><div class="t" style="background:#fff"><img src="file://{Path(f).resolve()}"></div>'
        f'<div class="t" style="background:#2b2b2b"><img src="file://{Path(f).resolve()}"></div>'
        f'<div class="n">{Path(f).name}</div></div>' for f in files)
    html = ("<html><body style='margin:0;font:12px sans-serif;background:#eee'><style>"
            ".g{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:10px;width:1200px}"
            ".c{background:#fff;padding:6px;display:grid;grid-template-columns:1fr 1fr;gap:4px}"
            ".t{height:120px;display:flex;align-items:center;justify-content:center;border:1px solid #ddd}"
            ".t img{max-width:90%;max-height:100px}.n{grid-column:1/3;word-break:break-all}</style>"
            f"<div class='g' id='g'>{cells}</div></body></html>")
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(out_png).with_suffix(".html")
    tmp.write_text(html, encoding="utf-8")
    with sync_playwright() as pw:
        b = launch_chromium(pw)
        page = b.new_page(viewport={"width": 1220, "height": 800})
        page.goto(f"file://{tmp.resolve()}")
        page.wait_for_timeout(200)
        page.locator("#g").screenshot(path=str(out_png))
        b.close()
    tmp.unlink()
    return str(out_png)


def run(paths, out_dir, palette=(), render=True):
    files = []
    for p in map(Path, paths):
        files += sorted(f for f in p.rglob("*") if f.suffix.lower() in LOGO_EXT) if p.is_dir() else [p]
    logos = [analyse(f, palette) for f in files]
    result = {"logos": logos}
    if render and files:
        try:
            result["sheet"] = contact_sheet([f for f in files if f.suffix.lower() != ".pdf"],
                                            Path(out_dir) / "logos" / "sheet.png")
        except Exception as e:  # noqa: BLE001 - sheet is a convenience, never block extraction
            result["sheet_error"] = str(e)[:200]
    write_json(Path(out_dir) / "logos.json", result)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--palette", default="", help="comma-separated brand HEX values to match against")
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    pal = [h.strip().upper() for h in a.palette.split(",") if h.strip()]
    r = run(a.paths, a.out, pal, not a.no_render)
    for lg in r["logos"]:
        print(f"{Path(lg['file']).name}: {lg.get('orientation')}, {lg.get('colorway')}, colours {lg.get('colors')}, "
              f"bg {lg.get('background')}" + (f"  ⚠ {'; '.join(lg['warnings'])}" if lg.get("warnings") else ""))
    print("sheet:", r.get("sheet") or r.get("sheet_error"))


if __name__ == "__main__":
    main()
