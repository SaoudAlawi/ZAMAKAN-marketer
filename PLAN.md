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

### Source notes (tested live 2026-10-13)
- **Ads of the World**: works with browser headers. Each campaign page has a standard sentence (country, month/year, brand,
  agency, medium, industry), credits and related campaigns. Search = `/campaigns?search=<ONE keyword>` (multi-word returns
  nothing); lists by `/countries|industries|brands|agencies|medium_types|regions/<slug>`; 60 cards per page.
- **YouTube**: search page and oEmbed work; watch pages are bot-blocked from cloud IPs, so date/views come from search.
- **Vimeo**: oEmbed works; vimeo.com search is bot-blocked, so find Vimeo links via web search.
- **Campaign ME, LBB, Arabad, AdForum…**: read via Open Graph; discovered via web search.

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
| 1 | Contract: `brief.schema.json`, `references.schema.json` (one file the agent writes; outputs are generated), `validate_run.py` (honesty + coverage rules); Rawaq Ramadan test brief (md + json); example run from 3 real search results | 14 tests pass | ✅ |
| 2 | Scripts: `discover.py` (Ads of the World search/lists/related, YouTube search), `fetch_meta.py` (site parsers + oEmbed + Open Graph fallback, thumbnails), `verify.py` (live check, rejects invented/broken), `library.py`, `score.py`; `_web.py` (cache + Chromium fallback) | 14 tests on saved real pages + live; 197 candidates found in seconds | ✅ |
| 3 | `build_outputs.py`: board.html (self-contained, filters, RTL), deck.pptx (+PDF via LibreOffice), report.md, territories.md; shared library committed (`library/references.jsonl`); real sample run (16 verified refs, 4 territories) | 5 tests + visual check; awaiting your review | ✅ |
| 4 | SKILL.md (4 modes) + references (sources, analysis framework, Gulf culture) + worked example + grader | E2E iteration 1: both 11/11, 0 invented links; skill 8.5 vs 12.9 min; 7 tool issues fixed (v0.2.0) | ✅ |
| 5 | Iteration 2: close the packaging gap (see 3c), harder checks, 3 runs each | clear win + your review | ⬜ |

### 3c. Scout iteration-1 learnings (https://claude.ai/artifact/UAd8URauEJzTHKWNeAGJ4Q)
The no-skill baseline packaged the same research better. Adopt into the contract and builders:
1. `insights`: dated, sourced facts about the audience and moment ("Ramadan has two coffees"), shown first.
2. A competitor check by default in brief mode: one row per named competitor in `competitor_summary`.
3. `recommendation`: which territories to brief and how they combine.
4. "Before kickoff" checklist (limits, what to watch or confirm) in the outputs.
5. Default outputs for a kickoff: board + deck. Reference codes (R01…) for citing in territories.
6. A better deck design (dark/light rhythm, arch motif); use the client design system when it exists.
Harder eval checks: insights with sources, competitor coverage, recommendation present, cross-run consistency.

### 3d. Scout iteration 2: plan (agreed 2026-10-13)
| # | Step | Test gate | Status |
|---|---|---|---|
| 2a | **Strategy layer** in the contract: `insights` (dated, sourced), `recommendation`, `before_kickoff`, competitor check per named competitor, reference codes (R01…); validator rules | schema + validator tests | ✅ |
| 2b | **Scope switch** `gcc` / `mena` / `global` in brief and run: scoring weights, search plan (global award shows, more languages), cultural fit still judged for the client's market | scorer + validator tests | ✅ |
| 2c | **DESIGN.md theming** for board and deck: ZAMAKAN house DESIGN.md (default), the client's own `design-system/DESIGN.md` when it exists, or any of the 84 in [awesome-design-md](https://github.com/voltagent/awesome-design-md) (MIT) by name | renders in 3 themes; house file passes Google's linter | ✅ |
| 2d | **Awesome-style library**: one `REFERENCE.md` analysis per campaign + a browsable `library/README.md` index by category, market and moment | export tests | ✅ |
| 2e | **Outputs v2**: insights first, competitor table, recommendation, before-kickoff list; board + deck by default for kickoffs; deck redesign | build tests + visual review | ✅ |
| 2g | **Sparks from elsewhere** (user, during 2d): 3–5 references from outside the client's region *and* category in every brief/pitch/creative question, each with a "What if <client>…?" provocation; `score.py --sparks`; own section in board, deck, report | validator + scorer + output tests | ✅ |
| 3 | **Iteration 3** (from 40+ benchmark-agent reports): 3a housekeeping, 3b fetching/thumbnails, 3c honest verification evidence, 3d competitor-watch rebuilt, 3e output fixes, 3f ranking, 3g blind judge + repeat runs | 173 tests; partial benchmark (stopped to save tokens) | ✅ |
| 2f | **Benchmark suite + scorecard**: 5 scenarios (GCC brief, global creative question, competitor watch, pitch, global-scope brief), with vs without skill, repeated runs; quality, real-link rate, consistency, time, tokens; scorecard page tracked across iterations | grader tests; then the benchmark run | ✅ (first pass) |

