# spec.json: worked example

A small but complete spec for a fictional client ("Noor Dental", a Jeddah clinic chain) showing
the shape of every section and the three statuses. Real specs are usually larger (more colours,
more rules), but no section looks different from this. Validate yours with `validate_spec.py`.

Things to notice:
- `sources[].method` says *how* you know: `text` (read from extracted text), `vision` (read from a
  page image), `pixel-sample` (measured fill), `file-metadata` / `svg-parse` (from asset files).
- Proposed items have `rationale` instead of `sources`.
- Colour `id`s are what every other file uses (`role.*`, logo backgrounds, tokens), so keep them stable.
- `type_scale` has one entry per level **per script**.
- The conflict's `chosen` value is the hex actually used in `colors`.

```json
{
  "schema_version": "1.0",
  "client": {
    "slug": "noor-dental", "name": "Noor Dental", "name_ar": "نور لطب الأسنان",
    "industry": "Dental clinics", "market": "Jeddah, Saudi Arabia",
    "visual_personality": ["Calm", "Clean", "Reassuring"],
    "guideline_source": {"file": "Noor_Brand_Book.pdf", "version": "1.0", "date": "2025"}
  },
  "colors": [
    {"id": "noor-teal", "name": "Noor Teal", "name_ar": "فيروزي نور", "hex": "#127C80", "rgb": [18, 124, 128],
     "group": "primary", "usage": "Logo, headlines, buttons", "status": "extracted", "confidence": "high",
     "sources": [{"file": "Noor_Brand_Book.pdf", "page": 6, "method": "text"}]},
    {"id": "pearl", "name": "Pearl", "name_ar": "لؤلؤي", "hex": "#F5F7F6", "group": "neutral",
     "usage": "Backgrounds", "status": "extracted", "confidence": "high",
     "sources": [{"file": "Noor_Brand_Book.pdf", "page": 6, "method": "text"}]},
    {"id": "ink", "name": "Ink", "hex": "#1D2B2C", "group": "neutral", "usage": "Body text",
     "status": "extracted", "confidence": "medium",
     "sources": [{"file": "Noor_Brand_Book.pdf", "page": 7, "method": "pixel-sample",
                  "note": "swatch has no HEX printed; fill measured from the PDF"}]},
    {"id": "coral", "name": "Coral", "name_ar": "مرجاني", "hex": "#F2765B", "group": "accent",
     "usage": "Highlights and offers only", "status": "extracted", "confidence": "high",
     "sources": [{"file": "Noor_Brand_Book.pdf", "page": 6, "method": "text"}]}
  ],
  "color_roles": [
    {"role": "text-primary", "color": "ink", "status": "extracted",
     "sources": [{"file": "Noor_Brand_Book.pdf", "page": 9, "method": "text"}]},
    {"role": "background", "color": "pearl", "status": "extracted",
     "sources": [{"file": "Noor_Brand_Book.pdf", "page": 6, "method": "text"}]},
    {"role": "brand", "color": "noor-teal", "status": "extracted",
     "sources": [{"file": "Noor_Brand_Book.pdf", "page": 4, "method": "text"}]},
    {"role": "accent", "color": "coral", "status": "extracted",
     "sources": [{"file": "Noor_Brand_Book.pdf", "page": 6, "method": "text"}]},
    {"role": "text-inverse", "color": "pearl", "status": "derived", "confidence": "medium",
     "sources": [{"file": "Noor_Brand_Book.pdf", "page": 5, "method": "vision",
                  "note": "reversed logo shown in Pearl on Teal"}]}
  ],
  "color_rules": [
    {"text": "Coral never exceeds 10% of a layout.", "kind": "dont", "status": "extracted",
     "sources": [{"file": "Noor_Brand_Book.pdf", "page": 6, "method": "text"}]}
  ],
  "fonts": [
    {"id": "tajawal", "family": "Tajawal", "role": "text", "script": "arabic", "weights": [400, 700],
     "files": ["fonts/Tajawal-Regular.ttf", "fonts/Tajawal-Bold.ttf"], "fallback": ["Tahoma", "sans-serif"],
     "status": "extracted", "sources": [{"file": "Noor_Brand_Book.pdf", "page": 8, "method": "text"}]},
    {"id": "inter", "family": "Inter", "role": "text", "script": "latin", "weights": [400, 600],
     "fallback": ["Arial", "sans-serif"], "status": "extracted",
     "sources": [{"file": "Noor_Brand_Book.pdf", "page": 8, "method": "text",
                  "note": "named in guideline; no font file supplied (open question)"}]}
  ],
  "type_scale": [
    {"level": "h1", "script": "latin", "font": "inter", "weight": 600, "size_px": 40, "line_height_px": 48,
     "status": "extracted", "sources": [{"file": "Noor_Brand_Book.pdf", "page": 8, "method": "text"}]},
    {"level": "h1", "script": "arabic", "font": "tajawal", "weight": 700, "size_px": 44, "line_height_px": 60,
     "status": "proposed", "confidence": "medium",
     "rationale": "Guideline gives Latin sizes only; Arabic set ~10% larger with looser leading for equal optical size."},
    {"level": "body", "script": "latin", "font": "inter", "weight": 400, "size_px": 16, "line_height_px": 24,
     "status": "extracted", "sources": [{"file": "Noor_Brand_Book.pdf", "page": 8, "method": "text"}]},
    {"level": "body", "script": "arabic", "font": "tajawal", "weight": 400, "size_px": 18, "line_height_px": 30,
     "status": "proposed", "confidence": "medium", "rationale": "As h1: +10% size, ~1.65 leading for Arabic."}
  ],
  "logo": {
    "variants": [
      {"id": "primary", "name": "Primary", "kind": "lockup", "orientation": "horizontal", "colorway": "full-color",
       "files": ["logos/noor-primary.svg"], "approved_backgrounds": ["pearl"], "forbidden_backgrounds": ["coral"],
       "min_size": {"digital_px": 40, "print_mm": 15}, "status": "extracted",
       "sources": [{"file": "Noor_Brand_Book.pdf", "page": 4, "method": "text"},
                   {"file": "logos/noor-primary.svg", "method": "svg-parse"}]}
    ],
    "clear_space": {"text": "Clear space equals the height of the tooth icon on all sides.", "status": "extracted",
                    "sources": [{"file": "Noor_Brand_Book.pdf", "page": 5, "method": "text"}]},
    "misuse": [
      {"text": "Do not rotate the logo.", "kind": "dont", "status": "extracted",
       "sources": [{"file": "Noor_Brand_Book.pdf", "page": 5, "method": "vision", "note": "image-only page"}]}
    ]
  },
  "layout": {
    "formats": [
      {"id": "feed-portrait", "name": "Instagram portrait", "width_px": 1080, "height_px": 1350, "margin_px": 60,
       "logo_placement": "top-left", "primary": true, "status": "extracted",
       "sources": [{"file": "Noor_Brand_Book.pdf", "page": 12, "method": "text"}]}
    ]
  },
  "spacing": {"base_px": 4, "scale_px": [4, 8, 12, 16, 24, 32, 48, 60], "status": "proposed", "confidence": "medium",
              "rationale": "Not specified. 4px base divides the 60px social margin and the 24px body leading."},
  "radii": [
    {"id": "md", "value": "12px", "usage": "Cards, buttons", "status": "extracted",
     "sources": [{"file": "Noor_Brand_Book.pdf", "page": 11, "method": "vision", "note": "rounded cards in UI mock-ups"}]}
  ],
  "conflicts": [
    {"topic": "Noor Teal HEX",
     "values": [{"value": "#127C80", "source": {"file": "Noor_Brand_Book.pdf", "page": 6}},
                {"value": "#137B80", "source": {"file": "Noor_Brand_Book.pdf", "page": 14, "note": "signage spec"}}],
     "chosen": "#127C80", "resolution": "Palette page outranks the signage production note.",
     "needs_client_confirmation": true}
  ],
  "open_questions": ["Confirm Noor Teal HEX (#127C80 vs #137B80).", "Please send Inter font files or confirm Google Fonts."]
}
```

## Choosing statuses: quick cases

| Situation | status | how |
|---|---|---|
| HEX printed on the palette page | extracted | `method: text`, page |
| Swatch with no HEX; digest measured the fill | extracted | `method: pixel-sample`, confidence medium (high if the HEX is also printed elsewhere) |
| Rule visible only in a flattened page image | extracted | `method: vision`, page |
| Reversed symbol file supplied, rules only stated for the reversed lockup | derived | cite both |
| Arabic type sizes missing, Latin given | proposed | rationale cites the bilingual rule or the 10% convention |
| No spacing / radii / shadows in guideline | proposed | rationale ties values to brand evidence |
