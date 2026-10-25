#!/usr/bin/env python3
"""Read the writer's side of the margin conversation from the annotated Word file they send back: replies to each
note (Word's Reply, a comment of their own on the same line, or text typed into the note), and notes they marked
Resolved. The next reading uses it: what the writer defended is respected, what they fixed is checked, what they
disagree with is reconsidered, never repeated blindly.

Usage: python replies.py <title>-notes.docx --notes notes.json --out replies.json
Works with Word, LibreOffice and Google Docs exports (replies are matched by Word's reply link when present, else by
sitting on the same line as the note).
"""
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
W15 = "{http://schemas.microsoft.com/office/word/2012/wordml}"
TAG = re.compile(r"^■.*#(\d+)\s*$")


def _xml(z, name):
    from lxml import etree
    try:
        return etree.fromstring(z.read(name))
    except KeyError:
        return None


def ptext(p):
    return "".join(t.text or "" for t in p.iter(W + "t")).strip()


def read(path, notes=None):
    with zipfile.ZipFile(path) as z:
        com, ext, doc = _xml(z, "word/comments.xml"), _xml(z, "word/commentsExtended.xml"), _xml(z, "word/document.xml")
    if com is None:
        return []
    comments = []
    for c in com.iter(W + "comment"):
        paras = [p for p in c.iter(W + "p")]
        lines = [ptext(p) for p in paras if ptext(p)]
        comments.append({"cid": c.get(W + "id"), "author": c.get(W + "author") or "", "lines": lines,
                         "para_ids": [p.get(W14 + "paraId") for p in paras if p.get(W14 + "paraId")]})
    by_para = {pid: c for c in comments for pid in c["para_ids"]}
    exinfo = {}
    if ext is not None:
        for e in ext.iter(W15 + "commentEx"):
            exinfo[e.get(W15 + "paraId")] = {"parent": e.get(W15 + "paraIdParent"), "done": e.get(W15 + "done") == "1"}
    # which comments start in the same paragraph (fallback when there is no reply link)
    same_par = {}
    if doc is not None:
        for p in doc.iter(W + "p"):
            ids = [s.get(W + "id") for s in p.iter(W + "commentRangeStart")]
            for i in ids:
                same_par[i] = ids
    ours = {}
    for c in comments:
        m = TAG.match(c["lines"][0]) if c["lines"] else None
        if m:
            c["note_id"] = int(m.group(1))
            ours[c["cid"]] = c
    items = {c["note_id"]: {"id": c["note_id"], "replies": [], "done": any(exinfo.get(p, {}).get("done") for p in c["para_ids"])}
             for c in ours.values()}
    for c in ours.values():  # text the writer typed into the note itself
        original = (notes or {}).get("notes", [{}] * (c["note_id"] + 1))[c["note_id"]].get("text") if notes and c["note_id"] < len(notes["notes"]) else None
        extra = [ln for ln in c["lines"][1:] if not original or (ln not in original and original not in ln)]
        if original is None:
            extra = c["lines"][2:]
        if extra:
            items[c["note_id"]]["replies"].append({"author": "(in the note)", "text": " ".join(extra)})
    for c in comments:
        if c["cid"] in ours:
            continue
        parent = None
        for pid in c["para_ids"]:
            par = exinfo.get(pid, {}).get("parent")
            if par and par in by_para and by_para[par]["cid"] in ours:
                parent = by_para[par]
        if parent is None:
            for other in same_par.get(c["cid"], []):
                if other in ours:
                    parent = ours[other]
                    break
        if parent is not None and c["lines"]:
            items[parent["note_id"]]["replies"].append({"author": c["author"], "text": " ".join(c["lines"])})
    out = []
    for nid, it in sorted(items.items()):
        n = notes["notes"][nid] if notes and nid < len(notes["notes"]) else {}
        if it["replies"] or it["done"]:
            out.append({**it, "scene": n.get("scene"), "lens": n.get("lens"), "note": (n.get("text") or "")[:200]})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx")
    ap.add_argument("--notes", help="the notes.json the Word file was made from (to tell new text from the note)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    notes = json.loads(Path(a.notes).read_text(encoding="utf-8")) if a.notes else None
    items = read(a.docx, notes)
    Path(a.out).write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(items)} note(s) with a reply or marked resolved → {a.out}")
    for it in items:
        rep = " | ".join(f"{r['author']}: {r['text'][:120]}" for r in it["replies"])
        print(f"  #{it['id']} S{it.get('scene')} {it.get('lens')}" + (" ✓ marked resolved" if it["done"] else "") + (f" · {rep}" if rep else ""))


if __name__ == "__main__":
    main()
