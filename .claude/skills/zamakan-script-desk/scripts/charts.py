"""Charts for the script reading, as self-contained HTML/SVG fragments (used by report.py and, as pictures, by
annotate.py): beat map with scene health, tension curve, character presence grid, dialect map and a production
stripboard. Built with the dataviz method: status colours only with an icon, one sequential hue for amounts, at most
three categorical hues plus labelled grey, text in ink, thin marks, 2 px gaps, a legend for every multi-colour chart,
hover titles on marks. Arabic charts run right to left (the film starts on the right).
"""
import html

E = html.escape
W = 1000
INK, MUTED, GRID, SURFACE = "var(--ink)", "var(--muted)", "var(--line)", "var(--card)"
SEQ = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab"]  # present silent, 1 line, 2-3, 4+
DIALECT = {"msa": "#2a78d6", "gulf": "#eb6834", "egyptian": "#1baf7a", "levantine": "#8a8984"}
DIALECT_LABEL = {"ar": {"msa": ("ف", "فصحى"), "gulf": ("خ", "خليجي/عماني"), "egyptian": ("م", "مصري"), "levantine": ("ش", "شامي")},
                 "en": {"msa": ("M", "MSA"), "gulf": ("G", "Gulf/Omani"), "egyptian": ("E", "Egyptian"), "levantine": ("L", "Levantine")}}
MARK = {"red": ("✕", "#d03b3b"), "amber": ("!", "#fab219"), "question": ("?", "#8a8984"), "green": ("✓", "#0ca30c")}
STRIP = {"int_day": ("#ffffff", {"ar": "داخلي نهار", "en": "INT day"}), "ext_day": ("#f7e27a", {"ar": "خارجي نهار", "en": "EXT day"}),
         "int_night": ("#8fb6ea", {"ar": "داخلي ليل", "en": "INT night"}), "ext_night": ("#8fd19e", {"ar": "خارجي ليل", "en": "EXT night"}),
         "dawn_dusk": ("#f4b183", {"ar": "فجر/غروب", "en": "dawn/dusk"})}
FLAG = {"ar": {"night exterior": "ليل خارجي", "water/sea": "بحر", "weather/FX": "طقس/مؤثرات", "crowd": "مجاميع", "vehicles/stunts": "حركة خطرة",
               "animals": "حيوانات", "children": "أطفال"},
        "en": {"night exterior": "night ext", "water/sea": "sea", "weather/FX": "weather/FX", "crowd": "crowd", "vehicles/stunts": "stunts",
               "animals": "animals", "children": "children"}}
TXT = {"ar": {"beat": "خريطة المحطات", "beat_sub": "أعلى: أين يتوقع البناء كل محطة. أسفل: المشاهد بعرضها الفعلي ولون أشد ملاحظة فيها. الخطوط تصل كل محطة بالمشهد الذي تحدث فيه فعلاً.",
              "tension": "منحنى التوتر", "tension_sub": "التوتر كما أحسّه القارئ في كل مشهد (٠-٥)، على طول الفيلم.",
              "presence": "حضور الشخصيات", "presence_sub": "من يظهر في كل مشهد؛ اللون الأغمق = أسطر حوار أكثر.",
              "dialect": "خريطة اللهجات", "dialect_sub": "اللهجة الغالبة في حوار كل شخصية في كل مشهد (تلميح، لا حكم).",
              "strip": "لوحة التصوير", "strip_sub": "كل مشهد بألوان لوحات الإنتاج المعروفة، مع ما يرفع الكلفة.",
              "scene": "مشهد", "lines": "أسطر", "silent": "حاضر دون كلام", "none": "لا ملاحظات", "len": "الطول",
              "marks": {"red": "مشكلة", "amber": "ملاحظة", "question": "سؤال", "green": "قوة"}, "expected": "المتوقع", "actual": "الفعلي",
              "now": "هذه المسودة", "before": "المسودة السابقة", "overlay": "الخط المتقطع: المسودة السابقة."},
       "en": {"beat": "Beat map", "beat_sub": "Top: where the structure expects each beat. Bottom: scenes at their real length, coloured by their most serious note. Lines join each beat to the scene where it actually happens.",
              "tension": "Tension curve", "tension_sub": "Tension as the reader felt it, scene by scene (0-5), across the film.",
              "presence": "Character presence", "presence_sub": "Who is in each scene; darker = more lines of dialogue.",
              "dialect": "Dialect map", "dialect_sub": "Main dialect of each character's dialogue per scene (a hint, not a verdict).",
              "strip": "Stripboard", "strip_sub": "Each scene in the usual production-board colours, with what drives cost.",
              "scene": "Scene", "lines": "lines", "silent": "present, silent", "none": "no notes", "len": "length",
              "marks": {"red": "problem", "amber": "note", "question": "question", "green": "strength"}, "expected": "expected", "actual": "actual",
              "now": "this draft", "before": "previous draft", "overlay": "Dashed: the previous draft."}}

