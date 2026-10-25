#!/usr/bin/env python3
"""Read a screenplay draft (Word, Fountain/Hekaya or plain text, Arabic or English) into script.json: each line typed
as scene heading, action, character, parenthetical, dialogue, transition or section, scenes numbered, and a short list
of lines it could not type with confidence. Claude only looks at that list, never at the whole script, to fix typing.

Usage:
  python parse_script.py <draft.docx|.fountain|.txt> --out script.json [--lang ar|en]
  python parse_script.py <draft> --out script.json --fix fixes.json    # {"<line index>": "<type>"} for the unsure lines

How lines are typed (most certain first): Word paragraph styles (the template's, or Final Draft's when exported to
Word) → Fountain/Hekaya marks (. heading, @ character, > transition, ! action, # section, = synopsis, [[notes]]) →
the screenplay words in references/vocabulary.json (داخلي/خارجي، ليل/نهار، قطع إلى…) → layout (a short line followed by
speech, names that come back as cues). In Arabic, a "name: speech" line is split into cue and dialogue when the name
is used as a cue more than once.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _screenplay as S  # noqa: E402

V = S.VOCAB
END_PUNCT = re.compile(r"[.!?؟،,:;…]$")


def _alts(words):
    return "|".join(re.escape(w).replace(r"\ ", r"\s*") for w in sorted(words, key=len, reverse=True))


IE_AR = _alts(V["int_ext"]["ar"])
IE_EN = _alts(V["int_ext"]["en"])
HEADING_RE = re.compile(
    rf"^\s*(?:(?:مشهد|م)\s*[\d٠-٩]+\s*[:.\-–)]?\s*)?(?:[\d٠-٩]+\s*[.\-–)]\s*)?(?:(?P<ar>{IE_AR})(?![؀-ۿ])|(?P<en>{IE_EN})(?=[\s.]))",
    re.I)
SCENE_WORD_RE = re.compile(r"^\s*(?:مشهد|م)\s*[\d٠-٩]+\s*[:.\-–]?\s*", re.I)
TIME_WORDS = sorted(V["time"]["ar"] + V["time"]["en"], key=len, reverse=True)
TRANS = [t.strip(":.").strip() for t in V["transitions"]["ar"] + V["transitions"]["en"]]
TRANS_RE = re.compile(rf"^[\s\-–—]*(?:{_alts(TRANS)})[\s:.\-–—]*$", re.I)
EXT_RE = re.compile(rf"\s*\((?P<ext>{_alts(V['extensions']['ar'] + V['extensions']['en'])})\)\s*$", re.I)
TITLE_KEYS = {k.lower(): field for field, keys in V["title_keys"].items() for k in keys}


def read_lines(path):
    """Lines plus any element type the source already states (Word styles)."""
    path = Path(path)
    if path.suffix.lower() == ".docx":
        from docx import Document
        out = []
        for p in Document(path).paragraphs:
            style = (p.style.name or "").lower() if p.style is not None else ""
            typed = S.STYLE_TO_TYPE.get(style)
            text = p.text.replace("‏", "").replace("‎", "").rstrip()
            if style.startswith(("heading", "title", "list")) and typed is None:
                typed = "section" if text else None
            for i, part in enumerate(text.split("\n")):
                out.append((part, typed))
        return out
    text = path.read_text(encoding="utf-8-sig")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)  # Fountain boneyard
    return [(ln.rstrip().replace("‏", "").replace("‎", ""), None) for ln in text.replace("\r\n", "\n").split("\n")]


def title_page(lines):
    """Fountain-style 'Key: value' lines at the very top (Title:, العنوان:, تأليف: …)."""
    meta, i = {}, 0
    while i < len(lines) and lines[i][0].strip():
        m = re.match(r"^\s*([^:]{2,25}):\s*(.*)$", lines[i][0])
        if not m or m.group(1).strip().lower() not in TITLE_KEYS:
            return {}, 0
        meta[TITLE_KEYS[m.group(1).strip().lower()]] = m.group(2).strip()
        i += 1
    return meta, i if meta else 0


def heading_parts(text):
    """داخلي - بيت سالم - ليل → {int_ext, place, time}; works for 'مشهد ٣: ليل - داخلي - بيت' too."""
    t = SCENE_WORD_RE.sub("", text.strip().lstrip("."))
    t = re.sub(r"^[\d٠-٩]+\s*[.\-–)]\s*", "", t)
    m = HEADING_RE.match(t)
    if m and m.group("en"):  # English: INT. PLACE - TIME (the dot after INT/EXT is not a separator)
        rest = [x.strip() for x in re.split(r"\s+[-–—]\s+", t[m.end():].strip(" .")) if x.strip()]
        tm = rest.pop() if len(rest) > 1 and any(re.fullmatch(re.escape(w), rest[-1], re.I) for w in TIME_WORDS) else None
        return {"int_ext": m.group("en").strip(), "place": " - ".join(rest) or None, "time": tm}
    parts = [p.strip() for p in re.split(r"\s+[-–—]\s+|\s*[-–—]\s*(?=\S)|\s{2,}|\s*\.\s+", t) if p.strip()]
    ie = tm = None
    rest = []
    for p in parts:
        m = HEADING_RE.match(p)
        if not ie and m:
            ie = m.group(0).strip()
            after = p[m.end():].strip(" .-–")
            if after:
                rest.append(after)
            continue
        if not tm and any(re.fullmatch(re.escape(w), p, re.I) for w in TIME_WORDS):
            tm = p
            continue
        rest.append(p)
    return {"int_ext": ie, "place": " - ".join(rest) or None, "time": tm}


def classify(lines, lang):
    els, unsure = [], []
    n = len(lines)

    def nxt(i):
        return lines[i + 1][0].strip() if i + 1 < n else ""

    def prev_blank(i):
        return i == 0 or not lines[i - 1][0].strip()

    cue_counts = Counter()
    for i, (ln, typed) in enumerate(lines):  # first pass: candidate cue names
        s = ln.strip()
        if typed == "character":
            cue_counts[EXT_RE.sub("", s).strip()] += 1
        elif s and typed is None and prev_blank(i) and nxt(i) and len(s) <= 30 and len(s.split()) <= 4 and not END_PUNCT.search(EXT_RE.sub("", s).strip()):
            if not HEADING_RE.match(s) and not TRANS_RE.match(s):
                cue_counts[EXT_RE.sub("", s.lstrip("@")).strip()] += 1
        m = re.match(r"^([^:：]{1,25})[:：]\s*\S", s)
        if m and typed is None and len(m.group(1).split()) <= 3:
            cue_counts[m.group(1).strip()] += 1
    known = {c for c, k in cue_counts.items() if k >= 2}

    in_dialogue = False
    for i, (ln, typed) in enumerate(lines):
        s = ln.strip()
        if not s:
            in_dialogue = False
            continue
        if s.startswith("[[") and s.endswith("]]"):
            els.append({"type": "note", "text": s[2:-2].strip()})
            continue
        if typed:
            t = typed
            if t == "character":
                in_dialogue = True
            elif t not in ("parenthetical", "dialogue"):
                in_dialogue = False
            els.append({"type": t, "text": s, "src": i})
            continue
        if s.startswith("#"):
            els.append({"type": "section", "text": s.lstrip("#").strip(), "level": len(s) - len(s.lstrip("#")), "src": i})
            continue
        if s.startswith("="):
            els.append({"type": "synopsis", "text": s.lstrip("=").strip(), "src": i})
            continue
        if s.startswith(">") and s.endswith("<"):
            els.append({"type": "centered", "text": s[1:-1].strip(), "src": i})
            continue
        if s.startswith(">"):
            els.append({"type": "transition", "text": s[1:].strip(), "src": i})
            in_dialogue = False
            continue
        if s.startswith("!"):
            els.append({"type": "action", "text": s[1:].strip(), "src": i})
            continue
        if s.startswith(".") and not s.startswith(".."):
            els.append({"type": "scene_heading", "text": s[1:].strip(), "src": i})
            in_dialogue = False
            continue
        if s.startswith("@"):
            els.append({"type": "character", "text": s[1:].strip(), "src": i})
            in_dialogue = True
            continue
        if in_dialogue:
            if s.startswith("(") and s.endswith(")"):
                els.append({"type": "parenthetical", "text": s, "src": i})
            else:
                els.append({"type": "dialogue", "text": s, "src": i})
            continue
        if HEADING_RE.match(s) or SCENE_WORD_RE.match(s):
            els.append({"type": "scene_heading", "text": s, "src": i})
            continue
        if TRANS_RE.match(s) or (lang == "en" and s.isupper() and s.endswith("TO:")):
            els.append({"type": "transition", "text": s.strip(" -–—"), "src": i})
            continue
        name = EXT_RE.sub("", s).strip()
        m = re.match(r"^([^:：]{1,25})[:：]\s*(.+)$", s)
        if m and m.group(1).strip() in known:  # "سالم: كلام" on one line
            els.append({"type": "character", "text": m.group(1).strip(), "src": i})
            els.append({"type": "dialogue", "text": m.group(2).strip(), "src": i})
            continue
        looks_cue = prev_blank(i) and nxt(i) and len(s) <= 30 and len(s.split()) <= 4 and not END_PUNCT.search(name)
        if lang == "en" and looks_cue and re.search(r"[A-Z]", name) and name == name.upper():
            els.append({"type": "character", "text": s, "src": i})
            in_dialogue = True
            continue
        if looks_cue and name in known:
            els.append({"type": "character", "text": s, "src": i})
            in_dialogue = True
            continue
        if looks_cue:  # a short lone line before text: a one-off cue, or a short action line?
            els.append({"type": "action", "text": s, "src": i})
            unsure.append({"i": len(els) - 1, "text": s, "guess": "action", "maybe": "character", "next": nxt(i)[:60]})
            continue
        els.append({"type": "action", "text": s, "src": i})
    return els, unsure


def number_scenes(els, lang):
    scenes, cur = [], None
    for idx, e in enumerate(els):
        if e["type"] == "scene_heading":
            cur = {"n": len(scenes) + 1, "heading": e["text"], **heading_parts(e["text"]), "start": idx, "end": idx}
            e["scene"] = cur["n"]
            scenes.append(cur)
        elif cur:
            cur["end"] = idx
            e["scene"] = cur["n"]
        if e["type"] == "character":
            m = EXT_RE.search(e["text"])
            if m:
                e["ext"] = m.group("ext")
                e["name"] = EXT_RE.sub("", e["text"]).strip()
            else:
                e["name"] = e["text"].strip().rstrip(":：")
    return scenes


def parse(path, lang=None, fixes=None):
    lines = read_lines(path)
    meta, skip = title_page(lines)
    if not meta and Path(path).suffix.lower() == ".docx":  # our own formatted Word file: centered title page
        cent = [(i, t) for i, (t, ty) in enumerate(lines) if ty == "centered" and t.strip()]
        first_scene = next((i for i, (t, ty) in enumerate(lines) if ty == "scene_heading"), len(lines))
        cent = [c for c in cent if c[0] < first_scene]
        if cent:
            meta["title"] = cent[0][1].strip()
            for _, t in cent[1:]:
                k, _, v = t.partition(":")
                key = TITLE_KEYS.get(k.strip().lower()) or {"written by": "author", "التاريخ": "draft_date", "المسودة": "draft", "based on": "credit"}.get(k.strip().lower())
                if key:
                    meta[key] = v.strip()
            skip = cent[-1][0] + 1
    body = lines[skip:]
    lang = lang or ("ar" if S.is_arabic(" ".join(t for t, _ in body[:400])) else "en")
    els, unsure = classify(body, lang)
    for k, t in (fixes or {}).items():
        k = int(k)
        if 0 <= k < len(els):
            els[k]["type"] = t
    if fixes:  # re-flow dialogue after fixed cues
        for i, e in enumerate(els):
            if e["type"] == "character" and i + 1 < len(els) and els[i + 1]["type"] == "action" and els[i + 1].get("src") == e.get("src", -9) + 1:
                els[i + 1]["type"] = "dialogue"
        unsure = [u for u in unsure if str(u["i"]) not in {str(k) for k in fixes}]
    scenes = number_scenes(els, lang)
    return {"schema": "zamakan-script/1", "source": str(path), "lang": lang, "title_page": meta, "scenes": scenes,
            "elements": els, "unsure": unsure}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft")
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", choices=["ar", "en"])
    ap.add_argument("--fix", help="JSON {element index: type} for unsure lines")
    a = ap.parse_args()
    fixes = json.loads(Path(a.fix).read_text(encoding="utf-8")) if a.fix else None
    sc = parse(a.draft, a.lang, fixes)
    Path(a.out).write_text(json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8")
    types = Counter(e["type"] for e in sc["elements"])
    print(f"{sc['lang']} · {len(sc['scenes'])} scenes · " + ", ".join(f"{k} {v}" for k, v in types.most_common()) + f" → {a.out}")
    if sc["unsure"]:
        print(f"{len(sc['unsure'])} unsure line(s): decide each, then rerun with --fix (e.g. {{\"{sc['unsure'][0]['i']}\": \"character\"}})")
        for u in sc["unsure"][:30]:
            print(f"  [{u['i']}] {u['text']!r} → guessed {u['guess']}, maybe {u['maybe']} (next: {u['next']!r})")


if __name__ == "__main__":
    main()
