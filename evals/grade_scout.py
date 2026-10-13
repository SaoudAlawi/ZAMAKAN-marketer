#!/usr/bin/env python3
"""Grade a reference-scout run (any output format) against a benchmark scenario.

Usage: python evals/grade_scout.py <run_dir> [--scenario s1-gcc-brief]

Scenarios live in evals/fixtures/scout/scenarios/<id>/scenario.json (the brief, the job folder and the checks).
Property-based: the web changes, so there is no fixed answer key. The grader re-opens every reference URL found in the
deliverables with a fresh cache, to catch invented or dead links, and reads deliverables in any format (markdown, HTML,
PowerPoint, JSON, PDF), so a run without the skill is graded on what it produced, not on our file contract.
Writes <run_dir>/grading.json in skill-creator format.
"""
import argparse
import html as htmllib
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCOUT = REPO / ".claude/skills/zamakan-reference-scout/scripts"
SCENARIOS = REPO / "evals/fixtures/scout/scenarios"
sys.path.insert(0, str(SCOUT))
from validate_run import GCC, MENA, REGION  # noqa: E402

TEXT_EXT = {".md", ".html", ".htm", ".json", ".txt", ".csv"}
NOT_REFS = re.compile(r"fonts\.(googleapis|gstatic)|cdnjs|jsdelivr|unpkg|image\.adsoftheworld|video\.adsoftheworld|i\.ytimg|img\.youtube|"
                      r"/rails/active_storage|vimeocdn|\.(png|jpe?g|webp|gif|svg|css|js|mp4)(\?|$)|schemas?\.|w3\.org|example\.(org|com)|"
                      r"designtokens|json-schema|claude\.ai|anthropic|wikipedia\.org|schema\.org|openxmlformats|purl\.org|microsoft\.com/office", re.I)
URL_RX = re.compile(r"https?://[^\s\"'<>)\]|`,]+")  # commas end a URL (CSV cells)
GCC_RX = re.compile(r"saudi|ksa|riyadh|jeddah|dammam|khobar|uae|emirates|dubai|abu dhabi|qatar|doha|kuwait|bahrain|oman|muscat|السعودية|الرياض", re.I)
AR_RX = re.compile(r"[؀-ۿ]{2,}")
NEG_RX = re.compile(r"avoid|not |no |never|cliché|cliche|instead of|without|away from|don.t|beyond|rather than|تجنب", re.I)


# ------------------------------------------------------------------ reading deliverables
def deliverable_texts(job):
    texts = {}
    for f in sorted(Path(job).rglob("*")):
        if not f.is_file() or any(p in str(f) for p in ("/thumbs/", "/.cache/", "/check/")) or f.name in ("candidates.jsonl",):
            continue
        if f.suffix.lower() in TEXT_EXT:
            texts[str(f.relative_to(job))] = f.read_text(encoding="utf-8", errors="replace")
        elif f.suffix.lower() == ".pptx":
            with zipfile.ZipFile(f) as z:
                xml = " ".join(z.read(n).decode("utf-8", "replace") for n in z.namelist()
                               if n.startswith("ppt/slides/") and n.endswith(".xml") or n.startswith("ppt/slides/_rels/"))
            texts[str(f.relative_to(job))] = re.sub(r"<[^>]+>", " ", xml) + " " + " ".join(re.findall(r'Target="(https?://[^"]+)"', xml))
        elif f.suffix.lower() == ".docx":
            with zipfile.ZipFile(f) as z:
                xml = z.read("word/document.xml").decode("utf-8", "replace")
            texts[str(f.relative_to(job))] = re.sub(r"<[^>]+>", " ", xml)
        elif f.suffix.lower() == ".pdf" and not (f.with_suffix(".pptx").exists()):
            try:
                import pymupdf
                texts[str(f.relative_to(job))] = "\n".join(p.get_text() for p in pymupdf.open(f))
            except Exception:  # noqa: BLE001
                pass
    return texts


