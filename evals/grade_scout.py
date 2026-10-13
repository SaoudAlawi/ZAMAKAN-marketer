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
import subprocess
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
                      r"designtokens|json-schema|claude\.ai|anthropic|wikipedia\.org|schema\.org|openxmlformats|purl\.org|microsoft\.com/office|"
                      r"localhost|127\.0\.0\.1|swiftpic|cdn\.builder\.io|squarespace\.com/static|[?&]format=\d|/wp-content/uploads/|cloudinary|imgix|"
                      r"googleusercontent|fbcdn|cdninstagram|ytimg|twimg|/thumbnail", re.I)
IMG_KEYS = re.compile(r"thumb|image|img|logo|photo|picture|poster|cover|icon|src|local|asset|still|preview", re.I)
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


def json_walk(o, key=""):
    """(key, value) for every string in a JSON document."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from json_walk(v, k)
    elif isinstance(o, list):
        for v in o:
            yield from json_walk(v, key)
    elif isinstance(o, str):
        yield key, o


def json_docs(texts):
    for name, t in texts.items():
        if name.endswith(".json") and not name.endswith("brief.json"):
            try:
                yield name, json.loads(t)
            except json.JSONDecodeError:
                continue


def candidate_urls(name, t):
    if name.endswith(".json"):
        try:
            return [v for k, v in json_walk(json.loads(t)) if not IMG_KEYS.search(k) for v in URL_RX.findall(v)]
        except json.JSONDecodeError:
            return URL_RX.findall(t)
    if name.endswith((".html", ".htm")):
        hrefs = re.findall(r'href="(https?://[^"]+)"', t)
        body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>|<img[^>]*>", " ", t)
        body = re.sub(r"<wbr\s*/?>|&shy;|\u00ad", "", body)
        return hrefs + URL_RX.findall(htmllib.unescape(re.sub(r"<[^>]+>", " ", body)))
    return URL_RX.findall(t)


def ref_urls(texts):
    """Reference links in the deliverables. PDF text wraps long URLs across lines, so PDFs only count when nothing else has links."""
    urls = set()
    names = [n for n in texts if not n.endswith(".pdf")] or list(texts)
    for name in names:
        t = texts[name]
        if name.endswith(("detail.jsonl", "top.jsonl", "brief.json", "link_check.json", "link_check.csv")):
            continue
        for u in candidate_urls(name, t):
            u = u.rstrip(".,;:'\"").replace("&amp;", "&")
            if not NOT_REFS.search(u):
                urls.add(u)
    return sorted(urls)


def deliverable_refs(texts, refs_json):
    """Reference records a run wrote itself, in any JSON shape: url -> {brand, title, country}."""
    out = {}
    for _, d in json_docs(texts):
        stack = [d]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                links = [v for k, v in json_walk(o) if not IMG_KEYS.search(k) for v in URL_RX.findall(v)]
                if links and any(k in o for k in ("brand", "title", "name", "campaign", "advertiser")):
                    cc = o.get("country") or o.get("market") or o.get("markets") or o.get("country_name")
                    rec = {"brand": o.get("brand") or o.get("advertiser"), "title": o.get("title") or o.get("campaign") or o.get("name"),
                           "country": to_cc(cc)}
                    for u in links:
                        out.setdefault(u.rstrip("/"), rec)
                stack.extend(v for v in o.values() if isinstance(v, (dict, list)))
            elif isinstance(o, list):
                stack.extend(x for x in o if isinstance(x, (dict, list)))
    return out


def to_cc(v):
    if not v:
        return None
    if isinstance(v, list):
        v = v[0] if v else None
    v = str(v).split(",")[0].split("(")[0].strip()
    if re.fullmatch(r"[A-Z]{2}", v):
        return v
    try:
        from sources import country_code
        return country_code(v)
    except Exception:  # noqa: BLE001
        return None


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
    for _, d in json_docs(texts):  # a run's own data file, any shape: {"territories": [{...}]}
        ts = next((v for k, v in (d.items() if isinstance(d, dict) else []) if re.search(r"territor", k, re.I) and isinstance(v, list)), None)
        if ts and all(isinstance(x, dict) for x in ts):
            out = []
            for x in ts:
                name = next((str(x[k]) for k in ("name", "en", "title", "name_en") if x.get(k)), "")
                ar = next((str(x[k]) for k in ("name_ar", "ar", "arabic", "title_ar") if x.get(k)), " ".join(AR_RX.findall(name)))
                refs = next((x[k] for k in ("reference_ids", "refs", "references", "grounded_in", "based_on") if x.get(k)), [])
                out.append({"name": name, "name_ar": ar, "text": json.dumps(x, ensure_ascii=False),
                            "n_refs": len(refs) if isinstance(refs, list) else len(re.split(r"[,;]", str(refs)))})
            return out
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
        numbered = [b for b in blocks if re.match(r"(\d+[.)]|T\d|territory \d)", b["name"], re.I)]
        if numbered:  # "## Creative territories" containers around "### 1. …" blocks are not territories
            blocks = numbered
        if blocks:
            return blocks
    return []


def largest(job, exts):
    fs = [f for f in Path(job).rglob("*") if f.suffix.lower() in exts and "/check/" not in str(f)]
    return max(fs, key=lambda f: f.stat().st_size) if fs else None


def unresolvable(url):
    import socket
    from urllib.parse import urlparse
    try:
        socket.getaddrinfo(urlparse(url).hostname, 443)
        return False
    except OSError:
        r = subprocess.run(["curl", "-sS", "-m", "15", "-o", "/dev/null", url], capture_output=True, text=True)
        return "resolve host" in r.stderr  # the proxy refuses names outside the environment's allowlist


def recheck_in_browser(fetched):
    """Links that failed a plain fetch get one more try in Chromium (some sites only serve browsers)."""
    failed = [r for r in fetched if r.get("error") or not (200 <= (r.get("http_status") or 0) < 400)]
    if not failed:
        return fetched
    try:
        from playwright.sync_api import sync_playwright
        sys.path.insert(0, str(REPO / ".claude/skills/zamakan-design-system/scripts"))
        from _common import launch_chromium
        with sync_playwright() as p:
            b = launch_chromium(p)
            pg = b.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36")
            for r in failed:
                try:
                    resp = pg.goto(r["url"], timeout=25000, wait_until="domcontentloaded")
                    st = resp.status if resp else 0
                except Exception:  # noqa: BLE001
                    st = 0
                if 200 <= st < 400:
                    r.pop("error", None)
                    r["http_status"], r["via"] = st, "browser-recheck"
                elif st in (401, 403, 429):
                    r["http_status"] = st
            b.close()
    except Exception:  # noqa: BLE001 - no browser: keep the plain results
        pass
    return fetched


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
    fetched = recheck_in_browser(fetched)
    # bot walls (401/403/429) and hosts this machine's network can't resolve: neither alive nor proven dead
    blocked = [r for r in fetched if r.get("http_status") in (401, 403, 429) or (not r.get("http_status") and unresolvable(r["url"]))]
    alive = [r for r in fetched if not r.get("error") and 200 <= (r.get("http_status") or 0) < 400]
    dead = [r for r in fetched if r not in alive and r not in blocked]
    own = deliverable_refs(texts, refs_json)
    for r in alive:
        mine = own.get(r["url"].rstrip("/"), {})
        for k in ("brand", "title"):
            r.setdefault(k, mine.get(k))
            if not r.get(k):
                r[k] = mine.get(k)
        r["_ctx"] = contexts(texts, r["url"])
        r["_cc"] = r.get("country") or mine.get("country") or country_of(r)
    all_text = "\n".join(texts.values())
    E = []

    def add(text, passed, evidence):
        E.append({"text": text, "passed": bool(passed), "evidence": str(evidence)[:300]})

    brands = {b for b in ({r.get("brand") or r.get("channel") for r in alive} | {v.get("brand") for v in own.values()}) - {None, ""}
              if len(str(b)) >= 4}
    brands |= {str(b).split(":")[0].split("(")[0].strip() for b in list(brands)}
    for c in sc["checks"]:
        k = c["type"]
        if k == "min_links":
            add(f"Delivers ≥{c['n']} distinct reference links", len(urls) >= c["n"], f"{len(urls)} reference URLs")
        elif k == "alive_rate":
            checkable = len(alive) + len(dead)
            rate = len(alive) / checkable if checkable else 0
            add(c.get("label", f"≥{c['min']:.0%} of reference links are real and open (no invented/dead links)"), rate >= c["min"],
                f"{len(alive)}/{checkable} alive ({len(blocked)} behind a bot wall, not counted); dead: {[(r['url'], r.get('http_status')) for r in dead][:6]}")
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
            js = [v for _, d in json_docs(texts) if isinstance(d, dict) for k, v in d.items() if re.search(r"insight", k, re.I) and isinstance(v, list)]
            if js:
                n = max(sum(1 for x in v if isinstance(x, dict) and any(URL_RX.search(str(y)) for y in x.values())) for v in js)
            else:
                n = max((sum(1 for l in items(s) if URL_RX.search(l) or re.search(r"\(.*20\d\d.*\)|source", l, re.I))
                         for s in sections(texts, r"insight|what we (learned|know)|audience truth")), default=0)
            add(f"≥{c['n']} sourced insights", n >= c["n"], f"{n}")
        elif k == "patterns":
            js = [v for _, d in json_docs(texts) if isinstance(d, dict) for k, v in d.items() if re.search(r"pattern|lesson", k, re.I) and isinstance(v, list)]
            if js:
                n = max(len(v) for v in js)
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
                h = board.read_text(encoding="utf-8", errors="replace")
                for href in re.findall(r'<link[^>]+href="([^"]+\.css)"|@import\s+url\([\'"]?([^\'")]+\.css)', h):  # linked or imported
                    href = next(x for x in (href if isinstance(href, tuple) else (href,)) if x)
                    css = (board.parent / href).resolve()
                    if css.exists():
                        h += css.read_text(encoding="utf-8", errors="replace")
                h = h.upper()
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
                        "alive": len(alive), "dead": len(dead), "blocked": len(blocked),
                        "alive_rate": round(len(alive) / (len(alive) + len(dead)), 3) if alive or dead else 0}}
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
    if board:  # a <base> keeps the board's own relative images and stylesheets working from the copy
        h = board.read_text(encoding="utf-8", errors="replace")
        base = f'<base href="{board.parent.resolve().as_uri()}/">'
        h = re.sub(r"(?i)<head[^>]*>", lambda m: m.group(0) + base, h, count=1) if re.search(r"(?i)<head", h) else base + h
        (tmp / "board.html").write_text(h, encoding="utf-8")
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
