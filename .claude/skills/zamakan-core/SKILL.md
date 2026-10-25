---
name: zamakan-core
description: "Shared conventions for ZAMAKAN agency work: where each client's files live, how to load a client's design system before making anything visual or on-brand, and the bilingual Arabic/English quality bar. Use this at the start of any client task, whenever a client or brand is named (\"for Rawaq\", \"our client X\") and you are about to produce a social post, ad, campaign, mock-up, deck or copy, or when asked which clients exist and what state their brand assets are in. If the client has no design system yet, this tells you to run zamakan-design-system first."
metadata:
  version: 0.1.0
---

# ZAMAKAN Core

ZAMAKAN is an agency based in Oman serving many clients in Oman and across the GCC, working in
Arabic and English. These conventions keep every sub-skill working from the same client facts.

## Home market

`agency.json` (next to this file) holds the agency's home market: **Oman** (`OM`). Skills use it as the default market,
for local references and for production notes. A job that names its own market (brief.market / markets) uses that instead.
Another agency or market sets its own home without editing the skills: a `zamakan-agency.json` in the project folder
(same keys, e.g. `{"name": "…", "home_country": "SA", "home_name": "Saudi Arabia", "default_markets": ["SA"],
"aotw_country_slug": "saudi-arabia"}`) overrides it. `python3 $CORE/scripts/workspace.py` shows what is in use.

## Where files go

Everything a run makes (`clients/`, `library/`, `jobs/`) goes in the **user's project folder**: the nearest folder
holding `clients/`, `library/` or `.git`, else the folder Claude is working in (`workspace.py` decides; `$ZAMAKAN_ROOT`
overrides). Never write into the skill folders: when the skills are installed as a plugin, they are replaced on update.

## First run on a computer

If a script fails on a missing package or browser, run `python3 $CORE/scripts/doctor.py`: it checks Python, the packages,
Chromium and LibreOffice and prints the exact install command for anything missing. Tell the user what to run.

## Client folders

```
clients/<slug>/                 # git-ignored: client material stays local
├── input/                      # brand files exactly as the client sent them
├── design-system/              # produced by zamakan-design-system (the "contract")
│   ├── brand.md                # READ FIRST for any visual work
│   ├── tokens.json / tokens.css / manifest.json / DESIGN.md / sources.md / preview.png
│   └── spec.json               # source of truth (agents edit this, then rebuild)
└── jobs/<yyyy-mm-dd>-<job>/    # every deliverable, one folder per job
```

`<slug>` is lowercase-kebab (`rawaq`, `noor-dental`). Use the helper instead of guessing:

```bash
python3 $CORE/scripts/client.py list                 # all clients + design-system status
python3 $CORE/scripts/client.py status <slug>        # what exists, what is missing, open questions
python3 $CORE/scripts/client.py init <slug> [--from <dir>]   # create folders, copy brand files into input/
python3 $CORE/scripts/client.py job <slug> <job-name>       # create jobs/<date>-<job-name>/ and print its path
```
(`$CORE` is the folder containing this file.)

## Before any on-brand work

1. Run `client.py status <slug>`.
2. **If there is no design system,** run the `zamakan-design-system` skill first. Making visuals without one
   means guessing colours and logo rules, which is the most common way agency work gets rejected.
3. **If there is one,** read `design-system/brand.md` (the Quick reference is usually enough; if `brand.md` is missing,
   read `DESIGN.md` and `spec.json`, and say so in your delivery notes). Then use
   `tokens.css` / `tokens.json` for exact values and `manifest.json` to pick logo files. The full
   consumer rules are in `references/design-system-contract.md`.
4. Mention any open conflicts from `sources.md` that affect your deliverable.

## Quality bar (all sub-skills)

- **Bilingual:** Arabic is written natively, not translated, and the Arabic register is set per client.
  Arabic text is right-to-left and right-aligned, is never letter-spaced, and uses the Arabic type tokens.
- **On-brand:** colours via role tokens, logos only on approved backgrounds, at or above minimum size.
- **Traceable:** say what came from the client and what you proposed.
- **Saved:** deliverables go in `clients/<slug>/jobs/…`. Summarise in chat; don't paste whole files.

## ZAMAKAN skills

| Skill | Does |
|---|---|
| `zamakan-design-system` | Brand files → verified design system (this contract) |
| `zamakan-shot-scout` | Cinematic references for a subject, effect or frame (Eyecannndy, Film-Grab, Vimeo, YouTube) → film language, shot board with palettes, credits and how-to-shoot notes |
| `zamakan-reference-scout` | Verified campaign references (Ads of the World, YouTube, Vimeo, award shows, trade press, competitor ads) → analysis, white space, creative territories; board / deck / report |

General marketing skills (copywriting, ad creative, social, A/B tests…) from
[marketingskills](https://github.com/coreyhaines31/marketingskills) work well alongside these. When one
asks for product or brand context, give it this client's `brand.md` and design system.
