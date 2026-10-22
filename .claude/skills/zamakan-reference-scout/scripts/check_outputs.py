#!/usr/bin/env python3
"""Beauty and brand check for a built board/deck, before anything is delivered.

Usage: python check_outputs.py <job_dir> [--json]

Board (board.html, rendered in Chromium at desktop 1280px and phone 390px):
  - no sideways scrolling; no broken images; no clipped text
  - text contrast ≥ 4.5:1 (3:1 for large text) against the real background behind it
  - the brand fonts actually loaded (the client's own files, not a fallback)
  - a logo on the cover; Arabic set right-to-left with no letter-spacing
Deck (deck.pptx):
  - every shape inside the slide; no text box whose text cannot fit even at its smallest size
  - logo on the cover; fonts used by the deck are installed for the PDF render
Writes <job_dir>/check/ with board-desktop.png, board-phone.png and deck-sheet.png (all pages on one sheet):
LOOK AT THEM before delivering. Exit code 1 if any error.
"""
import argparse
import io
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

JS_AUDIT = r"""
(brandFonts) => {
  const out = {errors: [], warnings: [], info: {}};
  const doc = document.documentElement;
  if (doc.scrollWidth > window.innerWidth + 1) out.errors.push(`page scrolls sideways: ${doc.scrollWidth}px wide in a ${window.innerWidth}px window`);
  const imgs = [...document.images];
  const broken = imgs.filter(i => i.complete && i.naturalWidth === 0);
  if (broken.length) out.errors.push(`${broken.length} broken image(s): ${broken.slice(0,3).map(i=>i.alt).join('; ')}`);
  out.info.images = imgs.length;
  const sel = 'h1,h2,h3,h4,p,li,a,dt,dd,td,th,.chip,.badge,.eyebrow,.code,.stat span';
  const clipped = [];
  for (const el of document.querySelectorAll(sel)) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || el.closest('[hidden]')) continue;
    if (el.scrollWidth > el.clientWidth + 2 && cs.overflow !== 'visible' && cs.overflowX !== 'visible') clipped.push(el.textContent.trim().slice(0,40));
  }
  if (clipped.length) out.errors.push(`clipped text: ${clipped.slice(0,4).join(' | ')}`);
  const rgb = s => (s.match(/[\d.]+/g) || []).map(Number);
  const L = c => { const f = v => { v /= 255; return v <= 0.04045 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); };
                   return 0.2126*f(c[0]) + 0.7152*f(c[1]) + 0.0722*f(c[2]); };
  const ratio = (a, b) => { const x = L(a), y = L(b); return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05); };
  const bgOf = el => { for (let e = el; e; e = e.parentElement) { const cs = getComputedStyle(e);
      if (cs.backgroundImage !== 'none' && e.tagName !== 'BODY') return null;
      const c = rgb(cs.backgroundColor); if (c.length >= 3 && (c.length < 4 || c[3] > 0.9)) return c; } return [255,255,255]; };
  const low = []; let checked = 0;
  for (const el of document.querySelectorAll('body *')) {
    if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none' || el.closest('[hidden]')) continue;
    if (el.closest('.img,.pics,.hero') && el.className === 'code') { /* label on its own chip */ }
    const bg = bgOf(el); if (!bg) continue;
    const fg = rgb(cs.color); const size = parseFloat(cs.fontSize); const bold = parseInt(cs.fontWeight) >= 600;
    const need = (size >= 24 || (size >= 18.6 && bold)) ? 3 : 4.5; checked++;
    const r = ratio(fg, bg); if (r < need) low.push(`${el.textContent.trim().slice(0,30)} (${r.toFixed(1)}:1)`);
  }
  out.info.text_checked = checked;
  if (low.length) out.errors.push(`low contrast text: ${low.slice(0,4).join(' | ')}${low.length > 4 ? ` (+${low.length-4})` : ''}`);
  const missing = brandFonts.filter(f => !document.fonts.check(`16px "${f}"`) || ![...document.fonts].some(ff => ff.family.replace(/"/g,'') === f && ff.status === 'loaded'));
  out.info.fonts_loaded = [...new Set([...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/"/g,'')))];
  if (missing.length) out.warnings.push(`brand fonts not loaded (fallback shown): ${missing.join(', ')}`);
  if (!document.querySelector('.cover .topbar img')) out.warnings.push('no logo on the cover (expected for the house style or a borrowed look; a client board should have one: check design-system/manifest.json)');
  for (const el of document.querySelectorAll('[lang=ar],.ar,.ar-d')) {
    const cs = getComputedStyle(el);
    const block = !cs.display.startsWith('inline');  // an Arabic phrase inline in an English line is laid out by the bidi algorithm
    if (block && cs.direction !== 'rtl') out.errors.push(`Arabic block not right-to-left: ${el.textContent.trim().slice(0,30)}`);
    if (cs.letterSpacing !== 'normal' && parseFloat(cs.letterSpacing) !== 0) out.errors.push(`Arabic letter-spaced (breaks joins): ${el.textContent.trim().slice(0,30)}`);
  }
  return out;
}
"""


