"""Write the hand-made gold spec for the Rawaq sample (evals/fixtures/rawaq/expected-spec.json).

Kept as Python so the many repeated `sources` stay short and consistent.
"""
import json
from pathlib import Path

G = "Rawaq_Brand_Guidelines_v2.1.pdf"


def src(page, method="text", note=None):
    s = {"file": G, "page": page, "method": method}
    if note:
        s["note"] = note
    return [s]


def X(page, method="text", **kw):  # extracted item helper
    return {"status": "extracted", "confidence": "high", "sources": src(page, method), **kw}


def P(rationale, **kw):  # proposed item helper
    return {"status": "proposed", "confidence": "medium", "rationale": rationale, **kw}


def rule(text, page, kind="info", method="text"):
    return {"text": text, "kind": kind, **X(page, method)}


spec = {
    "schema_version": "1.0",
    "client": {
        "slug": "rawaq", "name": "Rawaq Coffee Roasters", "name_ar": "رواق",
        "industry": "Specialty coffee / café chain", "market": "Riyadh, Saudi Arabia",
        "visual_personality": ["Warm", "Crafted", "Rooted", "Generous"],
        "guideline_source": {"file": G, "version": "2.1", "date": "March 2026"},
    },
    "colors": [
        {"id": "date-brown", "name": "Date Brown", "name_ar": "بني التمر", "hex": "#4A2C21", "rgb": [74, 44, 33],
         "cmyk": [35, 75, 80, 65], "pantone": "4625 C", "group": "primary",
         "usage": "Logo, headlines, primary type colour; 25% of colour balance", **X(9)},
        {"id": "cardamom-green", "name": "Cardamom Green", "name_ar": "أخضر الهيل", "hex": "#2F5D50", "rgb": [47, 93, 80],
         "cmyk": [80, 35, 60, 30], "pantone": "5545 C", "group": "primary", "usage": "Depth, arch frames, reversed backgrounds; 10%", **X(9)},
        {"id": "saffron", "name": "Saffron", "name_ar": "زعفران", "hex": "#E3A33B", "rgb": [227, 163, 59],
         "cmyk": [8, 38, 88, 0], "pantone": "7409 C", "group": "accent",
         "usage": "Accent only: highlights, prices, dividers, coffee bean; 5%. Never text on light backgrounds", **X(9)},
        {"id": "sand", "name": "Sand", "name_ar": "رمل", "hex": "#F3E7D3", "rgb": [243, 231, 211],
         "cmyk": [3, 8, 17, 0], "pantone": "7527 C", "group": "primary", "usage": "Main canvas / background; 60%", **X(9)},
        {"id": "najd-clay", "name": "Najd Clay", "name_ar": "طين نجد", "hex": "#B5573A", "rgb": [181, 87, 58],
         "cmyk": [20, 75, 85, 8], "group": "secondary", "usage": "Seasonal campaign support", **X(10)},
        {"id": "palm-frond", "name": "Palm Frond", "name_ar": "سعف النخيل", "hex": "#7A8B5C", "rgb": [122, 139, 92],
         "cmyk": [50, 30, 70, 10], "group": "secondary", "usage": "Seasonal campaign support", **X(10)},
        {"id": "charcoal", "name": "Charcoal", "name_ar": "فحمي", "hex": "#1F1B18", "rgb": [31, 27, 24],
         "cmyk": [0, 10, 20, 95], "group": "neutral", "usage": "Body text colour",
         "status": "extracted", "confidence": "high",
         "sources": [{"file": G, "page": 10, "method": "text", "note": "swatch + CMYK, no HEX"},
                     {"file": G, "page": 13, "method": "text", "note": "HEX #1F1B18 stated under 'Colour of type'"}]},
        {"id": "off-white", "name": "Off-White", "name_ar": "أبيض دافئ", "hex": "#FBF8F3", "rgb": [251, 248, 243],
         "group": "neutral", "usage": "Alternative light background / surfaces", **X(10)},
    ],
    "tints": [
        {"color": "date-brown", "steps_pct": [100, 80, 60, 40, 20], "usage": "Backgrounds, charts, illustration only; never the logo", **X(10)},
        {"color": "cardamom-green", "steps_pct": [100, 80, 60, 40, 20], "usage": "Backgrounds, charts, illustration only; never the logo", **X(10)},
    ],
    "color_roles": [
        {"role": "text-primary", "color": "charcoal", "usage": "Body text", **X(13)},
        {"role": "text-heading", "color": "date-brown", "usage": "Headlines", **X(13)},
        {"role": "text-inverse", "color": "sand", "usage": "Type on Date Brown / Cardamom Green", **X(13)},
        {"role": "background", "color": "sand", "usage": "Default canvas", **X(11)},
        {"role": "surface", "color": "off-white", "usage": "Alternative light background", **X(8)},
        {"role": "brand", "color": "date-brown", "usage": "Logo and brand moments", **X(4)},
        {"role": "brand-secondary", "color": "cardamom-green", "usage": "Depth, reversed panels", **X(11)},
        {"role": "accent", "color": "saffron", "usage": "Highlights, prices, dividers — never body text", **X(11)},
    ],
    "color_proportions_pct": {"sand": 60, "date-brown": 25, "cardamom-green": 10, "saffron": 5},
    "color_rules": [
        rule("Body text in Charcoal or Date Brown on Sand / Off-White.", 11, "do"),
        rule("Reversed text in Sand on Date Brown or Cardamom Green.", 11, "do"),
        rule("Never set text in Saffron on Sand or Off-White — contrast too low.", 11, "dont"),
        rule("Saffron may be a background only for large display numbers with Date Brown text.", 11, "info"),
        rule("Secondary colours support seasonal campaigns and never outweigh the primary palette.", 11, "info"),
        rule("Tints never used for the logo.", 10, "dont"),
    ],
    "fonts": [
        {"id": "reem-kufi", "family": "Reem Kufi", "role": "display", "script": "arabic", "weights": [600, 700],
         "files": ["Fonts/ReemKufi[wght].ttf"], "fallback": ["Tahoma", "sans-serif"], "license": "OFL", **X(12)},
        {"id": "ibm-plex-sans-arabic", "family": "IBM Plex Sans Arabic", "role": "text", "script": "arabic", "weights": [400, 500, 700],
         "files": ["Fonts/IBMPlexSansArabic-Regular.ttf", "Fonts/IBMPlexSansArabic-Medium.ttf", "Fonts/IBMPlexSansArabic-Bold.ttf"],
         "fallback": ["Tahoma", "sans-serif"], "license": "OFL", **X(12)},
        {"id": "playfair-display", "family": "Playfair Display", "role": "display", "script": "latin", "weights": [600, 700],
         "files": ["Fonts/PlayfairDisplay[wght].ttf"], "fallback": ["Georgia", "serif"], "license": "OFL", **X(12)},
        {"id": "ibm-plex-sans", "family": "IBM Plex Sans", "role": "text", "script": "latin", "weights": [400, 500, 600],
         "files": ["Fonts/IBMPlexSans[wdth,wght].ttf"], "fallback": ["Arial", "sans-serif"], "license": "OFL", **X(12)},
    ],
    "type_scale": [],
    "type_rules": [
        rule("Arabic is set ~10% larger than Latin at the same level for equal optical size.", 13),
        rule("Arabic body text uses generous leading (~1.7).", 13),
        rule("Arabic right-aligned, Latin left-aligned; in bilingual layouts Arabic leads (top or right).", 13),
        rule("Never letter-space (track) Arabic — it breaks the joins.", 13, "dont"),
        rule("Fallback fonts where brand fonts cannot be installed: Arial (Latin text), Tahoma (Arabic text).", 13),
    ],
    "logo": {
        "variants": [
            {"id": "primary-stacked", "name": "Primary stacked", "kind": "lockup", "orientation": "stacked", "colorway": "full-color",
             "files": ["Logos/Rawaq_Logo_Primary_Stacked.svg", "Logos/Rawaq_Logo_Primary_Stacked.png"],
             "usage": "Default; use wherever space allows", "approved_backgrounds": ["sand", "off-white"],
             "forbidden_backgrounds": ["saffron", "najd-clay"], "min_size": {"print_mm": 32, "digital_px": 120}, **X(5)},
            {"id": "horizontal", "name": "Horizontal", "kind": "lockup", "orientation": "horizontal", "colorway": "full-color",
             "files": ["Logos/Rawaq_Logo_Horizontal.svg", "Logos/Rawaq_Logo_Horizontal.png"],
             "usage": "Wide shallow spaces: website headers, signage fascia, email headers",
             "approved_backgrounds": ["sand", "off-white"], "min_size": {"print_mm": 12, "digital_px": 48}, **X(5)},
            {"id": "symbol", "name": "Symbol", "kind": "symbol", "orientation": "square", "colorway": "full-color",
             "files": ["Logos/Rawaq_Symbol.svg", "Logos/Rawaq_Symbol.png"],
             "usage": "Small or square spaces: social avatars, app icon, cup lids, favicons; social posts (bottom-right)",
             "approved_backgrounds": ["sand", "off-white"], "min_size": {"print_mm": 10, "digital_px": 32}, **X(5)},
            {"id": "reversed", "name": "Reversed", "kind": "lockup", "orientation": "stacked", "colorway": "reversed",
             "files": ["Logos/Rawaq_Logo_Primary_Stacked_Reversed.svg", "Logos/Rawaq_Logo_Primary_Stacked_Reversed_on_DateBrown.png"],
             "usage": "Sand on Date Brown or Cardamom Green backgrounds",
             "approved_backgrounds": ["date-brown", "cardamom-green"], "forbidden_backgrounds": ["najd-clay"],
             "min_size": {"print_mm": 32, "digital_px": 120}, **X(5)},
            {"id": "symbol-reversed", "name": "Symbol reversed", "kind": "symbol", "orientation": "square", "colorway": "reversed",
             "files": ["Logos/Rawaq_Symbol_Reversed.svg"], "usage": "Symbol on Date Brown or Cardamom Green",
             "approved_backgrounds": ["date-brown", "cardamom-green"], "min_size": {"print_mm": 10, "digital_px": 32},
             "status": "derived", "confidence": "medium",
             "sources": [{"file": "Logos/Rawaq_Symbol_Reversed.svg", "method": "file-metadata",
                          "note": "File supplied; rules inferred from reversed lockup (p5) and symbol min size (p6)"}]},
            {"id": "mono", "name": "Mono", "kind": "lockup", "orientation": "stacked", "colorway": "mono-dark",
             "files": ["Logos/Rawaq_Logo_Mono_Black.svg"], "usage": "Single-colour print only: stamps, receipts, embossing",
             "min_size": {"print_mm": 32}, **X(5)},
        ],
        "element_order": ["Arch symbol", "Arabic wordmark رواق", "English wordmark RAWAQ"],
        "clear_space": rule("Clear space x on all sides, where x = width of the coffee bean in the symbol.", 6),
        "on_photography": rule("On photos use the reversed logo over a calm area, or a Date Brown overlay at 40% behind it; never over busy detail or faces.", 8),
        "misuse": [rule(t, 7, "dont", "vision") for t in [
            "Do not stretch or squash the logo.", "Do not rotate the logo.",
            "Do not recolour the logo outside the approved colourways.", "Do not add drop shadows or effects.",
            "Do not place the logo on Saffron or low-contrast backgrounds.",
            "Do not swap the order of the Arabic and English wordmarks.", "Do not outline the logo.",
            "Do not crop or separate the symbol from the wordmark in a lockup."]],
        "rules": [rule("Never re-type the wordmarks; always use master artwork.", 4, "dont"),
                  rule("Below minimum sizes switch to the symbol.", 6)],
    },
    "graphic_elements": [
        {"id": "arch-frame", "name": "Arch frame", "description": "Rectangle with a full semicircular top (radius = 50% of width), square bottom corners.",
         "usage": "Frame photos and text panels; one arch per layout", "colors": ["cardamom-green", "date-brown"], **X(14)},
        {"id": "mashrabiya-pattern", "name": "Mashrabiya pattern", "description": "Eight-point star lattice inspired by Najdi screens.",
         "usage": "Behind content, never behind body text", "colors": ["date-brown", "sand"], "opacity_pct": [10, 15, 8],
         "rules": [rule("Date Brown on Sand at 10–15% opacity.", 14), rule("Sand on Date Brown at 8% opacity.", 14),
                   rule("Never behind body text.", 14, "dont")], **X(14)},
        {"id": "saffron-divider", "name": "Saffron divider", "description": "1px Saffron rule with a centred diamond.",
         "usage": "Separate sections in menus, print, social carousels", "colors": ["saffron"], **X(14)},
    ],
    "iconography": {"style": "line", "grid_px": 24, "stroke_px": 2, "caps": "round", "joins": "round",
                    "colors": ["date-brown", "cardamom-green", "sand"],
                    "rules": [rule("No filled or multi-colour icons.", 15, "dont"),
                              rule("Sand when reversed.", 15),
                              rule("Icons accompany text; never replace the logo symbol.", 15)], **X(15)},
    "photography": {
        "summary": "Warm natural daylight, amber-leaning grade, shallow depth of field; candid, crafted, rooted.",
        "do": [rule(t, 16, "do") for t in ["Warm natural daylight with an amber-leaning colour grade.", "Shallow depth of field.",
                                           "Close-ups of coffee being poured, hands at work, palm-wood and clay textures.",
                                           "People in authentic, modest everyday Saudi moments — candid."]],
        "dont": [rule(t, 16, "dont") for t in ["Cold or blue-toned light.", "Heavy filters.", "Cluttered backgrounds.",
                                               "Overly staged scenes or stock smiles.",
                                               "Clichéd Arabian imagery (camels at sunset, generic lanterns)."]],
    },
    "layout": {
        "grids": [rule("Print: 12-column grid, outer margins 8% of page width.", 17)],
        "formats": [
            {"id": "feed-portrait", "name": "Feed portrait", "width_px": 1080, "height_px": 1350, "margin_px": 64,
             "logo_placement": "symbol bottom-right", "logo_min_px": 64, "primary": True, **X(17)},
            {"id": "feed-square", "name": "Feed square", "width_px": 1080, "height_px": 1080, "margin_px": 64,
             "logo_placement": "symbol bottom-right", "logo_min_px": 64, **X(17)},
            {"id": "story", "name": "Story / Reel", "width_px": 1080, "height_px": 1920, "margin_px": 64,
             "safe_zone_px": {"top": 250, "bottom": 250}, "logo_placement": "symbol bottom-right, above bottom safe zone",
             "logo_min_px": 64, **X(17)},
        ],
        "rules": [rule("One message per post: headline + max. one supporting line.", 17),
                  rule("Arabic-first layouts; the English version may mirror the layout.", 17)],
    },
    "spacing": {"base_px": 8, "scale_px": [4, 8, 16, 24, 32, 48, 64, 96, 128],
                **P("Not specified. 8px base fits the 64px social margin (8×8) and the type scale's line-heights.")},
    "radii": [
        {"id": "none", "value": "0", "usage": "Default for panels and photos", **P("Guidelines show square corners except the arch.")},
        {"id": "sm", "value": "8px", "usage": "Buttons, chips, cards in digital UI", **P("Not specified; soft but restrained to match 'crafted' personality.")},
        {"id": "arch", "value": "9999px 9999px 0 0", "usage": "Arch frame top (semicircle, square bottom)", **X(14)},
    ],
    "shadows": [
        {"id": "soft", "value": "0 4px 16px rgba(74,44,33,0.12)", "usage": "Raised cards in digital UI only",
         **P("Not specified; warm Date-Brown-tinted shadow. Never on the logo (misuse p7).")},
    ],
    "borders": [
        {"id": "hairline", "value": "1px solid #E3A33B", "usage": "Saffron divider rule", **X(14)},
    ],
    "components": [
        {"id": "button-primary", "description": "Primary call-to-action button", "background": "date-brown", "text": "sand",
         "radius": "sm", "typography": {"level": "label", "script": "latin"}, "padding_px": [12, 24],
         **P("Not specified. Brand colour with reversed Sand type (AAA contrast), proposed 8px radius, label style.")},
        {"id": "button-primary-ar", "description": "Primary CTA, Arabic", "background": "date-brown", "text": "sand",
         "radius": "sm", "typography": {"level": "label", "script": "arabic"}, "padding_px": [12, 24],
         **P("Arabic counterpart of button-primary using the Arabic label style.")},
    ],
    "missing_assets": [
        {"asset": "Reversed horizontal logo (SVG)", "needed_for": "Storefront fascia shown on Date Brown",
         "sources": src(18, "vision")},
        {"asset": "Mashrabiya pattern tile (SVG)", "needed_for": "Backgrounds per Graphic Elements page", "sources": src(14)},
    ],
    "conflicts": [
        {"topic": "Saffron HEX", "values": [{"value": "#E3A33B", "source": {"file": G, "page": 9, "method": "text"}},
                                           {"value": "#E4A23C", "source": {"file": G, "page": 18, "method": "text", "note": "cup sleeve production note"}}],
         "chosen": "#E3A33B", "resolution": "Primary palette page is authoritative; p18 value is a production note and likely a typo.",
         "needs_client_confirmation": True},
    ],
    "open_questions": [
        "Confirm Saffron HEX (#E3A33B vs #E4A23C on the cup production note).",
        "Digital UI components (buttons, forms, shadows) are not defined — proposed values need sign-off.",
    ],
}

