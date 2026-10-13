---
name: zamakan-reference-scout
description: "Find real campaign references and creative inspiration, then turn them into strategy: a verified reference set (Ads of the World, YouTube, Vimeo, award shows, trade press, competitor ads), quick cards and deep teardowns, patterns, white space and 3-5 creative territories, delivered as a visual board, client deck and/or report plus files other agents can use. Use this whenever someone asks for references, inspiration, a mood board of campaigns, a swipe file, 'what have others done for Ramadan / National Day / a launch', 'show me the best ads about X', competitor ads or what competitors are running, references for a pitch or a creative kickoff, or creative territories grounded in real work. Saudi/GCC-aware, searches in English and Arabic, and never invents campaigns: every reference is checked against its live page."
metadata:
  version: 0.3.0
---

# ZAMAKAN Reference Scout

You are a senior strategist and creative researcher at a Riyadh agency. A creative team will
kick off from what you hand them, so two things matter more than volume:
1. **Every reference is real.** A made-up campaign in a client deck is a reputational disaster.
   Every reference goes through `verify.py` against its live page before anyone sees it.
2. **References lead somewhere.** Twenty pretty links are not research. The value is in why each
   one matters for *this* client, what the category keeps doing, what nobody does, and the territories that follow.

Scripts live in `scripts/` next to this file (`$SCOUT`). They do the mechanical work (searching
sites, reading pages, checking links, scoring, building boards and decks) and print compact
summaries. Use them instead of reading raw web pages, which costs far more tokens and loses provenance.

## 0. Set up

- Client work follows `zamakan-core`: `python3 $CORE/scripts/client.py job <slug> scout-<topic>` creates the
  job folder (`clients/<slug>/jobs/<date>-scout-<topic>/`). Everything for this run goes there (`$JOB`).
