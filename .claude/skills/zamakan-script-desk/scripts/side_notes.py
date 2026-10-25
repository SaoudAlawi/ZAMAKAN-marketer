#!/usr/bin/env python3
"""The script with the reader's notes as comments on the side: the screenplay in one column and, level with each
line a note is about, a comment card in the margin (viewpoint name, colour family, kind). Scene headings carry a
health mark (✕ red / ! amber / ? question / ✓ strength). Saved as HTML (comments under each line on a phone) and as a
PDF (A4, fonts embedded) for reading and printing anywhere.

Usage: python side_notes.py script.json notes.json --out <dir> [--name …] [--no-pdf]
"""
import argparse
import base64
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _screenplay as S  # noqa: E402
from annotate import LENS, LENSES, UI, VERDICT, anchor_index, check  # noqa: E402

E = html.escape
FAM = LENSES["families"]
T = {"ar": {"title": "النص مع الملاحظات", "legend": "ألوان الملاحظات", "health": "علامة المشهد",
            "marks": {"red": "مشكلة تعيق النص", "amber": "ملاحظة", "question": "سؤال", "green": "نقطة قوة"}},
     "en": {"title": "Script with notes", "legend": "Note colours", "health": "Scene mark",
            "marks": {"red": "holds it back", "amber": "note", "question": "question", "green": "strength"}}}
MARK = {"red": ("✕", "#d03b3b"), "amber": ("!", "#fab219"), "question": ("?", "#8a8984"), "green": ("✓", "#0ca30c")}


def font_face(family, file, weight):
    data = base64.b64encode((S.FONTS / file).read_bytes()).decode()
    return f"@font-face{{font-family:'{family}';src:url(data:font/ttf;base64,{data}) format('truetype');font-weight:{weight}}}"


def scene_marks(sc, notes):
    """Worst mark per scene: an issue under a red viewpoint → red; any issue → amber; questions → question; strengths → green."""
    verdict = {x["id"]: x["verdict"] for x in notes["lenses"]}
    order = ["green", "question", "amber", "red"]
    marks = {}
    for n in notes["notes"]:
        m = "green" if n["kind"] == "strength" else "question" if n["kind"] == "question" else \
            "red" if verdict.get(n["lens"]) == "red" else "amber"
        marks[n["scene"]] = max(marks.get(n["scene"], m), m, key=order.index)
    return marks


def css(lang):
    rtl = lang == "ar"
    faces = font_face("Naskh", "Amiri-Regular.ttf", 400) + font_face("Naskh", "Amiri-Bold.ttf", 700) + \
        font_face("CourierP", "CourierPrime-Regular.ttf", 400) + font_face("CourierP", "CourierPrime-Bold.ttf", 700)
    script_font = "'CourierP','Naskh',monospace" if not rtl else "'Naskh','CourierP',serif"
    fam = "".join(f".f-{k}{{--c:{v['hex']}}}" for k, v in FAM.items())
    famd = "".join(f".f-{k}{{--c:{v['hex_dark']}}}" for k, v in FAM.items())
    return faces + f"""
:root{{--bg:#fcfcfb;--paper:#ffffff;--ink:#1d1b18;--muted:#5e5a53;--line:#e4dfd5;--rail:#f6f4ef}}
@media (prefers-color-scheme:dark){{:root:where(:not([data-theme="light"])){{--bg:#1a1a19;--paper:#222220;--ink:#f0efec;--muted:#c3c2b7;--line:#3a3935;--rail:#262624}}
:root:where(:not([data-theme="light"])) {famd}}}
:root[data-theme="dark"]{{--bg:#1a1a19;--paper:#222220;--ink:#f0efec;--muted:#c3c2b7;--line:#3a3935;--rail:#262624}}
{fam}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 'Naskh',system-ui,sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:28px 16px 60px}}
header h1{{font-size:26px;margin:0 0 4px}}header p{{margin:2px 0;color:var(--muted);font-size:13px}}
.legend{{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12.5px;margin:10px 0 18px}}.legend span{{white-space:nowrap}}
.sw{{display:inline-block;width:11px;height:11px;border-radius:3px;background:var(--c);margin-inline-end:5px;vertical-align:-1px}}
.page{{background:var(--paper);border:1px solid var(--line);border-radius:10px;display:grid;grid-template-columns:minmax(0,1fr) 300px}}
.el{{padding:0 28px;font-family:{script_font};font-size:{15 if rtl else 13.5}px;line-height:{1.75 if rtl else 1.45}}}
.rail{{background:var(--rail);border-inline-start:1px solid var(--line);padding:0 10px}}
.el.scene_heading{{font-weight:700;padding-top:18px}}.el.action{{padding-top:10px}}.el.character{{padding-top:10px;padding-inline-start:calc(28px + 34%);font-weight:{700 if rtl else 400}}}
.el.parenthetical{{padding-inline-start:calc(28px + 26%);padding-inline-end:calc(28px + 24%)}}.el.dialogue{{padding-inline-start:calc(28px + 17%);padding-inline-end:calc(28px + 18%)}}
.el.transition{{text-align:end;padding-top:10px}}.el.centered{{text-align:center;padding-top:10px}}
.el .hl{{background:color-mix(in srgb,var(--c) 20%,transparent);box-decoration-break:clone;-webkit-box-decoration-break:clone;border-radius:3px;padding:1px 2px}}
.mark{{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;color:#fff;font:700 12px system-ui;margin-inline-end:8px;vertical-align:1px}}
.mark.amber{{color:#1d1b18}}
.card{{background:var(--paper);border:1px solid var(--line);border-inline-start:4px solid var(--c);border-radius:8px;padding:6px 9px;margin:8px 0;font-size:12.8px;line-height:1.55}}
.card .t{{font-size:11.5px;font-weight:700;color:var(--muted)}}.card .t .sw{{width:9px;height:9px}}
.top{{padding:14px 28px 6px;grid-column:1/-1;border-bottom:1px solid var(--line)}}
@media (max-width:760px){{.page{{grid-template-columns:1fr}}.rail{{border:0;background:transparent;padding:0 16px}}.rail:empty{{display:none}}
.el{{padding:0 16px}}.el.character{{padding-inline-start:30%}}.el.dialogue{{padding-inline-start:12%;padding-inline-end:8%}}.el.parenthetical{{padding-inline-start:20%}}}}
@page{{size:A4;margin:14mm 12mm}}
@media print{{body{{background:#fff}}.wrap{{max-width:none;padding:0}}.page{{border:0;grid-template-columns:minmax(0,1fr) 62mm}}
.el{{font-size:{12.5 if rtl else 11}px}}.card{{break-inside:avoid;font-size:10.5px}}.el,.rail{{break-inside:avoid}}}}
"""