## 3c. Feature 3: Shot Scout (cinematic references), ✅ BUILT v0.2.0 (2026-10-18, + Inspire me)

**Goal:** cinematic references for a subject, mood or effect: better than searching Vimeo, because the skill speaks
film language, searches the right source for each need, and tells production how to shoot it.

**Decisions (with the user, 2026-10-18)**
- Separate skill `zamakan-shot-scout`, reusing the reference scout's web, link-checking, brand-kit and board scripts.
- Four modes from day one: **subject/mood** ("desert at dawn, lonely and epic"), **effect/technique** ("dolly zoom",
  "liquid macro"), **match this frame** (an uploaded still → similar shots), **who does this well** (directors, DOPs,
  production houses known for a look).
- Every shot gets **production notes**: how it was done (practical / rig / VFX / edit), budget level, doable in KSA,
  AI-feasible.
- Vimeo without an API key for now: found through web search, each video checked through Vimeo's oEmbed. A free
  Vimeo developer key (environment secret) can be added later for direct search.

**Source map (tested 2026-10-18)**
| Need | Sources (reachable) | Blocked |
|---|---|---|
| Technique / effect | Eyecannndy, YouTube breakdowns, No Film School, ASC | |
| Film stills by look | Film-Grab, Shot.cafe, MovieStillsDB, Flim.ai / Frameset (search depth to test) | ShotDeck |
| Commercials + credits | Vimeo (via search + oEmbed), Shots, LBB, Directors Notes, Ads of the World | Vimeo search page |
| Motion / VFX / titles | Motionographer, Stash, Art of the Title | Behance |

**Steps (each tested before the next)**
- **3a Contract:** shot brief (mode, subject, effect, frame, purpose, client) + `shots.json` schema: technique, shot
  size, movement, lens, light, colour palette, frame rate, credits (director, DOP, production), timestamp, evidence
  level, production notes.
- **3b Film-language dictionary:** `techniques.json` (~60 techniques: movement, lens, speed, light, transitions, VFX,
  edit) with English/Arabic names, synonyms, search terms per source, canonical examples (verified links) and
  production notes. Lets plain words ("time slowing down") become searchable terms (speed ramp, high frame rate).
- **3c Discovery:** `discover_shots.py` adapters per source (above) + Vimeo via search and oEmbed; verify reuses
  the scout's `verify.py`.
- **3d Image tools:** colour palette from stills/thumbnails; frame-match guide (agent describes the frame in film terms,
  then searches).
- **3e Shot board:** grouped by technique; stills, palettes, credits, timestamps, "how to shoot it"; client or house
  look; one self-contained HTML; passes `check_outputs.py`.
**Built (2026-10-18):** all steps 3a–3f. Scripts: `expand.py` (language), `discover_shots.py` (Eyecannndy technique/
search/person, Film-Grab, Shot.cafe, Directors Notes, Motionographer, Stash, YouTube, Vimeo oEmbed, any page),
`contact_sheet.py` (choose by eye), `shotstub.py` (stubs + `--refill`), `verify_shots.py` (scout's verify + library
listings), `palette.py`, `validate_shots.py`, `build_shot_board.py`. 67 techniques, 17 moods. Real runs: Oman Oil
"Maghrib on the road" (subject, 15 shots), "speed ramp" (effect), "warm light DOPs" (who), the station frame
(frame-match; the link check caught a video made private). Learned: Eyecannndy search is single-word; `site:vimeo.com`
search is thin; shots.net is good for commercial credits; film clips on Eyecannndy often have no video link.
**Inspire me (v0.2.0, agreed 2026-10-18):** a mode for filmmakers' own creativity (writer, cinematographer,
director, editor): features, free shorts, scenes and essays in a running order. `film_facts.py` (Wikidata + Wikipedia:
checked credits, runtime, countries, Arabic title, `--craft` how-it-was-made sentences), Short of the Week API,
`roles.json` (watch-for prompts and exercises per craft), a "quiet" mood, programme board (numbered order, watch-for per
role, exercise, double bills). Real run: "The unsaid" (writer + DOP), 10 titles from 7 countries incl. Theeb and Norah.
Learned: Wikimedia rate-limits browser-like agents (use our own agent name + backoff); title search must reject people
("Norah" matched Nora Ephron) and try Arabic titles; a guessed Wikidata id was wrong, so facts only from lookups.
- **3f Tests + one real run** per mode on a small test set (answer keys in `evals/fixtures/shots/`, never shown to the
  agent under test). No benchmark runs without the user's go-ahead on cost.