CSS = """
.viz{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:14px 0}
.viz h3{margin:0 0 2px;font-size:17px}.viz .sub{margin:0 0 10px;color:var(--muted);font-size:13.5px}
.viz svg{width:100%;height:auto;display:block}.viz svg text{fill:var(--ink);font-family:inherit}.viz svg .m{fill:var(--muted)}
.lg{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12.5px;color:var(--muted);margin-top:8px}.lg i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-inline-end:5px;vertical-align:-1px;border:1px solid var(--line)}
.lg b{display:inline-flex;width:16px;height:16px;border-radius:50%;align-items:center;justify-content:center;color:#fff;font:700 10px system-ui;margin-inline-end:5px}
table.strip{width:100%;border-collapse:separate;border-spacing:0 3px;font-size:13.5px}table.strip td{padding:5px 8px;vertical-align:middle}
table.strip td.c{width:14px;border-radius:4px;border:1px solid var(--line)}table.strip .bar{height:8px;border-radius:4px;background:var(--muted);opacity:.45}
table.strip .fl{display:inline-block;font-size:11.5px;border:1px solid var(--line);border-radius:999px;padding:0 7px;margin-inline-end:4px;color:var(--muted)}
"""


def _x(lang, pad=40, width=W):
    span = width - 2 * pad
    return (lambda p: width - pad - p / 100 * span) if lang == "ar" else (lambda p: pad + p / 100 * span)


def _wrap(title, sub, svg, legend=""):
    return f'<div class="viz"><h3>{E(title)}</h3><p class="sub">{E(sub)}</p>{svg}{legend}</div>'


def beat_map(stats, notes, structure, marks, lang):
    t = TXT[lang]
    X = _x(lang)
    rows = stats["scene_rows"]
    beats = structure["beats"] if structure else []
    turns = (notes or {}).get("turns") or {}
    H = 190
    s = [f'<svg viewBox="0 0 {W} {H}" style="direction:ltr" role="img" aria-label="{E(t["beat"])}">']
    s.append(f'<line x1="{X(0)}" y1="70" x2="{X(100)}" y2="70" stroke="{GRID}" stroke-width="2"/>')
    for i, b in enumerate(beats):  # expected beats: ticks with staggered labels
        x = X(b["at"])
        y = 22 if i % 2 == 0 else 44
        nm = b["name_ar"] if lang == "ar" else b["name"]
        s.append(f'<line x1="{x}" y1="{y + 6}" x2="{x}" y2="74" stroke="{MUTED}" stroke-width="1.5"><title>{E(nm)} · {b["at"]}%</title></line>')
        s.append(f'<text x="{x}" y="{y}" font-size="12" text-anchor="middle">{E(nm[:18])}</text>')
    y0 = 120
    for r in rows:  # scenes at real length, coloured by worst note
        a, z = r["pos"], r["pos"] + r["share"]
        x1, x2 = sorted((X(a), X(z)))
        m = marks.get(r["n"])
        fill = MARK[m][1] if m else "var(--line)"
        lab = t["marks"][m] if m else t["none"]
        s.append(f'<rect x="{x1 + 1}" y="{y0}" width="{max(x2 - x1 - 2, 2)}" height="34" rx="4" fill="{fill}"><title>{t["scene"]} {r["n"]} · {E(lab)}</title></rect>')
        s.append(f'<text x="{(x1 + x2) / 2}" y="{y0 + 22}" font-size="12" text-anchor="middle" style="fill:{"#1d1b18" if m in ("amber", None) else "#fff"}">{r["n"]}</text>')
        if m:
            s.append(f'<text x="{(x1 + x2) / 2}" y="{y0 + 52}" font-size="11" text-anchor="middle" class="m">{MARK[m][0]}</text>')
    pos = {r["n"]: r["pos"] + r["share"] / 2 for r in rows}
    for b in beats:  # actual turns
        n = turns.get(b["id"])
        if n in pos:
            xe, xa = X(b["at"]), X(pos[n])
            s.append(f'<path d="M{xe},76 C{xe},100 {xa},96 {xa},{y0 - 2}" fill="none" stroke="{INK}" stroke-width="2"><title>{E(b["name_ar"] if lang == "ar" else b["name"])}: {t["expected"]} {b["at"]}% · {t["actual"]} {t["scene"]} {n}</title></path>')
            s.append(f'<circle cx="{xa}" cy="{y0 - 2}" r="4" fill="{INK}" stroke="var(--card)" stroke-width="2"/>')
    s.append("</svg>")
    legend = '<div class="lg">' + "".join(f'<span><b style="background:{MARK[m][1]}">{MARK[m][0]}</b>{E(t["marks"][m])}</span>' for m in MARK) + \
             f'<span><i style="background:var(--line)"></i>{E(t["none"])}</span></div>'
    return _wrap(t["beat"], t["beat_sub"], "".join(s), legend)


