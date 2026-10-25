# ZAMAKAN skills for Claude Code

Marketing and creative skills from ZAMAKAN (زمكان), an Omani agency, in Arabic and English:

| Skill | Ask for… | You get |
|---|---|---|
| **Reference scout** | "References for our Ramadan kickoff", "What are our competitors running?" | Real campaigns (every link checked live), insights with sources, patterns, white space, creative territories and a recommendation, as an HTML board, a deck (PowerPoint + PDF) and/or a report |
| **Shot scout** | "Maghrib light on the road, warm and spiritual", "Best dolly zoom examples", "Find shots like this frame", "I'm a writer, inspire me" | Cinematic references (films, shorts, documentaries) as a shot board with stills, palettes, credits and how-to-shoot notes, or a viewing programme for filmmakers |
| **Script desk** | "Template for a 12-minute short", «نسّق السيناريو», «ملاحظات على مسودتي» | Structure templates in Word, a formatter (right-to-left Arabic, Word + PDF + Fountain) and a reader's notes from ten viewpoints as side comments (Word + PDF), with charts, draft-to-draft tracking, an intent sheet, replies in the margin and scene cards. It helps you write; it never writes for you |
| **Design system** | "Here are the brand guidelines for client X" | The client's colours, fonts, logos and rules as files every other skill uses |
| **Core** | (used by the others) | Client folders, brand loading, the bilingual quality bar |

## Install

In Claude Code:
```
/plugin marketplace add SaoudAlawi/ZAMAKAN-marketer
/plugin install zamakan@zamakan-marketer
```
Then, once per computer, install the Python packages (the list in this folder's `requirements.txt`) and the browser
the skills render with:
```bash
pip install jsonschema pymupdf fonttools pillow python-pptx python-docx playwright beautifulsoup4 lxml pycountry
python3 -m playwright install chromium
```
LibreOffice is optional (decks also come as PDF when it is installed). Not sure what's missing? Ask Claude to
"check the ZAMAKAN setup": it runs a checker that prints the exact commands.

Updates: when a new version is published, run `/plugin marketplace update zamakan-marketer` (or switch on auto-update
for this marketplace in `/plugin`).

## Use

Open any folder in Claude Code and ask in plain language. Claude asks once about anything missing (scope, outputs),
then works on its own. Results land in that folder: `clients/<client>/jobs/<date>-<job>/` (or `jobs/` for general
questions), and a reference library builds up in `library/`. Keep `clients/` out of public repositories.

**Your home market.** The defaults are ZAMAKAN's (home market Oman). To set your own, put a `zamakan-agency.json` in
your project folder:
```json
{"name": "Your agency", "home_country": "SA", "home_name": "Saudi Arabia", "home_name_ar": "السعودية",
 "default_markets": ["SA"], "aotw_country_slug": "saudi-arabia"}
```

## Honest limits

- Videos are not watched by Claude; boards say so and list what to watch before a meeting.
- Instagram, TikTok, Snapchat, X and the Meta Ad Library can't be read; competitor checks include links to open by hand.
- Web searches are limited per session; the scripts do most of the collecting.
- In claude.ai cloud sessions, plugins installed on your computer don't load: open the repository itself there instead
  (its `.claude/skills/` hold the same skills).

Source, tests and the full plan: https://github.com/SaoudAlawi/ZAMAKAN-marketer
