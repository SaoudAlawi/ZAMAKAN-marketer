"""Build the fictional Rawaq brand-guidelines PDF (A4 landscape, ~19 pages).

The document intentionally contains realistic difficulties that the design-system
skill must cope with (see evals/fixtures/rawaq/answer-key.json):
  * a page that is a flattened image (no extractable text)  -> logo misuse page
  * a colour whose HEX appears on a different page than its swatch -> Charcoal
  * a conflicting HEX value on the applications page          -> Saffron
  * gaps the skill must propose: spacing scale, radii, UI/button styles, shadows

Usage: python build_guidelines.py <logos_dir> <out_pdf>
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
FONTS = (HERE / "../../../samples/rawaq/input/Fonts").resolve()

C = dict(brown="#4A2C21", green="#2F5D50", saffron="#E3A33B", sand="#F3E7D3",
         clay="#B5573A", palm="#7A8B5C", charcoal="#1F1B18", offwhite="#FBF8F3")

CSS = f"""
@font-face {{ font-family: 'Reem Kufi'; src: url('file://{FONTS}/ReemKufi[wght].ttf'); font-weight: 400 700; }}
@font-face {{ font-family: 'IBM Plex Sans Arabic'; src: url('file://{FONTS}/IBMPlexSansArabic-Regular.ttf'); font-weight: 400; }}
@font-face {{ font-family: 'IBM Plex Sans Arabic'; src: url('file://{FONTS}/IBMPlexSansArabic-Medium.ttf'); font-weight: 500; }}
@font-face {{ font-family: 'IBM Plex Sans Arabic'; src: url('file://{FONTS}/IBMPlexSansArabic-Bold.ttf'); font-weight: 700; }}
@font-face {{ font-family: 'Playfair Display'; src: url('file://{FONTS}/PlayfairDisplay[wght].ttf'); font-weight: 400 900; }}
@font-face {{ font-family: 'IBM Plex Sans'; src: url('file://{FONTS}/IBMPlexSans[wdth,wght].ttf'); font-weight: 100 700; }}
@page {{ size: 297mm 210mm; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: 'IBM Plex Sans', 'IBM Plex Sans Arabic', sans-serif; color: {C['charcoal']}; }}
.page {{ width: 297mm; height: 210mm; padding: 16mm 18mm; position: relative; overflow: hidden;
         background: {C['offwhite']}; page-break-after: always; }}
.page:last-child {{ page-break-after: auto; }}
.hdr {{ display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid {C['saffron']};
        padding-bottom: 3mm; margin-bottom: 8mm; }}
