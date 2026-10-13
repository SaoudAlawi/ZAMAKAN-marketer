# ZAMAKAN Marketer

Marketing and creative skills for ZAMAKAN, an agency with many clients, working in Arabic and English with a Saudi/GCC focus.
They are built as **sub-skills that share file contracts**, with scripts doing the mechanical work so agents spend tokens on judgement.

**Read `PLAN.md` first.** It has the architecture, every decision made with the user, status per step, and the progress log.

## Where things are
- `.claude/skills/zamakan-core/`: shared conventions (client folders, contracts, quality bar) and `scripts/client.py`
- `.claude/skills/zamakan-design-system/`: feature 1, brand files → design system. **Paused after iteration 1**; see PLAN §3 and §5b to resume.
- `.claude/skills/zamakan-reference-scout/`: feature 2, campaign references + analysis. **Active.**
- `samples/rawaq/input/`: fictional test client (brand PDF, logos, fonts). All development runs on it.
- `evals/fixtures/`: answer keys, gold outputs, and the scout test brief. **Never show these to an agent under test.**
- `tests/`: pytest suite, which must stay green.
- `clients/` and `*-workspace/` are git-ignored, because real client material stays local.

## Setup & checks
```bash
pip install -r requirements.txt uharfbuzz   # uharfbuzz only for tools/sample-builders
python3 -m pytest -q tests                  # all pass; DESIGN.md linter test skips unless ZAMAKAN_DESIGNMD is set,
                                            # live scout tests skip when offline
curl -sS -o /dev/null -w '%{http_code}\n' https://www.example.org/   # 200 = web access works (Ads of the World itself 403s plain curl; the scripts handle it)
```
Rendering uses Playwright with the preinstalled Chromium (`/opt/pw-browsers/chromium`). The scripts find it automatically.

## Working style the user wants
- Plan together, then **test every step** before moving on. Report results honestly, including weak spots.
- Look for existing work first (MIT/Apache skills, standards) and reuse it rather than rebuilding.
- Commit and push each finished step to the working branch; keep `PLAN.md` status and the progress log current.
- Explain in plain language; the user is an agency person, not necessarily a developer.

## Next step
Feature 2 (reference scout) iteration 2: implement PLAN §3c (insights, competitor check, recommendation,
before-kickoff list, deck by default, better deck design), harder grader checks, then re-run with/without skill.
Iteration-1 comparison: https://claude.ai/artifact/UAd8URauEJzTHKWNeAGJ4Q. The test brief is
`evals/fixtures/scout/rawaq-ramadan-brief.{md,json}`; grader `evals/grade_scout.py`. Run test agents with
ZAMAKAN_LIBRARY and ZAMAKAN_SCOUT_CACHE pointing into their sandbox (the committed library holds the sample run).