def tension_curve(stats, notes, structure, lang, prev=None):
    """Tension per scene (0-5). prev = (old stats, old notes) overlays the previous draft's curve, dashed and grey."""
    tens = (notes or {}).get("tension") or {}
    if not tens:
        return ""
    t = TXT[lang]
    X = _x(lang, pad=46)
    H, top, bot = 230, 20, 190
    Y = lambda v: bot - v / 5 * (bot - top)  # noqa: E731
    s = [f'<svg viewBox="0 0 {W} {H}" style="direction:ltr" role="img" aria-label="{E(t["tension"])}">']
    for v in range(6):
        s.append(f'<line x1="{X(0)}" y1="{Y(v)}" x2="{X(100)}" y2="{Y(v)}" stroke="{GRID}" stroke-width="1"/>')
        s.append(f'<text x="{X(0) + (14 if lang == "ar" else -14)}" y="{Y(v) + 4}" font-size="11" text-anchor="middle" class="m">{v}</text>')
    for b in (structure or {}).get("beats", []):
        s.append(f'<line x1="{X(b["at"])}" y1="{top}" x2="{X(b["at"])}" y2="{bot}" stroke="{GRID}" stroke-width="1" stroke-dasharray="3 4"><title>{E(b["name_ar"] if lang == "ar" else b["name"])}</title></line>')

    def curve(st, tn):
        return [(X(r["pos"] + r["share"] / 2), Y(tn[str(r["n"])]), r["n"], tn[str(r["n"])]) for r in st["scene_rows"] if str(r["n"]) in tn]
    legend = ""
    if prev and (prev[1] or {}).get("tension"):
        old = curve(prev[0], prev[1]["tension"])
        if old:
            s.append('<polyline fill="none" stroke="#8a8984" stroke-width="2" stroke-dasharray="6 5" points="' + " ".join(f"{x},{y}" for x, y, _, _ in old) + '"/>')
            for x, y, n, v in old:
                s.append(f'<circle cx="{x}" cy="{y}" r="3.5" fill="#8a8984"><title>{t["before"]} · {t["scene"]} {n} · {v}/5</title></circle>')
            legend = (f'<div class="lg"><span><i style="background:#2a78d6"></i>{E(t["now"])}</span>'
                      f'<span><i style="background:#8a8984"></i>{E(t["before"])}</span></div>')
    pts = curve(stats, tens)
    if pts:
        s.append('<polyline fill="none" stroke="#2a78d6" stroke-width="2" points="' + " ".join(f"{x},{y}" for x, y, _, _ in pts) + '"/>')
        for x, y, n, v in pts:
            s.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#2a78d6" stroke="var(--card)" stroke-width="2"><title>{t["scene"]} {n} · {v}/5</title></circle>')
            s.append(f'<text x="{x}" y="{bot + 18}" font-size="11" text-anchor="middle" class="m">{n}</text>')
        hi = max(pts, key=lambda p: p[3])
        s.append(f'<text x="{hi[0]}" y="{hi[1] - 10}" font-size="12" text-anchor="middle">{t["scene"]} {hi[2]}</text>')
    s.append("</svg>")
    return _wrap(t["tension"], t["tension_sub"] + (" " + t["overlay"] if legend else ""), "".join(s), legend)


