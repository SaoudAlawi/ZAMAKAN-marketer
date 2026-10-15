"""Build the fictional Rawaq (رواق) logo set as outlined SVGs + PNGs.

Text is converted to vector outlines with HarfBuzz (correct Arabic shaping), the way
an agency delivers final logo files, so the logos do not depend on installed fonts.

Usage: python make_logos.py <out_dir>
"""
import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

HERE = Path(__file__).parent
FONTS = HERE / "../../../samples/rawaq/input/Fonts"

DATE_BROWN = "#4A2C21"
SAFFRON = "#E3A33B"
SAND = "#F3E7D3"


def text_path(text, font_file, size, wght=None, tracking=0.0, x=0.0, baseline=0.0):
    """Return (svg_path_d, advance_width) for text set at `size` px."""
    blob = hb.Blob.from_file_path(str(FONTS / font_file))
    face = hb.Face(blob)
    font = hb.Font(face)
    if wght is not None:
        font.set_variations({"wght": wght})
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    scale = size / face.upem
    pen = SVGPathPen(None)
    cursor = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        gx = x + (cursor + pos.x_offset) * scale
        gy = baseline - pos.y_offset * scale
        tpen = TransformPen(pen, (scale, 0, 0, -scale, gx, gy))
        font.draw_glyph_with_pen(info.codepoint, tpen)
        cursor += pos.x_advance + tracking * face.upem
    width = cursor * scale - tracking * size  # no trailing tracking
    return pen.getCommands(), width


def symbol_group(arch, bean, x=0, y=0, h=120):
    """The arch-and-bean symbol, native box 100x120, scaled to height h."""
    s = h / 120
    return f"""<g transform="translate({x:.2f},{y:.2f}) scale({s:.4f})">
  <path fill="{arch}" fill-rule="evenodd" d="M10,120 V50 A40,40 0 0 1 90,50 V120 Z M24,120 V52 A26,26 0 0 1 76,52 V120 Z"/>
  <path fill="{bean}" d="M48.5,70.2 A13,18 0 0 0 48.5,105.8 C54.5,96 42.5,80 48.5,70.2 Z"/>
  <path fill="{bean}" d="M51.5,70.2 C45.5,80 57.5,96 51.5,105.8 A13,18 0 0 0 51.5,70.2 Z"/>
</g>"""


def svg(w, h, body, bg=None):
    rect = f'<rect width="100%" height="100%" fill="{bg}"/>' if bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" '
            f'width="{w:.0f}" height="{h:.0f}">{rect}{body}</svg>\n')


def stacked(text_color, arch, bean):
    W = 360
    ar_d, ar_w = text_path("رواق", "ReemKufi[wght].ttf", 104, wght=700)
    en_d, en_w = text_path("RAWAQ", "PlayfairDisplay[wght].ttf", 30, wght=600, tracking=0.32)
    ar_d, _ = text_path("رواق", "ReemKufi[wght].ttf", 104, wght=700, x=(W - ar_w) / 2, baseline=262)
    en_d, _ = text_path("RAWAQ", "PlayfairDisplay[wght].ttf", 30, wght=600, tracking=0.32,
                        x=(W - en_w) / 2, baseline=318)
    body = symbol_group(arch, bean, x=(W - 100) / 2, y=24, h=120)
    body += f'<path fill="{text_color}" d="{ar_d}"/><path fill="{text_color}" d="{en_d}"/>'
    return W, 344, body


def horizontal(text_color, arch, bean):
    # Arabic-first: symbol on the right, wordmarks to its left, right-aligned.
    _, ar_w = text_path("رواق", "ReemKufi[wght].ttf", 84, wght=700)
    _, en_w = text_path("RAWAQ", "PlayfairDisplay[wght].ttf", 24, wght=600, tracking=0.32)
    pad, gap, sym_h = 24, 28, 120
    text_w = max(ar_w, en_w)
    W = pad + text_w + gap + 100 + pad
    right = pad + text_w
    ar_d, _ = text_path("رواق", "ReemKufi[wght].ttf", 84, wght=700, x=right - ar_w, baseline=100)
    en_d, _ = text_path("RAWAQ", "PlayfairDisplay[wght].ttf", 24, wght=600, tracking=0.32,
                        x=right - en_w, baseline=140)
    body = symbol_group(arch, bean, x=right + gap, y=pad, h=sym_h)
    body += f'<path fill="{text_color}" d="{ar_d}"/><path fill="{text_color}" d="{en_d}"/>'
    return W, sym_h + 2 * pad, body


def build(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "Rawaq_Logo_Primary_Stacked.svg": svg(*stacked(DATE_BROWN, DATE_BROWN, SAFFRON)),
        "Rawaq_Logo_Primary_Stacked_Reversed.svg": svg(*stacked(SAND, SAND, SAFFRON)),
        "Rawaq_Logo_Horizontal.svg": svg(*horizontal(DATE_BROWN, DATE_BROWN, SAFFRON)),
        "Rawaq_Logo_Mono_Black.svg": svg(*stacked("#000000", "#000000", "#000000")),
        "Rawaq_Symbol.svg": svg(120, 140, symbol_group(DATE_BROWN, SAFFRON, x=10, y=10)),
        "Rawaq_Symbol_Reversed.svg": svg(120, 140, symbol_group(SAND, SAFFRON, x=10, y=10)),
    }
    for name, content in files.items():
        (out / name).write_text(content, encoding="utf-8")
    return files


def rasterize(svg_dir: Path, names_bgs, scale=3):
    """Render selected SVGs to PNG with Chromium (transparent unless bg given)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = browser.new_page(device_scale_factor=scale)
        for name, png_name, bg in names_bgs:
            svg_text = (svg_dir / name).read_text(encoding="utf-8")
            page.set_content(f'<html><body style="margin:0;background:{bg or "transparent"}">'
                             f'<div id="l" style="display:inline-block;line-height:0">{svg_text}</div></body></html>')
            page.locator("#l").screenshot(path=str(svg_dir / png_name), omit_background=bg is None)
        browser.close()


if __name__ == "__main__":
    out = Path(sys.argv[1])
    build(out)
    rasterize(out, [
        ("Rawaq_Logo_Primary_Stacked.svg", "Rawaq_Logo_Primary_Stacked.png", None),
        ("Rawaq_Logo_Primary_Stacked_Reversed.svg", "Rawaq_Logo_Primary_Stacked_Reversed_on_DateBrown.png", DATE_BROWN),
        ("Rawaq_Logo_Horizontal.svg", "Rawaq_Logo_Horizontal.png", None),
        ("Rawaq_Symbol.svg", "Rawaq_Symbol.png", None),
    ])
    print("logos written to", out)
