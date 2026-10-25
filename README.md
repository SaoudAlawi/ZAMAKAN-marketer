# ZAMAKAN Marketer

Marketing and creative skills for **ZAMAKAN (زمكان)**, an Omani agency with many clients across Oman and the GCC, working in Arabic and English. The skills run inside [Claude Code](https://claude.ai/code): you ask in plain language, and Claude follows
the skill, using small scripts for the mechanical work so its effort goes into judgement.

## What it can do

| Skill | Ask for… | You get |
|---|---|---|
| **Reference scout** (`zamakan-reference-scout`) | "Find us references for the Ramadan kickoff", "What are our competitors running?", "Best ads that made waiting fun, anywhere", "References for our pitch to X" | Real campaigns, every link checked live; insights with sources; competitor check; patterns and white space; 3–5 creative territories with Arabic names; "sparks from elsewhere"; a recommendation and a before-kickoff list. Delivered as an on-brand **board**, **deck** (PowerPoint + PDF) and/or **report**. |
| **Shot scout** (`zamakan-shot-scout`) | "Maghrib light on the road, warm and spiritual", "Best dolly zoom examples", "Find shots like this frame" (attach an image), "Which DOPs shoot warm portraits?", and for your own creativity: "I'm a writer, inspire me: films about silence" | Cinematic references (films, short films and documentaries) translated into film language (English and Arabic): a dark, image-first **shot board** grouped by technique, with stills, colour palettes, credits, links that jump to the moment, and "how to shoot it" notes (gear, budget level, notes for shooting in Oman (or the job's market), where AI helps). **Inspire me** gives a viewing programme instead: features, free short films and essays in a running order, with checked credits (Wikidata), "what to watch for" per craft (writer, cinematographer, director, editor) and a small exercise after each. |
| **Script desk** (`zamakan-script-desk`) | "I'm writing a 12-minute short, give me a template", «نسّق السيناريو», «أبغى ملاحظات على مسودتي» | Help for a screenwriter, Arabic first (it never writes the script for you): a Word **template** for the story structure you choose (three acts, Save the Cat, hero's journey, story circle, eight sequences, kishōtenketsu, short-film shapes) with page targets and questions; a **formatter** that turns a rough draft into a proper screenplay (right to left for Arabic, scene numbers, Word + PDF + Fountain); and a **reader** that gives notes from ten viewpoints (premise, structure, character, dialogue and dialect, visual storytelling, pacing, theme, cultural truth, producibility, festival fit), green/amber/red, **as comments on the side** of your script (Word margin comments, one colour per viewpoint, plus a PDF with comment cards beside each line), with pictures (beat map, tension curve, who is in which scene, dialect map, character voices, production stripboard). Bring draft 2 and it tells you which notes are resolved, partly done or still open, re-reading only the changed scenes. Fill a one-page **intent sheet** and the notes are judged against what you are going for (your deliberate choices aren't flagged); **reply to comments in Word** and the next reading takes your answers into account; **scene cards** let you try a new order and get the script rebuilt in it; a **character arc** chart shows how each main character moves. It reads **Word, PDF, Final Draft (.fdx)** and plain text, can do a quick **first-pages** read (the way festival readers decide) or a **dialogue-only** pass, and every verdict follows a written yardstick so colours stay consistent. |
| **Design system** (`zamakan-design-system`) | "Here are the brand guidelines for client X" | The client's visual identity as files every other skill uses: colours, fonts, logos with usage rules, design tokens, a `DESIGN.md`, and a style tile, each value traced to its page in the guideline. |
| **Core** (`zamakan-core`) | (used by the others) | Where client files live, how to load a client's brand, and the bilingual quality bar. |

The scouts work together with the design system: when a client has a design system, the scout's boards and decks wear that client's logo, fonts,
colours and shapes. Without one they use the ZAMAKAN house style.

## How to use it

Open this folder in Claude Code and ask, for example:

> Rawaq's Ramadan brief is in `clients/rawaq/brief.md`. Find us references for next week's kickoff and give us creative territories.

Claude asks once about anything missing (scope **GCC / MENA / Global**, which outputs you want), then works on its own.
Results land in `clients/<client>/jobs/<date>-scout-<topic>/`.

New client? Ask Claude to set one up from the brand files (`python3 .claude/skills/zamakan-core/scripts/client.py init <slug> --from <folder>`),
then to build its design system.

## Installing it

**For anyone, in any project (the plugin).** In Claude Code:
```
/plugin marketplace add SaoudAlawi/ZAMAKAN-marketer
/plugin install zamakan@zamakan-marketer
```
Then once per computer: `pip install -r plugins/zamakan/requirements.txt` (or the package list in
[plugins/zamakan/README.md](plugins/zamakan/README.md)) and `python3 -m playwright install chromium`. Ask Claude to "check
the ZAMAKAN setup" if something is missing; it runs a checker that prints the exact commands. The skills then appear as
`/zamakan:zamakan-reference-scout` and so on, and work in any folder: results land in that folder's `clients/` and `library/`.

Another agency or market? Put a `zamakan-agency.json` in your project folder to set your own home market
(example in the plugin README). Updates arrive when the plugin's version number goes up (`/plugin marketplace update zamakan-marketer`).

**In this repository.** Open the folder in Claude Code (or a claude.ai cloud session, where plugins from your computer
don't load): the skills in `.claude/skills/` load automatically. They are the same files the plugin installs
(`plugins/zamakan/skills` links to them). If you also installed the plugin, disable it while working here, so the skills
don't load twice.

## What to know

- **Nothing is invented.** Every reference is opened and matched to its page. Boards say how strong the evidence is:
  *page read*, *page exists, details unconfirmed* (login walls), or *video, not watched*.
- **Videos aren't watched by Claude.** Shot notes come from the source (Eyecannndy, the maker's description, trade
  press) or from the thumbnail Claude looked at; anything unwatched is on the board's "watch before the meeting" list.
- **Some places can't be read from here:** Instagram, TikTok, Snapchat, X and the Meta Ad Library. Competitor reports
  include a "check by hand" list of links for a person to open (about 5 minutes per brand).
- **Client material stays private.** `clients/` is never committed. The shared campaign library in `library/` holds no
  client names; what a campaign meant for a client stays in that client's folder.
- **Web searches are limited** per session; the skill plans around it and uses its own scripts where it can.

## Folders

```
.claude/skills/          the skills (instructions, scripts, schemas, references)
.claude-plugin/          plugin marketplace listing; plugins/zamakan/ is the installable plugin
library/                 shared campaign library: README index + one REFERENCE.md per campaign
clients/                 your clients (private, git-ignored): input/, design-system/, jobs/, library/
samples/rawaq/           a fictional test client (guideline PDF, logos, fonts) used for development
evals/                   benchmark scenarios, graders, blind judge, scorecard (never shown to agents under test)
tests/                   automatic checks (run before every change)
PLAN.md                  every decision, status per step, and the progress log
```

## Quality and status

- **Reference scout:** active, v0.4.1, three improvement rounds. Benchmarked against a strong agent without the skill
  on five scenarios; see the [scorecard](https://claude.ai/artifact/Gmjx7ao4bA2inZKD9CKsDT) (private link; share it from
  the page). Honest summary: no invented links on either side; the skill's work is more structured and actionable, quality
  is roughly even, and competitor watch was rebuilt after the last full round. Open issues are in `evals/scorecard/`.
- **Script desk:** v0.4.0 (2026-10-25): side comments, charts, voice profiles, draft comparison, intent sheet, margin conversation, scene cards, arcs, PDF/Final Draft input, focused passes, verdict yardstick. Tested on a fictional Arabic short (two drafts) with planted flaws and blind reader runs; Arabic page-per-minute and font norms are unverified (ask for real Arabic scripts to calibrate).
- **Shot scout:** new, v0.2.0 (with Inspire me). Tested on four real requests (one per mode); 15-shot Oman Oil "Maghrib on the road" board.
  Vimeo is reached through web search + a link check (its own search blocks us); a free Vimeo developer key would add
  direct search later. ShotDeck and Behance block us.
- **Design system:** first round done and paused (PLAN §3, §5b).

## For developers

```bash
pip install -r requirements.txt
python3 -m pytest -q tests        # must stay green; live web tests skip when offline
```
Rendering uses Playwright with Chromium (found automatically at `/opt/pw-browsers/chromium`). Benchmarks
(`evals/bench_scout.py`, `evals/judge_scout.py`) spawn agents and cost roughly 200k tokens per run: agree the cost first.
Read `CLAUDE.md` and `PLAN.md` before changing anything.
