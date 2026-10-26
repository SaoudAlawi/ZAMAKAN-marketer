#!/usr/bin/env python3
"""Two documentary production helpers, Arabic first (Word, right to left, plus CSV for spreadsheets).

archive   An archive log: every archive item the film uses (photos, footage, music), where it is used, and columns
          for owner, rights status, cost and credit line. Items are found in a documentary script.json (from
          av_script.py, paper_edit.py or doc_to_script.py); a filled-in log (CSV) is merged back, so statuses survive
          the next draft.
shoots    A shoot list from a plan.json: what to film, where, with whom, and whether access is confirmed. Items whose
          access is pending come first, so nobody travels to film a yes that hasn't been given.
          --skeleton av.json writes a plan.json to fill in, one item per picture line.

Usage:
  python doc_helpers.py archive script.json [--merge archive-log.csv] [--out <dir>]
  python doc_helpers.py shoots plan.json [--out <dir>]
  python doc_helpers.py shoots --skeleton av.json [--out <dir>]

plan.json: {"title": "...", "lang": "ar", "items": [{"what": "...", "where": "...", "who": "...", "when": "...",
            "access": "confirmed|pending|no", "needs": "...", "rows": [3, 4]}]}
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _screenplay as S  # noqa: E402
import build_template as B  # noqa: E402
from digest import DOC_HINTS  # noqa: E402

ARCHIVE_COLS = ["id", "item", "used_in", "owner", "rights", "cost", "credit", "notes"]
STATUS = {"confirmed": ("✓", "0ca30c"), "pending": ("!", "fab219"), "no": ("✕", "d03b3b")}
T = {"ar": {"archive": "سجل الأرشيف", "acols": ["#", "المادة", "أين تُستخدم", "المالك / المصدر", "حالة الحقوق", "الكلفة", "سطر الشكر", "ملاحظات"],
            "a_hint": "كل مادة أرشيفية في الفيلم. املأ المالك وحالة الحقوق (للسؤال / طُلبت / مُصرّح بها) قبل المونتاج النهائي.",
            "to_ask": "للسؤال", "shoots": "قائمة التصوير", "scols": ["#", "ماذا نصوّر", "أين", "مع من", "متى", "الوصول", "ما نحتاجه"],
            "s_hint": "ما ينتظر موافقة أحد في الأعلى: لا تسافر لتصوير موافقة لم تُعطَ بعد.",
            "access": {"confirmed": "مؤكد", "pending": "بانتظار الموافقة", "no": "مرفوض"}, "section": "القسم", "row": "صف"},
     "en": {"archive": "Archive log", "acols": ["#", "Item", "Used in", "Owner / source", "Rights status", "Cost", "Credit line", "Notes"],
            "a_hint": "Every archive item in the film. Fill in the owner and rights status (to ask / requested / cleared) before the final cut.",
            "to_ask": "to ask", "shoots": "Shoot list", "scols": ["#", "What we film", "Where", "With whom", "When", "Access", "Needs"],
            "s_hint": "Anything waiting on someone's yes comes first: don't travel to film a yes that hasn't been given.",
            "access": {"confirmed": "confirmed", "pending": "pending", "no": "refused"}, "section": "Section", "row": "row"}}


def find_archive(sc):
    """Archive items in a documentary script.json: picture or sound lines that mention archive."""
    heads = {s["n"]: s["heading"] for s in sc["scenes"]}
    t = T[sc["lang"]]
    items = []
    for e in sc["elements"]:
        if e["type"] in ("action", "dialogue") and re.search(DOC_HINTS["archive"], e["text"], re.I):
            where = f"{t['section']} {e.get('scene')}: {heads.get(e.get('scene'), '')}" + (f" · {t['row']} {e['row']}" if e.get("row") else "")
            items.append({"item": e["text"].strip(), "used_in": where})
    return items


def norm(s):
    return re.sub(r"\W+", "", s or "")


def merge(items, path):
    """Keep what the team already filled in (owner, rights, cost…) for items still in the film; keep removed ones
    at the end, marked, so nothing silently disappears from the log."""
    old = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    by = {norm(r.get("item")): r for r in old}
    out, seen = [], set()
    for it in items:
        r = by.get(norm(it["item"]))
        if r:
            seen.add(norm(it["item"]))
            it = {**{k: r.get(k, "") for k in ARCHIVE_COLS}, **it}
        out.append(it)
    for k, r in by.items():
        if k not in seen:
            out.append({**r, "notes": ((r.get("notes") or "") + " [no longer in this draft]").strip()})
    return out


def archive(sc, merge_csv=None):
    items = find_archive(sc)
    if merge_csv:
        items = merge(items, merge_csv)
    t = T[sc["lang"]]
    for i, it in enumerate(items, 1):
        it["id"] = f"AR{i:02d}"
        it.setdefault("rights", t["to_ask"])
        if not it.get("rights"):
            it["rights"] = t["to_ask"]
    return items


def archive_docx(items, lang, title):
    t = T[lang]
    doc = S.new_document(lang)
    S.add_page_numbers(doc, lang)
    B.para(doc, f"{title} · {t['archive']}", lang, style="Title")
    B.para(doc, t["a_hint"], lang, grey=True, italic=True, size=10)
    rows = [t["acols"]] + [[it["id"], it["item"], it["used_in"], it.get("owner", ""), it.get("rights", ""), it.get("cost", ""), it.get("credit", ""), it.get("notes", "")]
                           for it in items]
    B.table(doc, rows, lang)
    return doc


def write_csv(rows, cols, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel shows Arabic
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def skeleton(av):
    return {"title": av["title"], "lang": av["lang"], "items": [
        {"what": r["picture"], "where": "", "who": "", "when": "", "access": "pending", "needs": "", "rows": [r["n"]]}
        for r in av["rows"] if r["picture"].strip()]}


def check_plan(plan):
    errs = []
    for i, it in enumerate(plan.get("items", [])):
        if not it.get("what"):
            errs.append(f"item {i}: say what we film")
        if it.get("access") not in STATUS:
            errs.append(f"item {i}: access must be confirmed, pending or no")
    return errs


def shoots_docx(plan):
    lang = plan.get("lang", "ar")
    t = T[lang]
    doc = S.new_document(lang)
    S.add_page_numbers(doc, lang)
    B.para(doc, f"{plan.get('title', '')} · {t['shoots']}", lang, style="Title")
    B.para(doc, t["s_hint"], lang, grey=True, italic=True, size=10)
    rank = {"pending": 0, "no": 1, "confirmed": 2}
    items = sorted(plan["items"], key=lambda x: (rank[x["access"]], x.get("when") or "", x.get("where") or ""))
    rows = [t["scols"]] + [[S.digits(i, lang), it["what"], it.get("where", ""), it.get("who", ""), it.get("when", ""),
                            f"{STATUS[it['access']][0]} {t['access'][it['access']]}", it.get("needs", "")] for i, it in enumerate(items, 1)]
    tb = B.table(doc, rows, lang)
    for i, it in enumerate(items, 1):  # the status icon carries the meaning; the tint only supports it
        cell = tb.cell(i, 5)
        cell._tc.get_or_add_tcPr().append(S._el("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": {"confirmed": "DFF3DF", "pending": "FDECC8", "no": "F6D6D6"}[it["access"]]}))
    return doc, items


def stem_of(title):
    return re.sub(r"[^\w؀-ۿ-]+", "-", title or "film").strip("-") or "film"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("archive")
    a1.add_argument("script")
    a1.add_argument("--merge")
    a1.add_argument("--out", default=".")
    a2 = sub.add_parser("shoots")
    a2.add_argument("plan", nargs="?")
    a2.add_argument("--skeleton")
    a2.add_argument("--out", default=".")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "archive":
        sc = json.loads(Path(a.script).read_text(encoding="utf-8"))
        items = archive(sc, a.merge)
        title = (sc.get("title_page") or {}).get("title", "")
        stem = stem_of(title)
        archive_docx(items, sc["lang"], title).save(out / f"{stem}-archive-log.docx")
        write_csv(items, ARCHIVE_COLS, out / f"{stem}-archive-log.csv")
        print(f"OK: {len(items)} archive items → {out / (stem + '-archive-log.docx')} + .csv")
        return
    if a.skeleton:
        import av_script as AV
        p = Path(a.skeleton)
        av = json.loads(p.read_text(encoding="utf-8")) if p.suffix == ".json" else AV.read(p)
        plan = skeleton(av)
        dst = out / f"{stem_of(av['title'])}-plan.json"
        dst.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"OK: {len(plan['items'])} items to fill in (where, who, when, access, needs) → {dst}")
        return
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    errs = check_plan(plan)
    for e in errs:
        print("  ERROR", e)
    if errs:
        sys.exit(1)
    doc, items = shoots_docx(plan)
    stem = stem_of(plan.get("title"))
    doc.save(out / f"{stem}-shoot-list.docx")
    write_csv(items, ["what", "where", "who", "when", "access", "needs"], out / f"{stem}-shoot-list.csv")
    pend = sum(1 for x in items if x["access"] == "pending")
    print(f"OK: {len(items)} items · {pend} waiting on access → {out / (stem + '-shoot-list.docx')} + .csv")


if __name__ == "__main__":
    main()
