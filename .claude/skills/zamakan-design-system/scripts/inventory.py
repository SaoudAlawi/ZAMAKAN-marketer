#!/usr/bin/env python3
"""Classify every file in a client's brand folder.

Usage: python inventory.py <input_dir> [--out inventory.json]

Kinds: guideline (multi-page PDF), document (short PDF/DOCX), logo, font, license, image, deck,
vector-source (AI/EPS/PSD/Figma exports we cannot parse), archive, other.
Duplicates (same content hash) are reported once.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import write_json  # noqa: E402

FONT_EXT = {".ttf", ".otf", ".woff", ".woff2", ".ttc"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff", ".bmp", ".heic"}
VECTOR_SRC = {".ai", ".eps", ".psd", ".indd", ".sketch", ".fig", ".xd", ".cdr"}
DECK_EXT = {".pptx", ".ppt", ".key", ".potx"}
DOC_EXT = {".docx", ".doc", ".txt", ".md", ".rtf"}
ARCHIVE_EXT = {".zip", ".rar", ".7z"}
LOGO_HINT = re.compile(r"logo|symbol|icon[-_ ]?mark|wordmark|lockup|monogram|emblem|شعار", re.I)
LICENSE_HINT = re.compile(r"licen[cs]e|^OFL|eula", re.I)
GUIDE_HINT = re.compile(r"guide|brand[-_ ]?book|identity|manual|هوية|دليل", re.I)
SKIP = {".DS_Store", "Thumbs.db", "desktop.ini"}


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def pdf_pages(path):
    try:
        import pymupdf
        with pymupdf.open(path) as d:
            return d.page_count
    except Exception:  # noqa: BLE001
        return None


def classify(path: Path, rel: str):
    ext = path.suffix.lower()
    in_logo_dir = any(LOGO_HINT.search(p) for p in Path(rel).parts[:-1])
    info = {"path": rel, "ext": ext, "bytes": path.stat().st_size}
    if LICENSE_HINT.search(path.stem):
        info["kind"] = "license"
    elif ext in FONT_EXT:
        info["kind"] = "font"
    elif ext == ".pdf":
        n = pdf_pages(path)
        info["pages"] = n
        if (n or 0) >= 4 or GUIDE_HINT.search(path.name):
            info["kind"] = "guideline"
        elif LOGO_HINT.search(path.name) or in_logo_dir:
            info["kind"] = "logo"
        else:
            info["kind"] = "document"
    elif ext == ".svg" or ext in IMAGE_EXT:
        info["kind"] = "logo" if (LOGO_HINT.search(path.name) or in_logo_dir) else "image"
    elif ext in VECTOR_SRC:
        info["kind"] = "vector-source"
        info["note"] = "cannot parse directly; ask for SVG/PDF export if it holds unique assets"
    elif ext in DECK_EXT:
        info["kind"] = "deck"
    elif ext in DOC_EXT:
        info["kind"] = "document"
    elif ext in ARCHIVE_EXT:
        info["kind"] = "archive"
        info["note"] = "extract before running the pipeline"
    else:
        info["kind"] = "other"
    return info


def inventory(input_dir):
    root = Path(input_dir)
    files, seen = [], {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name in SKIP or p.name.startswith("._"):
            continue
        rel = str(p.relative_to(root))
        h = sha1(p)
        if h in seen:
            seen[h]["duplicates"] = seen[h].get("duplicates", []) + [rel]
            continue
        info = classify(p, rel)
        info["sha1"] = h
        seen[h] = info
        files.append(info)
    counts = {}
    for f in files:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    return {"root": str(root.resolve()), "counts": counts, "files": files}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_dir")
    ap.add_argument("--out")
    a = ap.parse_args()
    inv = inventory(a.input_dir)
    if a.out:
        write_json(a.out, inv)
    print(json.dumps(inv["counts"]))
    for f in inv["files"]:
        print(f"  {f['kind']:<13} {f['path']}" + (f"  ({f['pages']}p)" if f.get("pages") else ""))


if __name__ == "__main__":
    main()
