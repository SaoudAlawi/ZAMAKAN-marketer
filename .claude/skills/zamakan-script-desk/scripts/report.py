#!/usr/bin/env python3
"""One-page HTML report of a script reading: overall verdict, the viewpoints as coloured cards, a scene strip showing
where the notes fall, the numbers (pages, scenes, locations, dialogue share) and every note by scene. Arabic pages are
right to left. Optionally screenshots it (desktop + phone) to check the layout.

Usage: python report.py script.json notes.json --stats stats.json --out <dir> [--name …] [--check]
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _screenplay as S  # noqa: E402
from annotate import LENS, UI, VERDICT, check  # noqa: E402
import charts as C  # noqa: E402
from side_notes import scene_marks  # noqa: E402

E = html.escape
T = {"ar": {"title": "قراءة النص", "story": "القصة كما فهمناها", "numbers": "بالأرقام", "pages": "صفحات", "scenes": "مشاهد",
            "locations": "مواقع", "roles": "أدوار متكلمة", "dialogue": "نسبة الحوار", "strip": "أين تقع الملاحظات",
            "by_scene": "الملاحظات مشهداً مشهداً", "next": "أولويات المسودة القادمة", "questions": "أسئلة للكاتب",
            "works": "ما ينجح", "visuals": "النص بصرياً", "intent": "هل يحقق النص ما تريده؟", "why": "معنى هذا اللون", "side": "اقرأ النص مع الملاحظات على الجانب", "scene": "مشهد", "foot": "زمكان · مساعد الكتابة. ملاحظات وأسئلة، لا إعادة كتابة."},
     "en": {"title": "Script reading", "story": "The story as we read it", "numbers": "By the numbers", "pages": "pages", "scenes": "scenes",
            "locations": "locations", "roles": "speaking roles", "dialogue": "dialogue share", "strip": "Where the notes fall",
            "by_scene": "Notes, scene by scene", "next": "Priorities for the next draft", "questions": "Questions for the writer",
            "works": "What works", "visuals": "The script at a glance", "intent": "Does the script do what you are going for?", "why": "What this colour means", "side": "Read the script with the notes on the side", "scene": "Scene", "foot": "ZAMAKAN · script desk. Notes and questions, not rewrites."}}

CSS = """
:root{--bg:#F6F4EF;--ink:#1D1B18;--muted:#5E5A53;--card:#FFFFFF;--line:#E4DFD5}
@media (prefers-color-scheme:dark){:root{--bg:#15140F;--ink:#F2EFE8;--muted:#B5AFA4;--card:#201F19;--line:#38352C}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 "IBM Plex Sans Arabic","Amiri",system-ui,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:40px 20px 64px}h1{font-size:34px;line-height:1.2;margin:4px 0 8px}h2{font-size:21px;margin:40px 0 14px}
.kicker{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}.muted{color:var(--muted)}
.chip{display:inline-flex;align-items:center;gap:8px;padding:4px 14px 4px 6px;border-radius:999px;font-weight:600;font-size:15px;border:1px solid var(--line);background:var(--card)}
.mk{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;color:#fff;font:700 12px system-ui;margin-inline-end:6px}
.hero{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:24px;margin-top:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;border-top:6px solid var(--c)}
.card h3{margin:0 0 6px;font-size:16px}.card h3::before{content:'';display:inline-block;width:11px;height:11px;border-radius:3px;background:var(--c);margin-inline-end:7px}.card p{margin:6px 0 0;font-size:14.5px}
.v{font-size:13px;font-weight:700}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-inline-end:6px;vertical-align:middle}
.nums{display:flex;flex-wrap:wrap;gap:12px}.num{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 16px;min-width:110px}
.num b{display:block;font-size:24px}.strip{display:flex;height:46px;border-radius:10px;overflow:hidden;border:1px solid var(--line);background:var(--card)}
.seg{position:relative;border-inline-end:1px solid var(--line);display:flex;flex-wrap:wrap;align-content:flex-start;gap:2px;padding:4px 3px;min-width:10px}
.seg span.n{position:absolute;bottom:2px;inset-inline-start:4px;font-size:10px;color:var(--muted)}.pip{width:8px;height:8px;border-radius:50%}
.scene{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px;margin-bottom:12px}
.scene h4{margin:0 0 8px;font-size:15px}.note{border-inline-start:4px solid var(--c);padding:4px 12px;margin:8px 0;font-size:15px}
.note .t{font-size:12.5px;font-weight:700;color:var(--muted)}ol,ul{padding-inline-start:22px}[dir=rtl] ol{list-style-type:arabic-indic}footer{margin-top:48px;font-size:13px;color:var(--muted)}
@media (max-width:600px){h1{font-size:26px}.wrap{padding:24px 16px 48px}}
"""


PREV = {"resolved": ("✓", "#0ca30c", "حُلّت", "Resolved"), "partly": ("◐", "#fab219", "حُلّت جزئياً", "Partly"),
        "open": ("!", "#d03b3b", "ما زالت قائمة", "Still open"), "dropped": ("–", "#8a8984", "لم تعد تنطبق", "No longer applies")}


def prev_section(items, draft, lang):
    ar = lang == "ar"
    title = (f"منذ المسودة {draft}" if draft else "منذ المسودة السابقة") if ar else (f"Since draft {draft}" if draft else "Since the last draft")
    counts = "".join(f'<span class="chip"><b class="mk" style="background:{v[1]}">{v[0]}</b>{sum(i["status"] == k for i in items)} {v[2] if ar else v[3]}</span> '
                     for k, v in PREV.items() if any(i["status"] == k for i in items))
    rows = "".join(f'<div class="note" style="--c:{PREV[i["status"]][1]}"><div class="t">{PREV[i["status"]][0]} {PREV[i["status"]][2 if ar else 3]}'
                   f'{(" · " + ("مشهد " if ar else "scene ") + S.digits(i["scene"], lang)) if i.get("scene") else ""}</div>{E(i["text"])}'
                   f'{(" — " + E(i["comment"])) if i.get("comment") else ""}</div>' for i in sorted(items, key=lambda x: list(PREV).index(x["status"]), reverse=True))
    return f'<h2>{E(title)}</h2><div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px">{counts}</div>{rows}'


def build(sc, notes, stats, lang, side_link=None):
    t, u = T[lang], UI[lang]
    name = lambda L: L["name_ar"] if lang == "ar" else L["name"]  # noqa: E731
    ov = notes["overall"]
    have = {x["id"]: x for x in notes["lenses"]}
    title = (sc.get("title_page") or {}).get("title") or t["title"]
    h = [f'<!doctype html><html lang="{lang}" dir="{"rtl" if lang == "ar" else "ltr"}"><head><meta charset="utf-8">'
         f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(title)} · {t["title"]}</title>'
         '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet">'
         f'<style>{CSS}{C.CSS}</style></head><body><div class="wrap">',
         f'<div class="kicker">{t["title"]}</div><h1>{E(title)}</h1>',
         f'<div class="hero"><div class="kicker">{t["story"]}</div><p style="font-size:18px;margin:6px 0 14px">{E(notes["logline_read"])}</p>'
         f'<span class="chip"><b class="mk" style="background:{VERDICT[ov["verdict"]]["hex"]}">{VERDICT[ov["verdict"]]["icon"]}</b>{E(VERDICT[ov["verdict"]][lang])}</span>'
         f'<p>{E(ov["summary"])}</p></div>']
    if stats:
        nums = [(stats.get("pages") or "?", t["pages"]), (stats["scenes"], t["scenes"]), (stats["locations"], t["locations"]),
                (stats["speaking_roles"], t["roles"]), (f'{stats["dialogue_share"]}%', t["dialogue"])]
        h.append(f'<h2>{t["numbers"]}</h2><div class="nums">' + "".join(f'<div class="num"><b>{E(str(S.digits(v, lang) if isinstance(v, int) else v))}</b>{E(k)}</div>' for v, k in nums) + "</div>")
    ic = notes.get("intent_check") or []
    if ic:
        lands = {"yes": ("✓", "#0ca30c"), "partly": ("◐", "#fab219"), "no": ("✕", "#d03b3b")}
        h.append(f'<h2>{t["intent"]}</h2>' + "".join(
            f'<div class="note" style="--c:{lands[it["lands"]][1]}"><div class="t">{lands[it["lands"]][0]} {E(it["intent"])}'
            f'{(" · " + t["scene"] + " " + S.digits(it["scene"], lang)) if it.get("scene") else ""}</div>{E(it["note"])}</div>' for it in ic))
    prev = (notes.get("previous") or {}).get("items") or []
    if prev:
        h.append(prev_section(prev, notes["previous"].get("draft"), lang))
    if stats:
        st = next((x for x in S.STRUCTURES["structures"] if x["id"] == notes.get("structure")), None)
        h.append(f'<h2>{t["visuals"]}</h2>')
        h += C.all_charts(stats, notes, st, scene_marks(sc, notes), lang)
    if side_link:
        h.append(f'<p><a href="{E(side_link)}">{t["side"]} →</a></p>')
    h.append(f'<h2>{u["notes"]}</h2><div class="grid">')
    for lid, L in LENS.items():
        x = have.get(lid)
        if not x:
            continue
        works = "".join(f"<p>✓ {E(s)}</p>" for s in x.get("strengths", []))
        h.append(f'<div class="card" style="--c:{L["hex"]}"><h3>{E(name(L))}</h3><div class="v">'
                 f'<b class="mk" style="background:{VERDICT[x["verdict"]]["hex"]}">{VERDICT[x["verdict"]]["icon"]}</b>{E(VERDICT[x["verdict"]][lang])}</div>'
                 f'<p>{E(x["summary"])}</p>{works}'
                 f'<p class="muted" style="font-size:12.5px">{t["why"]}: {E(L.get("anchors", {}).get(x["verdict"], {}).get(lang, ""))}</p></div>')
    h.append("</div>")
    h.append(f'<h2>{t["next"]}</h2><ol>' + "".join(f"<li>{E(s)}</li>" for s in notes["next_draft"]) + "</ol>")
    if notes.get("questions_for_writer"):
        h.append(f'<h2>{t["questions"]}</h2><ul>' + "".join(f"<li>{E(q)}</li>" for q in notes["questions_for_writer"]) + "</ul>")
    # scene strip: width by share, a pip per note in the lens colour
    rows = (stats or {}).get("scene_rows") or [{"n": s["n"], "share": 100 / len(sc["scenes"])} for s in sc["scenes"]]
    by = {}
    for n in notes["notes"]:
        by.setdefault(n["scene"], []).append(n)
    h.append(f'<h2>{t["strip"]}</h2><div class="strip">')
    for r in rows:
        pips = "".join(f'<i class="pip" style="background:{LENS[n["lens"]]["hex"]}" title="{E(name(LENS[n["lens"]]))}"></i>' for n in by.get(r["n"], []))
        h.append(f'<div class="seg" style="flex:{max(r["share"], 1.5)}">{pips}<span class="n">{S.digits(r["n"], lang)}</span></div>')
    h.append("</div>")
    h.append(f'<h2>{t["by_scene"]}</h2>')
    heads = {s["n"]: s["heading"] for s in sc["scenes"]}
    for n in sorted(by):
        h.append(f'<div class="scene"><h4>{t["scene"]} {S.digits(n, lang)} · {E(re.sub(r"^\s*(?:مشهد|م)\s*[\d٠-٩]+\s*[:.\-–]?\s*", "", heads[n]))}</h4>')
        for x in by[n]:
            L = LENS[x["lens"]]
            q = f' <span class="muted">«{E(x["quote"])}»</span>' if x.get("quote") else ""
            h.append(f'<div class="note" style="--c:{L["hex"]}"><div class="t">■ {E(name(L))} · {E(u["kinds"][x["kind"]])}</div>{E(x["text"])}{q}</div>')
        h.append("</div>")
    h.append(f'<footer>{t["foot"]}</footer></div></body></html>')
    return "\n".join(h)


def screenshot(path):
    sys.path.insert(0, str(S.SKILL.parent / "zamakan-design-system" / "scripts"))
    from _common import launch_chromium
    from playwright.sync_api import sync_playwright
    shots = []
    with sync_playwright() as p:
        b = launch_chromium(p)
        for label, w in (("desktop", 1280), ("phone", 390)):
            pg = b.new_page(viewport={"width": w, "height": 900})
            pg.goto(path.resolve().as_uri())
            pg.wait_for_timeout(600)
            over = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            out = path.with_name(f"{path.stem}-{label}.png")
            pg.screenshot(path=str(out), full_page=True)
            shots.append((label, out, over))
        b.close()
    return shots


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script")
    ap.add_argument("notes")
    ap.add_argument("--stats")
    ap.add_argument("--out", default=".")
    ap.add_argument("--name")
    ap.add_argument("--check", action="store_true", help="screenshot desktop + phone and report sideways scrolling")
    a = ap.parse_args()
    sc = json.loads(Path(a.script).read_text(encoding="utf-8"))
    notes = json.loads(Path(a.notes).read_text(encoding="utf-8"))
    errs, _ = check(sc, notes)
    if errs:
        print("\n".join("  ERROR " + e for e in errs))
        sys.exit(1)
    stats = json.loads(Path(a.stats).read_text(encoding="utf-8")) if a.stats else None
    lang = notes.get("lang") or sc["lang"]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = a.name or (re.sub(r"[^\w؀-ۿ-]+", "-", (sc.get("title_page") or {}).get("title") or "script").strip("-") + "-report")
    path = out / f"{name}.html"
    side = out / (name.replace("-report", "") + "-side-notes.html")
    path.write_text(build(sc, notes, stats, lang, side.name if side.exists() else None), encoding="utf-8")
    print(f"report → {path}")
    if a.check:
        for label, shot, over in screenshot(path):
            print(f"  {label}: {shot}" + (f"  ✗ scrolls sideways by {over}px" if over > 1 else "  ✓ fits"))


if __name__ == "__main__":
    main()
