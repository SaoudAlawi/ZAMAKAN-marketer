#!/usr/bin/env python3
"""Grade a reference-scout run (any output format) for the Rawaq Ramadan brief.

Usage: python evals/grade_scout.py <run_dir> [--job clients/rawaq/jobs/2026-10-13-scout-ramadan]

Property-based (the web changes, so there is no fixed answer key). The grader independently
re-opens every reference URL found in the deliverables, with a fresh cache, to catch invented or
dead links. Writes <run_dir>/grading.json in skill-creator format.
"""
import argparse
import json
import os
import re
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCOUT = REPO / ".claude/skills/zamakan-reference-scout/scripts"
TEXT_EXT = {".md", ".html", ".htm", ".json", ".txt", ".csv"}
NOT_REFS = re.compile(r"fonts\.(googleapis|gstatic)|cdnjs|jsdelivr|unpkg|image\.adsoftheworld|video\.adsoftheworld|i\.ytimg|"
                      r"/rails/active_storage|vimeocdn|\.(png|jpe?g|webp|gif|svg|css|js|mp4)(\?|$)|schemas?\.|w3\.org|example\.(org|com)|"
                      r"designtokens|json-schema|claude\.ai|anthropic|wikipedia\.org", re.I)
URL_RX = re.compile(r"https?://[^\s\"'<>)\]|`,]+")  # commas end a URL (CSV cells)
GCC_RX = re.compile(r"saudi|ksa|riyadh|jeddah|dammam|khobar|uae|emirates|dubai|abu dhabi|qatar|doha|kuwait|bahrain|oman|muscat|السعودية|الرياض", re.I)
RAMADAN_RX = re.compile(r"ramadan|ramadhan|iftar|suhoor|sohour|taraweeh|eid|رمضان|سحور|افطار|إفطار|عيد", re.I)
COFFEE_RX = re.compile(r"coffee|caf[eé]|espresso|nespresso|nescaf|costa|starbucks|barn|dose|half million|tea\b|lipton|قهوة", re.I)
AR_RX = re.compile(r"[؀-ۿ]{2,}")
AVOID_RX = re.compile(r"lantern|crescent|camel|فانوس|هلال|جمل", re.I)
NEG_RX = re.compile(r"avoid|not |no |never|cliché|cliche|instead of|without|away from|don.t|beyond|rather than|تجنب", re.I)


def deliverable_texts(job):
    texts = {}
    for f in sorted(Path(job).rglob("*")):
        if not f.is_file() or "/thumbs/" in str(f) or "/.cache/" in str(f) or f.name in ("candidates.jsonl",):
            continue
        if f.suffix.lower() in TEXT_EXT:
            texts[str(f.relative_to(job))] = f.read_text(encoding="utf-8", errors="replace")
        elif f.suffix.lower() == ".pptx":
            with zipfile.ZipFile(f) as z:
                xml = " ".join(z.read(n).decode("utf-8", "replace") for n in z.namelist()
                               if n.startswith("ppt/slides/") and n.endswith(".xml") or n.startswith("ppt/slides/_rels/"))
            texts[str(f.relative_to(job))] = re.sub(r"<[^>]+>", " ", xml) + " " + " ".join(re.findall(r'Target="(https?://[^"]+)"', xml))
    return texts


def ref_urls(texts):
    """Reference URLs from human deliverables (and references.json if present); excludes assets/CDNs."""
    urls = set()
    for name, t in texts.items():
        if name.endswith(("detail.jsonl", "top.jsonl")):
            continue
        for u in URL_RX.findall(t):
            u = u.rstrip(".,;:'\"").replace("&amp;", "&")
            if not NOT_REFS.search(u):
                urls.add(u)
    return sorted(urls)


def territory_blocks(texts, refs_json, brands=()):
    if refs_json and refs_json.get("territories"):
        byid = {r["id"]: r for r in refs_json["references"]}
        return [{"name": t["name"], "name_ar": t.get("name_ar", ""), "text": json.dumps(t, ensure_ascii=False),
                 "n_refs": sum(1 for i in t["reference_ids"] if i in byid)} for t in refs_json["territories"]]
    blocks = []
    for name, t in texts.items():
        if not name.endswith(".md"):
            continue
        parts = re.split(r"\n(?=#{2,4} )", "\n" + t)
        for p in parts:
            head = p.strip().split("\n", 1)[0]
            if not re.match(r"#{2,4} ", head):  # skip the document title (H1) and preamble
                continue
            if re.search(r"territor|^#{2,4}\s*(\d+[.)]|T\d)", head, re.I) and not re.search(r"^#{2,4}\s*(creative )?territories\s*$", head, re.I):
                # a reference can be cited by link, by code (R08) or by brand name
                cites = set(URL_RX.findall(p)) | set(re.findall(r"\bR\d{1,2}\b", p)) | {b for b in brands if b and b.lower() in p.lower()}
                blocks.append({"name": head.lstrip("# ").strip(), "name_ar": " ".join(AR_RX.findall(head)), "text": p,
                               "n_refs": len(cites)})
        if blocks:
            break
    return blocks


