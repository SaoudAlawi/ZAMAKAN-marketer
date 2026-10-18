#!/usr/bin/env python3
"""Build the human outputs of a scout run from references.json (agents never hand-write these).

Usage:
  python build_outputs.py <references.json> --out <job_dir> [--formats board,deck,report] [--brief brief.json]
                          [--client-name "Rawaq Coffee Roasters"] [--design zamakan|awesome:<name>|<DESIGN.md>] [--no-pdf]

Always writes territories.md (for agents). Formats (ask the user; kickoffs default to board,deck):
  board   board.html: self-contained, on-brand board (render_board.py): insights, recommendation, territories,
          competitors, patterns, deep dives, every reference (R01…) with filters, before-kickoff list
  deck    deck.pptx (editable, 16:9, render_deck.py) + deck.pdf when LibreOffice is available
  report  report.md: the same story in writing
Then run check_outputs.py <job_dir> and look at the screenshots it writes before delivering.
Look (board and deck) comes from the brand kit (brandkit.py): --design if given, else the client's design system
found above --out (clients/<slug>/design-system/: logos, font files, colours by role, shapes, graphic elements),
else the ZAMAKAN house style. awesome:<name> borrows a look from github.com/VoltAgent/awesome-design-md.
Refuses to build if validate_run.py reports errors. Rejected references are never shown.
"""
import argparse
import base64
import html
import io
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _web  # noqa: E402
from brandkit import load_kit, with_client_logo  # noqa: E402
from validate_run import GCC, REGION, validate  # noqa: E402

RING_LABEL = {"direct": "Direct · same category, GCC", "category": "Category · worldwide",
              "adjacent": "Adjacent · shared insight", "wildcard": "Wildcard · craft & ambition"}
RING_ORDER = ["direct", "category", "adjacent", "wildcard"]
E = html.escape


# ------------------------------------------------------------------ shared
def display_title(run, brief, client_name):
    """run.title, else '<Client> · <moment> references', else the question."""
    if run["run"].get("title"):
        return run["run"]["title"]
    who = client_name or (run["run"].get("client") or "").replace("-", " ").title()
    moment = (brief or {}).get("moment", "").split("(")[0].strip()
    if who and moment:
        return f"{who} · {moment} references"
    return run["run"].get("question") or run["run"]["id"]


def load_run(path):
    run = json.loads(Path(path).read_text(encoding="utf-8"))
    errors, warnings = validate(run)
    if errors:
        raise SystemExit("references.json has errors; fix them first:\n  " + "\n  ".join(errors))
    run["references"] = [r for r in run["references"] if r["status"] != "rejected"]
    return run, warnings


def thumb_bytes(ref, cache_dir):
    """JPEG bytes (max 640px) for a reference thumbnail, cached in <out>/thumbs/."""
    url = (ref.get("thumbnail") or {}).get("url")
    local = (ref.get("thumbnail") or {}).get("local")
    import hashlib
    key = hashlib.sha1(f"{url}|{local}".encode()).hexdigest()[:8]  # a changed thumbnail never shows the old cached image
    dst = Path(cache_dir) / f"{ref['id']}-{key}.jpg"
    if dst.exists():
        return dst.read_bytes()
    src = None
    if local and Path(local).exists():
        src = Path(local).read_bytes()
    elif url:
        try:
            req = urllib.request.Request(url, headers=_web.HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                src = r.read(60_000_000)  # some sources serve full-size originals (8 MB+ PNGs)
        except Exception:  # noqa: BLE001 - a missing image never blocks a deliverable
            return None
    if not src:
        return None
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(src)).convert("RGB")
    except Exception:  # noqa: BLE001
        return None
    im = trim_bars(im)
    im.thumbnail((640, 640))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=78, optimize=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(buf.getvalue())
    return buf.getvalue()


REGION_NAME = {"gcc": "GCC", "mena": "Wider MENA", "europe": "Europe", "americas": "Americas", "asia-pacific": "Asia-Pacific",
               "africa": "Africa", "other": "Rest of world"}


def region_of(r):
    return REGION.get(r.get("country"), "other")