def build(sc, notes, lang):
    t, u = T[lang], UI[lang]
    els = sc["elements"]
    by_el = {}
    for n in notes["notes"]:
        by_el.setdefault(anchor_index(sc, n), []).append(n)
    marks = scene_marks(sc, notes)
    title = (sc.get("title_page") or {}).get("title") or ""
    name = lambda L: L["name_ar"] if lang == "ar" else L["name"]  # noqa: E731
    ov = notes["overall"]["verdict"]
    legend = "".join(f'<span class="f-{k}"><i class="sw"></i>{E(v[lang])}: {E("، ".join(name(L) for L in LENS.values() if L["family"] == k) if lang == "ar" else ", ".join(name(L) for L in LENS.values() if L["family"] == k))}</span>'
                     for k, v in FAM.items())
    legend += "".join(f'<span><b class="mark {m}" style="background:{MARK[m][1]}">{MARK[m][0]}</b>{E(t["marks"][m])}</span>' for m in ("red", "amber", "question", "green"))
    h = [f'<!doctype html><html lang="{lang}" dir="{"rtl" if lang == "ar" else "ltr"}"><head><meta charset="utf-8">'
         f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(title)} · {t["title"]}</title><style>{css(lang)}</style></head>'
         f'<body><div class="wrap"><header><p>{t["title"]}</p><h1>{E(title)}</h1>'
         f'<p>{E(u["overall"])}: <b class="mark {ov}" style="background:{VERDICT[ov]["hex"]}">{VERDICT[ov]["icon"]}</b>{E(VERDICT[ov][lang])} · {E(notes["logline_read"])}</p></header>'
         f'<div class="legend">{legend}</div><div class="page">']
    cue = None
    for i, e in enumerate(els):
        typ = e["type"]
        if typ in ("note", "synopsis", "section"):
            continue
        text = e["text"]
        if typ == "scene_heading":
            text = re.sub(r"^\s*(?:(?:مشهد|م)\s*[\d٠-٩]+|[\d٠-٩]+)\s*[:.\-–)]?\s*", "", text)
            m = marks.get(e["scene"])
            badge = f'<b class="mark {m}" style="background:{MARK[m][1]}" title="{E(t["marks"][m])}">{MARK[m][0]}</b>' if m else ""
            text_html = f'{badge}{S.digits(e["scene"], lang)}. {E(text)}'
        elif typ == "character":
            cue = e.get("name", text)
            text_html = E(text if lang == "ar" else text.upper())
        else:
            text_html = E(text if not (lang == "en" and typ == "transition") else text.upper())
        cards = by_el.get(i, [])
        fam = f' f-{LENS[cards[0]["lens"]]["family"]}' if cards else ""
        if cards and typ != "scene_heading":
            text_html = f'<span class="hl">{text_html}</span>'
        rail = "".join(f'<div class="card f-{LENS[n["lens"]]["family"]}"><div class="t"><i class="sw"></i>{E(name(LENS[n["lens"]]))} · {E(u["kinds"][n["kind"]])}</div>{E(n["text"])}</div>' for n in cards)
        h.append(f'<div class="el {typ}{fam}">{text_html}</div><div class="rail">{rail}</div>')
    h.append("</div></div></body></html>")
    return "\n".join(h)


def to_pdf(html_path):
    sys.path.insert(0, str(S.SKILL.parent / "zamakan-design-system" / "scripts"))
    from _common import launch_chromium
    from playwright.sync_api import sync_playwright
    pdf = html_path.with_suffix(".pdf")
    with sync_playwright() as p:
        b = launch_chromium(p)
        pg = b.new_page()
        pg.goto(html_path.resolve().as_uri())
        pg.wait_for_timeout(400)
        pg.emulate_media(media="print")
        pg.pdf(path=str(pdf), format="A4", print_background=True, prefer_css_page_size=True)
        b.close()
    return pdf


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script")
    ap.add_argument("notes")
    ap.add_argument("--out", default=".")
    ap.add_argument("--name")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    sc = json.loads(Path(a.script).read_text(encoding="utf-8"))
    notes = json.loads(Path(a.notes).read_text(encoding="utf-8"))
    errs, _ = check(sc, notes)
    if errs:
        print("\n".join("  ERROR " + e for e in errs))
        sys.exit(1)
    lang = notes.get("lang") or sc["lang"]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = a.name or (re.sub(r"[^\w؀-ۿ-]+", "-", (sc.get("title_page") or {}).get("title") or "script").strip("-") + "-side-notes")
    path = out / f"{name}.html"
    path.write_text(build(sc, notes, lang), encoding="utf-8")
    print(f"script with side notes → {path}")
    if not a.no_pdf:
        print(f"PDF → {to_pdf(path)}")


if __name__ == "__main__":
    main()
