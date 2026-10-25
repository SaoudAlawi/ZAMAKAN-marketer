#!/usr/bin/env python3
"""Check this computer has what the ZAMAKAN skills need, and say exactly how to install what's missing.

Usage: python doctor.py          # prints one line per check; exit 1 if something required is missing

Required: Python 3.10+, the Python packages in requirements.txt, a Chromium that Playwright can start (boards, decks
and the visual checks render with it). Optional: LibreOffice (deck PDFs; the .pptx is built without it), web access.
"""
import importlib
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REQ = next((p / "requirements.txt" for p in HERE.parents if (p / "requirements.txt").is_file()), None)
PACKAGES = {"jsonschema": "jsonschema", "pymupdf": "pymupdf", "fontTools": "fonttools", "PIL": "pillow", "playwright": "playwright",
            "bs4": "beautifulsoup4", "lxml": "lxml", "pptx": "python-pptx"}


def check():
    ok, lines = True, []
    v = sys.version_info
    good = v >= (3, 10)
    ok &= good
    lines.append(("✓" if good else "✗") + f" Python {v.major}.{v.minor}" + ("" if good else ": install Python 3.10 or newer"))
    missing = []
    for mod, pkg in PACKAGES.items():
        try:
            importlib.import_module(mod)
        except Exception:  # noqa: BLE001
            missing.append(pkg)
    if missing:
        ok = False
        how = f"pip install -r {REQ}" if REQ else "pip install " + " ".join(missing)
        lines.append(f"✗ Python packages missing: {', '.join(missing)} → {how}")
    else:
        lines.append("✓ Python packages")
    if "playwright" not in missing:
        try:
            sys.path.insert(0, str(HERE.parents[2] / "zamakan-design-system" / "scripts"))
            from _common import launch_chromium
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                launch_chromium(p).close()
            lines.append("✓ Chromium (for boards, decks and visual checks)")
        except Exception as e:  # noqa: BLE001
            ok = False
            lines.append(f"✗ Chromium won't start ({str(e).splitlines()[0][:80]}) → python3 -m playwright install chromium")
    office = shutil.which("soffice") or shutil.which("libreoffice")
    lines.append("✓ LibreOffice (deck PDFs)" if office else
                 "· LibreOffice not found (optional: decks come as .pptx only) → https://www.libreoffice.org/download/")
    try:
        sys.path.insert(0, str(HERE.parents[2] / "zamakan-reference-scout" / "scripts"))
        import _web
        if _web._urllib("https://www.example.org/", 15).get("status") != 200:
            raise OSError
        lines.append("✓ Web access")
    except Exception:  # noqa: BLE001
        lines.append("· No web access from scripts: research can't check links (references would stay unverified)")
    return ok, lines


if __name__ == "__main__":
    ok, lines = check()
    print("\n".join(lines))
    print("Ready." if ok else "Install the items marked ✗, then run this again.")
    sys.exit(0 if ok else 1)
