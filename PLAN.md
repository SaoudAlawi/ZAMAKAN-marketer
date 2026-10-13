# ZAMAKAN Marketer: Build Plan

A family of **sub-skills that work together** for Claude Code. It is built for an **agency
serving many clients**, works in **Arabic + English with a Gulf/Saudi focus**, and uses **custom
scripts to keep token use low**. Scripts do the mechanical work; the agent spends its tokens on judgement.

Status legend: ⬜ not started · 🟨 in progress · ✅ done & tested

---

## 1. Principles

1. **A shared contract between sub-skills.** Each sub-skill writes files that the next one reads.
   The first contract is the client **design system**: every later sub-skill (social posts,
   ads, decks…) reads it, so its output is on-brand without anyone re-explaining the brand.
2. **Scripts first, model second.** Anything deterministic (parsing PDFs, measuring colours,
   reading fonts, contrast maths, rendering) is a tested script whose *compact* output the
   agent reads. The agent never reads a raw 80-page PDF when a 2 KB digest will do.
3. **Evidence over guesswork.** Every extracted value records where it came from (file + page)
   and a confidence. Conflicts are surfaced, not silently resolved.
4. **When information is missing, the skill proposes a value.** Proposals are clearly marked
   `proposed` (vs `extracted`), so a human can tell them apart at a glance.
5. **Test everything on one fixed sample.** All development runs against the fictional client
   **Rawaq** (`samples/rawaq/`), graded against a hidden answer key.

## 2. Repository layout

```
.claude/skills/
├── zamakan-core/                 # shared conventions: client folders, contracts, quality bar
├── zamakan-design-system/        # FEATURE 1: brand files → design system
└── zamakan-reference-scout/      # FEATURE 2: campaign references + analysis

samples/rawaq/input/              # fixed sample client package (committed)
evals/fixtures/rawaq/             # hidden answer key for grading
tools/sample-builders/            # scripts that generate sample inputs
clients/<slug>/                   # real client work (git-ignored)
```

## 3. Feature 1: Design System Creator (visual only)

**Input:** a client folder containing a full guideline PDF, plus any logos, fonts and images.

**Pipeline**
1. `inventory`: list and classify every file (guideline, logo, font, image…).
2. `pdf digest`: per-page text, detected colour values, fonts, images, plus page thumbnails, so
   the agent can check visually where text extraction fails (flattened pages, garbled Arabic).
3. `colours`: parse HEX/RGB/CMYK/Pantone, sample swatches from pages, measure logo colours,
   cross-check for conflicts.
4. `fonts`: read family, weights, scripts covered (Arabic/Latin) and variable axes from font files.
5. `logos`: catalogue the variants (colourway, orientation, background), normalise them, and render
   light/dark previews.
6. **Agent synthesis**: reason over the digests, resolve conflicts, infer rules, propose gaps.
7. `build`: write tokens (JSON + CSS), validate them (schema, WCAG contrast), and render a preview.
8. **Self-check**: the agent compares the preview against the guideline pages and fixes mismatches.

**Output (the contract):** `clients/<slug>/design-system/`
```
brand.md          # agent-facing visual guide: logo rules, colour usage, type, imagery, layout, do/don't
tokens.json       # W3C design-tokens format: colour, typography, spacing, radii…
tokens.css        # same values as CSS custom properties (for HTML/PNG rendering)
manifest.json     # every asset: path, type, variant, colourway, allowed backgrounds, min size
sources.md        # provenance for every value: file + page, extracted|proposed, conflicts
assets/           # normalised logos, fonts
preview.html/png  # visual style tile for human sign-off
```

## 3b. Feature 2: Campaign Reference Scout (after Feature 1)