def _grid(stats, cell, title, sub, legend, lang, max_rows=10):
    t = TXT[lang]
    rows = stats["scene_rows"]
    chars = list(stats.get("presence_grid", {}).keys())[:max_rows]
    lab_w = 120
    pad = 10
    cw = (W - lab_w - 2 * pad) / max(len(rows), 1)
    ch = 26
    H = 30 + ch * len(chars) + 10
    s = [f'<svg viewBox="0 0 {W} {H}" style="direction:ltr" role="img" aria-label="{E(title)}">']
    for j, r in enumerate(rows):
        x = (W - lab_w - pad - (j + 1) * cw) if lang == "ar" else (lab_w + pad + j * cw)
        s.append(f'<text x="{x + cw / 2}" y="18" font-size="11" text-anchor="middle" class="m">{r["n"]}</text>')
    for i, c in enumerate(chars):
        y = 28 + i * ch
        lx = W - pad if lang == "ar" else pad
        s.append(f'<text x="{lx}" y="{y + 17}" font-size="13" text-anchor="{"end" if lang == "ar" else "start"}">{E(c[:14])}</text>')
        for j, r in enumerate(rows):
            x = (W - lab_w - pad - (j + 1) * cw) if lang == "ar" else (lab_w + pad + j * cw)
            s.append(cell(c, r, x, y, cw, ch))
    s.append("</svg>")
    return _wrap(title, sub, "".join(s), legend)


def presence(stats, lang):
    t = TXT[lang]
    grid = stats.get("presence_grid") or {}
    if not grid:
        return ""

    def cell(c, r, x, y, cw, ch):
        v = grid.get(c, {}).get(str(r["n"]))
        if v is None:
            return f'<rect x="{x + 1}" y="{y + 1}" width="{cw - 2}" height="{ch - 2}" rx="3" fill="none" stroke="var(--line)" stroke-width="1"/>'
        fill = SEQ[0] if v == 0 else SEQ[1] if v == 1 else SEQ[2] if v <= 3 else SEQ[3]
        return f'<rect x="{x + 1}" y="{y + 1}" width="{cw - 2}" height="{ch - 2}" rx="3" fill="{fill}"><title>{E(c)} · {t["scene"]} {r["n"]} · {v} {t["lines"]}</title></rect>'
    legend = '<div class="lg">' + "".join(f'<span><i style="background:{c}"></i>{E(l)}</span>' for c, l in
                                          zip(SEQ, [t["silent"], "1 " + t["lines"], "2-3 " + t["lines"], "4+ " + t["lines"]])) + "</div>"
    return _grid(stats, cell, t["presence"], t["presence_sub"], legend, lang)


def dialect_map(stats, lang):
    t = TXT[lang]
    grid = stats.get("dialect_grid") or {}
    if not grid or stats.get("lang") != "ar":
        return ""
    used = sorted({v for row in grid.values() for v in row.values()}, key=list(DIALECT).index)

    def cell(c, r, x, y, cw, ch):
        v = grid.get(c, {}).get(str(r["n"]))
        if not v:
            return f'<rect x="{x + 1}" y="{y + 1}" width="{cw - 2}" height="{ch - 2}" rx="3" fill="none" stroke="var(--line)" stroke-width="1"/>'
        letter, name = DIALECT_LABEL[lang][v]
        return (f'<rect x="{x + 1}" y="{y + 1}" width="{cw - 2}" height="{ch - 2}" rx="3" fill="{DIALECT[v]}"><title>{E(c)} · {t["scene"]} {r["n"]} · {E(name)}</title></rect>'
                f'<text x="{x + cw / 2}" y="{y + 18}" font-size="12" text-anchor="middle" style="fill:#fff;font-weight:700">{letter}</text>')
    legend = '<div class="lg">' + "".join(f'<span><i style="background:{DIALECT[v]}"></i>{DIALECT_LABEL[lang][v][0]} = {E(DIALECT_LABEL[lang][v][1])}</span>' for v in used) + "</div>"
    return _grid(stats, cell, t["dialect"], t["dialect_sub"], legend, lang)


def strip_kind(r):
    import re
    ie, tm = (r.get("int_ext") or ""), (r.get("time") or "")
    if re.search(r"فجر|غروب|شروق|مساء|DAWN|DUSK|SUNSET|SUNRISE|EVENING", tm, re.I):
        return "dawn_dusk"
    night = re.search(r"ليل|منتصف الليل|NIGHT", tm, re.I)
    ext = re.search(r"خارج|EXT", ie, re.I) and not re.search(r"داخل|INT", ie, re.I)
    return ("ext" if ext else "int") + ("_night" if night else "_day")


