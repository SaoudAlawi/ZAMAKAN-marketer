#!/usr/bin/env python3
"""Turn a DESIGN.md (Google Stitch format) into a theme for boards and decks.

Usage: python theme.py <source> [--client-dir clients/<slug>]      # prints the resolved theme
Sources:
  zamakan            the ZAMAKAN house style (assets/zamakan.DESIGN.md), the default
  client             clients/<slug>/design-system/DESIGN.md (made by zamakan-design-system)
  awesome:<name>     any brand in github.com/VoltAgent/awesome-design-md (MIT), e.g. awesome:nike
  <path>             any DESIGN.md file
Resolution order in build_outputs.py: --design if given, else the client's DESIGN.md if it exists, else zamakan.

Colours are read from the YAML front matter with fallbacks across naming styles (canvas/background/surface,
ink/on-surface, primary/accent…); prose-only files fall back to the hex codes in the text, picked by luminance and
saturation. Text/background contrast is enforced (WCAG AA). Arabic fonts come from `ar-*` typography tokens
when present (our design-system export), else IBM Plex Sans Arabic.
"""
import argparse
import colorsys
import json
import os
import re
import urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
HOUSE = SKILL / "assets" / "zamakan.DESIGN.md"
AWESOME = "https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/{name}/DESIGN.md"
HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def lum(h):
    def c(v):
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (c(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def sat(h):
    return colorsys.rgb_to_hls(*_rgb(h))[2]


def mix(a, b, t):
    ra, rb = _rgb(a), _rgb(b)
    return "#" + "".join(f"{round((x * (1 - t) + y * t) * 255):02X}" for x, y in zip(ra, rb))


def load_text(source, client_dir=None):
    if source in (None, "", "zamakan"):
        return HOUSE.read_text(encoding="utf-8"), "ZAMAKAN house style", str(HOUSE)
    if source == "client":
        p = Path(client_dir or ".") / "design-system" / "DESIGN.md"
        return p.read_text(encoding="utf-8"), "client design system", str(p)
    if source.startswith("awesome:"):
        name = source.split(":", 1)[1].strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9.\-]*", name):
            raise ValueError(f"not an awesome-design-md name: {name!r} (see github.com/VoltAgent/awesome-design-md)")
        root = Path(os.environ.get("ZAMAKAN_SCOUT_CACHE") or Path.home() / ".cache" / "zamakan-scout")
        cache = root / "awesome-design-md" / f"{name}.md"
        if not cache.exists():
            req = urllib.request.Request(AWESOME.format(name=name), headers={"User-Agent": "zamakan-scout"})
            with urllib.request.urlopen(req, timeout=20) as r:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(r.read())
        return cache.read_text(encoding="utf-8"), f"{name} (awesome-design-md, MIT)", AWESOME.format(name=name)
    p = Path(source)
    return p.read_text(encoding="utf-8"), p.parent.name or p.name, str(p)


def front_matter(text):
    """YAML front matter as a dict. Some upstream files have one malformed line (an unquoted description with a
    colon), so on failure each top-level key is parsed on its own and the broken ones are skipped."""
    import yaml
    if not text.startswith("---"):
        return {}
    block = text.split("---", 2)[1]
    try:
        fm = yaml.safe_load(block)
        return fm if isinstance(fm, dict) else {}
    except yaml.YAMLError:
        pass
    fm = {}
    for chunk in re.split(r"\n(?=[^\s#])", block.strip("\n")):
        try:
            d = yaml.safe_load(chunk)
        except yaml.YAMLError:
            continue
        if isinstance(d, dict):
            fm.update(d)
    return fm


def prose_fonts(text):
    """Font families from a prose-only DESIGN.md: the first `backticked` family under a 'Font Famil…' heading;
    a line labelled Title/Display/Headline sets the display face."""
    m = re.search(r"^#+ *Font Famil[^\n]*\n((?:(?!#).*\n){0,8})", text, re.M | re.I)
    if not m:
        return None, None
    body = display = None
    for line in m.group(1).splitlines():
        f = re.search(r"`([^`]+)`", line)
        if not f or re.search(r"secondary|fallback|loading|mono|code", line.split("`")[0], re.I):
            continue
        fam = _first_family(f.group(1))
        if re.search(r"title|display|headline", line, re.I) and not display:
            display = fam
        elif not body:
            body = fam
    return display or body, body or display


def _first_family(v):
    fam = str(v or "").split(",")[0].strip().strip("'\"")
    return fam or None


def resolve(colors, all_colors):
    def pick(*names):
        for n in names:
            v = colors.get(n)
            if isinstance(v, str) and v.startswith("{colors."):
                v = colors.get(v[8:-1])
            if isinstance(v, str) and HEX.fullmatch(v.strip()):
                return v.strip().upper()
        return None
    pool = sorted({c.upper() for c in all_colors})
    if not pool:
        pool = ["#FFFFFF", "#111111", "#2F6F62"]
    bg = pick("canvas", "background", "surface", "canvas-soft") or max(pool, key=lum)
    ink = pick("ink", "on-surface", "on-background", "body-strong", "text", "charcoal") or min(pool, key=lum)
    if contrast(ink, bg) < 4.5:
        ink = "#111111" if lum(bg) > 0.4 else "#F5F5F5"
    primary = pick("primary")
    chromatic = [c for c in pool if sat(c) > 0.25 and 0.03 < lum(c) < 0.7]
    if primary and sat(primary) >= 0.2 and lum(primary) > 0.03:  # a near-black "primary" is ink, not an accent
        accent = primary
    else:
        accent = pick("tertiary", "accent", "brand", "link", "secondary") or (max(chromatic, key=sat) if chromatic else primary or "#2F6F62")
        if sat(accent) < 0.2 and chromatic:
            accent = max(chromatic, key=sat)
    accent_text = accent  # links and labels: nudged toward ink until readable (fills keep the brand colour)
    for _ in range(8):
        if contrast(accent_text, bg) >= 4.5:
            break
        accent_text = mix(accent_text, ink, 0.2)
    else:
        accent_text = ink
    on_accent = "#FFFFFF" if contrast("#FFFFFF", accent) >= contrast("#111111", accent) else "#111111"
    panel = pick("surface-card", "surface", "surface-soft", "canvas-soft", "surface-container") or mix(bg, "#FFFFFF", 0.6)
    if panel == bg:
        panel = mix(bg, "#FFFFFF" if lum(bg) < 0.9 else "#000000", 0.04)
    if contrast(ink, panel) < 4.5:
        panel = mix(bg, ink, 0.05)
    muted = pick("muted", "mute", "body", "on-surface-variant", "slate", "stone", "ash") or mix(ink, bg, 0.4)
    if contrast(muted, bg) < 4.5 or contrast(muted, panel) < 4.5:
        muted = mix(ink, bg, 0.3)
    line = pick("hairline", "outline-variant", "outline", "hairline-soft", "border", "divider") or mix(ink, bg, 0.85)
    if contrast(line, bg) > 4 or contrast(line, bg) < 1.08:
        line = mix(ink, bg, 0.82)
    dark = pick("surface-dark", "inverse-surface", "ink-deep") or (primary if primary and lum(primary) < 0.08 else ink)
    if lum(dark) > 0.2:  # the dark band (deck covers) must be dark; on dark canvases reuse the canvas
        dark = bg if lum(bg) < 0.2 else mix(ink, "#000000", 0.3)
    on_dark = pick("on-dark", "inverse-on-surface") or "#FFFFFF"
    if contrast(on_dark, dark) < 4.5:
        on_dark = "#FFFFFF" if contrast("#FFFFFF", dark) >= contrast("#111111", dark) else "#111111"
    secondary = [c for c in chromatic if c not in (accent,)][:3]
    rings = (secondary + [mix(accent, ink, 0.45), mix(accent, "#7F7F7F", 0.5), mix(accent, bg, 0.35)])[:3]
    return {"bg": bg, "panel": panel, "ink": ink, "muted": muted, "line": line, "accent": accent, "accent_text": accent_text,
            "on_accent": on_accent,
            "dark": dark, "on_dark": on_dark, "chip": mix(bg, ink, 0.07),
            "ring": {"direct": accent, "category": rings[0], "adjacent": rings[1], "wildcard": rings[2]},
            "ring_on": {k: ("#FFFFFF" if contrast("#FFFFFF", c) >= contrast("#111111", c) else "#111111")
                        for k, c in zip(("direct", "category", "adjacent", "wildcard"), [accent] + rings)}}


def load(source=None, client_dir=None):
    text, label, origin = load_text(source, client_dir)
    fm = front_matter(text)
    colors = fm.get("colors") or {}
    all_hex = [v for v in colors.values() if isinstance(v, str) and HEX.fullmatch(v.strip())] or HEX.findall(text)
    theme = resolve(colors, all_hex)
    typo = fm.get("typography") or {}

    def fam(prefixes, arabic=False):
        for k, v in typo.items():
            if isinstance(v, dict) and k.startswith("ar-") == arabic and k.removeprefix("ar-").startswith(prefixes):
                f = _first_family(v.get("fontFamily"))
                if f:
                    return f
        return None
    p_disp, p_body = (None, None) if typo else prose_fonts(text)
    disp_w = next((v.get("fontWeight") for k, v in typo.items() if isinstance(v, dict) and not k.startswith("ar-")
                   and k.startswith(("display", "headline", "heading")) and v.get("fontWeight")), 600)
    theme.update(
        display_font=fam(("display", "headline", "heading", "title")) or p_disp or "Instrument Serif",
        body_font=fam(("body",)) or p_body or "IBM Plex Sans",
        ar_display_font=fam(("headline", "display", "heading"), arabic=True) or "IBM Plex Sans Arabic",
        ar_body_font=fam(("body",), arabic=True) or "IBM Plex Sans Arabic",
        display_weight=int(disp_w) if str(disp_w).isdigit() else 600,
        name=re.sub(r"[-\s](design[-\s])?analysis$", "", str(fm.get("name") or label), flags=re.I), label=label, origin=origin)
    return theme


SERIF = re.compile(r"serif(?!.*sans)|editorial|georgia|times|copernicus|lander|garamond|caslon|tiempos|domaine|playfair|fraunces", re.I)


def stack(family, arabic=None):
    """CSS font stack: the brand family first (it renders where installed or on Google Fonts), then a sensible fallback."""
    generic = "Georgia,serif" if SERIF.search(family) and not re.search(r"sans", family, re.I) else "system-ui,sans-serif"
    return ",".join(f"'{f}'" for f in dict.fromkeys(x for x in (family, arabic) if x)) + "," + generic


def font_links(theme):
    """One <link> per family: an unknown family must not break the others (Google returns 400 for the whole URL)."""
    fams = dict.fromkeys([theme["display_font"], theme["body_font"], theme["ar_display_font"], theme["ar_body_font"]])
    return "".join(f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={f.replace(" ", "+")}:wght@400;600&display=swap">'
                   for f in fams if f)


def find_client_design(out_dir):
    """clients/<slug>/design-system/DESIGN.md above an output folder (clients/<slug>/jobs/<job>/...), if any."""
    for p in [Path(out_dir).resolve(), *Path(out_dir).resolve().parents]:
        f = p / "design-system" / "DESIGN.md"
        if f.exists():
            return f
        if p.parent.name == "clients":
            break
    return None


def choose(design=None, out_dir=None):
    """--design wins; else the client's own DESIGN.md (found from the output folder); else the house style."""
    if design:
        return load(design)
    f = find_client_design(out_dir) if out_dir else None
    return load(str(f)) if f else load("zamakan")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", default="zamakan")
    ap.add_argument("--client-dir")
    a = ap.parse_args()
    print(json.dumps(load(a.source, a.client_dir), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
