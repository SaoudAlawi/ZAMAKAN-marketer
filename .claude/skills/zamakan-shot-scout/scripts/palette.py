#!/usr/bin/env python3
"""Colour palettes from stills and thumbnails, so a look can be read and matched at a glance.

Usage: python palette.py <shots.json> --thumbs <job>/thumbs [--write]   # per shot + the overall look
       python palette.py --image frame.png                               # one image (frame-match mode)

Downloads each shot's thumbnail (and up to 3 stills) into --thumbs (kept for the board), then takes 5 dominant colours
by median-cut quantisation, ignoring near-black letterbox bars. --write stores shot.palette, thumbnail.local and,
if the run has no look.palette yet, an overall palette from all shots.
"""
import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shared  # noqa: E402,F401
from PIL import Image  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


def fetch_image(url, folder):
    import urllib.request
    folder.mkdir(parents=True, exist_ok=True)
    dst = folder / (hashlib.sha1(url.encode()).hexdigest()[:12] + ".jpg")
    if dst.exists() and dst.stat().st_size > 1000:
        return dst
    try:
        from urllib.parse import quote
        safe = quote(url, safe=":/?&=%#@+,;~")  # Film-Grab file names contain spaces
        with urllib.request.urlopen(urllib.request.Request(safe, headers=UA), timeout=25) as r:
            data = r.read()
        im = Image.open(io.BytesIO(data))
        im.seek(0)  # first frame of a gif/webp animation
        im = im.convert("RGB")
        im.thumbnail((960, 960))
        im.save(dst, quality=84)
        return dst
    except Exception as e:  # noqa: BLE001
        print(f"  could not fetch {url[:80]}: {str(e)[:60]}", file=sys.stderr)
        return None


def trim_bars(im):
    """Drop letterbox bars (near-black rows top and bottom) so they don't dominate the palette."""
    g = im.convert("L")
    w, h = g.size
    rows = [sum(g.getpixel((x, y)) for x in range(0, w, max(1, w // 40))) / len(range(0, w, max(1, w // 40))) for y in range(h)]
    top = next((i for i, v in enumerate(rows) if v > 18), 0)
    bot = h - next((i for i, v in enumerate(reversed(rows)) if v > 18), 0)
    return im.crop((0, top, w, bot)) if bot - top > h * 0.4 else im


def palette(path, n=5):
    im = trim_bars(Image.open(path).convert("RGB"))
    im.thumbnail((200, 200))
    q = im.quantize(colors=n + 3, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    out = []
    for count, idx in counts:
        r, g, b = pal[idx * 3: idx * 3 + 3]
        hx = f"#{r:02X}{g:02X}{b:02X}"
        if all(abs(r - int(o[1:3], 16)) + abs(g - int(o[3:5], 16)) + abs(b - int(o[5:7], 16)) > 40 for o in out):
            out.append(hx)
        if len(out) == n:
            break
    return out


def overall(palettes, n=6):
    from collections import Counter
    def tone(h):
        return sum(int(h[i:i + 2], 16) for i in (1, 3, 5)) / 765
    c = Counter(h for p in palettes for h in p[:3] if 0.06 < tone(h) < 0.96)  # black bars and blown highlights aren't the look
    out = []
    for hx, _ in c.most_common():
        r, g, b = (int(hx[i:i + 2], 16) for i in (1, 3, 5))
        if all(abs(r - int(o[1:3], 16)) + abs(g - int(o[3:5], 16)) + abs(b - int(o[5:7], 16)) > 60 for o in out):
            out.append(hx)
        if len(out) == n:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shots", nargs="?")
    ap.add_argument("--thumbs")
    ap.add_argument("--image")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    if a.image:
        print(" ".join(palette(a.image)))
        return
    path = Path(a.shots)
    run = json.loads(path.read_text(encoding="utf-8"))
    folder = Path(a.thumbs or path.parent / "thumbs")
    pals = []
    for s in run["shots"]:
        srcs = ([s["thumbnail"]["url"]] if s.get("thumbnail", {}).get("url") else []) + s.get("stills", [])[:3]
        files = [f for f in (fetch_image(u, folder) for u in srcs) if f]
        if not files:
            print(f"  {s['id']}: no image")
            continue
        s.setdefault("thumbnail", {"url": srcs[0]})["local"] = str(files[0].relative_to(path.parent)) if path.parent in files[0].parents else str(files[0])
        p = palette(files[0])
        if len(files) > 1:  # stills add colours the thumbnail may miss
            p = overall([p] + [palette(f) for f in files[1:]], n=5)
        s["palette"] = p
        pals.append(p)
        print(f"  {s['id']:<34} {' '.join(p)}")
    if pals and not (run.get("look") or {}).get("palette"):
        run.setdefault("look", {})["palette"] = overall(pals)
        print(f"overall look: {' '.join(run['look']['palette'])}")
    if a.write:
        path.write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"updated {path}")


if __name__ == "__main__":
    main()