## 3e. Feature 4: Script Desk (screenwriting help), ✅ BUILT v0.1.0 (2026-10-25)

Agreed with the user: a sub-skill that **helps you write, never writes for you**; film and short film first; Arabic
first. Prior art checked: no Arabic-aware screenwriting skill exists (community Claude skills write scenes for you;
coverage SaaS is closed and English); reused Hekaya's Arabic screenplay vocabulary (MIT), WriterDuet's mirrored RTL
layout, afterwriting's idea of measurable stats; python-docx (MIT) for Word; GPL apps (Trelby, KIT Scenarist) not used.

| Part | Script | Notes |
|---|---|---|
| Templates | `build_template.py` | 7 structures in `references/structures.json` (three acts, Save the Cat, hero's journey, story circle, 8 sequences, kishōtenketsu, short "one moment"); page targets from running time; questions only; draft section in screenplay styles |
| Formatter | `parse_script.py`, `format_script.py` | Word styles → Fountain/Hekaya marks → vocabulary → layout; unsure lines listed for Claude (no full read); Word + PDF (bundled OFL fonts embedded) + Fountain; RTL with mirrored margins (Word/LibreOffice treat left indent/alignment as start side in RTL paragraphs, tested) |
| Reader | `digest.py`, `show.py`, `annotate.py`, `report.py` | ~1.3k-token digest first, then only needed scenes; 10 viewpoints in `references/lenses.json` with colours; green/amber/red; notes schema + checker (scene exists, quote found, every amber/red has a note, rewrite warning); Word comments shaded by viewpoint + one-page HTML report |

Test (2026-10-25): fictional Omani short «المرساة» (`samples/script-desk/`) with 9 planted flaws (answer key in
`evals/fixtures/script-desk/`). Digest alone flagged 4 (repeat, dialect switch, telling line, night-storm cost). Blind
reader agent (~80k tokens, full workflow): **8/9 flaws found** + both planted strengths; missed "empty scene 6" (called
it a quiet strength); extra valid notes (mother disappears, 17-year-old at sea with a 25-year-old man unremarked).
Fixed from its feedback: SKILL.md now says every amber/red viewpoint needs a scene note and how to treat a page/minute
gap; show.py headings cleaned. Open: Arabic page-per-minute ratio and font norms unverified (calibrate with real
Arabic scripts); two-column (documentary/TV) layout not built; FDX import not built.

**v0.2.0 (2026-10-25, user: "visuals and colour codes; notes as comments on the side").** Notes now sit beside their
lines everywhere: Word margin comments with one reviewer per viewpoint (own colour, show/hide in Word), and
`side_notes.py` (script + comment cards in the margin, HTML + A4 PDF; LibreOffice's own margin-comment PDF clips RTL,
so we print through Chromium). `charts.py`: beat map with scene health, tension curve, presence grid, dialect map,
character voices, production stripboard (industry colours), in the report and as pictures on the Word notes page.
Colours follow the dataviz method: ten viewpoints in three validated colour families (only three categorical colours
pass all-pairs CVD checks), always labelled; verdicts use status colours with icons. New: voice profiles (digest),
`compare.py` for draft 2 (scene matching, old-note starting status), notes `turns`, `tension`, `previous`.
Blind test of the new-draft workflow (~90k tokens) against `al-mirsah-draft2-answer-key.json`: every checkable item
matched (incl. the compass note in an unchanged scene, correctly resolved via its new payoff; the telling line kept
open); it also found a real new issue (the engine setup no longer pays off). Fixed from its feedback: ids/strengths and
status definitions in SKILL.md, real path in compare.py output. Open: compare tension between drafts.

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
| [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) (MIT, 50 skills) | Architecture confirmation (shared context file read by every skill = our contract); Agent Skills spec conventions (name = dir, description ≤1024 chars, SKILL.md <500 lines, `metadata.version`); `evals/evals.json` per skill (ours live in `evals/skill-evals/`, outside the skill folders, so test agents never see them); plugin packaging. Generic skills (copywriting, ad-creative, social, ab-testing, competitor-profiling…) can be **used alongside** ZAMAKAN instead of rebuilt | Its single per-project context file (we need many clients); no Arabic/Gulf layer; no design-system extraction; no campaign-reference research |
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
- 2026-10-25: Script desk v0.2 (§3e): side comments (Word reviewers per viewpoint, side-notes PDF), six charts, voice profiles, draft comparison; blind new-draft test matched the answer key; plugin 1.2.0.
- 2026-10-25: Script desk built (§3e): templates, Arabic RTL formatter (Word/PDF/Fountain), ten-viewpoint reader with coloured comments and report; blind test 8/9 planted flaws; plugin 1.1.0.
- 2026-10-25: Installable plugin (user: "a skill that anyone can use"). The repo is now a Claude Code marketplace (`.claude-plugin/marketplace.json`) with one plugin, `plugins/zamakan` (v1.0.0, all four skills, since they share scripts). Skills stay real folders in `.claude/skills/` (cloud sessions load them); `plugins/zamakan/skills` is a link that Claude Code resolves into real files on install (tested in a clean home: install, then client/library/board/deck run from the cache). New `zamakan-core/scripts/workspace.py`: outputs go to the user's project folder (never the plugin cache or ~), and a project `zamakan-agency.json` overrides the home market for other agencies. New `doctor.py` checks Python, packages, Chromium, LibreOffice and web access. `claude plugin validate` passes; tests/test_plugin.py added. Open: no LICENSE yet (the user's choice); the shared library/ is not shipped in the plugin (each user's library starts empty).
- 2026-10-21: Shot scout documentaries (user request): `docs` search (Short of the Week documentary genre + YouTube channels Guardian Documentaries, NYT Op-Docs, Al Jazeera Documentary (Arabic), Al Jazeera English, BBC Stories, POV + YouTube), `channel-search`, `--genre`; 8 documentary techniques (interview, direct address, observational, archival, reenactment, animated doc, diary film, essay film); documentary + mental-health moods; kind documentary/docuseries; ethics rules (consent, trigger warnings, documentaries vs explainers). BPD board now 27 references with a Documentaries part. 221 tests.
- 2026-10-18: Oman Oil campaign recreated in the client's theme: a light design system from the one-page brand sheet (blue #0D80BF, green #99BF3C, grey #DEDEDB; GE Flow / ITC Avant Garde named, stand-ins Tajawal + TeX Gyre Adventor until the files arrive), 21-slide deck (pptx + pdf). Renderer fixes: logo on a white panel on dark covers when no reversed logo exists, fills/rings/muted text nudged to stay readable, deck text fitting measured from the actual font (wide faces). 218 tests.
- 2026-10-18: No limits on output (user): default scope is now `global` (GCC/MENA preference only when asked); reference and shot counts are floors, never caps (brief.target_count max removed); Omani/Gulf work is included when it fits, never as a quota or ordering rule. Oman stays the home market only for production notes, fit and the direct ring. 215 tests.
- 2026-10-18: The user is Omani and ZAMAKAN is based in Oman: home market moved to Oman for every skill (`zamakan-core/agency.json`, OM default in briefs, competitor click-lists, Ads of the World country list, 'Shooting in Oman' production notes, Omani calendar + culture notes incl. National Day 20–21 Nov per RD 15/2025). Inspire me puts Omani cinema first (`references/oman-cinema.md`: sources + checked starting list). Oman Oil boards and 'The unsaid' updated. 214 tests.
- 2026-10-18: Shot scout v0.2.0: Inspire me mode (viewing programmes for writers, DOPs, directors, editors), film_facts.py (Wikidata credits + craft notes), Short of the Week; 33 shot tests.
- 2026-10-18: Feature 3 (Shot Scout) built end to end (§3c): 8 scripts, 67-technique EN/AR dictionary, dark shot board, 27 tests (207 total); one real run per mode.
- 2026-10-18: Feature 3 (Shot Scout) planned with the user; see §3c.
- 2026-10-15: First real client run (Oman Oil, Ramadan for taxi drivers, MENA, board): 23 references all live (10 read, 8 login walls, 5 videos unwatched), 4 territories. Added `build_outputs.py --logo` (house look + client logo). Fixed a privacy leak: client-relative tags (client-own-work, competitor) no longer reach the shared library. 180 tests.
- 2026-10-14: Shipped: final polish (unused imports/f-strings removed), plain-language README.md added; PR to `develop`.
- 2026-10-14: Fixed the remaining agent-reported issues without new runs (see iteration-3-agent-feedback.md, Status); 178 tests.
- 2026-10-14: Iteration 3 benchmark stopped early at the user's request (tokens; usage limit hit twice). Done: blind
  judging of iteration 2 (fixed packets): skill 2 wins, 3 losses, 83% vs 88%; iteration 3 partial checks 31/33 with vs
  22/25 without, no judging. Found: the skill's examples leaked the Rawaq scenario (fixed, test added); YouTube thumbnails
  treated as logos (fixed); broken Snapchat click-list links (fixed). Remaining issues in
  `evals/scorecard/iteration-3-agent-feedback.md`. Next benchmark only when the user wants to spend on it.
- 2026-10-13: Scout iteration 3 built (benchmark not yet re-run). 3a test definitions moved out of skill folders
  (`evals/skill-evals/`), brand.md fallback. 3b fetch_meta: URL normalising, requested URL kept, oEmbed retry + YouTube
  thumbnail fallback, tiny/logo images dropped and flat ones flagged (real flat ads exist: Coinbase QR, VOO), `--out`
  appends; thumbnails keyed by URL, letterbox trimmed, `run.cover`, competitors' ads never cover/lead. 3c verify:
  per-link evidence content/title/video, body-text matching; boards say "page read" / "page exists, details unconfirmed" /
  "video, not watched"; shared award sources allowed; thin-evidence teardowns and repeated thumbnails warned.
  3d competitor watch: `competitors.py` (search plan, click-list for social and ad libraries, recent YouTube uploads),
  `discover.py youtube-channel` (YouTube's new layout), window_months, owns/last_seen/manual_checks; SKILL.md 0.4.0
  with rules for search budget, missing competitors, country, alcohol, unwatched videos, award level, cover. 3e deck
  shows up to 6 insights; placeholders instead of empty tiles. 3f ranking: place names no longer count as relevance,
  off-topic pushed down, award signals, alcohol flag. 3g `evals/judge_scout.py`: blind A/B judgement on a creative
  director's rubric, scorecard shows it; prompts give both sides the same search-budget note. 171 tests pass.
- 2026-10-13: Scout 2f first pass done (user chose 1 run per scenario, ~2M tokens). 5 scenarios (GCC brief, global creative
  question, competitor watch, pitch, global brief) × with/without skill; `evals/bench_scout.py` + scenario-driven
  `grade_scout.py`; scorecard https://claude.ai/artifact/Gmjx7ao4bA2inZKD9CKsDT (history in `evals/scorecard/`).
  Result: with skill 62/62 checks, without 58/62; no invented links on either side; skill ~14% more tokens (202k vs
  177k), ~10% faster (10.5 vs 11.7 min). First grading was unfair to the baseline (8/17 on s1): fixed the grader
  (JSON territories/insights/countries, numbered headings, beauty check with base href, href/PDF link extraction,
  stylesheet @import, bot walls and unresolvable hosts not counted) and regraded. Honest read: property checks are near
  their ceiling; next round needs a blind side-by-side quality judgement and repeat runs for consistency. Competitor
  watch without the skill found more recent activity: that mode needs work. All agents shared a 200-search limit.
  Fixed during the run: client name leaking into the shared library via thumbnail.local; YouTube channel pages marked
  dead (fetch_meta used oEmbed for them); Arabic inline-span false positive in check_outputs. 40+ agent-reported issues
  logged in `evals/scorecard/iteration-2-agent-feedback.md` for iteration 3.
- 2026-10-13: Scout 2d done + sparks (2g). Library is now two layers: SHARED and client-neutral (`library/README.md`
  index by moment/category/market, one `campaigns/<name>/REFERENCE.md` per campaign with front matter, like
  awesome-design-md; usage counted via anonymous run fingerprints) and PRIVATE per client (`clients/<slug>/library/`,
  git-ignored: why it mattered, ring, scores, borrow, fit, territories). Any shared text naming the client is moved to
  the private notes and reported (tested with a planted leak). User asked for global inspiration whatever the scope:
  "Sparks from elsewhere" (3–5 far-away references, each with a provocation), `score.py --sparks`, validator warning,
  dark section in board + slide in deck. Sample run gained 3 real, verified sparks (Burger King Whopper Detour US,
  Heinz Draw Ketchup CA, McDonald's Raise Your Arches UK). Fixed: AotW parser preferred a dead YouTube thumbnail over the
  page's own image (and "first image on page" proved unsafe: it was a related campaign). 149 tests pass.
- 2026-10-13: Scout 2e done (user moved it before 2d): outputs wear the client's brand and are checked for beauty.
  `brandkit.py` reads the whole feature-1 design system: logo variant approved for each background (manifest), the
  client's own font files (subset + embedded in the board, installed for the deck PDF), colours by role, panel radius,
  divider, shadow and the signature element (Rawaq's arch frames the cover image, once, as its guideline says). Missing
  assets (mashrabiya tile) are reported, never drawn. New board (`render_board.py`) and deck (`render_deck.py`, 19
  slides) follow the kickoff story: insights → recommendation → territories → competitors → patterns → deep dives →
  references (R01…) → before kickoff. `check_outputs.py` renders desktop + phone + every slide and fails on sideways
  scroll, broken images, clipped text, low contrast, unloaded fonts, wrongly set Arabic; a sabotaged board is caught
  in tests. House style ships its OFL fonts. SKILL.md 0.3.0: scope question, strategy layer, build → check → look →
  deliver; kickoff default outputs board + deck. 140 tests pass. Weak spots: no ZAMAKAN logo file yet (house outputs
  show a wordmark-free cover); deck text fitting is estimated, not measured; proprietary fonts of borrowed looks fall
  back to system fonts.
- 2026-10-13: Scout 2c done: boards and decks take their look from a DESIGN.md (`theme.py`, `build_outputs.py --design`).
  Order: `--design` > the client's own `design-system/DESIGN.md` (found automatically) > ZAMAKAN house style
  (`assets/zamakan.DESIGN.md`, 0 errors / 0 warnings in Google's linter). `awesome:<name>` pulls any of the 84
  awesome-design-md brands (MIT, credited in the footer). All 84 load with readable text (WCAG AA enforced; brand
  colour kept for fills, nudged only for link text); prose-only files and one with broken YAML handled. Checked
  visually in 4 looks (house, Rawaq, Nike, Al Jazeera). Weak spots: brand fonts that are proprietary fall back to
  system fonts; the deck layout itself is unchanged until 2e. 137 tests pass.
- 2026-10-13: Scout 2a+2b done: strategy layer (insights, recommendation, before-kickoff, competitor check) and scope
  switch gcc/mena/global in contract, scorer and validator.
- 2026-10-13: User added to iteration 2: global scope switch, DESIGN.md theming + awesome-style library (both), full benchmark + scorecard.
- 2026-10-13: Scout step 4 done + iteration-1 eval: both 11/11, no invented links; skill faster, baseline better packaged (3c).
- 2026-10-13: Scout step 3 done: outputs built from a real 16-reference Ramadan run; library committed (user decision).
- 2026-10-13: Scout step 2 done: web access confirmed after restart; all sources tested live.
- 2026-10-13: Scout step 1 done. Network allowed by user but not applied to the running session; restarting the session. Apify skipped.
- 2026-10-13: Feature 1 paused by the user; switching to Feature 2 (reference scout).
- 2026-10-13: Step 5 done + iteration-1 eval (see 5b). Fixed: canonical roles, components, missing_assets, contrast pairing, docs.
- 2026-10-13: Step 4 done. One build command generates all contract files from spec.json; DESIGN.md validated with @google/design.md 0.4.0.
- 2026-10-13: Step 3 done. One command (`extract_all.py`, about 5 s) turns the brand folder into a 6 KB digest + 10 KB page text + 2 contact sheets. Reviewed marketingskills + DESIGN.md (see 4b).
