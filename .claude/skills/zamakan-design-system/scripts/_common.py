"""Shared helpers for zamakan-design-system scripts (stdlib only)."""
import json
import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = SKILL_DIR / "schemas" / "spec.schema.json"

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def hex_to_rgb(hex_str):
    m = HEX_RE.match(hex_str.strip())
    if not m:
        raise ValueError(f"not a 6-digit hex colour: {hex_str!r}")
    h = m.group(1)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def relative_luminance(rgb):
    def chan(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex_a, hex_b):
    la = relative_luminance(hex_to_rgb(hex_a))
    lb = relative_luminance(hex_to_rgb(hex_b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def rgb_to_lab(rgb):
    """sRGB (0-255) -> CIE Lab (D65)."""
    def lin(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 1.0
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(hex_a, hex_b):
    """CIE76 colour difference. <2.3 ≈ just noticeable; <6 ≈ 'same colour, typo/variant'."""
    la, lb = rgb_to_lab(hex_to_rgb(hex_a)), rgb_to_lab(hex_to_rgb(hex_b))
    return sum((p - q) ** 2 for p, q in zip(la, lb)) ** 0.5


def cmyk_to_hex(c, m, y, k):
    """Naive (uncalibrated) CMYK% -> hex; only for sanity checks, never as a brand value."""
    c, m, y, k = (v / 100 for v in (c, m, y, k))
    return rgb_to_hex((255 * (1 - c) * (1 - k), 255 * (1 - m) * (1 - k), 255 * (1 - y) * (1 - k)))


def launch_chromium(playwright):
    """Launch Chromium via Playwright, falling back to known install paths.

    Order: $ZAMAKAN_CHROMIUM, Playwright's bundled browser, then common system paths.
    """
    import os
    import shutil
    candidates = [os.environ.get("ZAMAKAN_CHROMIUM"), None, "/opt/pw-browsers/chromium",
                  shutil.which("chromium"), shutil.which("chromium-browser"), shutil.which("google-chrome"),
                  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    last = None
    for exe in candidates:
        if exe is not None and not Path(exe).exists():
            continue
        try:
            return playwright.chromium.launch(executable_path=exe) if exe else playwright.chromium.launch()
        except Exception as e:  # noqa: BLE001 - try the next candidate
            last = e
    raise RuntimeError(f"No usable Chromium found (set ZAMAKAN_CHROMIUM). Last error: {last}")


def wcag_grade(ratio):
    """WCAG 2.x grade for text: AAA (7), AA (4.5), AA-large (3), fail."""
    if ratio >= 7:
        return "AAA"
    if ratio >= 4.5:
        return "AA"
    if ratio >= 3:
        return "AA-large"
    return "fail"
