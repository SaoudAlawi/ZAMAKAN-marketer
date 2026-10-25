#!/usr/bin/env python3
"""Where the user's work lives, and which agency settings apply. Shared by every ZAMAKAN skill.

The skills can run from this repo (.claude/skills/) or from an installed plugin (~/.claude/plugins/...), so files a run
writes (clients/, library/, jobs/) never go next to the scripts: they go in the user's project folder.

  project_root()  $ZAMAKAN_ROOT, else the nearest folder above the current one that holds clients/, library/ or .git
                  (never the home folder itself), else the current folder.
  agency()        zamakan-core/agency.json (the defaults: ZAMAKAN, home market Oman), overlaid with the project's own
                  zamakan-agency.json (or the file $ZAMAKAN_AGENCY names), so another agency or market can set its home
                  without editing the skills.

Usage: python workspace.py            # prints the project folder and the agency settings in use
"""
import json
import os
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
AGENCY_FILE = "zamakan-agency.json"


def project_root(start=None):
    env = os.environ.get("ZAMAKAN_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(start or Path.cwd()).resolve()
    home = Path.home().resolve()
    for d in [here, *here.parents]:
        if d == home or d == d.parent:
            break
        if (d / "clients").is_dir() or (d / "library" / "references.jsonl").is_file() or (d / ".git").exists():
            return d
    return here


def agency(root=None):
    a = json.loads((CORE / "agency.json").read_text(encoding="utf-8"))
    env = os.environ.get("ZAMAKAN_AGENCY")
    local = Path(env) if env else project_root(root) / AGENCY_FILE
    if local.is_file():
        a.update(json.loads(local.read_text(encoding="utf-8")))
        a["source"] = str(local)
    else:
        a["source"] = str(CORE / "agency.json")
    return a


if __name__ == "__main__":
    print(f"project folder: {project_root()}")
    print(json.dumps(agency(), ensure_ascii=False, indent=1))