def grade(run_dir, job_rel):
    job = Path(run_dir) / "outputs" / job_rel
    if not job.exists():
        cands = list((Path(run_dir) / "outputs").rglob("*scout*"))
        job = cands[0] if cands else Path(run_dir) / "outputs"
    texts = deliverable_texts(job)
    refs_json = None
    for name, t in texts.items():
        if name.endswith("references.json"):
            try:
                d = json.loads(t)
                if isinstance(d, dict) and d.get("schema_version") and isinstance(d.get("references"), list):
                    refs_json = d  # our contract; other formats are graded on their deliverables only
            except json.JSONDecodeError:
                pass
    urls = ref_urls(texts)
    os.environ["ZAMAKAN_SCOUT_CACHE"] = tempfile.mkdtemp(prefix="grade-cache-")  # fresh: re-check now
    sys.path.insert(0, str(SCOUT))
    from fetch_meta import fetch_one
    with ThreadPoolExecutor(max_workers=8) as ex:
        fetched = list(ex.map(fetch_one, urls))
    alive = [r for r in fetched if not r.get("error") and 200 <= (r.get("http_status") or 0) < 400]
    dead = [r for r in fetched if r not in alive]
    E = []

    def add(text, passed, evidence):
        E.append({"text": text, "passed": bool(passed), "evidence": str(evidence)[:300]})

    add("Delivers ≥20 distinct reference links", len(urls) >= 20, f"{len(urls)} reference URLs")
    rate = len(alive) / len(urls) if urls else 0
    add("≥95% of reference links are real and open (no invented/dead links)", rate >= 0.95,
        f"{len(alive)}/{len(urls)} alive; dead: {[ (r['url'], r.get('http_status')) for r in dead][:6]}")
    rec_text = lambda r: " ".join(str(r.get(k) or "") for k in ("title", "brand", "channel", "description", "country_name", "category", "url"))  # noqa: E731
    gcc = [r for r in alive if r.get("country") in {"SA", "AE", "QA", "KW", "BH", "OM"} or GCC_RX.search(rec_text(r))]
    add("≥5 references from the GCC", len(gcc) >= 5, f"{len(gcc)} GCC")
    coffee = [r for r in alive if COFFEE_RX.search(rec_text(r))]
    other = [r for r in alive if not COFFEE_RX.search(rec_text(r))]
    add("Range: ≥3 coffee/tea references AND ≥5 from other categories", len(coffee) >= 3 and len(other) >= 5,
        f"coffee/tea {len(coffee)}, other {len(other)}")
    ram = [r for r in alive if RAMADAN_RX.search(rec_text(r))]
    add("Ramadan relevance: ≥40% of live references are Ramadan/Eid work", alive and len(ram) / len(alive) >= 0.4,
        f"{len(ram)}/{len(alive)}")
    brands = {r.get("brand") or r.get("channel") for r in alive} - {None, ""}
    brands = {b for b in brands if len(b) >= 4}
    terr = territory_blocks(texts, refs_json, brands)
    add("3–5 creative territories", 3 <= len(terr) <= 5, f"{len(terr)}: {[t['name'][:40] for t in terr]}")
    add("Every territory has an Arabic name", terr and all(AR_RX.search(t["name_ar"] or t["name"]) for t in terr),
        [t["name_ar"] for t in terr])
    add("Every territory is grounded in ≥2 references", terr and all(t["n_refs"] >= 2 for t in terr), [t["n_refs"] for t in terr])
    bad = []
    for t in terr:
        for line in t["text"].splitlines():
            if AVOID_RX.search(line) and not NEG_RX.search(line):
                bad.append(line.strip()[:90])
    add("Territories respect the brief's avoid-list (no lanterns/crescents/camels as ideas)", not bad, bad or "clean")
    all_text = "\n".join(texts.values())
    visual = [n for n in texts if n.endswith((".html", ".htm", ".pptx"))] + [str(p.relative_to(job)) for p in job.rglob("*.pdf")]
    imgs = sum(t.count("<img") for n, t in texts.items() if n.endswith((".html", ".htm"))) + \
        sum(1 for p in job.rglob("*.pptx") for n in zipfile.ZipFile(p).namelist() if n.startswith("ppt/media/"))
    add("Visual deliverable with campaign images (board or deck)", visual and imgs >= 10, f"{visual}, {imgs} images")
    risk = len(re.findall(r"cultural|sensitiv|risk|watch-out|watch out", all_text, re.I))
    add("Cultural fit / risks addressed (≥5 mentions)", risk >= 5, f"{risk} mentions")
    passed = sum(e["passed"] for e in E)
    result = {"expectations": E, "summary": {"passed": passed, "failed": len(E) - passed, "total": len(E),
                                             "pass_rate": round(passed / len(E), 2)},
              "stats": {"files": sorted(texts), "ref_urls": len(urls), "alive": len(alive), "dead": len(dead),
                        "gcc": len(gcc), "ramadan": len(ram), "territories": len(terr)}}
    if refs_json:
        sys.path.insert(0, str(SCOUT))
        from validate_run import validate
        errs, warns = validate(refs_json)
        result["contract"] = {"valid": not errs, "errors": errs[:8], "warnings": warns[:8],
                              "statuses": {s: sum(r["status"] == s for r in refs_json["references"])
                                           for s in ("verified", "unverified", "rejected")}}
    (Path(run_dir) / "grading.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--job", default="clients/rawaq/jobs/2026-10-13-scout-ramadan")
    a = ap.parse_args()
    r = grade(a.run_dir, a.job)
    s = r["summary"]
    print(f"{s['passed']}/{s['total']} passed ({s['pass_rate']:.0%}) · {r['stats']}")
    for e in r["expectations"]:
        print(f"  {'✓' if e['passed'] else '✗'} {e['text']}  [{e['evidence'][:140]}]")
    if "contract" in r:
        print("  contract:", json.dumps(r["contract"], ensure_ascii=False)[:300])


if __name__ == "__main__":
    main()