def ref_codes(run):
    """Stable short codes R01… in ring order (direct first), used in every output so people can say 'look at R07'."""
    order = [r for k in RING_ORDER for r in run["references"] if r["ring"] == k]
    return {r["id"]: f"R{i:02d}" for i, r in enumerate(order, 1)}


def lead_order(run, has_img, avoid=()):
    """Up to 3 references per territory, ordered so each territory opens on a different picture where possible
    (images first, then not a competitor's own ad, then references not yet used as another territory's lead)."""
    byid = {r["id"]: r for r in run["references"]}
    rival = lambda r: any(a and a.split()[0].lower() in (r.get("brand") or "").lower() for a in avoid)  # noqa: E731
    used, out = set(), {}
    for t in run.get("territories", []):
        rs = [byid[i] for i in t["reference_ids"] if i in byid]
        rs.sort(key=lambda r: (not has_img.get(r["id"]), rival(r), r["id"] in used))
        if rs:
            used.add(rs[0]["id"])
        out[t["id"]] = rs[:3]
    return out


def country_name(cc):
    try:
        import pycountry
        c = pycountry.countries.get(alpha_2=cc or "")
        return (getattr(c, "common_name", None) or c.name) if c else (cc or "")
    except Exception:  # noqa: BLE001
        return cc or ""


