#!/usr/bin/env python3
"""Benchmark the reference scout: scenarios × {with_skill, without_skill} × runs, graded and tracked across iterations.

Usage:
  python evals/bench_scout.py prepare  --iteration 2 [--runs 1] [--scenarios s1-gcc-brief,...] --root <workspace>
      creates <root>/iteration-N/<scenario>/<config>/run-K/outputs with brief.md (and the client's design system where the
      scenario has one) and writes prompt.txt next to it: the exact task for the test agent
  python evals/bench_scout.py timing   <run_dir> --tokens N --seconds S        # record what the agent run cost
  python evals/bench_scout.py grade    --iteration 2 --root <workspace>        # grade every run (grade_scout.py)
  python evals/bench_scout.py scorecard --iteration 2 --root <workspace> [--note "..."]
      aggregates into evals/scorecard/history.json (committed; one entry per iteration) and renders
      evals/scorecard/scorecard.html (quality, real-link rate, consistency, time, tokens; with vs without; trend)

Agents are launched by the orchestrating Claude session with each run's prompt.txt (subagents, run in parallel).
Test agents must never see evals/: prompts forbid it, and briefs are copied into the run folder.
"""
import argparse
import datetime as dt
import json
import shutil
import statistics as st
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCEN = REPO / "evals/fixtures/scout/scenarios"
SKILL = REPO / ".claude/skills/zamakan-reference-scout"
CORE = REPO / ".claude/skills/zamakan-core"
HIST = REPO / "evals/scorecard/history.json"
CONFIGS = ("with_skill", "without_skill")

WITH = """You are a strategist at a Riyadh creative agency. Execute this task using the skill described below.

Skill: read and follow {skill}/SKILL.md (its scripts, schemas and references are in that folder; shared conventions: {core}/SKILL.md).

Working directory (treat it as the agency repo root for this task):
W={w}
Use job folder: $W/{job}/  (create it yourself; don't use client.py).{ds}

User request:
"{request}"

Rules for this run:
- Before running any skill script, export these so this test run is isolated:
  export ZAMAKAN_LIBRARY=$W/library/references.jsonl ZAMAKAN_SCOUT_CACHE=$W/.cache ZAMAKAN_CLIENTS=$W/clients
  (they must be set in every shell command that runs a skill script).
- Use absolute paths. Write everything under $W.
- Do NOT read anything in {repo}/ outside the two skill folders named above (never open evals/, library/, samples/, tests/, tools/: they contain grading material).
- Work autonomously; nobody can answer questions. Where you would ask, use the skill's defaults and record open questions.
- You have web search and the skill's scripts; internet access works.
- When done, reply with: your final message to the user, then a short candid list of problems you hit with the skill's instructions or scripts.
"""

WITHOUT = """You are a strategist at a Riyadh creative agency. Execute this task.

Working directory (write everything here):
W={w}
Put your deliverables in $W/{job}/.{ds}

User request:
"{request}"

Rules for this run:
- Use absolute paths. Do NOT read anything in {repo}/ (it contains grading material for this test). Do not use any skills.
- You have web search, a web-fetch tool, curl and Python (urllib, BeautifulSoup, Playwright with Chromium at /opt/pw-browsers/chromium, python-pptx, PyMuPDF). Internet access works; some sites block plain requests.
- Work autonomously; nobody can answer questions. Choose sensible deliverable formats yourself.
- When done, reply with your final message to the user.
"""


def scenarios(sel=None):
    ids = sorted(p.name for p in SCEN.iterdir() if (p / "scenario.json").exists())
    return [i for i in ids if not sel or i in sel.split(",")]


def load(sid):
    return json.loads((SCEN / sid / "scenario.json").read_text(encoding="utf-8"))


def runs(root, it):
    base = Path(root) / f"iteration-{it}"
    return sorted(p for p in base.glob("*/*/run-*") if (p / "outputs").exists())


def prepare(a):
    made = []
    for sid in scenarios(a.scenarios):
        sc = load(sid)
        for cfg in CONFIGS:
            for k in range(1, a.runs + 1):
                run = Path(a.root) / f"iteration-{a.iteration}" / sid / cfg / f"run-{k}"
                w = run / "outputs"
                w.mkdir(parents=True, exist_ok=True)
                shutil.copy(SCEN / sid / "brief.md", w / "brief.md")
                ds_line = ""
                if sc.get("design_system"):
                    ds = w / "clients" / sc["client"] / "design-system"
                    if not (ds / "spec.json").exists():
                        subprocess.run([sys.executable, SKILL.parent / "zamakan-design-system/scripts/build_design_system.py",
                                        REPO / "evals/fixtures/rawaq/expected-spec.json", "--input", REPO / "samples/rawaq/input",
                                        "--out", ds, "--no-preview"], check=True, capture_output=True)
                    ds_line = (f"\nThe client's design system (made by our design-system tool) is in $W/clients/{sc['client']}/design-system/ "
                               "(brand.md, tokens, logos, fonts); use it for anything visual.")
                tpl = WITH if cfg == "with_skill" else WITHOUT
                (run / "prompt.txt").write_text(tpl.format(skill=SKILL, core=CORE, w=w, job=sc["job"], ds=ds_line,
                                                           request=sc["request"], repo=REPO), encoding="utf-8")
                made.append(str(run))
    print("\n".join(made))