SCALE = [  # level, latin(size,lh,font,weight), arabic(size,lh,font,weight)
    ("display", (64, 72, "playfair-display", 600), (70, 84, "reem-kufi", 700)),
    ("h1", (48, 56, "playfair-display", 600), (53, 64, "reem-kufi", 700)),
    ("h2", (36, 44, "playfair-display", 600), (40, 52, "reem-kufi", 600)),
    ("h3", (28, 36, "ibm-plex-sans", 600), (31, 44, "ibm-plex-sans-arabic", 700)),
    ("body", (18, 28, "ibm-plex-sans", 400), (20, 34, "ibm-plex-sans-arabic", 400)),
    ("small", (14, 20, "ibm-plex-sans", 400), (15, 26, "ibm-plex-sans-arabic", 400)),
    ("label", (12, 16, "ibm-plex-sans", 600), (13, 20, "ibm-plex-sans-arabic", 500)),
]
for lvl, lat, ara in SCALE:
    for script, (size, lh, font, w) in (("latin", lat), ("arabic", ara)):
        t = {"level": lvl, "script": script, "font": font, "weight": w, "size_px": size, "line_height_px": lh, **X(13)}
        if lvl == "label" and script == "latin":
            t.update(letter_spacing_em=0.12, text_transform="uppercase")
        spec["type_scale"].append(t)

out = Path(__file__).resolve().parents[2] / "evals/fixtures/rawaq/expected-spec.json"
out.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("wrote", out)
