#!/usr/bin/env python3
"""Plain words → film language + a search plan per source (the step that makes this better than typing into Vimeo).

Usage: python expand.py "the feeling of time slowing down in a crowd" [--json] [--out plan.json]
       python expand.py "dolly zoom" ; python expand.py "صحراء عند الفجر، وحدة وملحمية"

Matches the request against techniques.json (names, English/Arabic synonyms) and moods.json (feeling words → techniques).
What is left (nouns like 'desert', 'crowd', 'coffee') becomes the subject. Prints the techniques with why each matched,
and ready-to-run searches: Eyecannndy technique pages and search, Film-Grab / Shot.cafe for the subject, YouTube queries,
and web-search queries for Vimeo and the trade/motion sites. The agent judges and edits the plan; it is a start, not a rule.
"""
import argparse
import json
import re
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared import ar_variants, moods, norm, techniques  # noqa: E402

STOP = set(norm("the a an of in on at with and or for to by from like feel feeling look looking shot shots scene scenes "
                "down up slowing slow getting gets short shorts about i'm im me my inspire inspiration motivate films movies cinema watch "
                "أنا انا اشاهد أشاهد افلام أفلام ابغى أبغى ابي أبي "
                "reference references cinematic film films video videos ad ads commercial commercials something about some "
                "want need show me find give we our that this very really kind sort style effect technique "
                "في من على عند مع عن الى إلى و أو لقطة لقطات مشهد مشاهد مراجع مرجع اعلان إعلان فيلم احساس إحساس شعور مثل نريد ابغى").split())


MOOD_TOP = 3  # techniques taken per matched mood: more floods the plan


def _has(q, tokens, phrase):
    """phrase in the query; single Arabic words also match with و/ال prefixes and endings (ملحمي ~ وملحمية)."""
    if f" {phrase} " in q:
        return True
    if " " not in phrase and re.search("[\u0600-\u06FF]", phrase) and len(phrase) >= 4:
        return any(v.startswith(phrase) for t in tokens for v in ar_variants(t))
    return False


def match(text):
    q = f" {norm(text)} "
    tokens = q.split()
    found, used = {}, set()
    for t in techniques():
        names = [t["id"].replace("-", " "), t["name"], t["name_ar"], *t["synonyms"]]
        for n in sorted({norm(x) for x in names if x}, key=len, reverse=True):
            if len(n) > 2 and _has(q, tokens, n):
                found.setdefault(t["id"], {"technique": t, "why": f"named: '{n}'"})
                used.update(n.split())
                used.update(t for t in tokens if any(v.startswith(n) for v in ar_variants(t)))
                break
    for m in moods():
        for w in sorted({norm(x) for x in m["words"]}, key=len, reverse=True):
            if len(w) > 2 and _has(q, tokens, w):
                if not m.get("keeps_subject"):
                    used.update(w.split())
                    used.update(t for t in tokens if any(v.startswith(w) for v in ar_variants(t)))
                for tid in m["techniques"][:MOOD_TOP]:
                    found.setdefault(tid, {"technique": next(t for t in techniques() if t["id"] == tid), "why": f"mood '{m['id']}' (from '{w}')"})
                break
    subject = [w for w in tokens if w not in used and w not in STOP and len(w) > 2 and not (ar_variants(w) & STOP)]
    return list(found.values()), subject


INSPIRE = re.compile(r"\b(inspire|inspiration|motivate|watch|watchlist|what to watch|cinephile|study)\b|إلهام|الهام|أشاهد|اشاهد|مشاهدة|يحفز|تحفيز", re.I)


def roles_of(text):
    import json as _j
    from _shared import REFS
    q = f" {norm(text)} "
    out = []
    for r in _j.loads((REFS / "roles.json").read_text(encoding="utf-8"))["roles"]:
        if any(f" {norm(w)} " in q or (len(norm(w)) > 4 and norm(w) in q) for w in r["words"]):
            out.append(r["id"])
    return out


def plan(text, max_tech=8):
    roles = roles_of(text)
    hits, subject = match(text)
    role_words = {norm(w) for w in sum((r for r in [[]]), [])}
    if roles:
        import json as _j
        from _shared import REFS
        role_words = {t for r in _j.loads((REFS / "roles.json").read_text(encoding="utf-8"))["roles"] for w in r["words"] for t in norm(w).split()}
        subject = [w for w in subject if w not in role_words and not any(v in role_words for v in ar_variants(w))]
    named = [h for h in hits if h["why"].startswith("named")]
    hits = named + [h for h in hits if not h["why"].startswith("named")]
    hits = hits[:max(max_tech, len(named))]
    subj = " ".join(subject)
    eye_slugs = list(dict.fromkeys(s for h in hits for s in h["technique"]["eyecannndy"]))[:8]
    yt, web = [], []
    for h in hits[:6]:
        term = h["technique"]["search_terms"][0]
        yt.append(f"{term} {subj}".strip())
        web.append(f'site:vimeo.com "{h["technique"]["name"].split(" (")[0].split(" /")[0]}" {subj}'.strip())
    if subj:
        yt.append(f"{subj} cinematic")
        web += [f"site:vimeo.com {subj} cinematography", f"site:directorsnotes.com {subj}", f"{subj} commercial cinematography breakdown"]
    mode = "inspire" if (roles and INSPIRE.search(text)) or INSPIRE.search(text) and not hits else None
    return {
        "request": text,
        "mode_hint": mode or ("effect" if any(h["why"].startswith("named") for h in hits) and not subj else "subject"),
        "roles": roles,
        "subject": subj,
        "techniques": [{"id": h["technique"]["id"], "name": h["technique"]["name"], "name_ar": h["technique"]["name_ar"],
                        "why": h["why"], "feeling": h["technique"]["feeling"]} for h in hits],
        "searches": {
            "eyecannndy_technique": eye_slugs,
            "eyecannndy_search": [x for x in [subj] + [h["technique"]["name"].split(" (")[0] for h in hits[:3]] if x],
            "filmgrab": subject[:3], "shotcafe": subject[:3],
            "youtube": yt[:8], "web_search": web[:8],
            "shortoftheweek": [subj] if subj else [],
            "docs": [subj] if subj else [],  # discover_shots.py docs: documentary shorts, doc channels, YouTube
        },
        "next": "Run discover_shots.py for each search, then rank and pick. Add your own terms: the dictionary can't know every subject.",
    }


def main():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    p = plan(a.text)
    if a.out:
        Path(a.out).write_text(json.dumps(p, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if a.json:
        print(json.dumps(p, ensure_ascii=False, indent=1))
        return
    print(f"mode: {p['mode_hint']}" + (f" · roles: {', '.join(p['roles'])}" if p["roles"] else ""))
    print(f"subject: {p['subject'] or '(none: technique-only request)'}")
    if re.search("[\u0600-\u06FF]", p["subject"]):
        print("  (Arabic subject: also search it in English; Film-Grab, Shot.cafe and Eyecannndy are English-only)")
    print("techniques:")
    for t in p["techniques"]:
        print(f"  {t['id']:<20} {t['name']} · {t['name_ar']}  ({t['why']})")
    if not p["techniques"]:
        print("  none matched: describe the look in film terms yourself (see references/film-language.md) or search the subject")
    for k, v in p["searches"].items():
        if v:
            print(f"{k}: " + " | ".join(v))


if __name__ == "__main__":
    main()
