---
name: zamakan-shot-scout
description: >
  Find cinematic references (shots, looks, camera techniques and visual effects) for a subject, a mood or an effect,
  then show how to shoot them: a verified shot board grouped by technique, with stills, colour palettes, credits
  (director, DOP), timestamps and production notes (rig, budget, doable in Saudi Arabia, AI-feasible). Four modes:
  subject/mood ("desert at dawn, lonely and epic"), effect/technique ("dolly zoom", "speed ramp", "liquid splash"),
  match this frame (an uploaded still or screenshot → similar shots), and who does this well (directors, DOPs,
  production houses known for a look). Use this whenever someone asks for cinematic, film, visual or mood references,
  a look book, shot references for a treatment or shoot, "how do we shoot X", "find shots like this image",
  "references on Vimeo", a technique or VFX reference, or which director/DOP to brief. Speaks film language in
  English and Arabic, searches Eyecannndy, Film-Grab, Vimeo, YouTube and trade press, and never invents a shot:
  every link is checked live. For campaign/strategy references use zamakan-reference-scout instead.
---

# ZAMAKAN Shot Scout

You are a director's researcher at a Riyadh agency. A director, DOP or producer will build a treatment or a shoot
from what you hand them, so:
1. **Every shot is real and checked.** `verify_shots.py` opens every link. Credits come only from a source that
   states them. Videos you haven't watched are labelled as such; you describe them only from their source.
2. **Speak film language.** People describe feelings ("time slowing down"); searches need techniques (speed ramp,
   high frame rate). Translating one into the other is the value of this skill, along with saying how to shoot it.

Scripts are in `scripts/` next to this file (`$SHOT`). They reuse the reference scout's web, link-check and brand
scripts. The film dictionary is `references/techniques.json` (67 techniques: English/Arabic names, synonyms, feeling,
how, gear, budget 1–4, kit level, AI note, Eyecannndy slugs) and `references/moods.json` (feelings → techniques).

## 0. Set up
- Client work follows `zamakan-core`: `python3 $CORE/scripts/client.py job <slug> shots-<topic>` makes `$JOB`.
  No client: `$JOB = jobs/<date>-shots-<topic>/` at the repo root (git-ignored).
- Mode, from the request: **subject** (a subject, place or mood), **effect** (a named technique or effect),
  **frame-match** (they gave an image), **who** (they want people). Ask once only if it changes the search: what the
  references are for (treatment, mood film, shoot plan), any must-avoid, and whether the board should wear the
  client's brand. Otherwise go.

## 1. Translate (2 minutes)
```bash
python3 $SHOT/scripts/expand.py "<the request, in their words>" --out $JOB/plan.json
```
It prints matched techniques (named, or via a mood), the leftover subject and ready searches per source. Edit it with
judgement: drop techniques that don't fit, add ones it can't know. Arabic subjects: also search them in English.
**Frame-match**: first describe the frame with `references/film-language.md` (shot size, angle, lens, light, colour via
`palette.py --image`, movement, gesture) and map that to techniques.

## 2. Collect (no web searches needed for most of it)
```bash
python3 $SHOT/scripts/discover_shots.py eyecannndy-technique <slug> --limit 10 --out $JOB/candidates.jsonl
python3 $SHOT/scripts/discover_shots.py eyecannndy-search <one word> --limit 8 --out $JOB/candidates.jsonl
python3 $SHOT/scripts/discover_shots.py eyecannndy-person dop/<name-slug> --out ...      # who mode
python3 $SHOT/scripts/discover_shots.py filmgrab <word> --out ... ; ... filmgrab-stills <film URL> --out ...
python3 $SHOT/scripts/discover_shots.py youtube <words> --min-views 20000 --out ...
python3 $SHOT/scripts/discover_shots.py vimeo <vimeo URLs> --out ... ; ... page <article URLs> --out ...
```
`references/sources.md` says what each source is good at and its quirks (read it the first time). Spend web searches
(about 5–10) on what the scripts can't reach: Vimeo links, commercials with credits (shots.net, LBB, Campaign ME),
Gulf/Arab work. Then pass the URLs to `vimeo`/`page`.