def as_outline(name, t):
    """Markdown-like outline of a deliverable: '## heading' lines and '- item' lines, from md or html."""
    if name.endswith((".html", ".htm")):
        t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
        t = re.sub(r"(?i)<h[1-4][^>]*>", "\n## ", t)
        t = re.sub(r"(?i)<(li|article|p|tr)[^>]*>", "\n- ", t)
        t = re.sub(r'(?i)<a [^>]*href="(https?://[^"]+)"[^>]*>', r" \1 ", t)
        t = htmllib.unescape(re.sub(r"<[^>]+>", " ", t))
    return t


def sections(texts, head_rx):
    """Bodies of sections whose heading matches head_rx, across md and html deliverables."""
    out = []
    for name, t in texts.items():
        if not name.endswith((".md", ".html", ".htm")):
            continue
        o = as_outline(name, t)
        parts = re.split(r"\n(?=#{1,4} )", "\n" + o)
        for p in parts:
            head = p.strip().split("\n", 1)[0]
            if re.match(r"#{1,4} ", head) and re.search(head_rx, head, re.I):
                out.append(p)
    return out


def items(section):
    return [l for l in section.splitlines()[1:] if re.match(r"\s*([-*•]|\d+[.)])\s+\S", l)]


def ref_urls(texts):
    urls = set()
    for name, t in texts.items():
        if name.endswith(("detail.jsonl", "top.jsonl", "brief.json")):
            continue
        for u in URL_RX.findall(t):
            u = u.rstrip(".,;:'\"").replace("&amp;", "&")
            if not NOT_REFS.search(u):
                urls.add(u)
    return sorted(urls)


def contexts(texts, url, width=450):
    out = []
    for t in texts.values():
        for m in re.finditer(re.escape(url), t):
            out.append(re.sub(r"<[^>]+>", " ", t[max(0, m.start() - width):m.end() + width]))
    return " ".join(out)


def country_of(r, ctx=""):
    if r.get("country"):
        return r["country"]
    t = rec_text(r)
    if GCC_RX.search(t):
        return "SA" if re.search(r"saudi|ksa|riyadh|jeddah|dammam|khobar|السعودية|الرياض", t, re.I) else "AE"
    try:
        import pycountry
        for c in pycountry.countries:
            if len(c.name) > 4 and re.search(rf"\b{re.escape(c.name)}\b", t):
                return c.alpha_2
    except Exception:  # noqa: BLE001
        pass
    for rx, cc in ((r"\buk\b|london|british", "GB"), (r"\busa?\b|america|new york", "US")):
        if re.search(rx, t, re.I):
            return cc
    return None


def rec_text(r):
    return " ".join(str(r.get(k) or "") for k in ("title", "brand", "channel", "description", "country_name", "category", "url"))


def territory_blocks(texts, refs_json, brands=()):
    if refs_json and refs_json.get("territories"):
        byid = {r["id"]: r for r in refs_json["references"]}
        return [{"name": t["name"], "name_ar": t.get("name_ar", ""), "text": json.dumps(t, ensure_ascii=False),
                 "n_refs": sum(1 for i in t["reference_ids"] if i in byid)} for t in refs_json["territories"]]
    for name, t in texts.items():
        if not name.endswith(".md"):
            continue
        blocks = []
        for p in re.split(r"\n(?=#{2,4} )", "\n" + t):
            head = p.strip().split("\n", 1)[0]
            if not re.match(r"#{2,4} ", head):  # skip the document title (H1) and preamble
                continue
            if re.search(r"territor|^#{2,4}\s*(\d+[.)]|T\d)", head, re.I) and not re.search(r"^#{2,4}\s*(creative )?territories\s*$", head, re.I):
                cites = set(URL_RX.findall(p)) | set(re.findall(r"\bR\d{1,2}\b", p)) | {b for b in brands if b and b.lower() in p.lower()}
                blocks.append({"name": head.lstrip("# ").strip(), "name_ar": " ".join(AR_RX.findall(head)), "text": p, "n_refs": len(cites)})
        if blocks:
            return blocks
    return []