def trim_bars(im):
    """Cut black (letterbox/pillarbox) bars off video stills, so frames and arches show the picture, not the bars."""
    from PIL import ImageOps
    g = ImageOps.grayscale(im)
    w, h = g.size
    px = g.load()

    def dark_row(y):
        return sum(px[x, y] for x in range(0, w, max(1, w // 40))) / len(range(0, w, max(1, w // 40))) < 18

    def dark_col(x):
        return sum(px[x, y] for y in range(0, h, max(1, h // 40))) / len(range(0, h, max(1, h // 40))) < 18
    top = next((y for y in range(h // 3) if not dark_row(y)), 0)
    bottom = next((y for y in range(h - 1, h - h // 3, -1) if not dark_row(y)), h - 1)
    left = next((x for x in range(w // 3) if not dark_col(x)), 0)
    right = next((x for x in range(w - 1, w - w // 3, -1) if not dark_col(x)), w - 1)
    if (bottom - top) < h * 0.4 or (right - left) < w * 0.4:  # a mostly dark image is a dark image, not bars
        return im
    return im.crop((left, top, right + 1, bottom + 1))


def cover_ref(run, has_img, avoid=()):
    """The cover image: run.cover if set; else a deep dive with an image that isn't a competitor's own ad."""
    byid = {r["id"]: r for r in run["references"]}
    if run["run"].get("cover") in byid and has_img(byid[run["run"]["cover"]]):
        return byid[run["run"]["cover"]]
    rival = lambda r: any(a and a.split()[0].lower() in (r.get("brand") or "").lower() for a in avoid)  # noqa: E731
    pool = [byid[i] for i in run.get("top", []) if i in byid] + run["references"]
    return next((r for r in pool if has_img(r) and not rival(r)), next((r for r in pool if has_img(r)), None))


def competitor_names(run, brief):
    return [c for c in (brief or {}).get("competitors", [])] + [c["advertiser"] for c in run.get("competitor_summary", [])]


def evidence_of(r):
    """The strongest evidence verify.py recorded for a reference: content, title, video, or None."""
    ev = [u.get("evidence") for u in r["urls"] if u.get("verified")]
    return next((e for e in ("content", "title", "video") if e in ev), "content" if r["status"] == "verified" and not any(ev) else None)


def evidence_badge(r):
    if r["status"] != "verified":
        return '<span class="badge warn">unverified</span>'
    return {"content": '<span class="badge">✓ page read</span>',
            "title": '<span class="badge warn">page exists · details unconfirmed</span>',
            "video": '<span class="badge warn">▶ video, not watched</span>'}.get(evidence_of(r), '<span class="badge">✓ link checked</span>')


def meta_line(r):
    bits = [r.get("agency"), r.get("country"), str(r.get("year") or "")]
    return " · ".join(b for b in bits if b)


def primary_url(r):
    return r["urls"][0]["url"]


def link_label(r):
    return "Watch" if r["urls"][0].get("kind") == "video" or "youtube" in primary_url(r) or "vimeo" in primary_url(r) else "View case"


# ------------------------------------------------------------------ territories.md
def build_territories(run, brief=None, client_name=None):
    byid = {r["id"]: r for r in run["references"]}
    codes = ref_codes(run)
    L = [f"# Creative territories: {display_title(run, brief, client_name)}", "",
         f"Run `{run['run']['id']}` · mode {run['run']['mode']} · {len(run['references'])} references "
         f"({sum(r['status'] == 'verified' for r in run['references'])} verified). Generated from references.json.", ""]
    for i, t in enumerate(run.get("territories", []), 1):
        L += [f"## {i}. {t['name']}" + (f" · {t['name_ar']}" if t.get("name_ar") else ""), "", f"**Thesis:** {t['thesis']}", ""]
        if t.get("why_this_client"):
            L += [f"**Why this client:** {t['why_this_client']}", ""]
        L.append("**Built on:**")
        for rid in t["reference_ids"]:
            r = byid.get(rid)
            if r:
                L.append(f"- {codes[rid]} {r['brand']}: *{r['title']}* ({meta_line(r)}). {r['card']['idea']} {primary_url(r)}")
        for k, lab in (("example_executions", "Example executions"), ("risks", "Risks")):
            if t.get(k):
                L += ["", f"**{lab}:**"] + [f"- {x}" for x in t[k]]
        L.append("")
    if run.get("white_space"):
        L += ["## White space", ""] + [f"- {w}" for w in run["white_space"]] + [""]
    sparks = [r for r in run["references"] if r.get("spark")]
    if sparks:
        L += ["## Sparks from elsewhere", ""] + [f"- {codes[r['id']]} **{r['spark']}** (from {r['brand']}: *{r['title']}*, "
                                                 f"{r.get('country', '')} {r.get('year', '')}; {primary_url(r)})" for r in sparks] + [""]
    rec = run.get("recommendation")
    if rec:
        names = {t["id"]: t["name"] for t in run.get("territories", [])}
        L += ["## Recommendation", "", rec["summary"], "", "Territories: " + ", ".join(names.get(i, i) for i in rec.get("territory_ids", [])),
              "", f"Why: {rec.get('rationale', '')}", ""]
    return "\n".join(L)


# ------------------------------------------------------------------ report.md
def build_report(run, brief, client_name):
    refs = run["references"]
    byid = {r["id"]: r for r in refs}
    L = [f"# Reference scout report: {display_title(run, brief, client_name)}", "",
         f"**Question:** {run['run'].get('question', '')}", ""]
    if brief:
        L += ["| Brief | |", "|---|---|"] + [f"| {k.title()} | {brief[k] if isinstance(brief[k], str) else ', '.join(brief[k])} |"
                                             for k in ("objective", "audience", "moment", "channels", "competitors", "avoid") if brief.get(k)] + [""]
    rings = {k: sum(r["ring"] == k for r in refs) for k in RING_ORDER}
    L += ["## Summary", "",
          f"{len(refs)} references ({sum(r['status'] == 'verified' for r in refs)} verified against their live pages), "
          f"{sum(r.get('country') in GCC for r in refs)} from the GCC. Rings: "
          + ", ".join(f"{k} {v}" for k, v in rings.items()) + ".", ""]
    codes = ref_codes(run)
    if run.get("insights"):
        L += ["## Insights", ""] + [f"{n}. {x['text']} ([{x.get('source_name') or 'source'}]({x['source_url']})"
                                    + (f", {x['date']}" if x.get("date") else "") + ")" for n, x in enumerate(run["insights"], 1)] + [""]
    rec = run.get("recommendation")
    if rec:
        names = {t["id"]: t["name"] for t in run.get("territories", [])}
        L += ["## Recommendation", "", f"**{rec['summary']}**", "",
              "Territories: " + ", ".join(names.get(i, i) for i in rec.get("territory_ids", [])), "", f"Why: {rec.get('rationale', '')}", ""]
    sparks = [r for r in refs if r.get("spark")]
    if sparks:
        L += ["## Sparks from elsewhere", "", "Work from far outside the category and region: provocations, not references to copy.", ""]
        L += [f"- **{r['spark']}** ({codes[r['id']]}: {r['brand']}, *{r['title']}*, {country_name(r.get('country'))} {r.get('year', '')}, "
              f"[{link_label(r)}]({primary_url(r)})). {r['card']['idea']}" for r in sparks] + [""]
    if run.get("competitor_summary"):
        L += ["## Competitors", "", "| Competitor | Campaign found | What they own | Last seen | References | Checked |", "|---|---|---|---|---|---|"]
        L += [f"| {c['advertiser']}{' (benchmark)' if c.get('benchmark') else ''} | {'Yes' if c.get('found_campaign') else 'None found'} | "
              f"{c.get('owns') or ', '.join(c.get('messaging_pillars', [])) or c.get('notes', '')} | {c.get('last_seen', '–')} | "
              f"{', '.join(codes[i] for i in c.get('reference_ids', []) if i in codes) or '–'} | {c.get('checked', '')} |"
              for c in run["competitor_summary"]] + [""]
        notes = [c for c in run["competitor_summary"] if c.get("owns") and c.get("notes")]
        if notes:
            L += [f"- **{c['advertiser']}:** {c['notes']}" for c in notes] + [""]
        checks = [(c["advertiser"], m) for c in run["competitor_summary"] for m in c.get("manual_checks", [])]
        if checks:
            L += ["### Check by hand", "", "These can't be read from here (login walls); a person should look, about 5 minutes per brand:", ""]
            L += [f"- [ ] {a}: [{m['what']}]({m['url']})" for a, m in checks] + [""]
    if run.get("patterns"):
        L += ["## Patterns", ""] + [f"- {p['pattern']} ({', '.join(codes[i] + ' ' + byid[i]['brand'] for i in p['reference_ids'] if i in byid)})"
                                    for p in run["patterns"]] + [""]
    if run.get("white_space"):
        L += ["## White space", ""] + [f"- {w}" for w in run["white_space"]] + [""]
    L += ["## Creative territories", "", build_territories(run, brief, client_name).split("\n", 4)[-1].replace("\n## ", "\n### "), ""]
    if run.get("top"):
        L += ["## Deep dives", ""]
        for rid in run["top"]:
            r, td = byid[rid], byid[rid]["teardown"]
            L += [f"### {codes[rid]} · {r['brand']}: {r['title']}", "", f"{meta_line(r)} · [{link_label(r)}]({primary_url(r)})", "",
                  f"- **Insight:** {td['insight']}", f"- **Idea:** {td['idea']}", f"- **Execution:** {td['execution']}"]
            for k in ("channels", "tone", "results"):
                if td.get(k):
                    L.append(f"- **{k.title()}:** {td[k]}")
            L += ["- **What we can borrow:** " + "; ".join(td["transferable"]),
                  f"- **Cultural fit ({td['cultural_fit']['score']}/5):** {td['cultural_fit']['notes']}"]
            if td.get("risks"):
                L.append("- **Risks:** " + "; ".join(td["risks"]))
            L.append("")
    L += ["## All references", ""]
    for ring in RING_ORDER:
        rs = [r for r in refs if r["ring"] == ring]
        if not rs:
            continue
        L += [f"### {RING_LABEL[ring]}", "", "| Code | Brand | Campaign | Agency · country · year | Idea | Link |", "|---|---|---|---|---|---|"]
        L += [f"| {codes[r['id']]} | {r['brand']} | {r['title']} | {meta_line(r)} | {r['card']['idea']} | [{link_label(r)}]({primary_url(r)}) |" for r in rs]
        L.append("")
    if run.get("before_kickoff"):
        L += ["## Before kickoff", ""] + [f"- [ ] {q}" for q in run["before_kickoff"]] + [""]
    if run.get("open_questions"):
        L += ["## Open questions", ""] + [f"- {q}" for q in run["open_questions"]] + [""]
    L += ["---", f"*Method: searched {', '.join(run['run'].get('queries', [])[:8])}. Every link was checked against its live page.*"]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ board.html
def build_board(run, brief, client_name, thumbs_dir, kit=None):
    import types
    import render_board
    kit = kit or load_kit("zamakan")
    img = {}
    for r in run["references"]:
        b = thumb_bytes(r, thumbs_dir)
        img[r["id"]] = "data:image/jpeg;base64," + base64.b64encode(b).decode() if b else ""
    h = types.SimpleNamespace(display_title=display_title, meta_line=meta_line, primary_url=primary_url, link_label=link_label,
                              region_of=region_of, REGION_NAME=REGION_NAME, lead_order=lead_order, cover_ref=cover_ref, evidence_badge=evidence_badge,
                              competitor_names=competitor_names,
                              country_name=country_name)
    return render_board.build(run, brief, client_name, kit, img, ref_codes(run), h)


# ------------------------------------------------------------------ deck.pptx
def build_deck(run, brief, client_name, thumbs_dir, path, kit=None):
    import types
    import render_deck
    kit = kit or load_kit("zamakan")
    h = types.SimpleNamespace(display_title=display_title, meta_line=meta_line, primary_url=primary_url, link_label=link_label,
                              region_of=region_of, REGION_NAME=REGION_NAME, lead_order=lead_order, cover_ref=cover_ref, evidence_badge=evidence_badge,
                              competitor_names=competitor_names,
                              country_name=country_name)
    return render_deck.build(run, brief, client_name, kit, lambda r: thumb_bytes(r, thumbs_dir), ref_codes(run), h, path,
                             Path(thumbs_dir) / "brand")


def to_pdf(pptx_path, kit=None):
    if kit:
        import render_deck
        render_deck.install_fonts(kit)
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return None
    out = Path(pptx_path).parent
    r = subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", str(out), str(pptx_path)],
                       capture_output=True, text=True, timeout=180)
    pdf = out / (Path(pptx_path).stem + ".pdf")
    return str(pdf) if r.returncode == 0 and pdf.exists() else None


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("references")
    ap.add_argument("--out", required=True)
    ap.add_argument("--formats", default="board")
    ap.add_argument("--brief")
    ap.add_argument("--client-name")
    ap.add_argument("--design", help="zamakan | awesome:<name> | path to a DESIGN.md (default: client's, else zamakan)")
    ap.add_argument("--logo", help="client logo file (PNG/SVG) when the client has no design system yet; keeps the chosen look")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    run, warnings = load_run(a.references)
    brief = json.loads(Path(a.brief).read_text(encoding="utf-8")) if a.brief else None
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    thumbs = out / "thumbs"
    kit = load_kit(a.design, out)
    if a.logo:
        kit = with_client_logo(kit, a.logo, out, a.client_name)
    th = kit["theme"]
    client_name = a.client_name or kit.get("client_name")
    made = []
    (out / "territories.md").write_text(build_territories(run, brief, client_name), encoding="utf-8")
    made.append("territories.md")
    fmts = {f.strip() for f in a.formats.split(",") if f.strip()}
    if "report" in fmts:
        (out / "report.md").write_text(build_report(run, brief, client_name), encoding="utf-8")
        made.append("report.md")
    if "board" in fmts:
        (out / "board.html").write_text(build_board(run, brief, client_name, thumbs, kit), encoding="utf-8")
        made.append("board.html")
    if "deck" in fmts:
        build_deck(run, brief, client_name, thumbs, out / "deck.pptx", kit)
        made.append("deck.pptx")
        if not a.no_pdf:
            pdf = to_pdf(out / "deck.pptx", kit)
            made.append("deck.pdf" if pdf else "(deck.pdf skipped: LibreOffice not available)")
    print(f"built in {out}: {', '.join(made)} · look: {th['name']} ({th['origin']})")
    for w in warnings:
        print("  warn", w)
    if kit["source"] == "client" and not (Path(kit["theme"]["origin"]).parent / "brand.md").exists():
        print("  note: the design system has no brand.md yet (personality and tone came from DESIGN.md/spec.json); "
              "say so in your delivery notes")
    for m in kit["missing_assets"]:
        print(f"  note: the design system lists '{m}' as missing; it was not invented (ask the client for it)")
    for n in kit["proposed_notes"]:
        print("  note:", n)


if __name__ == "__main__":
    main()