.hdr h1 {{ font-family: 'Playfair Display'; font-weight: 600; font-size: 26pt; margin: 0; color: {C['brown']}; }}
.hdr .ar {{ font-family: 'Reem Kufi'; font-weight: 700; font-size: 24pt; color: {C['brown']}; direction: rtl; }}
.sec {{ position: absolute; bottom: 9mm; left: 18mm; font-size: 8pt; letter-spacing: .12em; text-transform: uppercase; color: {C['brown']}; }}
.pn {{ position: absolute; bottom: 9mm; right: 18mm; font-size: 8pt; color: {C['brown']}; }}
p, li {{ font-size: 10.5pt; line-height: 1.55; }}
.ar-p {{ font-family: 'IBM Plex Sans Arabic'; direction: rtl; text-align: right; font-size: 11.5pt; line-height: 1.7; }}
.cols {{ display: flex; gap: 10mm; }}
.cols > div {{ flex: 1; }}
.label {{ font-size: 8pt; letter-spacing: .12em; text-transform: uppercase; color: {C['brown']}; font-weight: 600; }}
table {{ border-collapse: collapse; width: 100%; font-size: 9.5pt; }}
td, th {{ border-bottom: 1px solid #e6dccb; padding: 2.2mm 2mm; text-align: left; vertical-align: top; }}
th {{ font-size: 8pt; letter-spacing: .1em; text-transform: uppercase; color: {C['brown']}; }}
.sw {{ border-radius: 2mm; padding: 5mm; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; }}
.sw .n {{ font-family: 'Playfair Display'; font-size: 15pt; font-weight: 600; }}
.sw .na {{ font-family: 'Reem Kufi'; font-size: 14pt; font-weight: 600; direction: rtl; }}
.sw .v {{ font-size: 8.5pt; line-height: 1.6; margin-top: 2mm; font-family: 'IBM Plex Sans'; }}
.box {{ background: #fff; border: 1px solid #eadfcd; border-radius: 2mm; padding: 6mm; display: flex; align-items: center; justify-content: center; }}
.cap {{ font-size: 8.5pt; color: #6b5a50; margin-top: 2mm; line-height: 1.45; }}
.do {{ color: {C['green']}; font-weight: 600; }} .dont {{ color: {C['clay']}; font-weight: 600; }}
"""


def page(title, ar, section, n, body, bg=None, hdr=True):
    style = f' style="background:{bg}"' if bg else ""
    head = f'<div class="hdr"><h1>{title}</h1><div class="ar">{ar}</div></div>' if hdr else ""
    return (f'<section class="page"{style}>{head}{body}'
            f'<div class="sec">Rawaq Brand Guidelines · {section}</div><div class="pn">{n:02d}</div></section>')


def logo(logos, name, height):
    svg = (logos / name).read_text(encoding="utf-8")
    return svg.replace("<svg ", f'<svg style="height:{height};width:auto;max-width:100%;display:block" ', 1)


PATTERN = f"""<svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
<defs><pattern id="mash" width="40" height="40" patternUnits="userSpaceOnUse">
<g fill="none" stroke="{{stroke}}" stroke-width="1.4">
<rect x="10" y="10" width="20" height="20"/><rect x="10" y="10" width="20" height="20" transform="rotate(45 20 20)"/>
<path d="M0 0 L10 10 M40 0 L30 10 M0 40 L10 30 M40 40 L30 30"/></g></pattern></defs>
<rect width="100%" height="100%" fill="url(#mash)" opacity="{{op}}"/></svg>"""


def icon(paths):
    return (f'<svg viewBox="0 0 24 24" width="64" height="64" fill="none" stroke="{C["brown"]}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">{paths}</svg>')


ICONS = {
    "Cup": '<path d="M4 9h12v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V9z"/><path d="M16 11h2a2 2 0 0 1 0 4h-2"/><path d="M8 3c0 2 2 2 2 4M12 3c0 2 2 2 2 4"/>',
    "Bean": '<ellipse cx="12" cy="12" rx="6" ry="8.5"/><path d="M12 3.5c-2 3 2 6 0 9s2 6 0 8"/>',
    "Location": '<path d="M12 21s-7-6.5-7-11a7 7 0 0 1 14 0c0 4.5-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    "Hours": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/>',
    "Takeaway": '<path d="M6 8h12l-1.2 12H7.2L6 8z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    "Dates": '<path d="M12 3c4 3 6 6 6 10a6 6 0 0 1-12 0c0-4 2-7 6-10z"/><path d="M12 7v9"/>',
}


def misuse_html(logos):
    """Logo misuse page; rendered to an image and flattened into the PDF."""
    L = lambda h, style="": f'<div style="{style}">{logo(logos, "Rawaq_Logo_Primary_Stacked.svg", h)}</div>'
    items = [
        ("Do not stretch or squash the logo.", L("26mm", "transform:scaleX(1.6)")),
        ("Do not rotate the logo.", L("26mm", "transform:rotate(-18deg)")),
        ("Do not recolour the logo outside the approved colourways.",
         L("26mm", "filter:hue-rotate(150deg) saturate(2)")),
        ("Do not add drop shadows or effects.", L("26mm", "filter:drop-shadow(3mm 3mm 2mm rgba(0,0,0,.55))")),
        ("Do not place the logo on Saffron or low-contrast backgrounds.",
         f'<div style="background:{C["saffron"]};padding:4mm;border-radius:2mm">{logo(logos, "Rawaq_Logo_Primary_Stacked.svg", "24mm")}</div>'),
        ("Do not swap the order of the Arabic and English wordmarks.",
         f'<div style="font-family:Playfair Display;font-weight:600;letter-spacing:.3em;color:{C["brown"]};font-size:13pt;text-align:center">RAWAQ<div style="font-family:Reem Kufi;font-size:34pt;letter-spacing:0">رواق</div></div>'),
        ("Do not outline the logo.", f'<div style="filter:url(#o)">{logo(logos, "Rawaq_Logo_Primary_Stacked.svg", "26mm").replace(C["brown"], "none").replace("<path fill=", "<path stroke=\'#4A2C21\' stroke-width=\'3\' fill=")}</div>'),
        ("Do not crop or separate the symbol from the wordmark in a lockup.",
         f'<div style="height:16mm;overflow:hidden">{logo(logos, "Rawaq_Logo_Primary_Stacked.svg", "30mm")}</div>'),
    ]
    cells = "".join(
        f'<div style="text-align:center"><div class="box" style="height:44mm;position:relative">{v}'
        f'<svg style="position:absolute;top:3mm;right:3mm" width="20" height="20" viewBox="0 0 20 20"><circle cx="10" cy="10" r="9" fill="{C["clay"]}"/>'
        f'<path d="M6 6l8 8M14 6l-8 8" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/></svg></div>'
        f'<div class="cap">{t}</div></div>' for t, v in items)
    body = f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6mm">{cells}</div>'
    return (f'<html><head><style>{CSS}</style></head><body>'
            f'{page("Logo Misuse", "الاستخدام الخاطئ للشعار", "Logo", 7, body)}</body></html>')


def build_pages(logos, misuse_png):
    P = []
    pat = lambda stroke, op: PATTERN.replace("{stroke}", stroke).replace("{op}", str(op))

    # 1 Cover
    P.append(f"""<section class="page" style="background:{C['brown']};display:flex;align-items:center;justify-content:center;flex-direction:column">
<div style="position:absolute;inset:0">{pat(C['sand'], 0.08)}</div>
<div style="position:relative">{logo(logos, 'Rawaq_Logo_Primary_Stacked_Reversed.svg', '78mm')}</div>
<div style="position:relative;margin-top:10mm;text-align:center;color:{C['sand']}">
<div style="font-family:Playfair Display;font-size:22pt">Brand Guidelines</div>
<div style="font-family:Reem Kufi;font-size:20pt">دليل الهوية البصرية</div>
<div style="font-size:9pt;letter-spacing:.14em;margin-top:5mm;text-transform:uppercase">Version 2.1 · March 2026</div></div></section>""")

    # 2 Contents
    toc = [("Brand Essence", "جوهر العلامة", 3), ("Logo", "الشعار", 4), ("Colour", "الألوان", 9),
           ("Typography", "الخطوط", 12), ("Graphic Elements", "العناصر الجرافيكية", 14),
           ("Iconography", "الأيقونات", 15), ("Photography", "التصوير", 16),
           ("Layout & Social", "التخطيط والسوشال ميديا", 17), ("Applications", "التطبيقات", 18)]
    rows = "".join(f'<tr><td style="font-family:Playfair Display;font-size:14pt">{e}</td>'
                   f'<td style="font-family:Reem Kufi;font-size:14pt;text-align:right;direction:rtl">{a}</td>'
                   f'<td style="width:20mm;text-align:right">{n:02d}</td></tr>' for e, a, n in toc)
    P.append(page("Contents", "المحتويات", "Contents", 2, f"<table>{rows}</table>"))

    # 3 Brand essence
    P.append(page("Brand Essence", "جوهر العلامة", "Brand", 3, f"""
<div class="cols"><div>
<p class="label">Our idea</p>
<p style="font-family:Playfair Display;font-size:24pt;line-height:1.25;color:{C['brown']};margin:2mm 0 6mm">Rooted hospitality, crafted daily.</p>
<p>A <em>riwaq</em> is the shaded arcade of a traditional Najdi courtyard — the place where guests were welcomed and coffee was poured.
Rawaq brings that welcome to modern Riyadh: specialty coffee, roasted in-house, served with the generosity of Saudi hospitality.</p>
<p class="label" style="margin-top:8mm">Visual personality</p>
<table><tr><th>Warm</th><th>Crafted</th><th>Rooted</th><th>Generous</th></tr>
<tr><td>Earthy, sunlit colour; never cold or clinical.</td><td>Precise geometry, quality materials, considered detail.</td>
<td>Najdi architecture and Saudi craft — interpreted, not copied.</td><td>Open space, calm layouts, room to breathe.</td></tr></table>
</div><div>
<p class="ar-p" style="font-family:Reem Kufi;font-size:22pt;color:{C['brown']}">ضيافة أصيلة، تُحضَّر كل يوم.</p>
<p class="ar-p">الرواق هو الممر المظلل في الفناء النجدي التقليدي، حيث يُستقبل الضيوف وتُصب القهوة. يقدّم رواق هذا الترحيب للرياض الحديثة: قهوة مختصة تُحمّص في بيتنا، وتُقدَّم بكرم الضيافة السعودية.</p>
</div></div>"""))

    # 4 Primary logo
    P.append(page("Primary Logo", "الشعار الرئيسي", "Logo", 4, f"""
<div class="cols"><div class="box" style="height:140mm;flex:1.3">{logo(logos, 'Rawaq_Logo_Primary_Stacked.svg', '110mm')}</div>
<div><p class="label">The primary logo</p>
<p>The stacked lockup is our primary logo and should be used wherever space allows. It combines three elements that always appear together in this order:</p>
<ol><li><b>The Arch symbol</b> — the riwaq arch framing a single coffee bean.</li>
<li><b>Arabic wordmark</b> “رواق” — custom-drawn from Reem Kufi Bold.</li>
<li><b>English wordmark</b> “RAWAQ” — Playfair Display SemiBold, tracked +320.</li></ol>
<p>The Arabic wordmark always leads. The logo is supplied as master artwork; never re-type the wordmarks.</p>
<p class="label" style="margin-top:6mm">Colourway</p>
<p>Arch and wordmarks in Date Brown, coffee bean in Saffron.</p></div></div>"""))

    # 5 Variations
    var = [("Rawaq_Logo_Primary_Stacked.svg", "Primary stacked", "Default. Use wherever space allows.", C['offwhite']),
           ("Rawaq_Logo_Horizontal.svg", "Horizontal", "For wide, shallow spaces: website headers, signage fascia, email headers.", C['offwhite']),
           ("Rawaq_Symbol.svg", "Symbol", "For small or square spaces: social avatars, app icon, cup lids, favicons.", C['offwhite']),
           ("Rawaq_Logo_Primary_Stacked_Reversed.svg", "Reversed", "Sand on Date Brown or Cardamom Green backgrounds.", C['brown']),
           ("Rawaq_Logo_Mono_Black.svg", "Mono", "Single-colour print only: stamps, receipts, embossing.", "#ffffff")]
    cells = "".join(f'<div><div class="box" style="height:52mm;background:{bg}">{logo(logos, f, "38mm")}</div>'
                    f'<div class="label" style="margin-top:3mm">{t}</div><div class="cap">{d}</div></div>' for f, t, d, bg in var)
    P.append(page("Logo Variations", "نسخ الشعار", "Logo", 5,
                  f'<div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:5mm">{cells}</div>'))

    # 6 Clear space & min size
    P.append(page("Clear Space & Minimum Size", "المساحة الآمنة والحد الأدنى", "Logo", 6, f"""
<div class="cols"><div class="box" style="height:130mm;position:relative">
<div style="outline:1.5px dashed {C['clay']};outline-offset:9mm">{logo(logos, 'Rawaq_Logo_Primary_Stacked.svg', '88mm')}</div>
<div style="position:absolute;top:10mm;left:10mm;font-family:Playfair Display;font-size:14pt;color:{C['clay']}">x</div></div>
<div><p class="label">Clear space</p>
<p>Keep a clear space of <b>x</b> on all sides of the logo, where <b>x = the width of the coffee bean</b> in the symbol.
No text, graphics or edges may enter this area.</p>
<p class="label" style="margin-top:6mm">Minimum size</p>
<table><tr><th>Version</th><th>Print</th><th>Digital</th></tr>
<tr><td>Primary stacked</td><td>32 mm height</td><td>120 px height</td></tr>
<tr><td>Horizontal</td><td>12 mm height</td><td>48 px height</td></tr>
<tr><td>Symbol</td><td>10 mm height</td><td>32 px height</td></tr></table>
<p class="cap">Below these sizes the English wordmark loses legibility; switch to the symbol.</p></div></div>"""))

    # 7 Misuse (flattened image -> no extractable text)
    P.append(f'<section class="page" style="padding:0"><img src="file://{misuse_png}" style="width:297mm;height:210mm;display:block"></section>')

    # 8 Logo on backgrounds
    bgs = [(C['sand'], "Rawaq_Logo_Primary_Stacked.svg", "Sand", "do"),
           (C['offwhite'], "Rawaq_Logo_Primary_Stacked.svg", "Off-White", "do"),
           (C['brown'], "Rawaq_Logo_Primary_Stacked_Reversed.svg", "Date Brown (reversed)", "do"),
           (C['green'], "Rawaq_Logo_Primary_Stacked_Reversed.svg", "Cardamom Green (reversed)", "do"),
           (C['saffron'], "Rawaq_Logo_Primary_Stacked.svg", "Saffron", "dont"),
           (C['clay'], "Rawaq_Logo_Primary_Stacked_Reversed.svg", "Najd Clay", "dont")]
    cells = "".join(f'<div><div class="box" style="height:46mm;background:{b};border:none">{logo(logos, f, "34mm")}</div>'
                    f'<div class="cap"><span class="{k}">{"✓ Approved" if k == "do" else "✕ Not allowed"}</span> — {t}</div></div>'
                    for b, f, t, k in bgs)
    P.append(page("Logo on Backgrounds", "الشعار على الخلفيات", "Logo", 8,
                  f'<div style="display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:4mm">{cells}</div>'
                  f'<p style="margin-top:8mm">On photography, place the reversed logo over an area of calm tone, or apply a '
                  f'Date Brown overlay at 40% opacity behind it. Never place the logo over busy detail or faces.</p>'))

    # 9 Primary palette
    prim = [("Date Brown", "بني التمر", C['brown'], "74 44 33", "35 75 80 65", "4625 C", C['sand']),
            ("Cardamom Green", "أخضر الهيل", C['green'], "47 93 80", "80 35 60 30", "5545 C", C['sand']),
            ("Saffron", "زعفران", C['saffron'], "227 163 59", "8 38 88 0", "7409 C", C['brown']),
            ("Sand", "رمل", C['sand'], "243 231 211", "3 8 17 0", "7527 C", C['brown'])]
    cells = "".join(f'<div class="sw" style="background:{h};color:{fg};height:120mm"><div class="na">{a}</div><div class="n">{n}</div>'
                    f'<div class="v">HEX {h}<br>RGB {r}<br>CMYK {cm}<br>Pantone {pt}</div></div>' for n, a, h, r, cm, pt, fg in prim)
    P.append(page("Primary Colour Palette", "الألوان الرئيسية", "Colour", 9,
                  f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:5mm">{cells}</div>'
                  f'<p class="cap" style="margin-top:4mm">Our primary palette is drawn from Najdi earth, dates, cardamom and saffron — the colours of a Saudi coffee table.</p>'))

    # 10 Secondary palette + tints (Charcoal HEX deliberately only on page 13)
    sec = [("Najd Clay", "طين نجد", f"HEX {C['clay']}<br>RGB 181 87 58<br>CMYK 20 75 85 8", C['clay'], C['offwhite']),
           ("Palm Frond", "سعف النخيل", f"HEX {C['palm']}<br>RGB 122 139 92<br>CMYK 50 30 70 10", C['palm'], C['offwhite']),
           ("Charcoal", "فحمي", "CMYK 0 10 20 95<br>Text colour — see Typography", C['charcoal'], C['sand']),
           ("Off-White", "أبيض دافئ", f"HEX {C['offwhite']}<br>RGB 251 248 243", C['offwhite'], C['brown'])]
    cells = "".join(f'<div class="sw" style="background:{bg};color:{fg};height:58mm;border:1px solid #e6dccb"><div class="na">{a}</div>'
                    f'<div class="n">{n}</div><div class="v">{v}</div></div>' for n, a, v, bg, fg in sec)
    tints = ""
    for name, hexv in (("Date Brown", C['brown']), ("Cardamom Green", C['green'])):
        steps = "".join(f'<div style="flex:1;height:14mm;background:{hexv};opacity:{t / 100}"></div>' for t in (100, 80, 60, 40, 20))
        tints += (f'<div class="label" style="margin:4mm 0 1.5mm">{name} tints — 100 / 80 / 60 / 40 / 20%</div>'
                  f'<div style="display:flex;gap:1.5mm;background:#fff">{steps}</div>')
    P.append(page("Secondary Colours & Tints", "الألوان الثانوية والدرجات", "Colour", 10,
                  f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:5mm">{cells}</div>{tints}'
                  f'<p class="cap">Tints are for backgrounds, charts and illustration only — never for the logo.</p>'))

    # 11 Proportions & accessibility
    bar = "".join(f'<div style="flex:{w};background:{c};color:{fg};padding:4mm;font-size:9pt">{n}<br><b>{w}%</b></div>'
                  for n, c, w, fg in (("Sand", C['sand'], 60, C['brown']), ("Date Brown", C['brown'], 25, C['sand']),
                                      ("Cardamom", C['green'], 10, C['sand']), ("Saffron", C['saffron'], 5, C['brown'])))
    P.append(page("Colour Balance & Contrast", "توازن الألوان والتباين", "Colour", 11, f"""
<div style="display:flex;height:40mm;border-radius:2mm;overflow:hidden">{bar}</div>
<div class="cols" style="margin-top:8mm"><div><p class="label">Balance</p>
<p>Sand is our canvas. Date Brown carries type and the logo. Cardamom Green adds depth; Saffron is a spark — used for highlights, prices,
dividers and the coffee bean only. Secondary colours support seasonal campaigns and never outweigh the primary palette.</p></div>
<div><p class="label">Contrast rules</p><ul>
<li>Body text: Charcoal or Date Brown on Sand / Off-White.</li>
<li>Reversed text: Sand on Date Brown or Cardamom Green.</li>
<li><span class="dont">Never</span> set text in Saffron on Sand or Off-White — contrast is too low.</li>
<li>Saffron may be used as a background only for large display numbers with Date Brown text.</li></ul></div></div>"""))

    # 12 Typefaces
    specs = [("Reem Kufi", "Arabic Display", "Bold 700 · SemiBold 600", "رواق قهوة مختصة", "Reem Kufi", 700, "rtl"),
             ("IBM Plex Sans Arabic", "Arabic Text", "Regular 400 · Medium 500 · Bold 700", "نحمّص البن في الرياض كل صباح", "IBM Plex Sans Arabic", 400, "rtl"),
             ("Playfair Display", "Latin Display", "SemiBold 600 · Bold 700", "Rooted hospitality", "Playfair Display", 600, "ltr"),
             ("IBM Plex Sans", "Latin Text", "Regular 400 · Medium 500 · SemiBold 600", "Roasted in Riyadh, every morning.", "IBM Plex Sans", 400, "ltr")]
    cells = "".join(f'<div class="box" style="display:block;height:66mm"><div class="label">{role}</div>'
                    f'<div style="font-family:Playfair Display;font-size:15pt;margin:1mm 0">{n}</div><div class="cap">{w}</div>'
                    f'<div style="font-family:\'{fam}\';font-weight:{wt};font-size:24pt;direction:{d};color:{C["brown"]};margin-top:4mm;line-height:1.3">{s}</div></div>'
                    for n, role, w, s, fam, wt, d in specs)
    P.append(page("Typefaces", "الخطوط", "Typography", 12,
                  f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:5mm">{cells}</div>'
                  f'<p class="cap">All four families are open-source (SIL Open Font License) and free to use in print, web and apps.</p>'))

    # 13 Hierarchy
    scale = [("Display", "64 / 72", "70 / 84", "Playfair Display 600", "Reem Kufi 700"),
             ("Heading 1", "48 / 56", "53 / 64", "Playfair Display 600", "Reem Kufi 700"),
             ("Heading 2", "36 / 44", "40 / 52", "Playfair Display 600", "Reem Kufi 600"),
             ("Heading 3", "28 / 36", "31 / 44", "IBM Plex Sans 600", "IBM Plex Sans Arabic 700"),
             ("Body", "18 / 28", "20 / 34", "IBM Plex Sans 400", "IBM Plex Sans Arabic 400"),
             ("Small", "14 / 20", "15 / 26", "IBM Plex Sans 400", "IBM Plex Sans Arabic 400"),
             ("Label / Caps", "12 / 16, +120 tracking", "13 / 20", "IBM Plex Sans 600 uppercase", "IBM Plex Sans Arabic 500")]
    rows = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td>{d}</td><td>{e}</td></tr>" for a, b, c, d, e in scale)
    P.append(page("Type Hierarchy", "تسلسل الخطوط", "Typography", 13, f"""
<table><tr><th>Level</th><th>Latin size / leading (px)</th><th>Arabic size / leading (px)</th><th>Latin font</th><th>Arabic font</th></tr>{rows}</table>
<div class="cols" style="margin-top:6mm"><div><p class="label">Bilingual rules</p><ul>
<li>Arabic is set ~10% larger than Latin at the same level so both read at the same optical size.</li>
<li>Arabic body text uses generous leading (≈1.7) — Arabic ascenders and dots need room.</li>
<li>Arabic is right-aligned, Latin left-aligned. In bilingual layouts Arabic leads: on top, or on the right.</li>
<li>Never apply letter-spacing (tracking) to Arabic — it breaks the joins.</li></ul></div>
<div><p class="label">Colour of type</p>
<p>Body text colour is <b>Charcoal #1F1B18</b>. Headlines may use Date Brown. Reversed type is Sand.</p>
<p class="label" style="margin-top:4mm">Fallbacks</p>
<p>Where brand fonts cannot be installed (e.g. Office documents): Arial for Latin text, Tahoma for Arabic text.</p></div></div>"""))

    # 14 Graphic elements
    P.append(page("Graphic Elements", "العناصر الجرافيكية", "Graphic Elements", 14, f"""
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6mm">
<div><div class="box" style="height:80mm;background:{C['sand']}"><div style="width:42mm;height:62mm;background:{C['green']};border-radius:21mm 21mm 0 0"></div></div>
<p class="label" style="margin-top:3mm">The Arch frame</p><p class="cap">Photos and text panels may be framed in the arch shape: a rectangle whose top
is a full semicircle (corner radius = 50% of the frame width). Bottom corners stay square. Use one arch per layout.</p></div>
<div><div class="box" style="height:80mm;background:{C['sand']};padding:0;overflow:hidden">{pat(C['brown'], 0.14)}</div>
<p class="label" style="margin-top:3mm">Mashrabiya pattern</p><p class="cap">An eight-point star lattice inspired by Najdi screens.
Use at 10–15% opacity in Date Brown on Sand, or Sand on Date Brown at 8%. Pattern sits behind content, never behind body text.</p></div>
<div><div class="box" style="height:80mm"><svg width="160" height="20" viewBox="0 0 160 20"><line x1="0" y1="10" x2="70" y2="10" stroke="{C['saffron']}" stroke-width="1"/>
<rect x="75" y="5" width="10" height="10" transform="rotate(45 80 10)" fill="{C['saffron']}"/><line x1="90" y1="10" x2="160" y2="10" stroke="{C['saffron']}" stroke-width="1"/></svg></div>
<p class="label" style="margin-top:3mm">Saffron divider</p><p class="cap">A 1px Saffron rule with a centred diamond. Separates sections in menus, print and social carousels.</p></div></div>"""))

    # 15 Icons
    cells = "".join(f'<div style="text-align:center"><div class="box" style="height:36mm">{icon(p)}</div><div class="cap">{n}</div></div>' for n, p in ICONS.items())
    P.append(page("Iconography", "الأيقونات", "Iconography", 15,
                  f'<div style="display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:5mm">{cells}</div>'
                  f'<ul style="margin-top:8mm"><li>Line icons only, drawn on a 24 × 24 grid with a <b>2px stroke</b>, round caps and round joins.</li>'
                  f'<li>Colour: Date Brown or Cardamom Green; Sand when reversed. No filled or multi-colour icons.</li>'
                  f'<li>Icons accompany text; they never replace the logo symbol.</li></ul>'))

    # 16 Photography
    moods = [("linear-gradient(135deg,#6b3f24,#d79a4c 60%,#f3dcb2)", "Pour & process", "do"),
             ("linear-gradient(160deg,#3d2a1f,#a9744a 55%,#e8c99a)", "Hands & craft", "do"),
             ("linear-gradient(120deg,#b98b5e,#efdcbf 70%,#fbf3e6)", "Texture: palm, clay, wood", "do"),
             ("linear-gradient(135deg,#2b4a6b,#9fc0de 60%,#e9f2fb)", "Cold, blue-toned light", "dont"),
             ("linear-gradient(135deg,#d0d0d0,#ffffff)", "Sterile studio white-outs", "dont")]
    cells = "".join(f'<div><div style="height:60mm;border-radius:2mm;background:{g}"></div><div class="cap"><span class="{k}">'
                    f'{"✓" if k == "do" else "✕"}</span> {t}</div></div>' for g, t, k in moods)
    P.append(page("Photography", "التصوير", "Photography", 16,
                  f'<div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4mm">{cells}</div>'
                  f'<div class="cols" style="margin-top:7mm"><div><p class="label">Style</p><p>Warm natural daylight, amber-leaning colour grade, '
                  f'shallow depth of field. Close-ups of coffee being poured, hands at work, raw textures of palm wood and clay. '
                  f'People appear in authentic, modest everyday Saudi moments — candid, never posed stock smiles.</p></div>'
                  f'<div><p class="label">Avoid</p><p>Cold or blue light, heavy filters, cluttered backgrounds, overly staged scenes, '
                  f'and imagery that clichés Arabian culture (desert sunsets with camels, generic lanterns).</p></div></div>'))

    # 17 Layout & social
    fmts = [("Feed portrait", "1080 × 1350", 108, 135, "Primary feed format.", 0),
            ("Feed square", "1080 × 1080", 108, 108, "Carousels & grid.", 0),
            ("Story / Reel", "1080 × 1920", 108, 192, "Keep 250px top & bottom clear of text.", 25)]
    cells = ""
    for n, s, w, h, note, safe in fmts:
        k = 0.55
        safe_html = (f'<div style="position:absolute;left:0;right:0;top:0;height:{safe * k}mm;background:rgba(181,87,58,.25)"></div>'
                     f'<div style="position:absolute;left:0;right:0;bottom:0;height:{safe * k}mm;background:rgba(181,87,58,.25)"></div>') if safe else ""
        cells += (f'<div><div style="position:relative;width:{w * k}mm;height:{h * k}mm;background:{C["sand"]};border:1px solid #d9c9ad">'
                  f'<div style="position:absolute;inset:{6.4 * k}mm;border:1px dashed {C["brown"]}"></div>{safe_html}'
                  f'<div style="position:absolute;right:{8 * k}mm;bottom:{(safe + 8) * k}mm;width:{9 * k}mm;height:{11 * k}mm;background:{C["brown"]};border-radius:{4.5 * k}mm {4.5 * k}mm 0 0"></div></div>'
                  f'<div class="label" style="margin-top:2mm">{n}</div><div class="cap">{s} px · {note}</div></div>')
    P.append(page("Layout & Social Grids", "التخطيط وشبكات السوشال", "Layout", 17,
                  f'<div class="cols"><div style="display:flex;gap:8mm;align-items:flex-end;flex:1.6">{cells}</div>'
                  f'<div><p class="label">Rules</p><ul><li>Print: 12-column grid, outer margins 8% of the page width.</li>'
                  f'<li>Social: 64px margin on a 1080px canvas (dashed line).</li>'
                  f'<li>Logo: the symbol, bottom-right (the reading start in Arabic), min 64px tall on social.</li>'
                  f'<li>One message per post. Headline + max. one supporting line.</li>'
                  f'<li>Arabic-first layouts; English version may mirror the layout.</li></ul></div></div>'))

    # 18 Applications (Saffron HEX conflict planted here)
    post = (f'<div style="width:62mm;height:77.5mm;background:{C["sand"]};position:relative;border-radius:1mm;overflow:hidden">'
            f'<div style="position:absolute;inset:0">{pat(C["brown"], 0.1)}</div>'
            f'<div style="position:absolute;left:8mm;right:8mm;top:7mm;bottom:22mm;background:{C["green"]};border-radius:23mm 23mm 0 0"></div>'
            f'<div style="position:absolute;right:5mm;bottom:5mm;left:5mm;direction:rtl;text-align:right;font-family:Reem Kufi;font-weight:700;color:{C["brown"]};font-size:14pt">قهوة الصباح</div></div>')
    cup = (f'<svg width="120" height="170" viewBox="0 0 120 170"><path d="M15 20h90l-10 145H25z" fill="{C["offwhite"]}" stroke="#d9c9ad"/>'
           f'<path d="M20 70h80l-4 50H24z" fill="#E4A23C"/><rect x="10" y="8" width="100" height="14" rx="3" fill="{C["brown"]}"/>'
           f'<g transform="translate(48,80) scale(.24)"><path fill="{C["brown"]}" fill-rule="evenodd" d="M10,120 V50 A40,40 0 0 1 90,50 V120 Z M24,120 V52 A26,26 0 0 1 76,52 V120 Z"/></g></svg>')
    sign = (f'<div style="width:90mm;height:30mm;background:{C["brown"]};border-radius:1mm;display:flex;align-items:center;justify-content:center">'
            f'{logo(logos, "Rawaq_Logo_Horizontal.svg", "20mm").replace(C["brown"], C["sand"])}</div>')
    P.append(page("Applications", "التطبيقات", "Applications", 18, f"""
<div style="display:grid;grid-template-columns:1fr 1fr 1.4fr;gap:8mm;align-items:end">
<div>{post}<div class="label" style="margin-top:3mm">Instagram post</div><div class="cap">Arch frame + pattern, Arabic headline bottom-right.</div></div>
<div class="box" style="height:77.5mm">{cup}</div>
<div><div class="box" style="height:77.5mm;background:#e9e2d6">{sign}</div><div class="label" style="margin-top:3mm">Storefront fascia</div>
<div class="cap">Horizontal logo, reversed, on Date Brown.</div></div></div>
<p class="label" style="margin-top:6mm">Production notes</p>
<table><tr><td>Takeaway cup</td><td>Off-White cup, Date Brown lid, sleeve band in Saffron (#E4A23C), arch symbol in Date Brown.</td></tr>
<tr><td>Fascia</td><td>Brushed metal letters, Sand finish, on Date Brown cladding. Back-lit warm white (3000K).</td></tr></table>"""))

    # 19 Back cover
    P.append(f"""<section class="page" style="background:{C['brown']};display:flex;align-items:center;justify-content:center;flex-direction:column;color:{C['sand']}">
{logo(logos, 'Rawaq_Symbol_Reversed.svg', '40mm')}
<p style="margin-top:8mm;text-align:center">Questions about the brand? brand@rawaq-coffee.example<br>
<span style="font-family:'IBM Plex Sans Arabic'">للاستفسارات حول الهوية: brand@rawaq-coffee.example</span></p>
<p style="font-size:8pt;opacity:.7">© 2026 Rawaq Coffee Roasters · Riyadh · Fictional brand created for testing</p></section>""")
    return P


def main(logos_dir, out_pdf):
    from playwright.sync_api import sync_playwright
    logos = Path(logos_dir).resolve()
    out_pdf = Path(out_pdf).resolve()
    tmp = out_pdf.parent / "_build"
    tmp.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        # 1) flatten the misuse page to an image
        mp = tmp / "misuse.html"
        mp.write_text(misuse_html(logos), encoding="utf-8")
        page = browser.new_page(viewport={"width": 1123, "height": 794}, device_scale_factor=2)
        page.goto(f"file://{mp}")
        page.wait_for_timeout(300)
        misuse_png = tmp / "misuse.png"
        page.screenshot(path=str(misuse_png))
        # 2) the full document
        html = f'<html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(build_pages(logos, misuse_png))}</body></html>'
        dp = tmp / "guidelines.html"
        dp.write_text(html, encoding="utf-8")
        page.goto(f"file://{dp}")
        page.wait_for_timeout(500)
        page.pdf(path=str(out_pdf), width="297mm", height="210mm", print_background=True)
        browser.close()
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    print("wrote", out_pdf)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