def largest(job, exts):
    fs = [f for f in Path(job).rglob("*") if f.suffix.lower() in exts and "/check/" not in str(f)]
    return max(fs, key=lambda f: f.stat().st_size) if fs else None


# ------------------------------------------------------------------ grading
def grade(run_dir, scenario_id):
    sc = json.loads((SCENARIOS / scenario_id / "scenario.json").read_text(encoding="utf-8"))
    outputs = Path(run_dir) / "outputs"
    job = outputs / sc["job"]
    if not job.exists():  # the agent may have used another folder name: take the one holding deliverables
        cands = sorted({p.parent for p in outputs.rglob("*") if p.suffix.lower() in (".md", ".html", ".pptx", ".pdf", ".docx")
                        and p.name != "brief.md" and "design-system" not in str(p)}, key=lambda p: len(str(p)))
        job = cands[0] if cands else outputs
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
    from fetch_meta import fetch_one
    with ThreadPoolExecutor(max_workers=8) as ex:
        fetched = list(ex.map(fetch_one, urls))
    alive = [r for r in fetched if not r.get("error") and 200 <= (r.get("http_status") or 0) < 400]
    dead = [r for r in fetched if r not in alive]
    for r in alive:
        r["_ctx"] = contexts(texts, r["url"])
        r["_cc"] = country_of(r)
    all_text = "\n".join(texts.values())
    E = []

    def add(text, passed, evidence):
        E.append({"text": text, "passed": bool(passed), "evidence": str(evidence)[:300]})

    brands = {b for b in ({r.get("brand") or r.get("channel") for r in alive} - {None, ""}) if len(b) >= 4}
    for c in sc["checks"]:
        k = c["type"]
        if k == "min_links":
            add(f"Delivers ≥{c['n']} distinct reference links", len(urls) >= c["n"], f"{len(urls)} reference URLs")
        elif k == "alive_rate":
            rate = len(alive) / len(urls) if urls else 0
            add(c.get("label", f"≥{c['min']:.0%} of reference links are real and open (no invented/dead links)"), rate >= c["min"],
                f"{len(alive)}/{len(urls)} alive; dead: {[(r['url'], r.get('http_status')) for r in dead][:6]}")
        elif k == "home_refs":
            n = sum(1 for r in alive if r["_cc"] in GCC)
            add(c["label"], n >= c["n"], f"{n} GCC")
        elif k == "global_refs":
            far = [r for r in alive if r["_cc"] and r["_cc"] not in MENA]
            add(c["label"], len(far) >= c["n"], f"{len(far)}: {sorted({r['_cc'] for r in far})}")
        elif k == "country_refs":
            n = sum(1 for r in alive if r["_cc"] in c["codes"] or re.search(c["rx"], rec_text(r), re.I))
            add(c["label"], n >= c["n"], f"{n}")
        elif k == "region_count":
            regs = {REGION.get(r["_cc"], f"other:{r['_cc']}") for r in alive if r["_cc"]}
            add(c["label"], len(regs) >= c["n"], sorted(regs))
        elif k == "mix":
            rx = re.compile(c["rx"], re.I)
            n_in = sum(1 for r in alive if rx.search(rec_text(r)))
            add(c["label"], n_in >= c["n_in"] and len(alive) - n_in >= c["n_out"], f"in {n_in}, other {len(alive) - n_in}")
        elif k == "topic_ratio":
            rx = re.compile(c["rx"], re.I)
            hit = [r for r in alive if rx.search(rec_text(r) + (" " + r["_ctx"] if c.get("context") else ""))]
            add(c["label"], alive and len(hit) / len(alive) >= c["min"], f"{len(hit)}/{len(alive)}")
        elif k == "territories":
            terr = territory_blocks(texts, refs_json, brands)
            add(f"{c['min']}–{c['max']} creative territories", c["min"] <= len(terr) <= c["max"], f"{len(terr)}: {[t['name'][:40] for t in terr]}")
            add("Every territory has an Arabic name", terr and all(AR_RX.search(t["name_ar"] or t["name"]) for t in terr), [t["name_ar"] for t in terr])
            add("Every territory is grounded in ≥2 references", terr and all(t["n_refs"] >= 2 for t in terr), [t["n_refs"] for t in terr])
        elif k == "avoid":
            terr = territory_blocks(texts, refs_json, brands)
            bad = [l.strip()[:90] for t in terr for l in t["text"].splitlines() if re.search(c["rx"], l, re.I) and not NEG_RX.search(l)]
            add("Territories respect the brief's avoid-list", terr and not bad, bad or ("clean" if terr else "no territories"))
        elif k == "visual":
            visual = [n for n in texts if n.endswith((".html", ".htm", ".pptx"))] + [str(p.relative_to(job)) for p in job.rglob("*.pdf")]
            imgs = sum(t.count("<img") for n, t in texts.items() if n.endswith((".html", ".htm"))) + \
                sum(1 for p in job.rglob("*.pptx") for n in zipfile.ZipFile(p).namelist() if n.startswith("ppt/media/"))
            add(f"Visual deliverable with campaign images (≥{c['min_images']})", visual and imgs >= c["min_images"], f"{visual[:4]}, {imgs} images")
            add_beauty(job, add)
        elif k == "deck":
            decks = list(job.rglob("*.pptx")) + [p for p in job.rglob("*.pdf") if "deck" in p.name.lower() or "pitch" in p.name.lower()]
            add("A presentable deck (pptx or pdf)", bool(decks), [str(p.relative_to(job)) for p in decks][:3])
            add_beauty(job, add)
        elif k == "written_report":
            reps = [(n, len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", t)))) for n, t in texts.items() if n.endswith((".md", ".docx", ".pdf", ".html"))]
            best = max(reps, key=lambda x: x[1]) if reps else ("-", 0)
            add("A written report (≥800 words)", best[1] >= 800, best)
        elif k == "mentions":
            n = len(re.findall(c["rx"], all_text, re.I))
            add(c["label"], n >= c["n"], f"{n} mentions")
        elif k == "competitors":
            missing, unlinked = [], []
            for name in c["names"]:
                stem = re.escape(name.split()[0].rstrip("'s").lower())
                if not re.search(stem, all_text.lower()):
                    missing.append(name)
                elif c.get("links_each") and not any(re.search(stem, (r["_ctx"] + " " + rec_text(r)).lower().replace(" ", "")) or
                                                     re.search(stem.replace(r"\ ", ""), r["url"].lower()) for r in alive):
                    unlinked.append(name)
            add("Every named competitor is covered" + (" with a working link" if c.get("links_each") else ""), not missing and not unlinked,
                f"missing {missing}, no link {unlinked}")
        elif k == "insights":
            if refs_json and refs_json.get("insights"):
                n = sum(1 for x in refs_json["insights"] if x.get("source_url"))
            else:
                n = max((sum(1 for l in items(s) if URL_RX.search(l) or re.search(r"\(.*20\d\d.*\)|source", l, re.I))
                         for s in sections(texts, r"insight|what we (learned|know)|audience truth")), default=0)
            add(f"≥{c['n']} sourced insights", n >= c["n"], f"{n}")
        elif k == "patterns":
            if refs_json and refs_json.get("patterns"):
                n = len(refs_json["patterns"])
            else:
                n = max((len(items(s)) for s in sections(texts, r"pattern|lesson|learn|takeaway|principle|what .* (share|have in common)")), default=0)
            add(f"≥{c['n']} patterns / lessons drawn across references", n >= c["n"], f"{n}")
        elif k == "recommendation":
            ok = bool((refs_json or {}).get("recommendation")) or bool(sections(texts, r"recommend")) or \
                bool(re.search(r"we recommend|our recommendation|recommended (route|territory|direction)", all_text, re.I))
            add("Takes a position: a recommendation", ok, "found" if ok else "none")
        elif k == "limitations":
            n = len(re.findall(r"could not|couldn.t|not (publicly )?visible|limited|unable to|no access|not indexed|didn.t find|no .{0,20}found", all_text, re.I))
            add("Honest about coverage (what could not be seen)", n >= 1, f"{n} mentions")
        elif k == "no_estimates":
            est = re.findall(r"estimated? (?:ad )?(?:spend|budget|reach|impressions)[^.\n]{0,60}", all_text, re.I)
            add("No invented spend/reach estimates", not est, est[:3] or "clean")
        elif k == "on_brand":
            ds = next((p / "clients" / c["client"] / "design-system" for p in [outputs] if (p / "clients" / c["client"] / "design-system").exists()), None)
            board = largest(job, {".html", ".htm"})
            if not ds or not board:
                add("Visual deliverable uses the client's design system", False, "no design system or no board")
            else:
                h = board.read_text(encoding="utf-8", errors="replace").upper()
                spec = json.loads((ds / "spec.json").read_text(encoding="utf-8"))
                hexes = [x["hex"].upper() for x in spec["colors"]]
                fams = [f["family"].upper() for f in spec["fonts"]]
                n_hex, n_font = sum(x in h for x in hexes), sum(f in h for f in fams)
                logo = any(Path(l).stem.upper() in h for l in os.listdir(ds / "assets/logos")) or "IMAGE/SVG+XML" in h
                add("Visual deliverable uses the client's design system (colours, fonts, logo)", n_hex >= 3 and n_font >= 2 and logo,
                    f"{n_hex}/{len(hexes)} brand colours, {n_font}/{len(fams)} brand fonts, logo {'yes' if logo else 'no'}")
    passed = sum(e["passed"] for e in E)
    result = {"scenario": scenario_id, "expectations": E,
              "summary": {"passed": passed, "failed": len(E) - passed, "total": len(E), "pass_rate": round(passed / len(E), 2)},
              "stats": {"job": str(job.relative_to(outputs)) if job != outputs else ".", "files": sorted(texts)[:40], "ref_urls": len(urls),
                        "alive": len(alive), "dead": len(dead), "alive_rate": round(len(alive) / len(urls), 3) if urls else 0}}
    if refs_json:
        from validate_run import validate
        errs, warns = validate(refs_json)
        result["contract"] = {"valid": not errs, "errors": errs[:8], "warnings": warns[:8]}
    (Path(run_dir) / "grading.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


_beauty_done = set()


def add_beauty(job, add):
    """The same beauty check the skill runs, applied to whatever board/deck the run produced (copied under the expected names)."""
    if job in _beauty_done:
        return
    _beauty_done.add(job)
    board, deck = largest(job, {".html", ".htm"}), largest(job, {".pptx"})
    if not board and not deck:
        return
    tmp = Path(tempfile.mkdtemp(prefix="beauty-"))
    if board:
        shutil.copy(board, tmp / "board.html")
    if deck:
        shutil.copy(deck, tmp / "deck.pptx")
    from check_outputs import run_checks
    try:
        out = run_checks(tmp)
    except Exception as e:  # noqa: BLE001
        add("Passes the beauty check (layout, contrast, images, fonts, Arabic)", False, f"check failed to run: {e}")
        return
    add("Passes the beauty check (layout, contrast, images, fonts, Arabic)", out["ok"], out["errors"][:3] or f"{len(out['warnings'])} warnings")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--scenario", default="s1-gcc-brief")
    a = ap.parse_args()
    r = grade(a.run_dir, a.scenario)
    s = r["summary"]
    print(f"{s['passed']}/{s['total']} passed ({s['pass_rate']:.0%}) · {r['stats']['ref_urls']} links, {r['stats']['alive']} alive")
    for e in r["expectations"]:
        print(f"  {'✓' if e['passed'] else '✗'} {e['text']}  [{e['evidence'][:140]}]")
    if "contract" in r:
        print("  contract:", json.dumps(r["contract"], ensure_ascii=False)[:300])


if __name__ == "__main__":
    main()