def stripboard(stats, lang):
    t = TXT[lang]
    flags = {}
    for k, ns in (stats.get("production") or {}).items():
        for n in ns:
            flags.setdefault(n, []).append(k)
    mx = max((r["share"] for r in stats["scene_rows"]), default=1)
    rows = []
    for r in stats["scene_rows"]:
        col, _ = STRIP[strip_kind(r)]
        fl = "".join(f'<span class="fl">{E(FLAG[lang].get(k, k))}</span>' for k in flags.get(r["n"], []) if k != "night exterior")
        rows.append(f'<tr><td class="c" style="background:{col}" title="{E(STRIP[strip_kind(r)][1][lang])}"></td><td><b>{r["n"]}</b></td>'
                    f'<td>{E(r.get("int_ext") or "")} · {E(r.get("time") or "")}</td><td>{E(r.get("place") or "")}</td><td>{fl}</td>'
                    f'<td style="width:22%"><div class="bar" style="width:{r["share"] / mx * 100:.0f}%" title="{t["len"]} {r["share"]}%"></div></td></tr>')
    legend = '<div class="lg">' + "".join(f'<span><i style="background:{c}"></i>{E(l[lang])}</span>' for c, l in STRIP.values()) + "</div>"
    return _wrap(t["strip"], t["strip_sub"], '<table class="strip">' + "".join(rows) + "</table>", legend)


def voices_table(stats, lang):
    vs = stats.get("voices") or []
    if not vs:
        return ""
    ar = lang == "ar"
    head = ("الشخصية", "أسطر", "كلمات/سطر", "أسئلة", "تعجب", "اللهجة", "كلماتها") if ar else \
        ("Character", "Lines", "Words/line", "Questions", "Exclaims", "Dialect", "Own words")
    mx = max(v["avg_words"] for v in vs) or 1
    rows = "".join(
        f'<tr><td><b>{E(v["name"])}</b></td><td>{v["lines"]}</td><td style="white-space:nowrap">{v["avg_words"]} <div class="bar" style="width:{v["avg_words"] / mx * 70:.0f}%;display:inline-block;vertical-align:middle"></div></td>'
        f'<td>{int(v["questions"] * 100)}%</td><td>{int(v["exclaims"] * 100)}%</td><td>{E(DIALECT_LABEL[lang].get(v["dialect"], ("", "-"))[1] if v["dialect"] else "-")}</td>'
        f'<td>{E("، ".join(v["own_words"]) if ar else ", ".join(v["own_words"]))}</td></tr>' for v in vs)
    alike = stats.get("similar_voices") or []
    note = (("قد تتشابه أصوات: " if ar else "May sound alike: ") + ", ".join(f"{a} / {b}" for a, b in alike)) if alike else ""
    table = f'<table class="strip"><tr>{"".join(f"<td class=m><b>{h}</b></td>" for h in head)}</tr>{rows}</table>' + (f'<p class="sub">{E(note)}</p>' if note else "")
    return _wrap("أصوات الشخصيات" if ar else "Character voices",
                 "كيف تتكلم كل شخصية: طول السطر، الأسئلة، التعجب، اللهجة، والكلمات الخاصة بها." if ar else
                 "How each character talks: line length, questions, exclamations, dialect and their own words.", table)


ARC = ["#2a78d6", "#eb6834", "#1baf7a"]  # the three validated categorical colours