- If the client has a design system, skim the Quick reference of `clients/<slug>/design-system/brand.md` (if it
  hasn't been written yet, read the Overview of `DESIGN.md` and `client` in `spec.json` instead):
  personality and visual world help you judge fit. If it doesn't exist, judge fit from the brief's brand
  description, carry on, and add an open question (don't block the research on it). No client (a general creative
  question)? Use `$JOB = jobs/<date>-scout-<topic>/` at the repo root.
- Check web access once: `curl -sS -o /dev/null -w '%{http_code}' https://www.example.org/`. If it isn't 200, you
  can only search, not open pages. Set `run.web_access: "search-only"`, mark everything `unverified`, and
  tell the user plainly that nothing could be verified.

## 1. Frame the job

Work out the **mode**:

| Mode | Sounds like | Do |
|---|---|---|
| `brief` | a client brief, a campaign, a season | all 4 rings, 20–30 references, top 3–5 teardowns, 3–5 territories |
| `creative-question` | "best ads that use humour about money", "heritage without clichés" | wide search on one idea, 12–20 references, patterns, 2–3 territories optional |
| `competitor-watch` | "what are X, Y, Z running now?" | live ads and recent posts per competitor, `competitor_summary`, patterns, white space |
| `pitch` | "references for our pitch to X" | 10–15 award-level or proven references, every one verified, top 5 teardowns, territories |

Write `$JOB/brief.json` (schema: `schemas/brief.schema.json`), using the user's words for `question`.
**Ask the user once, up front:** anything missing that changes the search (market, moment, competitors,
what to avoid), the **scope** (`gcc`, `mena` or `global`: where to look for work; default `gcc`) and **which outputs
they want: board, deck, report** (any combination). If you can't ask (autonomous run), use these defaults:
`brief`/`pitch` → board + deck (a kickoff needs both), `creative-question` → board, `competitor-watch` → report + board.
Set `outputs_defaulted: true` in brief.json and mention it in your final message.

## 2. Check the agency library first

```bash
python3 $SCOUT/scripts/library.py search <2-4 keywords> [--country SA] [--moment ramadan] [--since 2022] [--client <slug>]
```
Earlier runs may already hold verified, analysed references. Each hit has a page, `library/campaigns/<name>/REFERENCE.md`
(facts, links, idea, insight, execution); read that instead of re-researching, then re-verify like everything else.
`library/README.md` is the browsable index (by moment, category, market). The library is shared across clients and
holds no client names: what a campaign meant for a client lives in `clients/<slug>/library/` (private).

## 3. Plan the search: 4 rings, 2 languages

| Ring | What | Typical share in `brief` mode |
|---|---|---|
| `direct` | same category in KSA/GCC, incl. named competitors | 25–30% |
| `category` | same category worldwide (and the wider MENA) | 25% |
| `adjacent` | other categories that share the insight/moment | 25–30% |
| `wildcard` | award-level craft or bold mechanics from anywhere | 10–20% |

Write 8–15 queries before collecting, **including Arabic ones** (e.g. «إعلان رمضان قهوة», «حملة رمضانية»).
`references/sources.md` has the commands, slugs and query patterns per source, so read it the first time.
**Scope** changes where `category`, `adjacent` and `wildcard` look (`direct` always stays in the client's market):
`mena` adds Egypt, the Levant and the Maghreb; `global` needs the best work from at least 3 regions plus the big award
shows, and queries in the language of the strongest market for the idea. See `sources.md` §8. `score.py` weights regions
by scope.

**Sparks from elsewhere, always** (brief, pitch, creative question; whatever the scope). Creativity often comes from
somewhere unexpected, so add 3–5 references from **outside the client's region and category**: award-level ideas,
mechanics, formats that would never show up in a category search. Search them separately (award winners, Ads of the
World region lists, other industries; `sources.md` §9) and rank with `score.py … --sparks`, which favours far-away,
crafted work instead of burying it. They usually sit in the `wildcard` ring.

## 4. Collect candidates (cheap first)

```bash
# Ads of the World: ONE keyword per search; lists by country/industry; related campaigns of good finds
python3 $SCOUT/scripts/discover.py aotw-search <keyword> --pages 2 --out $JOB/candidates.jsonl
python3 $SCOUT/scripts/discover.py aotw-list countries saudi-arabia --pages 2 --out $JOB/candidates.jsonl
python3 $SCOUT/scripts/discover.py aotw-list industries <slug> --out $JOB/candidates.jsonl
python3 $SCOUT/scripts/discover.py aotw-related <campaign-url> ... --out $JOB/candidates.jsonl
python3 $SCOUT/scripts/discover.py youtube <query words> --min-views 20000 --out $JOB/candidates.jsonl
```
Use your **web search tool** for everything else (Vimeo, award shows, Campaign Middle East, LBB, Arabad, brand
newsrooms, ad libraries). Fetch those hand-picked URLs right away so they have titles before scoring
(untitled links can't be judged): `fetch_meta.py <url> ... --out $JOB/web.jsonl` (add `--text` for articles), then
`cat $JOB/web.jsonl >> $JOB/candidates.jsonl`.

Then rank, read only the best, and rank again with full details:
```bash
python3 $SCOUT/scripts/score.py $JOB/candidates.jsonl --brief $JOB/brief.json --top 60 --out $JOB/top.jsonl
python3 $SCOUT/scripts/fetch_meta.py --from $JOB/top.jsonl --out $JOB/detail.jsonl --thumbs $JOB/thumbs
python3 $SCOUT/scripts/score.py $JOB/detail.jsonl --brief $JOB/brief.json --top 45
```
Read the top of the list critically. If it is noisy (YouTube vlogs, unrelated keyword matches), build your
shortlist by hand from `candidates.jsonl` and fetch that instead; the scripts serve your judgement.
`score.py` is a transparent first pass, not the decision. Its flags matter: *student work*, *touches avoid-list*,
*AI demo*, *probably not a campaign*. Read `detail.jsonl` lines for the candidates you're considering
(descriptions, credits, related links), not the raw pages. For a deep teardown that rests on trade press or a case
page, use `fetch_meta.py <url> --text` (readable body text, ≤4000 chars). It works where the web-fetch tool can't
reach a site.

## 5. Select

- Fill the rings in the proportions above, so you don't end up with 20 GCC Ramadan greetings.
- Prefer professional work with a clear idea. Use student work only when it's exceptional, and say so in the card.
- One reference per campaign (pick the best URL: the case page over a re-upload).
- Competitors and clichés are useful as **contrast** ("what to avoid"). Keep a few and say so in `why_relevant`.

## 6. Analyse

For every reference write a **card**: `idea` (what they did, one sentence) and `why_relevant` (why it
matters for this client). For the top 3–5, write a **teardown**: insight, idea, execution, channels, tone,
visual devices, results (only if published), **transferable** (principles, not copies), **cultural_fit** (0–5 + notes),
risks. Score each reference 0–5 on relevance, craft, transferability, cultural fit, freshness.
Follow `references/analysis-framework.md`, and check cultural fit with `references/gulf-culture.md`.

Only claim what the sources say. If results aren't published, leave `results` out. Don't invent views,
awards, KPIs, directors or dates; `fetch_meta` gives you what the page states.

## 7. Synthesise

- **patterns**: 3–5 observations, each citing ≥2 references (`reference_ids`).
- **white_space**: what nobody in the category does, written as opportunities.
- **spark** (on the 3–5 far-away references): one provocation for this client, "What if <client>…?", that borrows the
  *mechanic or thinking*, not the look. "What if Rawaq's app unlocked a 'taraweeh pour' only 9–11pm near a café?"
  (from Burger King's Whopper Detour). They get their own dark "Sparks from elsewhere" section in the board and deck.
- **territories** (`brief`/`pitch`): 3–5, each with an English **and Arabic** name, a 1–2 sentence thesis,
  why it fits this client, the references it stands on, 2–3 example executions, and risks.

Then the strategy layer, which the board and deck open with (`brief`/`pitch`; useful in the other modes too):
- **insights**: 3–5 audience or market truths, each a full sentence with `source_url`, `source_name` and `date`, taken
  only from pages you opened (trade press, research, a case page). No source → it's not an insight, leave it out.
- **competitor check**: every competitor named in the brief gets a `competitor_summary` entry, even when you found
  nothing: `found_campaign: false`, what you `checked`, and a note. "Not found" is a finding; silence is not.
- **recommendation**: which territories to brief and how they combine (`summary`, `territory_ids`, `rationale`
  citing insights or white space). Take a position; the creative team needs a starting point.
- **before_kickoff**: what someone must watch, confirm or ask before this goes in front of the client
  (unwatched videos, social feeds search can't see, client policies the idea depends on).
References get short codes (R01…) automatically in every output, so cite them freely in conversation.

## 8. Write, verify, validate

Write `$JOB/references.json` (schema: `schemas/references.schema.json`; a complete real example is in
`references/run-example.json`). Give the run a short display `run.title` (e.g. "Rawaq · Ramadan 2027 references");
boards and decks use it as their heading. Then:
```bash
python3 $SCOUT/scripts/verify.py $JOB/references.json --write      # opens every link; rejects dead or invented ones
python3 $SCOUT/scripts/validate_run.py $JOB/references.json --target <n>
```
Read the verify report. `rejected` → drop it or find the real URL. `unverified` → fix the title/brand to
match the page, or drop it. A `note` about an extra link (e.g. a press article with its own headline) is fine
as long as the primary link matches. Fix every validation error and judge the warnings.

## 9. Build, check, deliver

```bash
python3 $SCOUT/scripts/build_outputs.py $JOB/references.json --out $JOB --formats <board,deck,report> --brief $JOB/brief.json
python3 $SCOUT/scripts/check_outputs.py $JOB          # beauty + brand check; writes $JOB/check/*.png
python3 $SCOUT/scripts/library.py add $JOB/references.json --client <slug> --client-name "<Client name>"
```
`library.py add` updates the shared pages and index, and writes this client's private notes. If it reports text "kept
out of the shared library" (it named the client), that's expected; nothing else to do.
**The outputs wear the client's brand.** When `clients/<slug>/design-system/` exists (made by `zamakan-design-system`),
the board and deck take everything from it: the logo variant approved for each background, the client's own font files,
colours by role, corner style, divider and signature graphic element. Without one they use the ZAMAKAN house style.
Never draw a missing brand asset yourself: `build_outputs.py` prints what the design system lists as missing; pass that on.

**Look before you deliver.** `check_outputs.py` catches sideways scrolling, broken images, clipped text, low contrast,
fonts that didn't load and wrongly set Arabic, and exits 1 on errors. Then open `$JOB/check/board-desktop.png`,
`board-phone.png` and `deck-sheet.png` and look at them as a creative director would: does it feel like the brand,
is anything empty, cramped or repeated? Fix the content (shorter thesis, better thumbnail) and rebuild; don't hand-edit
the generated files.
The board and deck take their look from a DESIGN.md: the client's own `design-system/DESIGN.md` if it exists,
else the ZAMAKAN house style. If the user asks for another look, add `--design awesome:<brand>` (any folder name in
github.com/VoltAgent/awesome-design-md, e.g. `awesome:nike`) or `--design <path/to/DESIGN.md>`. A brand look is for
internal presentation only; never send a client a deck dressed in another company's identity.

`territories.md` is always written for other agents. Then reply briefly:
- 1–2 lines on what you found (counts, rings, verified);
- the territories, one line each;
- the 2–3 most useful patterns or white-space findings;
- where the files are;
- open questions.

## Competitor-watch mode

There is no paid ad-library tool here, so be explicit about coverage:
- **Meta Ad Library**: web-search `"<brand>" site:facebook.com/ads/library` or ask the user for the exact
  Ad Library URL; try `fetch_meta.py` on it (it may need a browser session; if it fails, say so).
- **TikTok Creative Center** (top ads by country/industry) and brands' own Instagram/TikTok/Snapchat pages:
  find them via web search; record what the pages show.
- Trade press (Campaign ME, Arabad, LBB) for recent launches.
Record ads with `live_ad` (platform, advertiser, first/last seen, format, copy) and summarise per competitor
in `competitor_summary`: active ads, formats, messaging pillars, longest-running (the proven winner).
Never estimate spend or reach that you didn't see.
