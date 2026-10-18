#!/usr/bin/env python3
"""Checked facts for a film from Wikidata + Wikipedia: year, director, writer, cinematographer, editor, composer,
production designer, runtime, countries, Arabic title, summary and the Wikipedia page. Never type credits from memory:
look them up here (even well-known ones are easy to get wrong).

Usage: python film_facts.py "In the Mood for Love" [--year 2000] [--craft] [--json] [--out cand.jsonl]
  --craft  also pulls how-it-was-made sentences (camera, lenses, light, editing, sound, casting) from Wikipedia
       python film_facts.py --titles titles.txt --out cand.jsonl        # one "Title | year" per line

Picks the Wikidata item whose description says it is a film (and matches --year when given). Prints what it found
and how sure it is; with --out it writes a candidate (source wikidata, kind film/short, url = Wikipedia page) that
shotstub.py turns into a shot with `credits` and `credits_source: wikidata`.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shared  # noqa: E402,F401

API = "https://www.wikidata.org/w/api.php?format=json&"
UA = {"User-Agent": "ZAMAKAN-shot-scout/0.2 (film credits lookup; https://github.com/SaoudAlawi/ZAMAKAN-marketer)",
      "Accept": "application/json"}


def get_json(url, tries=5):
    """Wikimedia asks tools to identify themselves (a browser-like agent gets HTTP 429) and to back off when busy."""
    import time
    import urllib.error
    import urllib.request
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                return json.loads(r.read().decode("utf-8")), r.status
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and i < tries - 1:
                wait = e.headers.get("Retry-After")
                time.sleep(min(int(wait), 30) if wait and wait.isdigit() else 3 * (i + 1))
                continue
            return None, e.code
        except Exception:  # noqa: BLE001
            if i == tries - 1:
                return None, 0
            time.sleep(1)
    return None, 0
ROLES = {"P57": "director", "P58": "writer", "P344": "dop", "P1040": "editor", "P86": "composer", "P2554": "design"}
FILMISH = re.compile(r"\b(film|movie|documentary)\b", re.I)
PERSON = re.compile(r"\b(director|actor|actress|producer|writer|screenwriter|cinematographer|composer|editor|born|\(\d{4}[–-])", re.I)


def _claims(e, p):
    return [(c["mainsnak"].get("datavalue") or {}).get("value") for c in e.get("claims", {}).get(p, []) if c["mainsnak"].get("datavalue")]


def labels(ids):
    out = {}
    ids = list(dict.fromkeys(ids))
    for i in range(0, len(ids), 40):
        d, _ = get_json(API + "action=wbgetentities&props=labels&languages=en|ar&ids=" + "|".join(ids[i:i + 40]))
        for k, v in ((d or {}).get("entities") or {}).items():
            lab = v.get("labels", {})
            out[k] = (lab.get("en") or lab.get("ar") or {}).get("value", k)
    return out


def search(title, year=None):
    d, status = get_json(API + f"action=wbsearchentities&type=item&language=en&limit=10&search={quote(title)}")
    if not d:
        return None, f"search failed (HTTP {status})"
    def is_film(desc):  # "2012 film by ..." yes; "American film director (1941–2012)" no
        return bool(FILMISH.search(desc)) and not (PERSON.search(desc) and not re.match(r"^\d{4}\b", desc))
    hits = [h for h in d.get("search", []) if is_film(h.get("description") or "")]
    if year:
        dated = [h for h in hits if any(str(int(year) + k) in (h.get("description") or "") for k in (0, -1, 1))]
        if not dated:
            return None, f"no film from {year} with that title on Wikidata (try the original or Arabic title)"
        hits = dated
    exact = [h for h in hits if (h.get("label") or "").lower() == title.lower()]
    hits = exact or hits
    if not hits:
        return None, "no film with that title on Wikidata"
    return hits[0], ("exact title" if exact else "closest title") + (f", described as '{hits[0].get('description')}'")


def facts(title, year=None):
    hit, how = search(title, year)
    if not hit:
        return {"title": title, "error": how}
    qid = hit["id"]
    d, _ = get_json(API + f"action=wbgetentities&props=claims|sitelinks|labels&languages=en|ar&ids={qid}")
    e = d["entities"][qid]
    people = {r: [v["id"] for v in _claims(e, p) if isinstance(v, dict) and v.get("id")] for p, r in ROLES.items()}
    countries = [v["id"] for v in _claims(e, "P495") if isinstance(v, dict)]
    names = labels([i for ids in people.values() for i in ids] + countries)
    years = sorted(int(v["time"][1:5]) for v in _claims(e, "P577") if isinstance(v, dict) and v.get("time"))
    mins = [float(v["amount"]) for v in _claims(e, "P2047") if isinstance(v, dict) and "amount" in v]
    sl = e.get("sitelinks", {})
    en = sl.get("enwiki", {}).get("title")
    rec = {"title": (e.get("labels", {}).get("en") or {}).get("value", title), "title_ar": (e.get("labels", {}).get("ar") or {}).get("value"),
           "year": years[0] if years else None, "wikidata": f"https://www.wikidata.org/wiki/{qid}", "match": how,
           "credits": {r: [names.get(i, i) for i in ids] for r, ids in people.items() if ids},
           "runtime_min": int(min(mins)) if mins else None, "countries": [names.get(c, c) for c in countries],
           "kind": "short" if re.search(r"short", hit.get("description") or "", re.I) else "film"}
    if year and rec["year"] and abs(rec["year"] - int(year)) > 1:
        rec["warning"] = f"Wikidata says {rec['year']}, you asked for {year}: is this the right film?"
    if en:
        rec["wikipedia"] = f"https://en.wikipedia.org/wiki/{quote(en.replace(' ', '_'))}"
        s, _ = get_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(en.replace(' ', '_'))}")
        if s:
            rec["summary"] = (s.get("extract") or "")[:500]
            rec["thumbnail"] = (s.get("originalimage") or s.get("thumbnail") or {}).get("source")
    if sl.get("arwiki"):
        rec["wikipedia_ar"] = f"https://ar.wikipedia.org/wiki/{quote(sl['arwiki']['title'].replace(' ', '_'))}"
    return rec


CRAFT = re.compile(r"\b(camera|lens(es)?|anamorphic|film stock|35 ?mm|16 ?mm|super 8|minidv|camcorder|digital|handheld|steadicam|"
                   r"long take|one take|single take|close-?ups?|wide shots?|framing|composition|aspect ratio|lighting|lit |natural light|"
                   r"colou?r|palette|grade|edit(ed|ing|or)?|cuts?|montage|sound|silence|score|music|off[- ]camera|off[- ]screen|"
                   r"improvis|non-professional|rehears|location|shot (on|in|at)|filmed|cinematograph)", re.I)


def craft_notes(wikipedia_url, limit=8):
    """Sentences from the film's Wikipedia article about how it was made (camera, lenses, light, editing, sound,
    casting, locations): grounded material for 'what to watch for'. Each comes with the article as its source."""
    import urllib.request
    from bs4 import BeautifulSoup
    try:
        req = urllib.request.Request(wikipedia_url, headers={"User-Agent": UA["User-Agent"]})
        with urllib.request.urlopen(req, timeout=25) as r:
            soup = BeautifulSoup(r.read().decode("utf-8"), "html.parser")
    except Exception:  # noqa: BLE001
        return []
    for bad in soup.select("table, .reference, .reflist, .navbox, .infobox, .mw-editsection, sup"):
        bad.decompose()
    out = []
    for para in soup.select("div.mw-parser-output p"):
        text = re.sub(r"\s+", " ", para.get_text(" ")).strip()
        for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text):
            if 40 < len(sent) < 400 and CRAFT.search(sent) and sent not in out:
                out.append(sent)
        if len(out) >= limit * 3:
            break
    ranked = sorted(out, key=lambda x: -len(CRAFT.findall(x)))  # most craft-dense first
    return ranked[:limit]


def as_candidate(f):
    return {"source": "wikidata", "kind": f.get("kind", "film"), "url": f.get("wikipedia") or f.get("wikidata"), "title": f["title"],
            "year": f.get("year"), "credits": f.get("credits", {}), "description": f.get("summary", ""), "thumbnail": f.get("thumbnail"),
            "runtime_min": f.get("runtime_min"), "countries": f.get("countries"), "title_ar": f.get("title_ar"),
            "craft_notes": f.get("craft_notes", []),
            "extra_urls": [u for u in (f.get("wikidata"), f.get("wikipedia_ar")) if u]}


def show(f):
    if f.get("error"):
        print(f"  ✗ {f['title']}: {f['error']}")
        return
    cr = f.get("credits", {})
    who = " · ".join(f"{k} {', '.join(v)}" for k, v in cr.items())
    print(f"  ✓ {f['title']} ({f.get('year')}) {('· ' + f['title_ar']) if f.get('title_ar') else ''} · {f.get('runtime_min') or '?'} min · "
          f"{', '.join(f.get('countries') or [])}\n    {who}\n    [{f['match']}] {f.get('wikipedia') or f['wikidata']}")
    if f.get("warning"):
        print(f"    ⚠ {f['warning']}")
    for n in f.get("craft_notes", []):
        print(f"    · {n[:220]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("title", nargs="?")
    ap.add_argument("--year")
    ap.add_argument("--titles")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--craft", action="store_true", help="also pull how-it-was-made sentences from Wikipedia")
    a = ap.parse_args()
    items = [(a.title, a.year)] if a.title else []
    if a.titles:
        for line in Path(a.titles).read_text(encoding="utf-8").split("\n"):
            if line.strip() and not line.startswith("#"):
                t, _, y = line.partition("|")
                items.append((t.strip(), y.strip() or None))
    import time
    found = []
    for i, (t, y) in enumerate(items):
        if i:
            time.sleep(1.5)  # be gentle with Wikidata
        f = facts(t, y)
        if a.craft and f.get("wikipedia"):
            f["craft_notes"] = craft_notes(f["wikipedia"])
        found.append(f)
    if a.json:
        print(json.dumps(found, ensure_ascii=False, indent=1))
    else:
        for f in found:
            show(f)
    if a.out:
        from discover_shots import write
        write([as_candidate(f) for f in found if not f.get("error")], a.out)
        print(f"{sum(not f.get('error') for f in found)} films → {a.out}")


if __name__ == "__main__":
    main()