def arc_chart(stats, notes, lang):
    arcs = (notes or {}).get("arcs") or {}
    if not arcs:
        return ""
    ar = lang == "ar"
    X = _x(lang, pad=50)
    H, top, bot = 250, 24, 200
    Y = lambda v: (top + bot) / 2 - v / 2 * (bot - top) / 2  # noqa: E731
    pos = {str(r["n"]): r["pos"] + r["share"] / 2 for r in stats["scene_rows"]}
    s = [f'<svg viewBox="0 0 {W} {H}" style="direction:ltr" role="img" aria-label="arcs">']
    for v in (-2, -1, 0, 1, 2):
        s.append(f'<line x1="{X(0)}" y1="{Y(v)}" x2="{X(100)}" y2="{Y(v)}" stroke="{GRID}" stroke-width="{1.5 if v == 0 else 1}"/>')
        s.append(f'<text x="{X(0) + (16 if ar else -16)}" y="{Y(v) + 4}" font-size="11" text-anchor="middle" class="m">{v:+d}</text>'.replace("+0", "0"))
    rows = []
    for i, (name, a) in enumerate(list(arcs.items())[:3]):
        col = ARC[i]
        pts = sorted(((pos[k], v["value"], k, v.get("want")) for k, v in a["points"].items() if k in pos), key=lambda p: p[0] if not ar else -p[0])
        pts = sorted(pts, key=lambda p: float(p[2]))
        if not pts:
            continue
        path = " ".join(f"{X(x)},{Y(v)}" for x, v, _, _ in pts)
        s.append(f'<polyline fill="none" stroke="{col}" stroke-width="2" points="{path}"/>')
        for x, v, k, want in pts:
            tip = f"{name} · {('مشهد' if ar else 'scene')} {k} · {v:+d}" + (f" · {want}" if want else "")
            s.append(f'<circle cx="{X(x)}" cy="{Y(v)}" r="5" fill="{col}" stroke="var(--card)" stroke-width="2"><title>{E(tip)}</title></circle>')
        lx, lv = X(pts[-1][0]), pts[-1][1]
        s.append(f'<text x="{lx + (-8 if ar else 8)}" y="{Y(lv) - 8}" font-size="12.5" text-anchor="{"end" if ar else "start"}" style="font-weight:700">{E(name)}</text>')
        rows.append(f'<span><i style="background:{col}"></i><b style="background:none;color:var(--ink);width:auto">{E(name)}</b>: {E(a["start"])} ← {E(a["end"])}</span>'
                    if ar else f'<span><i style="background:{col}"></i><b style="background:none;color:var(--ink);width:auto">{E(name)}</b>: {E(a["start"])} → {E(a["end"])}</span>')
    for r in stats["scene_rows"]:
        s.append(f'<text x="{X(r["pos"] + r["share"] / 2)}" y="{bot + 22}" font-size="11" text-anchor="middle" class="m">{r["n"]}</text>')
    s.append("</svg>")
    title = "أقواس الشخصيات" if ar else "Character arcs"
    sub = "الحال الداخلية لكل شخصية رئيسية على طول الفيلم (−٢ أدنى، +٢ أعلى)، وما تريده في البداية والنهاية." if ar else \
        "Each main character's inner state across the film (-2 lowest, +2 highest), and what they want at the start and the end."
    return _wrap(title, sub, "".join(s), '<div class="lg" style="flex-direction:column;gap:4px">' + "".join(rows) + "</div>")


def all_charts(stats, notes, structure, marks, lang, prev=None):
    return [c for c in (beat_map(stats, notes, structure, marks, lang), tension_curve(stats, notes, structure, lang, prev),
                        arc_chart(stats, notes, lang), presence(stats, lang), dialect_map(stats, lang), voices_table(stats, lang), stripboard(stats, lang)) if c]


def to_pngs(fragments, out_dir, lang, stem="chart"):
    """Render chart fragments to PNG (light theme, 2x) for Word, one file per chart."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "zamakan-design-system" / "scripts"))
    from _common import launch_chromium
    from playwright.sync_api import sync_playwright
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    page_html = (f'<!doctype html><html lang="{lang}" dir="{"rtl" if lang == "ar" else "ltr"}"><head><meta charset="utf-8">'
                 '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet">'
                 '<style>:root{--ink:#1d1b18;--muted:#5e5a53;--line:#e4dfd5;--card:#ffffff}body{margin:0;background:#fff;color:var(--ink);'
                 'font:15px/1.6 "IBM Plex Sans Arabic","Amiri",sans-serif;width:900px;padding:8px}' + CSS + '</style></head><body>'
                 + "".join(fragments) + "</body></html>")
    tmp = out_dir / f".{stem}.html"
    tmp.write_text(page_html, encoding="utf-8")
    files = []
    with sync_playwright() as p:
        b = launch_chromium(p)
        pg = b.new_page(viewport={"width": 920, "height": 800}, device_scale_factor=2)
        pg.goto(tmp.resolve().as_uri())
        pg.wait_for_timeout(500)
        for i, el in enumerate(pg.query_selector_all(".viz")):
            f = out_dir / f"{stem}-{i + 1}.png"
            el.screenshot(path=str(f))
            files.append(f)
        b.close()
    tmp.unlink(missing_ok=True)
    return files
