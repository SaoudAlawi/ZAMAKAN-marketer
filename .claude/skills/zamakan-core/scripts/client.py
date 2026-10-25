#!/usr/bin/env python3
"""ZAMAKAN client folders: list, status, init, job.

Usage:
  client.py list
  client.py status <slug>
  client.py init <slug> [--from <dir>]
  client.py job <slug> <job-name>
Options: --root <project dir> (default: workspace.project_root(): the nearest folder holding clients/, library/ or .git, else the CWD)
"""
import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from workspace import project_root  # noqa: E402

SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DS_FILES = ["spec.json", "brand.md", "tokens.json", "tokens.css", "manifest.json", "sources.md", "DESIGN.md", "preview.png"]


def repo_root(start=None):
    return project_root(start)


def status(root, slug):
    c = root / "clients" / slug
    if not c.exists():
        return {"slug": slug, "exists": False}
    ds = c / "design-system"
    have = [f for f in DS_FILES if (ds / f).exists()]
    st = {"slug": slug, "exists": True,
          "input_files": sum(1 for f in (c / "input").rglob("*") if f.is_file()) if (c / "input").exists() else 0,
          "design_system": "complete" if len(have) == len(DS_FILES) else ("partial" if have else "missing"),
          "missing": [f for f in DS_FILES if f not in have],
          "jobs": sorted(p.name for p in (c / "jobs").iterdir()) if (c / "jobs").exists() else []}
    if (ds / "spec.json").exists():
        spec = json.loads((ds / "spec.json").read_text(encoding="utf-8"))
        st["name"] = spec.get("client", {}).get("name")
        st["open_questions"] = spec.get("open_questions", [])
        st["conflicts"] = [x["topic"] for x in spec.get("conflicts", [])]
    return st


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["list", "status", "init", "job"])
    ap.add_argument("slug", nargs="?")
    ap.add_argument("job", nargs="?")
    ap.add_argument("--from", dest="src")
    ap.add_argument("--root")
    a = ap.parse_args()
    root = Path(a.root).resolve() if a.root else repo_root()
    clients = root / "clients"

    if a.cmd == "list":
        rows = [status(root, p.name) for p in sorted(clients.iterdir()) if p.is_dir()] if clients.exists() else []
        if not rows:
            print("no clients yet: create one with `client.py init <slug> --from <brand files dir>`")
        for r in rows:
            print(f"{r['slug']:<20} design-system: {r['design_system']:<8} input files: {r['input_files']:<4} jobs: {len(r['jobs'])}")
        return
    if not a.slug or not SLUG.match(a.slug):
        sys.exit("slug must be lowercase-kebab, e.g. 'rawaq' or 'noor-dental'")
    if a.cmd == "status":
        print(json.dumps(status(root, a.slug), ensure_ascii=False, indent=1))
    elif a.cmd == "init":
        inp = clients / a.slug / "input"
        inp.mkdir(parents=True, exist_ok=True)
        (clients / a.slug / "design-system").mkdir(exist_ok=True)
        if a.src:
            shutil.copytree(a.src, inp, dirs_exist_ok=True)
        print(json.dumps(status(root, a.slug), ensure_ascii=False))
    elif a.cmd == "job":
        if not a.job:
            sys.exit("usage: client.py job <slug> <job-name>")
        name = re.sub(r"[^a-z0-9]+", "-", a.job.lower()).strip("-")
        d = clients / a.slug / "jobs" / f"{dt.date.today():%Y-%m-%d}-{name}"
        d.mkdir(parents=True, exist_ok=True)
        print(d)


if __name__ == "__main__":
    main()