def timing(a):
    p = Path(a.run_dir) / "timing.json"
    p.write_text(json.dumps({"total_tokens": a.tokens, "duration_seconds": a.seconds}, indent=1) + "\n", encoding="utf-8")
    print(p)


def grade(a):
    sys.path.insert(0, str(REPO / "evals"))
    import grade_scout
    for run in runs(a.root, a.iteration):
        sid = run.parents[1].name
        r = grade_scout.grade(run, sid)
        print(f"{sid:22} {run.parent.name:14} {run.name}: {r['summary']['passed']}/{r['summary']['total']}  "
              f"links {r['stats']['alive']}/{r['stats']['ref_urls']}")


def aggregate(root, it):
    rows = []
    for run in runs(root, it):
        g = run / "grading.json"
        if not g.exists():
            continue
        gr = json.loads(g.read_text(encoding="utf-8"))
        tm = json.loads((run / "timing.json").read_text()) if (run / "timing.json").exists() else {}
        rows.append({"scenario": run.parents[1].name, "config": run.parent.name, "run": run.name,
                     "pass_rate": gr["summary"]["pass_rate"], "passed": gr["summary"]["passed"], "total": gr["summary"]["total"],
                     "alive_rate": gr["stats"]["alive_rate"], "links": gr["stats"]["ref_urls"],
                     "tokens": tm.get("total_tokens"), "seconds": tm.get("duration_seconds"),
                     "failed": [e["text"] for e in gr["expectations"] if not e["passed"]]})
    by = {}
    for cfg in CONFIGS:
        rs = [r for r in rows if r["config"] == cfg]
        if not rs:
            continue
        per_sc = {}
        for r in rs:
            per_sc.setdefault(r["scenario"], []).append(r["pass_rate"])
        spread = [max(v) - min(v) for v in per_sc.values() if len(v) > 1]
        num = lambda k: [r[k] for r in rs if r.get(k) is not None]  # noqa: E731
        by[cfg] = {"runs": len(rs), "quality": round(st.mean(num("pass_rate")), 3), "real_links": round(st.mean(num("alive_rate")), 3),
                   "consistency": round(1 - st.mean(spread), 3) if spread else None,
                   "minutes": round(st.mean(num("seconds")) / 60, 1) if num("seconds") else None,
                   "tokens_k": round(st.mean(num("tokens")) / 1000) if num("tokens") else None,
                   "per_scenario": {s: round(st.mean(v), 3) for s, v in per_sc.items()}}
    return rows, by