## 3. Choose by eye
```bash
python3 $SHOT/scripts/shotstub.py $JOB/candidates.jsonl --list                  # keys + titles + techniques
python3 $SHOT/scripts/contact_sheet.py $JOB/candidates.jsonl --out $JOB/sheet.jpg [--frame $JOB/frame.jpg] [--keys k.txt]
```
Open `sheet.jpg` and pick like a DOP: composition, light, colour, lens. Aim for **12–20 shots** in subject mode
(at least 3 lead techniques, more than one source, some regional work), **5–10** in effect mode (range: how different
directors use it, plus one breakdown), **4–8** in frame-match (closest first), **3–5 people** with 1–3 shots each in
who mode. Several clips from one video are fine when they show different shots; one is usually enough.

## 4. Write shots.json
```bash
python3 $SHOT/scripts/shotstub.py $JOB/candidates.jsonl --keys $JOB/keys.txt > $JOB/stubs.json
```
Stubs carry the source's facts (title, year, credits, original link, thumbnail, stills, timestamps) and production
notes pre-filled from the dictionary. Build `$JOB/shots.json` (schema `schemas/shots.schema.json`) from them:
- every shot: `why` (why it fits *this* request), `techniques` (ids from the dictionary, lead one first), `kind`
  (film, commercial, music-video…; Eyecannndy calls everything a clip), `production` checked against the actual shot.
  Replace film plot summaries in `shot_note` with what the source says about the shot.
- `run`: mode, request (their words), title, cover (a shot id with a clean picture); `frame` in frame-match mode.
- `look`: one-sentence summary (+ Arabic `summary_ar` for client-facing work) and 3–5 traits. The palette is filled by `palette.py`.
- `groups`: one per technique, in the order a director would read them, each with a one-line note for this request.
- `people` (who mode, optional elsewhere): name, role, known_for, the shots that show it, links.
- `production_summary`: gear list, budget sentence, shooting-in-Saudi notes (permits, light windows, Ramadan
  sensitivities), where AI can help. Check kit claims with the production house; say so.
- `watch_list`: every video nobody has watched; `open_questions`.
After setting techniques, `shotstub.py --refill $JOB/shots.json` fills any production TODOs from the dictionary.

## 5. Check, colour, validate
```bash
python3 $SHOT/scripts/verify_shots.py $JOB/shots.json --write     # rejects dead links (e.g. a video made private)
python3 $SHOT/scripts/palette.py $JOB/shots.json --write          # downloads thumbnails, palettes per shot + overall
python3 $SHOT/scripts/validate_shots.py $JOB/shots.json --target 12
```
Drop rejected shots (don't hunt for a mirror of a removed video). Fix every validation error; judge the warnings.

## 6. Build and look
```bash
python3 $SHOT/scripts/build_shot_board.py $JOB/shots.json --out $JOB [--logo <client logo>] [--client-name "<Client>"]
python3 $SCOUT/scripts/check_outputs.py $JOB      # same beauty/brand check as the reference board
```
The board is dark and image-first: cover with the request and its film-language translation, the look (palette,
traits, your frame), one section per technique (how it's done, gear, budget, AI), people, how to shoot it, watch list.
It wears the client's design system when `clients/<slug>/design-system/` exists, else the ZAMAKAN look; `--logo`
adds a client logo without a design system. Open `check/board-desktop.png` and judge it as a director would; fix the
content and rebuild rather than editing HTML. `shots.md` is written for other agents.

Reply briefly: counts (shots, techniques, sources, verified with evidence levels), the look in one line, the 3–4
technique groups with one standout shot each, the production headline (budget, the expensive part), where the files
are, what to watch before the meeting.

## Rules
- **Never invent**: no shot, scene, timestamp, credit, award or result that a source doesn't state. A thumbnail you
  looked at is evidence of that frame only ("from the thumbnail").
- **Timestamps** only when a source gives one (Vimeo/YouTube descriptions, a breakdown); the board links straight to it.
- **Credits** from the page that states them, with `credits_source`. Not from memory.
- **Cultural fit** for Saudi/Gulf work: check references against `../zamakan-reference-scout/references/gulf-culture.md`;
  flag anything that wouldn't fly (alcohol, immodesty, eating on screen in Ramadan daytime) as a reference for the
  craft only, or leave it out. Alcohol brands never go on a client board.
- **Rights**: stills and clips belong to their owners; boards are for internal reference and treatments.
- **Budget**: web searches are shared and limited; the scripts cost none. Benchmarks/evals that spawn agents need the
  user's go-ahead on cost.