def check_board(job, kit_fonts, shots):
    from playwright.sync_api import sync_playwright
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "zamakan-design-system" / "scripts"))
    from _common import launch_chromium
    E, W, info = [], [], {}
    with sync_playwright() as p:
        b = launch_chromium(p)
        for name, vw, vh in (("desktop", 1280, 900), ("phone", 390, 844)):
            pg = b.new_page(viewport={"width": vw, "height": vh})
            pg.goto((job / "board.html").resolve().as_uri())
            pg.wait_for_load_state("networkidle")
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(300)
            r = pg.evaluate(JS_AUDIT, kit_fonts)
            E += [f"board/{name}: {e}" for e in r["errors"]]
            W += [f"board/{name}: {w}" for w in r["warnings"]]
            info[name] = r["info"]
            pg.screenshot(path=str(shots / f"board-{name}.png"), full_page=name == "desktop")
            pg.close()
        b.close()
    return E, W, info


def check_deck(job, shots):
    from pptx import Presentation
    from pptx.util import Emu
    E, W = [], []
    prs = Presentation(job / "deck.pptx")
    sw, sh = prs.slide_width, prs.slide_height
    fonts = set()
    for n, s in enumerate(prs.slides, 1):
        for shp in s.shapes:
            if shp.left is None:
                continue
            if shp.left < 0 or shp.top < 0 or shp.left + shp.width > sw + Emu(9000) or shp.top + shp.height > sh + Emu(9000):
                E.append(f"deck/slide {n}: shape outside the slide ({shp.shape_type}, {getattr(shp, 'text', '')[:30]!r})")
            if not shp.has_text_frame or not shp.text_frame.text.strip():
                continue
            w_cm, h_cm = shp.width / 360000, shp.height / 360000
            lines, size = [], None
            for p in shp.text_frame.paragraphs:
                for r in p.runs:
                    size = size or (r.font.size.pt if r.font.size else 12)
                    if r.font.name:
                        fonts.add(r.font.name)
                lines += p.text.split("\n")
            if size and h_cm > 0.4:
                cpl = max(8, w_cm / (size * 0.0353 * 0.5))
                need = sum(max(1, math.ceil(len(l) / cpl)) for l in lines) * size * 0.0353 * 1.2
                if need > h_cm * 1.25 + 0.3:
                    W.append(f"deck/slide {n}: text may overflow its box ({shp.text_frame.text[:40]!r})")
    if not any(sh_.shape_type == 13 for sh_ in prs.slides[0].shapes):
        W.append("deck: no image on the cover")
    if shutil.which("fc-list"):
        installed = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True).stdout
        missing = sorted(f for f in fonts if f not in installed)
        if missing:
            W.append(f"deck: fonts not installed here, the PDF shows a fallback: {missing}")
    pdf = job / "deck.pdf"
    if pdf.exists():
        import pymupdf
        from PIL import Image
        doc = pymupdf.open(pdf)
        ims = [Image.open(io.BytesIO(pg.get_pixmap(dpi=45).tobytes("png"))) for pg in doc]
        w, h = ims[0].size
        cols = 3
        sheet = Image.new("RGB", (cols * w + (cols - 1) * 12, math.ceil(len(ims) / cols) * (h + 12)), "white")
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % cols) * (w + 12), (i // cols) * (h + 12)))
        sheet.save(shots / "deck-sheet.png")
    return E, W, {"slides": len(prs.slides), "fonts": sorted(fonts)}


def run_checks(job):
    job = Path(job)
    shots = job / "check"
    shots.mkdir(exist_ok=True)
    E, W, info = [], [], {}
    kit_fonts = []
    if (job / "board.html").exists():
        import re
        html_ = (job / "board.html").read_text(encoding="utf-8")
        kit_fonts = sorted(set(re.findall(r"@font-face\{font-family:'([^']+)'", html_)))
        e, w, i = check_board(job, kit_fonts, shots)
        E, W, info["board"] = E + e, W + w, i
    if (job / "deck.pptx").exists():
        e, w, i = check_deck(job, shots)
        E, W, info["deck"] = E + e, W + w, i
    out = {"ok": not E, "errors": E, "warnings": W, "info": info, "look_at": sorted(str(p) for p in shots.glob("*.png"))}
    (shots / "check.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    out = run_checks(a.job)
    if a.json:
        print(json.dumps(out, indent=1, ensure_ascii=False))
    else:
        print(("OK" if out["ok"] else "FAIL") + f": {len(out['errors'])} errors, {len(out['warnings'])} warnings · {json.dumps(out['info'], ensure_ascii=False)[:300]}")
        for e in out["errors"]:
            print("  ERROR", e)
        for w in out["warnings"]:
            print("  warn ", w)
        print("  look at:", ", ".join(out["look_at"]))
    sys.exit(0 if out["ok"] else 1)


if __name__ == "__main__":
    main()
