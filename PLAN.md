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

## 3. Feature 1: Design System Creator (visual only), ⏸ PAUSED after iteration 1

> **Resume here:** iteration 2 = adopt the 4 baseline ideas (section 5b), write harder assertions
> (format consistency, rule-vs-mock-up contradictions), and run 3 times per configuration. Results of iteration 1:
> https://claude.ai/artifact/MTc8Fcf1zEhJq5dTGuq5ti

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

## 3b. Feature 2: Campaign Reference Scout, 🟨 ACTIVE

**Goal:** bring the best campaign references, both from similar clients and from anywhere (so creativity
isn't limited), and turn them into analysis that people and other agents can both use.

### Modes (the skill detects which one, or asks)
| Mode | Example | Emphasis |
|---|---|---|
| **Brief** | "Rawaq Ramadan campaign, awareness, young Riyadh professionals" | All 4 rings → territories for the creative team |
| **Creative question** | "Best coffee ads that use heritage without clichés" | Wide search on one idea; fewer rings |
| **Competitor watch** | "What are Riyadh coffee brands running right now?" | Live ads (Meta Ad Library, TikTok Creative Center, Google Ads Transparency) + recent posts |
| **Pitch prep** | "References section for our pitch to X" | Fewer, stronger, award-level work; presentation-ready |

### Pipeline
1. **Frame**: read the brief + the client's design system/brand.md (via zamakan-core); fill a short
   `brief.json` (category, market, objective, audience, channels, moment e.g. Ramadan); ask only what's missing.
2. **Check the library first**: `library.py search` returns references the agency already analysed.
3. **Search plan**: queries per ring × source × language (English **and Arabic** queries).
   Rings: ① direct (same category, KSA/GCC, incl. competitors) ② category worldwide
   ③ adjacent categories that share the insight ④ wildcard award-level work.
4. **Collect**: web search → candidate URLs → `fetch_meta.py` pulls a compact record per URL
   (title, brand, agency, country, year, media, credits, thumbnail, video link) using site parsers
   (Ads of the World, Vimeo/YouTube oEmbed, award sites) with an Open Graph fallback.
5. **Verify**: **no invented campaigns.** Every reference must resolve to a real page whose title
   matches (`verify.py`); unverifiable items are dropped or marked `unverified`.
6. **Score & select**: relevance, ring balance, recency, region, awards/results → shortlist of 20–30 + top 5.
7. **Analyse (tiered)**: quick card for each; deep teardown for the top 5 (insight, idea, execution,
   channels, tone, visual devices, published results, **what's transferable to this client**,
   **Saudi/Gulf cultural fit**, risks).
8. **Synthesise**: patterns, white space (what nobody in the category does), 3–5 **creative territories**,
   each tied to the references that support it.
9. **Deliver**: the skill **asks which output(s)**: visual **board** (HTML: thumbnails, filters, cards),
   **deck** (client-ready slides), **report** (written analysis). Agents always get `references.json` + `territories.md`.
10. **Save to the shared library**: dedupe and merge into `library/references.jsonl`.

### Contract (what other agents read)
```
clients/<slug>/jobs/<date>-scout-<topic>/
├── brief.json            # framed brief
├── references.json       # every reference: metadata, ring, scores, card, teardown, provenance
├── territories.md        # 3–5 creative territories + supporting references
├── board.html | deck | report.md   # human outputs, as chosen
└── thumbs/               # thumbnails (internal reference use only)
library/references.jsonl  # agency-wide, deduplicated, grows every run
```

### Web access
Searching works everywhere. **Reading pages** needs the sites allowed in this environment's network
settings (title-bar environment menu → Edit → Network access). Either pick a broader access level, which suits
"references from anywhere", or add these domains under *Allowed domains*:
`adsoftheworld.com`, `vimeo.com`, `player.vimeo.com`, `i.vimeocdn.com`, `youtube.com`, `www.youtube.com`,
`i.ytimg.com`, `lovethework.com`, `dandad.org`, `oneclub.org`, `dubailynx.com`, `campaignme.com`,
`behance.net`, `adforum.com`, `lbbonline.com`, `campaignlive.co.uk`, `adage.com`, `adweek.com`,
`facebook.com` (Ad Library), `ads.tiktok.com` (Creative Center), `adstransparency.google.com`, `pinterest.com`.

### Prior art & reuse (researched 2026-10-13)
| Existing work | Covers | Decision |
|---|---|---|
| [apify/awesome-skills → apify-ads-intelligence](https://github.com/apify/awesome-skills) (Apache-2.0) | Live ads from Meta, Google Transparency, TikTok Library + Creative Center, LinkedIn, X via Apify scrapers; intent routing, cost limits | **Reuse for Competitor-watch mode** (use the skill or its actor routing). Needs an Apify account (pay per result) |
| marketingskills `ads/references/creative-research-automation.md` (MIT) | Ad Library teardown fields (format split, partnership %, longest-running = proven winner), organic teardown, persona gap | **Adopt its teardown fields** in our competitor analysis |
| marketingskills `competitor-profiling` (MIT) | Full competitor dossiers from URLs | Hand off to it when a deep dossier is asked |
| Meta's official Ads MCP (mcp.facebook.com/ads) | Managing *your own* ad accounts | Not for research; ignore |
| Foreplay API, AdForum Creative Library, Cannes Lions "The Work" | Commercial ad/award archives | Optional paid connectors later |
| Award/showcase research (Ads of the World, Vimeo, Love the Work, Dubai Lynx…) + Arabic/GCC lens + territories + shared library | **Nothing found** | **Build: this is ZAMAKAN's core** |

### Testing
There is no fixed answer key (the web changes), so the grader checks **properties**:
- every URL resolves and matches its title, so nothing is hallucinated;
- the rings are covered and enough GCC references are included;
- the top-5 teardowns are complete;
- each territory is linked to its references;
- Ramadan relevance;
- the schema is valid and the board renders.
It runs with and without the skill, 3 runs each, plus your review.

### Build steps
| # | Step | Test gate | Status |
|---|---|---|---|
| 1 | Contract: `reference.schema.json`, `brief.json`, library format; Rawaq Ramadan test brief; saved sample pages for offline tests | schema tests | ⬜ |
| 2 | Scripts: `fetch_meta.py` (site parsers + OG fallback), `verify.py`, `library.py`, `score.py` | pytest on saved pages + live smoke test | ⬜ |
| 3 | Output builders: board (HTML), deck, report | pytest + your visual review | ⬜ |
| 4 | SKILL.md (4 modes) + references (sources guide, analysis framework, Gulf calendar & cultural-fit guide) | first end-to-end run | ⬜ |
| 5 | Evals: with vs without skill, property-based grader, 3 runs each | clear win + your review | ⬜ |

## 4. Build steps & test gates (Feature 1)

| # | Step | Test gate | Status |
|---|------|-----------|--------|
| 0 | Plan + requirements | You approve | ✅ |
| 1 | Sample client package (Rawaq) + answer key | PDF renders correctly; known traps verified | ✅ |
| 2 | Output contract: spec.json schema + validator, gold Rawaq spec, consumer contract, brand.md template | 17 pytest pass; every deliberate mistake caught | ✅ |
| 3 | Scripts: inventory, pdf digest (colours/swatches/conflicts/flags/renders), fonts, logos, extract_all → digest.md | 59 pytest pass; every answer-key trap detected | ✅ |
| 4 | build_design_system.py: tokens.json (DTCG 2025.10), tokens.css, manifest, sources.md (+contrast), **DESIGN.md** (passes Google's linter: 0 errors), preview style tile | 73 pytest pass; deterministic; preview awaiting your review | ✅ |
| 5 | SKILL.md for zamakan-design-system + zamakan-core (+ client.py, spec guide, grader) | First end-to-end run on Rawaq: 16/16, spec matches gold; 6 skill issues fixed | ✅ |
| 6 | Evals: with-skill vs without-skill, graded against answer key | Iteration 1: both 16/16 (assertions too easy); skill 3.4× faster, 37% fewer tokens, fixed contract. Iteration 2: harder assertions, 3 runs each | 🟨 |
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

## 5b. Iteration-1 learnings (adopt from the baseline)

The no-skill baseline did several generic things worth building into the skill:
1. Extract icons / vector graphics from the PDF as SVG assets (script).
2. Generate clear-space-padded logo files (script, from the clear-space rule).
3. Render graphic elements, pattern and icons on the preview style tile.
4. Audit application/mock-up pages against the rules and flag contradictions.
5. Sample on-brand renders → belongs to a future *social post designer* sub-skill.

## 6. Progress log

- 2026-10-13: Requirements captured; plan drafted.
- 2026-10-13: Re-scoped to the sub-skill architecture; built the Rawaq sample package and answer key.
- 2026-10-13: Feature 2 (reference scout) defined; network limits of the cloud environment noted.
- 2026-10-13: Step 2 done. Design: the agent writes only spec.json + brand.md; scripts generate the rest.
- 2026-10-13: Feature 1 paused by the user; switching to Feature 2 (reference scout).
- 2026-10-13: Step 5 done + iteration-1 eval (see 5b). Fixed: canonical roles, components, missing_assets, contrast pairing, docs.
- 2026-10-13: Step 4 done. One build command generates all contract files from spec.json; DESIGN.md validated with @google/design.md 0.4.0.
- 2026-10-13: Step 3 done. One command (`extract_all.py`, about 5 s) turns the brand folder into a 6 KB digest + 10 KB page text + 2 contact sheets. Reviewed marketingskills + DESIGN.md (see 4b).