**Goal:** bring the best campaign references, both from similar clients and from anywhere
(so creativity isn't limited), and turn them into analysis that both people and agents can use.

**Input:** a client's design system + brief (category, market, objective, audience), or an open creative question.

**Search rings:** ① direct, meaning the same category in KSA/GCC, including competitors · ② the same category worldwide ·
③ adjacent categories that share the insight · ④ wildcard award-level work from any category.

**Sources:** Ads of the World, Vimeo, YouTube, Dubai Lynx, MENA Effies, Cannes Lions/Love the Work,
D&AD, One Show, Campaign Middle East, Behance, Pinterest, plus **live competitor activity**
(Meta Ad Library, TikTok Creative Center, Google Ads Transparency).

**Depth (tiered):** a quick card for each of the ~20–30 references, and a deep teardown for the top 5: insight, idea,
execution, channels, tone, visual devices, results, what is transferable to this client, and Saudi cultural fit.

**Synthesis:** patterns, white space, and 3–5 creative territories.

**Outputs:** `references.json` (fixed schema, for agents) · `territories.md` · a visual HTML board
with thumbnails/filters/links + a strategic summary (for people).

**Shared agency library:** every search adds to one reference library that all clients share
(`library/references.jsonl`), so later searches reuse earlier work.

**Network note:** web search works everywhere. Fetching full pages (adsoftheworld.com, vimeo.com…)
needs those domains allowed in the environment's network settings; the skill falls back to a
search-only mode when it cannot fetch pages.

## 4. Build steps & test gates (Feature 1)

| # | Step | Test gate | Status |
|---|------|-----------|--------|
| 0 | Plan + requirements | You approve | ✅ |
| 1 | Sample client package (Rawaq) + answer key | PDF renders correctly; known traps verified | ✅ |
| 2 | Output contract: spec.json schema + validator, gold Rawaq spec, consumer contract, brand.md template | 17 pytest pass; every deliberate mistake caught | ✅ |
| 3 | Scripts: inventory, pdf digest (colours/swatches/conflicts/flags/renders), fonts, logos, extract_all → digest.md | 59 pytest pass; every answer-key trap detected | ✅ |
| 4 | Scripts: build tokens.json/CSS, manifest, sources.md, **DESIGN.md export**, contrast check, preview render | pytest; preview PNG reviewed by you | ⬜ |
| 5 | SKILL.md for zamakan-design-system + zamakan-core | First end-to-end run on Rawaq | ⬜ |
| 6 | Evals: with-skill vs without-skill, graded against answer key | Clear win over baseline; your review in eval viewer | ⬜ |
| 7 | Iterate until the answer-key score and your review are both satisfied | — | ⬜ |
| 8 | Trigger tuning (description optimisation) | Trigger accuracy on held-out queries | ⬜ |

## 4b. Prior art & reuse ("don't reinvent the wheel")

| Source | What we take | What we don't |
|---|---|---|
| [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) (MIT, 50 skills) | Architecture confirmation (shared context file read by every skill = our contract); Agent Skills spec conventions (name = dir, description ≤1024 chars, SKILL.md <500 lines, `metadata.version`); `evals/evals.json` per skill; plugin packaging. Generic skills (copywriting, ad-creative, social, ab-testing, competitor-profiling…) can be **used alongside** ZAMAKAN instead of rebuilt | Its single per-project context file (we need many clients); no Arabic/Gulf layer; no design-system extraction; no campaign-reference research |
| [google-labs-code/design.md](https://github.com/google-labs-code/design.md) (Apache-2.0, alpha) | Emerging standard for describing a design system to AI agents → we **export a DESIGN.md** from spec.json for interoperability (Stitch, coding agents) | Not our source of truth: UI-only, no logos/photography/Arabic typography rules |

ZAMAKAN focuses on what nobody else covers: brand files → verified design system, the campaign
reference scout, bilingual Arabic/Gulf craft, and agency-scale multi-client structure.

## 5. Decisions log

- Agency with many clients; Arabic + English (Gulf); used in Claude Code.
- Architecture: many sub-skills sharing contracts, with scripts to save tokens.
- Feature 1 = design-system creator, **visual identity only** (verbal identity later).
- Typical input = a full guideline PDF. Missing values → **skill proposes**, marked as proposed.
- Arabic register will be asked per client (relevant for later copy skills).
- Client data lives in git-ignored `clients/`; only the fictional sample is committed.
- Feature 2 = campaign reference scout: tiered depth, award work + live competitor ads,
  shared agency library. Build after Feature 1 is finished and tested.

## 6. Progress log

- 2026-10-13: Requirements captured; plan drafted.
- 2026-10-13: Re-scoped to the sub-skill architecture; built the Rawaq sample package and answer key.
- 2026-10-13: Feature 2 (reference scout) defined; network limits of the cloud environment noted.
- 2026-10-13: Step 2 done. Design: the agent writes only spec.json + brand.md; scripts generate the rest.
- 2026-10-13: Step 3 done. One command (`extract_all.py`, about 5 s) turns the brand folder into a 6 KB digest + 10 KB page text + 2 contact sheets. Reviewed marketingskills + DESIGN.md (see 4b).
