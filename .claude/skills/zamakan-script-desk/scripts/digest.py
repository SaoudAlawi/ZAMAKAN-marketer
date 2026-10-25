#!/usr/bin/env python3
"""A compact read of a parsed script for the reader: one line per scene plus the measurable facts (length, who
speaks, day/night, locations, dialect per character, action lines that narrate thoughts, production flags, where the
chosen structure's beats fall). About 1-2k tokens for a short, so Claude reads this first and opens only the scenes
that need a closer look (show.py).

Usage:
  python digest.py script.json [--structure three-act] [--out stats.json]
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _screenplay as S  # noqa: E402

DIALECTS = json.loads((S.SKILL / "references" / "dialects.json").read_text(encoding="utf-8"))["varieties"]
TELLING = re.compile(r"(?<![؀-ۿ])(?:[يت]?تذكر|[يت]شعر|[يت]فكر|[يت]درك|[يت]عرف أن|[يت]تمنى|[يت]حلم|[يت]ساءل|[يت]خيل|في داخله|في داخلها|"
                     r"remembers|feels|thinks|realizes|realises|knows that|wonders|wishes|deep down)", re.I)
PRODUCTION = {
    "night exterior": None,
    "water/sea": r"بحر|البحر|قارب|قوارب|موج|أمواج|سفينة|غوص|sea|ocean|boat|wave|underwater",
    "weather/FX": r"عاصفة|مطر|برق|رعد|حريق|انفجار|نار|دخان|storm|rain|lightning|fire|explosion|smoke",
    "crowd": r"حشد|جمهور|عشرات|مئات|عشرة|زحام|crowd|dozens|hundreds|extras",
    "vehicles/stunts": r"سيارة|مطاردة|حادث|تصادم|يتحطم|تتحطم|يسقط|car chase|crash|stunt|falls",
    "animals": r"جمل|حصان|خيل|كلب|قطة|طيور|ماعز|camel|horse|dog|cat|birds|goat",
    "children": r"طفل|طفلة|أطفال|رضيع|child|kid|baby",
}
WORD = re.compile(r"[\w؀-ۿ]+")


def words(text):
    return WORD.findall(text)


def norm_word(w):
    w = re.sub("[ً-ْ]", "", w)
    return w[1:] if len(w) > 3 and w[0] in "وف" else w


def dialect_scores(text):
    toks = [norm_word(w) for w in words(text)]
    joined = " " + " ".join(toks) + " "
    out = {}
    for k, v in DIALECTS.items():
        hits = {w for w in v["words"] if f" {norm_word(w)} " in joined}
        if hits:
            out[k] = sorted(hits)
    return out


def digest(sc, structure=None):
    els, lang = sc["elements"], sc["lang"]
    scenes = sc["scenes"]
    by_scene = defaultdict(list)
    for e in els:
        if e.get("scene"):
            by_scene[e["scene"]].append(e)
    size = {n: sum(len(e["text"]) for e in by_scene[n]) + 40 for n in by_scene}
    total = sum(size.values()) or 1
    pages = (sc.get("format") or {}).get("pages")
    lines, wc, scenes_of = Counter(), Counter(), defaultdict(set)
    speech_words = action_words = 0
    longest = (0, None, None)
    dial = defaultdict(lambda: defaultdict(dict))  # character -> scene -> variety hits
    cur = None
    for e in els:
        if e["type"] == "character":
            cur = e.get("name", e["text"])
            lines[cur] += 1
            scenes_of[cur].add(e.get("scene"))
        elif e["type"] == "dialogue" and cur:
            n = len(words(e["text"]))
            wc[cur] += n
            speech_words += n
            if n > longest[0]:
                longest = (n, cur, e.get("scene"))
            if lang == "ar":
                for k, hits in dialect_scores(e["text"]).items():
                    dial[cur][e.get("scene")].setdefault(k, set()).update(hits)
        elif e["type"] == "action":
            action_words += len(words(e["text"]))
    # protagonist: the character present in the most scenes (speaking or named in the action), then most lines
    present = Counter()
    for c in lines:
        for n, es in by_scene.items():
            if c in scenes_of and n in scenes_of[c] or any(e["type"] == "action" and c in e["text"] for e in es):
                present[c] += 1
    hero = max(lines, key=lambda c: (present[c], lines[c])) if lines else None
    # per scene lines
    rows, cum = [], 0
    for s in scenes:
        n = s["n"]
        start = cum / total * 100
        cum += size.get(n, 40)
        who = []
        for e in by_scene[n]:
            if e["type"] == "character" and e.get("name") not in who:
                who.append(e.get("name"))
        first = next((e["text"] for e in by_scene[n] if e["type"] == "action"), "")
        rows.append({"n": n, "pos": round(start), "share": round(size.get(n, 40) / total * 100, 1), "int_ext": s.get("int_ext"),
                     "place": s.get("place"), "time": s.get("time"), "speakers": who, "first": first[:70],
                     "dialogue_lines": sum(e["type"] == "dialogue" for e in by_scene[n])})
    # flags
    telling = [{"scene": e.get("scene"), "text": e["text"][:90]} for e in els if e["type"] == "action" and TELLING.search(e["text"])]
    prod = defaultdict(list)
    for r in rows:
        txt = " ".join(e["text"] for e in by_scene[r["n"]] if e["type"] in ("action", "scene_heading"))
        night = r["time"] and re.search(r"ليل|منتصف الليل|NIGHT", r["time"], re.I)
        if night and r["int_ext"] and re.search(r"خارج|EXT", r["int_ext"], re.I) and not re.search(r"داخل|INT", r["int_ext"], re.I):
            prod["night exterior"].append(r["n"])
        for k, rx in PRODUCTION.items():
            if rx and re.search(rx, txt, re.I):
                prod[k].append(r["n"])
    mixed = []
    for who, per in dial.items():
        dom = {}
        for scn, hits in per.items():
            best = max(hits.items(), key=lambda kv: len(kv[1]))
            if len(best[1]) >= 2 or len(hits) == 1 and len(best[1]) >= 1:
                dom[scn] = best[0]
        kinds = set(dom.values())
        if len(kinds) > 1:
            mixed.append({"character": who, "by_scene": {str(k): v for k, v in sorted(dom.items(), key=lambda kv: kv[0] or 0)}})
    repeats = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if a["place"] and a["place"] == b["place"] and a["speakers"] and set(a["speakers"]) == set(b["speakers"]):
                repeats.append([a["n"], b["n"]])
    beats = []
    if structure:
        st = next((x for x in S.STRUCTURES["structures"] if x["id"] == structure), None)
        if st:
            for b in st["beats"]:
                inside = [r["n"] for r in rows if b["at"] <= r["pos"] + r["share"] / 2 <= b["end"]] or \
                         [min(rows, key=lambda r: abs(r["pos"] - b["at"]))["n"]]
                beats.append({"beat": b["id"], "name": b["name_ar"] if lang == "ar" else b["name"], "at": b["at"], "end": b["end"], "scenes": inside})
    sections = [{"text": e["text"], "scene_after": next((x.get("scene") for x in els[i:] if x.get("scene")), None)}
                for i, e in enumerate(els) if e["type"] == "section"]
    locs = Counter(r["place"] for r in rows if r["place"])
    return {
        "title": (sc.get("title_page") or {}).get("title"), "lang": lang, "pages": pages, "scenes": len(scenes),
        "est_minutes": pages, "locations": len(locs), "top_locations": locs.most_common(5),
        "int_ext": Counter((r["int_ext"] or "?") for r in rows).most_common(),
        "time_of_day": Counter((r["time"] or "?") for r in rows).most_common(),
        "speaking_roles": len(lines), "one_line_roles": [c for c, k in lines.items() if k == 1],
        "characters": [{"name": c, "lines": lines[c], "words": wc[c], "scenes": len(scenes_of[c])} for c, _ in lines.most_common()],
        "protagonist_guess": hero, "presence": dict(present), "scenes_without_protagonist": [r["n"] for r in rows if hero and hero not in r["speakers"]
                                                                  and hero not in " ".join(e["text"] for e in by_scene[r["n"]])],
        "dialogue_share": round(speech_words / ((speech_words + action_words) or 1) * 100),
        "longest_speech": {"words": longest[0], "character": longest[1], "scene": longest[2]},
        "longest_scenes": sorted(rows, key=lambda r: -r["share"])[:3] and [r["n"] for r in sorted(rows, key=lambda r: -r["share"])[:3]],
        "silent_scenes": [r["n"] for r in rows if not r["dialogue_lines"]],
        "telling_lines": telling, "production": dict(prod), "dialect_mix": mixed, "same_place_same_people": repeats,
        "beats": beats, "sections": sections, "scene_rows": rows,
    }


def show(d):
    ar = d["lang"] == "ar"
    out = [f"# {d['title'] or 'script'} · {d['lang']} · {d['scenes']} scenes · {d['pages'] or '?'} pages (≈{d['est_minutes'] or '?'} min)",
           f"locations {d['locations']} (top: {', '.join(f'{p}×{n}' for p, n in d['top_locations'])}) · "
           f"int/ext {', '.join(f'{k} {v}' for k, v in d['int_ext'])} · time {', '.join(f'{k} {v}' for k, v in d['time_of_day'])}",
           f"speaking roles {d['speaking_roles']} (one line only: {', '.join(d['one_line_roles']) or '-'}) · dialogue {d['dialogue_share']}% of words · "
           f"longest speech {d['longest_speech']['words']} words ({d['longest_speech']['character']}, S{d['longest_speech']['scene']})",
           "characters: " + "; ".join(f"{c['name']} {c['lines']} lines/{c['words']}w/{c['scenes']} sc" for c in d["characters"][:8]),
           f"protagonist (in most scenes): {d['protagonist_guess']} · absent from scenes {d['scenes_without_protagonist'] or '-'}",
           "", "## scenes (S | position% | share% | heading | speakers | first action)"]
    for r in d["scene_rows"]:
        out.append(f"S{r['n']} | {r['pos']}% | {r['share']}% | {r['int_ext'] or ''} - {r['place'] or ''} - {r['time'] or ''} | "
                   f"{', '.join(r['speakers']) or '(silent)'} | {r['first']}")
    out.append("")
    out.append("## flags (hints to check, not verdicts)")
    if d["telling_lines"]:
        out.append("action lines that narrate thoughts/feelings: " + " · ".join(f"S{t['scene']}: {t['text'][:60]}" for t in d["telling_lines"][:8]))
    if d["dialect_mix"]:
        out.append("dialect changes: " + " · ".join(f"{m['character']} {m['by_scene']}" for m in d["dialect_mix"]))
    if d["same_place_same_people"]:
        out.append("same place + same speakers (possible repeat): " + ", ".join(f"S{a}/S{b}" for a, b in d["same_place_same_people"]))
    if d["silent_scenes"]:
        out.append(f"scenes with no dialogue: {d['silent_scenes']}")
    if d["production"]:
        out.append("production: " + " · ".join(f"{k} {v}" for k, v in d["production"].items()))
    if d["beats"]:
        out.append("")
        out.append("## where the structure's beats fall (by length)")
        out += [f"{b['name']} ({b['at']}-{b['end']}%): S{', S'.join(map(str, b['scenes']))}" for b in d["beats"]]
    if d["sections"]:
        out.append("writer's sections: " + " · ".join(f"{s['text']} → S{s['scene_after']}" for s in d["sections"]))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script")
    ap.add_argument("--structure")
    ap.add_argument("--out")
    a = ap.parse_args()
    sc = json.loads(Path(a.script).read_text(encoding="utf-8"))
    d = digest(sc, a.structure)
    if a.out:
        Path(a.out).write_text(json.dumps(d, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    print(show(d))


if __name__ == "__main__":
    main()
