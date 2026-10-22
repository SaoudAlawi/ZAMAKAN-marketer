#!/usr/bin/env python3
"""One image with many candidates' thumbnails, labelled with their keys, so you can compare looks at a glance
(cheap: one picture instead of many pages). Essential for frame-match; useful for any shortlist.

Usage: python contact_sheet.py cand.jsonl --out sheet.jpg [--keys keys.txt] [--source eyecannndy] [--max 24] [--frame frame.jpg]
  --frame  puts the uploaded frame first (outlined), so matches sit next to it.
Then open sheet.jpg and judge: composition, light, colour, lens. Write down why each pick matches.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from palette import fetch_image  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

W, H, LAB = 320, 180, 22


def key(r):
    return f"eye:{r['clip_id']}" if r.get("clip_id") else r.get("url")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("candidates")
    ap.add_argument("--out", required=True)
    ap.add_argument("--keys")
    ap.add_argument("--source")
    ap.add_argument("--max", type=int, default=24)
    ap.add_argument("--frame")
    a = ap.parse_args()
    cands = [json.loads(line) for line in Path(a.candidates).read_text(encoding="utf-8").split("\n") if line.strip()]
    cands = [c for c in cands if c.get("thumbnail") and not c.get("error")]
    if a.keys:
        want = [k.strip() for k in Path(a.keys).read_text(encoding="utf-8").split("\n") if k.strip()]
        by = {key(c): c for c in cands}
        cands = [by[k] for k in want if k in by]
    if a.source:
        cands = [c for c in cands if c.get("source") == a.source]
    folder = Path(a.out).parent / "thumbs"
    tiles = []
    if a.frame:
        tiles.append(("YOUR FRAME", Image.open(a.frame).convert("RGB")))
    for c in cands[:a.max]:
        f = fetch_image(c["thumbnail"], folder)
        if f:
            tiles.append((f"{key(c)[-26:]}  {(c.get('title') or '')[:22]}", Image.open(f).convert("RGB")))
    if not tiles:
        sys.exit("no thumbnails to show")
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (W * cols, (H + LAB) * rows), "white")
    d = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(tiles):
        im = im.copy()
        im.thumbnail((W, H))
        x, y = (i % cols) * W, (i // cols) * (H + LAB)
        sheet.paste(im, (x + (W - im.width) // 2, y + (H - im.height) // 2))
        if label == "YOUR FRAME":
            d.rectangle((x, y, x + W - 1, y + H - 1), outline="red", width=4)
        d.text((x + 4, y + H + 5), label, fill="black")
    sheet.save(a.out, quality=85)
    print(f"{len(tiles)} tiles → {a.out}")


if __name__ == "__main__":
    main()
