# ZAMAKAN Marketer

Marketing and creative skills for **ZAMAKAN (زمكان)**, an agency with many clients working in Arabic and English with a
Saudi/GCC focus. The skills run inside [Claude Code](https://claude.ai/code): you ask in plain language, and Claude follows
the skill, using small scripts for the mechanical work so its effort goes into judgement.

## What it can do

| Skill | Ask for… | You get |
|---|---|---|
| **Reference scout** (`zamakan-reference-scout`) | "Find us references for the Ramadan kickoff", "What are our competitors running?", "Best ads that made waiting fun, anywhere", "References for our pitch to X" | Real campaigns, every link checked live; insights with sources; competitor check; patterns and white space; 3–5 creative territories with Arabic names; "sparks from elsewhere"; a recommendation and a before-kickoff list. Delivered as an on-brand **board**, **deck** (PowerPoint + PDF) and/or **report**. |
| **Design system** (`zamakan-design-system`) | "Here are the brand guidelines for client X" | The client's visual identity as files every other skill uses: colours, fonts, logos with usage rules, design tokens, a `DESIGN.md`, and a style tile, each value traced to its page in the guideline. |
| **Core** (`zamakan-core`) | (used by the others) | Where client files live, how to load a client's brand, and the bilingual quality bar. |

The two work together: when a client has a design system, the scout's boards and decks wear that client's logo, fonts,
colours and shapes. Without one they use the ZAMAKAN house style.

## How to use it

Open this folder in Claude Code and ask, for example:

> Rawaq's Ramadan brief is in `clients/rawaq/brief.md`. Find us references for next week's kickoff and give us creative territories.

Claude asks once about anything missing (scope **GCC / MENA / Global**, which outputs you want), then works on its own.
Results land in `clients/<client>/jobs/<date>-scout-<topic>/`.

New client? Ask Claude to set one up from the brand files (`python3 .claude/skills/zamakan-core/scripts/client.py init <slug> --from <folder>`),
then to build its design system.

## What to know

- **Nothing is invented.** Every reference is opened and matched to its page. Boards say how strong the evidence is:
  *page read*, *page exists, details unconfirmed* (login walls), or *video, not watched*.
- **Some places can't be read from here:** Instagram, TikTok, Snapchat, X and the Meta Ad Library. Competitor reports
  include a "check by hand" list of links for a person to open (about 5 minutes per brand).
- **Client material stays private.** `clients/` is never committed. The shared campaign library in `library/` holds no
  client names; what a campaign meant for a client stays in that client's folder.
- **Web searches are limited** per session; the skill plans around it and uses its own scripts where it can.

## Folders

```
.claude/skills/          the three skills (instructions, scripts, schemas, references)
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
- **Design system:** first round done and paused (PLAN §3, §5b).

## For developers

```bash
pip install -r requirements.txt
python3 -m pytest -q tests        # must stay green; live web tests skip when offline
```
Rendering uses Playwright with Chromium (found automatically at `/opt/pw-browsers/chromium`). Benchmarks
(`evals/bench_scout.py`, `evals/judge_scout.py`) spawn agents and cost roughly 200k tokens per run: agree the cost first.
Read `CLAUDE.md` and `PLAN.md` before changing anything.
