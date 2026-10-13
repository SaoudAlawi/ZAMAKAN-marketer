# ZAMAKAN Marketer — Build Plan

A state-of-the-art marketing & creative skill for Claude Code, built for an
**agency serving many clients**, **bilingual Arabic + English with a Gulf/Saudi focus**,
covering **strategy, copy, visual creative, and performance**.

Status legend: ⬜ not started · 🟨 in progress · ✅ done & tested

---

## 1. Design principles

1. **Think like a senior agency team, not a copy generator.** Every job flows
   brief → insight → strategy → idea → execution → critique. Output that skips the
   insight is rejected by the skill's own quality gate.
2. **Client memory lives in files.** Each client gets a persistent Brand Book
   (`clients/<slug>/brand.md`) that the skill creates once and reuses on every job.
   No re-explaining the brand each session.
3. **Arabic is transcreated, never translated.** Arabic copy is written natively
   (Saudi white dialect or MSA by context), with its own hooks, wordplay and rhythm.
4. **Deterministic where possible.** Character limits, platform specs, A/B sample sizes,
   cultural dates, and RTL rendering are handled by tested scripts, not guesswork.
5. **Show, don't describe.** Visual concepts are rendered as real PNG mockups
   (HTML/CSS → Chromium), in both RTL Arabic and English.
6. **Lean core, deep references.** `SKILL.md` is a router (<500 lines); expertise lives
   in reference files loaded only when the task needs them.

## 2. Architecture

```
.claude/skills/zamakan-marketer/
├── SKILL.md                      # router: intake → pick workflow → quality gate
├── references/
│   ├── intake/                   # brief interview, brand-book builder
│   ├── strategy/                 # positioning, insight mining, personas, funnel, big idea
│   ├── copy/                     # frameworks, hooks, headlines, CTAs, Arabic craft
│   ├── channels/                 # Snapchat, TikTok, Instagram, X, YouTube, LinkedIn,
│   │                             # Meta/Google/Snap/TikTok ads, email, SMS/WhatsApp, SEO
│   ├── visual/                   # art direction, image-gen prompting, storyboards, layouts
│   ├── performance/              # testing, KPIs, benchmarks, budget allocation, reporting
│   ├── gulf-market/              # Saudi/GCC consumer, dialects, cultural calendar,
│   │                             # sensitivities, regulatory notes (verify-before-use)
│   └── quality/                  # scoring rubric, red-flag checklist
├── workflows/                    # step-by-step playbooks (campaign, launch, calendar, ad set…)
├── templates/                    # brief, brand book, campaign plan, calendar, report
├── assets/mockups/               # HTML/CSS ad & post templates (RTL + LTR, per format)
└── scripts/
    ├── validate_copy.py          # per-platform length/format checks (Arabic-aware)
    ├── render_mockup.py          # HTML → PNG via Playwright/Chromium
    ├── ab_test.py                # sample size, significance, MDE
    ├── gulf_calendar.py          # campaign moments for a date range (Ramadan, Eids, …)
    └── brief_check.py            # brief completeness score + missing questions

clients/<slug>/                   # created by the skill per client
├── brand.md                      # Brand Book: voice, audience, offers, do/don't, examples
└── jobs/<date>-<job>/            # every deliverable, versioned
```

## 3. Core workflow (what SKILL.md enforces)

1. **Identify client** → load `clients/<slug>/brand.md`, or run Brand Book intake.
2. **Check brief** → `brief_check.py`; ask only the missing high-impact questions.
3. **Route** to workflow: campaign · launch · content calendar · ad set · copy pack ·
   visual concepts · performance analysis · strategy doc.
4. **Strategy pass** → audience truth, insight, single-minded proposition.
5. **Ideas** → 3 distinct creative routes (safe / bold / unexpected), each with a reason to exist.
6. **Execution** → bilingual assets per channel, validated by scripts.
7. **Quality gate** → score against rubric; revise anything below threshold.
8. **Deliver** → files in `clients/<slug>/jobs/…` + a concise summary.

## 4. Build phases & test gates

Each phase ends with a **test gate**: unit tests for scripts (pytest) + eval prompts run
with and without the skill, graded with assertions, plus your review in the eval viewer.
We do not move on until the gate passes.

| # | Phase | Deliverables | Test gate |
|---|-------|-------------|-----------|
| 0 | Plan | This document | You approve it ✅ when signed off |
| 1 | Foundation | SKILL.md router, brand-book intake, brief_check.py, quality rubric, eval harness | pytest green; evals: new-client intake, vague brief handling |
| 2 | Strategy | strategy refs, personas, insight mining, campaign architecture, gulf_calendar.py | evals: campaign strategy for 2 different clients beat baseline |
| 3 | Copy | frameworks, hooks library, Arabic craft guide, channel specs, validate_copy.py | evals: bilingual ad set passes all length checks; native-quality Arabic (your review) |
| 4 | Visual | art direction, image-prompt guide, storyboards, mockup templates, render_mockup.py | rendered RTL + LTR PNGs look right; evals: visual concept pack |
| 5 | Performance | testing/KPI/budget refs, ab_test.py, results-analysis workflow | pytest for stats; eval: analyse a sample campaign CSV |
| 6 | Integration | end-to-end campaign workflow, cross-phase polish | full eval suite, blind A/B vs baseline |
| 7 | Triggering | description optimisation (20 trigger/no-trigger queries) | trigger accuracy on held-out set |

## 5. Open decisions (to settle together)

- Default Arabic register: Saudi white dialect vs MSA vs ask per client
- Image-generation tools the team uses (Midjourney, GPT-Image, Firefly, Imagen…) → prompt formats
- Whether client Brand Books are committed to this repo or kept in a git-ignored folder
- A real (or realistic) client brief to use as our main eval case

## 6. Progress log

- 2026-10-13 — Repo empty; requirements captured; plan drafted (Phase 0).
