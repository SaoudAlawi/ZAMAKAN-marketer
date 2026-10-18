#!/usr/bin/env python3
"""The brand kit a scout board/deck is dressed in: colours, fonts, logos and graphic elements.

Usage: python brandkit.py [--design <source>] [--out <job_dir>]      # prints the resolved kit

Sources, in priority order (see build_outputs.py):
  --design <client design-system dir | DESIGN.md | zamakan | awesome:<name>>
  the client's design system found above --out (clients/<slug>/design-system/, made by zamakan-design-system)
  the ZAMAKAN house style
From a client design system the kit reads the full feature-1 output, not just DESIGN.md:
  colours from spec.json roles (background, surface, text-primary, text-heading, text-inverse, brand, accent…),
  logos from manifest.json (the variant approved for each background), the client's own font files,
  the corner radius for panels, shadows, divider style, and graphic elements (e.g. an arch frame).
Assets the design system lists as missing are reported, never invented.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import theme as T  # noqa: E402

WEIGHT_NAMES = {"thin": 100, "extralight": 200, "light": 300, "regular": 400, "book": 400, "medium": 500,
                "semibold": 600, "bold": 700, "extrabold": 800, "black": 900}


def find_design_system(out_dir):
    f = T.find_client_design(out_dir) if out_dir else None
    return f.parent if f else None


def _role_colors(spec):
    hexes = {c["id"]: c["hex"].upper() for c in spec.get("colors", [])}
    roles = {r["role"]: hexes.get(r["color"]) for r in spec.get("color_roles", []) if hexes.get(r["color"])}
    m = {"canvas": "background", "surface-card": "surface", "ink": "text-primary", "primary": "brand",
         "tertiary": "accent", "link": "text-link", "surface-dark": "background-inverse", "on-dark": "text-inverse",
         "hairline": "divider", "border": "border", "muted": "text-secondary"}
    colors = {k: roles[v] for k, v in m.items() if v in roles}
    if "surface-dark" not in colors:  # the darkest brand colour carries covers
        dark = [h for h in hexes.values() if T.lum(h) < 0.08 and T.sat(h) > 0.1]
        if dark:
            colors["surface-dark"] = min(dark, key=T.lum)
    order = sorted(hexes, key=lambda i: -(spec.get("color_proportions_pct") or {}).get(i, 0))
    return colors, roles, [hexes[i] for i in order], hexes


def _weight_of(path, weights):
    stem = Path(path).stem.lower().replace("-", "").replace("_", "")
    if "[" in Path(path).name and "wght" in Path(path).name:
        return f"{min(weights or [100])} {max(weights or [900])}" if weights else "100 900"
    for name, w in sorted(WEIGHT_NAMES.items(), key=lambda kv: -len(kv[0])):
        if stem.endswith(name):
            return str(w)
    return "400"


def _pick_logo(manifest, bg_id, prefer):
    ids = (manifest.get("logo_for_background") or {}).get(bg_id, [])
    logos = {l["id"]: l for l in manifest.get("logos", [])}
    cands = [logos[i] for i in ids if i in logos]
    for orient in prefer:
        for l in cands:
            if l.get("orientation") == orient:
                return l
    return cands[0] if cands else None


def _file(ds, logo, ext):
    for f in (logo or {}).get("files", []):
        if f.lower().endswith(ext) and (ds / f).exists():
            return ds / f
    return None


def from_design_system(ds):
    ds = Path(ds)
    spec = json.loads((ds / "spec.json").read_text(encoding="utf-8"))
    manifest = json.loads((ds / "manifest.json").read_text(encoding="utf-8")) if (ds / "manifest.json").exists() else {}
    colors, roles, palette, hexes = _role_colors(spec)
    th = T.resolve(colors, palette)
    # fonts: by role and script from the spec, files from the manifest
    fonts = manifest.get("fonts") or []
    def fam(script, role):
        return next((f["family"] for f in fonts if f.get("script") == script and f.get("role") == role), None)
    th.update(display_font=fam("latin", "display") or fam("latin", "text") or "Georgia",
              body_font=fam("latin", "text") or fam("latin", "display") or "Arial",
              ar_display_font=fam("arabic", "display") or fam("arabic", "text") or "IBM Plex Sans Arabic",
              ar_body_font=fam("arabic", "text") or fam("arabic", "display") or "IBM Plex Sans Arabic")
    disp_w = [s.get("weight") for s in spec.get("type_scale", []) if s.get("script") == "latin" and s.get("level") in ("display", "h1")]
    th["display_weight"] = disp_w[0] if disp_w else 600
    heading = roles.get("text-heading")
    th["heading"] = heading if heading and T.contrast(heading, th["bg"]) >= 4.5 else th["ink"]
    client = spec.get("client", {})
    th.update(name=client.get("name") or ds.parent.name, label="client design system", origin=str(ds / "spec.json"))
    # covers use a dark brand colour the reversed logo is approved on (largest share of the palette first)
    props = spec.get("color_proportions_pct") or {}
    approved_dark = sorted((i for i in (manifest.get("logo_for_background") or {}) if i in hexes and T.lum(hexes[i]) < 0.2),
                           key=lambda i: -props.get(i, 0))
    if approved_dark:
        th["dark"] = hexes[approved_dark[0]]
        inv = roles.get("text-inverse")
        th["on_dark"] = inv if inv and T.contrast(inv, th["dark"]) >= 4.5 else (
            "#FFFFFF" if T.contrast("#FFFFFF", th["dark"]) >= T.contrast("#111111", th["dark"]) else "#111111")
    # logos: the variant approved for the background it sits on
    rev = {v: k for k, v in hexes.items()}
    bg_id, dark_id = rev.get(th["bg"]), rev.get(th["dark"])
    on_light = _pick_logo(manifest, bg_id, ("horizontal", "stacked", "square"))
    on_dark = _pick_logo(manifest, dark_id, ("stacked", "horizontal", "square"))
    mark_light = _pick_logo(manifest, bg_id, ("square",))
    mark_dark = _pick_logo(manifest, dark_id, ("square",))
    logos = {}
    for key, l in (("on_light", on_light), ("on_dark", on_dark), ("mark_light", mark_light), ("mark_dark", mark_dark)):
        if l:
            logos[key] = {"id": l["id"], "svg": _file(ds, l, ".svg"), "png": _file(ds, l, ".png")}
    font_files = []
    for f in fonts:
        for path in f.get("files", []):
            if (ds / path).exists():
                font_files.append({"family": f["family"], "path": ds / path, "weight": _weight_of(path, f.get("weights")),
                                   "script": f.get("script")})
    # shapes and elements
    radii = spec.get("radii", [])
    panel_r = next((r["value"] for r in radii if re.search(r"panel|card", r.get("usage", ""), re.I)
                    and re.fullmatch(r"\d+(px)?", str(r["value"]).strip())), None)
    elements = {e["id"]: e for e in spec.get("graphic_elements", [])}
    arch = next((e for e in elements.values() if "arch" in (e["id"] + e.get("name", "")).lower()), None)
    divider = next((b["value"] for b in spec.get("borders", []) if re.search(r"divider|rule", b.get("usage", "") + b["id"], re.I)), None)
    shadow = next((s["value"] for s in spec.get("shadows", [])), None)
    kit = {"theme": th, "source": "client", "client_name": client.get("name"), "client_name_ar": client.get("name_ar"),
           "logos": logos, "font_files": font_files,
           "radius": (panel_r if str(panel_r).endswith("px") else f"{panel_r}px") if panel_r is not None else "6px",
           "arch": bool(arch), "arch_colors": [hexes[c] for c in (arch or {}).get("colors", []) if c in hexes],
           "divider": divider, "shadow": shadow,
           "arabic_leads": any(re.search(r"arabic leads", r.get("text", ""), re.I) for r in spec.get("type_rules", [])),
           "missing_assets": [m["asset"] for m in manifest.get("missing_assets", spec.get("missing_assets", []))],
           "proposed_notes": [], "rules": [r["text"] for r in spec.get("color_rules", []) if r.get("kind") == "dont"]}
    if not logos.get("on_dark") and (logos.get("on_light") or {}).get("png"):
        panel = logo_panel(logos["on_light"]["png"], ds / "assets" / f"_panel-{logos['on_light']['id']}.png")
        logos["on_dark"] = {"id": logos["on_light"]["id"] + "-panel", "svg": None, "png": str(panel)}
        kit["proposed_notes"].append(f"no logo variant is approved on the cover colour {th['dark']}; the cover uses the light logo on a white panel")
    return kit


def logo_panel(png, dst):
    """The approved light-background logo on a white rounded panel, for dark covers when no reversed logo exists
    (the logo itself is untouched; nothing is redrawn)."""
    from PIL import Image, ImageDraw
    dst = Path(dst)
    if dst.exists() and dst.stat().st_mtime >= Path(png).stat().st_mtime:
        return dst
    im = Image.open(png).convert("RGBA")
    pad = max(im.height // 4, 8)
    panel = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle((0, 0, panel.width - 1, panel.height - 1), radius=pad, fill=(255, 255, 255, 255))
    panel.alpha_composite(im, (pad, pad))
    dst.parent.mkdir(parents=True, exist_ok=True)
    panel.save(dst)
    return dst


def load_kit(design=None, out_dir=None):
    src = design
    if src and Path(src).is_dir() and (Path(src) / "spec.json").exists():
        return from_design_system(src)
    if src and Path(src).name == "DESIGN.md" and (Path(src).parent / "spec.json").exists():
        return from_design_system(Path(src).parent)
    if not src:
        ds = find_design_system(out_dir)
        if ds and (ds / "spec.json").exists():
            return from_design_system(ds)
    th = T.choose(src, out_dir)
    th.setdefault("heading", th["ink"])
    house = th["origin"] == str(T.HOUSE)
    fonts_dir = T.HOUSE.parent / "fonts"
    house_fonts = [{"family": fam, "path": fonts_dir / f, "weight": w, "script": sc} for fam, f, w, sc in (
        ("Instrument Serif", "InstrumentSerif-Regular.ttf", "400", "latin"), ("IBM Plex Sans", "IBMPlexSans[wdth,wght].ttf", "100 700", "latin"),
        ("IBM Plex Sans Arabic", "IBMPlexSansArabic-Regular.ttf", "400", "arabic"), ("IBM Plex Sans Arabic", "IBMPlexSansArabic-Bold.ttf", "700", "arabic"),
        ("Reem Kufi", "ReemKufi[wght].ttf", "400 700", "arabic")) if (fonts_dir / f).exists()] if house else []
    return {"theme": th, "source": "house" if house else ("awesome" if "awesome-design-md" in th["origin"] else "design-md"),
            "client_name": None, "client_name_ar": None, "logos": {}, "font_files": house_fonts, "radius": "6px", "arch": False,
            "arch_colors": [], "divider": None, "shadow": None, "arabic_leads": False, "missing_assets": [],
            "proposed_notes": [], "rules": []}


def with_client_logo(kit, logo, out_dir, name=None):
    """House style (or any look) plus the client's own logo file, for clients without a design system yet.
    The logo isn't approved on the dark cover, so it sits on a white panel there (a PNG made here, for board and deck)."""
    logo = Path(logo)
    dst = logo_panel(logo, Path(out_dir) / "thumbs" / f"_logo-panel-{logo.stem}.png")
    svg = str(logo) if logo.suffix == ".svg" else None
    kit["logos"] = {"on_light": {"id": "client", "svg": svg, "png": str(logo)}, "mark_light": {"id": "client", "svg": svg, "png": str(logo)},
                    "on_dark": {"id": "client-panel", "svg": None, "png": str(dst)}}
    kit["client_name"] = kit.get("client_name") or name
    kit["proposed_notes"].append(f"client logo from {logo.name}, shown on a white panel on dark backgrounds (no design system yet)")
    return kit


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--design")
    ap.add_argument("--out")
    a = ap.parse_args()
    print(json.dumps(load_kit(a.design, a.out), indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