def scorecard(a):
    rows, by = aggregate(a.root, a.iteration)
    hist = json.loads(HIST.read_text(encoding="utf-8")) if HIST.exists() else []
    hist = [h for h in hist if h["iteration"] != a.iteration]
    findings = [l.strip("-• ").strip() for l in Path(a.findings).read_text(encoding="utf-8").splitlines() if l.strip()] if a.findings else []
    hist.append({"iteration": a.iteration, "date": dt.date.today().isoformat(), "note": a.note or "", "skill_version": skill_version(), "findings": findings,
                 "scenarios": {s: load(s)["title"] for s in sorted({r["scenario"] for r in rows})}, "summary": by, "runs": rows})
    hist.sort(key=lambda h: h["iteration"])
    HIST.parent.mkdir(parents=True, exist_ok=True)
    HIST.write_text(json.dumps(hist, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    out = HIST.parent / "scorecard.html"
    out.write_text(render(hist), encoding="utf-8")
    print(json.dumps(by, indent=1, ensure_ascii=False))
    print(f"wrote {HIST} and {out}")


def skill_version():
    import re
    m = re.search(r"version:\s*([\d.]+)", (SKILL / "SKILL.md").read_text(encoding="utf-8"))
    return m.group(1) if m else "?"


def render(hist):
    import html
    E = html.escape
    cur = hist[-1]
    by = cur["summary"]
    w, wo = by.get("with_skill", {}), by.get("without_skill", {})

    def fmt(v, kind):
        if v is None:
            return "–"
        return f"{v:.0%}" if kind == "pct" else (f"{v:.1f} min" if kind == "min" else f"{v:,}k" if kind == "tok" else str(v))

    def delta(a_, b_, kind, better="up"):
        if a_ is None or b_ is None:
            return ""
        d = a_ - b_
        good = d > 0 if better == "up" else d < 0
        txt = f"{d:+.0%}" if kind == "pct" else (f"{d:+.1f} min" if kind == "min" else f"{d:+,}k")
        return f'<span class="d {"good" if good else "bad" if d else ""}">{txt}</span>'
    metrics = [("Quality", "quality", "pct", "up", "share of checks passed, averaged over scenarios"),
               ("Real links", "real_links", "pct", "up", "share of delivered links that open (re-checked by the grader)"),
               ("Consistency", "consistency", "pct", "up", "1 − spread of quality between repeat runs (needs ≥2 runs)"),
               ("Time", "minutes", "min", "down", "average minutes per run"),
               ("Cost", "tokens_k", "tok", "down", "average tokens per run")]
    tiles = "".join(f'<div class="tile"><div class="k">{E(n)}</div><div class="v">{fmt(w.get(k), kind)}</div>'
                    f'<div class="s">without skill {fmt(wo.get(k), kind)} {delta(w.get(k), wo.get(k), kind, better)}</div>'
                    f'<div class="h">{E(hint)}</div></div>' for n, k, kind, better, hint in metrics)
    scen_rows = ""
    for sid, title in cur["scenarios"].items():
        rs = [r for r in cur["runs"] if r["scenario"] == sid]
        cell = {}
        for cfg in CONFIGS:
            x = [r for r in rs if r["config"] == cfg]
            if x:
                fails = sorted({f for r in x for f in r["failed"]})
                cell[cfg] = (f'<b>{st.mean(r["pass_rate"] for r in x):.0%}</b> <small>({x[0]["passed"]}/{x[0]["total"]})</small>'
                             f'<div class="bar"><i style="width:{st.mean(r["pass_rate"] for r in x) * 100:.0f}%"></i></div>'
                             + (f'<details><summary>{len(fails)} failed</summary><ul>{"".join(f"<li>{E(f)}</li>" for f in fails)}</ul></details>' if fails else '<small class="ok">all passed</small>'))
            else:
                cell[cfg] = "–"
        meta = [r for r in rs if r["config"] == "with_skill"]
        meta_wo = [r for r in rs if r["config"] == "without_skill"]
        tm = lambda x: f'{st.mean(r["seconds"] for r in x) / 60:.0f} min · {st.mean(r["tokens"] for r in x) / 1000:.0f}k' if x and all(r.get("seconds") and r.get("tokens") for r in x) else ""  # noqa: E731
        scen_rows += (f'<tr><th>{E(title)}<br><small>{E(sid)}</small></th><td>{cell["with_skill"]}<small class="m">{tm(meta)}</small></td>'
                      f'<td>{cell["without_skill"]}<small class="m">{tm(meta_wo)}</small></td></tr>')
    trend = "".join(f'<tr><td>Iteration {h["iteration"]}</td><td>{E(h["date"])}</td><td>v{E(h.get("skill_version", "?"))}</td>'
                    f'<td>{len(h["scenarios"])}</td><td>{fmt(h["summary"].get("with_skill", {}).get("quality"), "pct")}</td>'
                    f'<td>{fmt(h["summary"].get("without_skill", {}).get("quality"), "pct")}</td>'
                    f'<td>{fmt(h["summary"].get("with_skill", {}).get("real_links"), "pct")}</td>'
                    f'<td>{fmt(h["summary"].get("with_skill", {}).get("minutes"), "min")}</td>'
                    f'<td>{fmt(h["summary"].get("with_skill", {}).get("tokens_k"), "tok")}</td><td>{E(h.get("note", ""))}</td></tr>' for h in hist)
    findings = "".join(f"<li>{E(f)}</li>" for f in cur.get("findings", []))
    return f"""<title>Reference Scout Scorecard</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Serif&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap">
<style>
/* layout: one reading column, headline tiles, then per-scenario table, findings, history. ZAMAKAN house style. */
:root{{--bg:#F6F6F2;--panel:#FFFFFF;--ink:#14213D;--muted:#5C6575;--line:#DADDE3;--acc:#0B7C7C;--good:#1E7B4F;--bad:#A8402C;
--disp:"Instrument Serif",Georgia,serif;--body:"IBM Plex Sans",system-ui,sans-serif;--mono:"IBM Plex Mono",ui-monospace,monospace}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#10141D;--panel:#181E2B;--ink:#E7EAF1;--muted:#A2AABA;--line:#2B3345;--acc:#4CC3BD;--good:#62C995;--bad:#EE8B74;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#10141D;--panel:#181E2B;--ink:#E7EAF1;--muted:#A2AABA;--line:#2B3345;--acc:#4CC3BD;--good:#62C995;--bad:#EE8B74;color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 var(--body)}}
.wrap{{max-width:1080px;margin:0 auto;padding-inline:16px;padding-block:36px 64px;display:grid;gap:36px}}.wrap>*{{min-width:0}}
h1{{font:400 clamp(32px,5vw,46px)/1.05 var(--disp);margin:0;text-wrap:balance}}h2{{font:400 26px/1.2 var(--disp);margin:0 0 14px;text-wrap:balance}}
.eyebrow{{font:600 11px/1 var(--body);letter-spacing:.12em;text-transform:uppercase;color:var(--acc);margin-bottom:12px}}
.lede{{color:var(--muted);margin:12px 0 0;max-width:68ch}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}
.tile{{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:16px;min-width:0}}
.tile .k{{font:600 11px/1 var(--body);text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}}
.tile .v{{font:500 30px/1.1 var(--mono);font-variant-numeric:tabular-nums;margin:10px 0 6px}}.tile .s{{font-size:13px;color:var(--muted)}}.tile .h{{font-size:12px;color:var(--muted);margin-top:8px}}
.d{{font-weight:600;margin-left:4px}}.d.good{{color:var(--good)}}.d.bad{{color:var(--bad)}}
.scroll{{overflow-x:auto}}.tbl{{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:6px;font-variant-numeric:tabular-nums}}
.tbl th,.tbl td{{text-align:left;vertical-align:top;padding:12px 14px;border-bottom:1px solid var(--line)}}.tbl tr:last-child>*{{border-bottom:0}}
.tbl thead th{{font:600 11px/1.2 var(--body);text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}}.tbl tbody th{{font-weight:600;min-width:180px}}
.bar{{height:6px;background:var(--line);border-radius:3px;margin:6px 0;max-width:200px}}.bar i{{display:block;height:100%;background:var(--acc);border-radius:3px}}
small{{color:var(--muted)}}small.m{{display:block;margin-top:4px;font-family:var(--mono);font-size:12px}}.ok{{color:var(--good)}}
details summary{{cursor:pointer;color:var(--bad);font-size:13px}}details summary:focus-visible{{outline:2px solid var(--acc);outline-offset:2px}}details ul{{margin:6px 0 0;padding-left:18px;font-size:13px}}
.findings{{margin:0;padding-left:20px;display:grid;gap:10px;max-width:72ch}}
footer{{color:var(--muted);font-size:13px;max-width:72ch}}
</style>
<div class="wrap">
<header><div class="eyebrow">ZAMAKAN · reference scout · benchmark</div><h1>Reference scout scorecard</h1>
<p class="lede">Iteration {cur["iteration"]} · skill v{E(cur.get("skill_version", "?"))} · {E(cur["date"])} ·
{len(cur["scenarios"])} scenarios, each done once by an agent <b>with</b> the skill and once <b>without</b> it, then graded by the same checks.
{E(cur.get("note", ""))}</p></header>
<section><h2>With the skill, compared with without</h2><div class="tiles">{tiles}</div></section>
<section><h2>Per scenario</h2><div class="scroll"><table class="tbl"><thead><tr><th>Scenario</th><th>With skill</th><th>Without skill</th></tr></thead><tbody>{scen_rows}</tbody></table></div></section>
{f'<section><h2>What this round taught us</h2><ul class="findings">{findings}</ul></section>' if findings else ''}
<section><h2>Across iterations</h2><div class="scroll"><table class="tbl"><thead><tr><th>Iteration</th><th>Date</th><th>Skill</th><th>Scenarios</th><th>Quality (with)</th>
<th>Quality (without)</th><th>Real links</th><th>Time</th><th>Tokens</th><th>Note</th></tr></thead><tbody>{trend}</tbody></table></div></section>
<footer>Graded by evals/grade_scout.py: property checks per scenario (evals/fixtures/scout/scenarios), every link re-opened live by the grader,
the same beauty check for both sides. Links behind a bot wall or on hosts this machine can't reach are not counted either way.
Consistency needs repeat runs. Generated by evals/bench_scout.py.</footer>
</div>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("prepare", "grade", "scorecard"):
        p = sub.add_parser(name)
        p.add_argument("--iteration", type=int, required=True)
        p.add_argument("--root", required=True)
        if name == "prepare":
            p.add_argument("--runs", type=int, default=1)
            p.add_argument("--scenarios")
        if name == "scorecard":
            p.add_argument("--note")
            p.add_argument("--findings", help="text file, one finding per line, shown on the scorecard")
    p = sub.add_parser("timing")
    p.add_argument("run_dir")
    p.add_argument("--tokens", type=int, required=True)
    p.add_argument("--seconds", type=float, required=True)
    a = ap.parse_args()
    {"prepare": prepare, "grade": grade, "scorecard": scorecard, "timing": timing}[a.cmd](a)


if __name__ == "__main__":
    main()
