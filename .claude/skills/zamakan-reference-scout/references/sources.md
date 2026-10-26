# Sources: where to look and how

Tested live from this environment (October 2026). Each source is listed with what it gives, how to query it, and its quirks.

## Contents
1. Ads of the World (primary archive)
2. YouTube
3. Vimeo
4. Award shows
5. Trade press and newsrooms (MENA first)
6. Live competitor activity
7. Query patterns per ring (English + Arabic)
8. Scope: GCC, MENA or global
9. Sparks from elsewhere

---

## 1. Ads of the World (adsoftheworld.com): the richest source
Each campaign page gives country, month/year, brand(s), agency, medium, industry, number of assets,
full credits, the video file and **related campaigns**. `fetch_meta.py` parses all of it.

- **Search:** `discover.py aotw-search <keyword>` accepts **one keyword only**; multi-word searches return nothing.
  Run several single-word searches (`ramadan`, `iftar`, `suhoor`, `heritage`) and let `score.py` combine them.
  The search matches inside words and descriptions, so short or common words are noisy (`eid` hits "Leidos",
  `coffee` and `hospitality` return mostly unrelated work). Prefer distinctive words, and use **lists**
  (`countries/saudi-arabia`, `industries/non-alcoholic-drinks`) plus **related** for precision.
- **Lists:** `discover.py aotw-list <kind> <slug> --pages N` (60 cards per page).
  - `countries`: `saudi-arabia`, `united-arab-emirates`, `qatar`, `kuwait`, `bahrain`, `oman`, `egypt`,
    `jordan`, `lebanon` … (slugs are full names; `uae` does not exist)
  - `industries`: `agency-self-promo alcoholic-drinks automotive beauty cannabis confectionery-snacks delivery-services
    education electronic-devices electronics-technology fashion finance fitness food gambling gaming health
    hospitality-tourism house-garden household-products industrial-agriculture insurance jewelry lottery media
    military movies music non-alcoholic-drinks office-equipment other personal-accessories pets pharmaceutical
    professional-services public-interest-ngo public-utility real-estate recreation-leisure religion retail-services
    sports sportswear tobacco toys transport travel tv-promos`
  - `medium_types`: `360 ambient audio content design digital direct experiential film integrated outdoor print`
  - `regions`: `africa asia central-america europe far-east latin-america middle-east north-america oceania`
- **Related:** `discover.py aotw-related <url> ...` expands from your best finds, which is often the fastest way to more relevant work.
- **Student work** is common (pages say "student campaign" or "by ad school"). `score.py` flags it.
- Plain `curl` gets 403; the scripts send browser headers and fall back to Chromium automatically.

## 2. YouTube
- `discover.py youtube <words> --min-views 20000` returns title, channel, upload age, views and duration.
  Use `--min-views` to cut noise; official brand channels are the best signal.
- `fetch_meta.py` uses YouTube's oEmbed (title, channel, thumbnail). Watch pages are bot-blocked from cloud
  servers, so the upload date and views come from the search card only.
- Noise to skip: news agencies, fan re-uploads, "AI ad I made" demos, compilations (`score.py` flags most of them).

## 3. Vimeo
- Agency and director reels, often the original high-quality upload of a commercial.
- vimeo.com search is bot-blocked, so find Vimeo links with web search (`site:vimeo.com <brand> <campaign>`,
  `<director> <brand> vimeo`). `fetch_meta.py` reads them through Vimeo's oEmbed (title, author, thumbnail, date).

## 4. Award shows (proven creative quality)
Use web search for winners and shortlists, then link the case page (often on Ads of the World or the agency site):
- **Dubai Lynx** (MENA's festival): `"Dubai Lynx" <year> Grand Prix <category>`, `dubailynx.com`
- **MENA Effie Awards** (effectiveness, so results are published): `"MENA Effie" <year> gold <category>`
- **Cannes Lions** (lovethework.com; most case pages need login, so use press coverage), **D&AD**, **One Show**, **Clio**, **Epica**, **LIA**
- Results claims are only usable when a source states them. Put the source URL in `results[].source_url`.

## 5. Trade press and newsrooms (MENA first)
Read via `fetch_meta.py` (add `--text` for the article body; the web-fetch tool may fail on some of these hosts);
discover via web search:
- **Campaign Middle East** (campaignme.com): `site:campaignme.com <brand OR moment> campaign`
- **Arabad** (arabadonline.com), **Communicate**, **LBB Online** (lbbonline.com, "Middle East" tag), **AdForum**
- Brand and agency newsrooms or case pages: good for credits and stated results.

## 6. Live competitor activity (competitor-watch mode)
- **Meta Ad Library**: web search `"<brand>" site:facebook.com/ads/library`, or ask for the exact URL. The page is
  script-heavy; if `fetch_meta.py` can't read it, record what web search shows and say coverage was limited.
- **TikTok Creative Center**: top ads by country (Saudi Arabia) and industry; find through web search.
- **Brands' own channels**: Instagram, TikTok, Snapchat and X profiles found through search. Note the dates of recent posts.
- Record only what you saw: `live_ad.first_seen/last_seen/format/copy`. Never estimate spend or reach.

## 7. Query patterns per ring
Write 8–15 queries before collecting, and mix languages.

| Ring | English | Arabic |
|---|---|---|
| direct | `<category> <moment> Saudi campaign`, `<competitor> campaign <year>` | «حملة <الفئة> رمضان», «إعلان <المنافس>» |
| category | `<category> <moment> ad`, `best <category> commercials <year>` | «إعلان <الفئة>» |
| adjacent | `<moment> campaign <insight word>` (e.g. *togetherness, hospitality, generosity*) | «حملة رمضانية كرم», «إعلان ضيافة» |
| wildcard | `Grand Prix <year> <medium>`, `Dubai Lynx Grand Prix <year>` | n/a |

Seasonal moments to search: Ramadan, Eid al-Fitr, Eid al-Adha, Saudi Founding Day (22 Feb), Saudi National Day (23 Sep),
Riyadh Season, back to school, White Friday. Check the dates in `gulf-culture.md`.

## 8. Scope: GCC, MENA or global
9. Sparks from elsewhere
`brief.scope` changes where the rings look; cultural fit is always judged for the client's own market.

| Scope | direct | category / adjacent | wildcard | Languages |
|---|---|---|---|---|
| `gcc` (default) | KSA + GCC | GCC first, then MENA and the world | anywhere | EN + AR |
| `mena` | KSA + GCC | Egypt, Levant and Maghreb as well as the GCC (`countries/egypt`, `jordan`, `lebanon`, `morocco`) | anywhere | EN + AR (+ FR for the Maghreb) |
| `global` | KSA + GCC (the client still competes at home) | the best work from **≥3 regions**: AotW `regions/europe`, `north-america`, `latin-america`, `asia`, `far-east` | Cannes Lions, D&AD, One Show, Effies Grand Prix and gold | EN + AR + the language of the strongest market for the idea (e.g. ES/PT for Latin America, FR, JA) |

Global tips: search award winners by year and medium (`"Cannes Lions" <year> Grand Prix <category>`, `"D&AD" <year> pencil <category>`,
`"Effie" <year> gold <category>`), then find the case film on Ads of the World, YouTube or Vimeo. A global reference needs a
`why_relevant` that says what translates to the client's market and what doesn't. `validate_run.py` warns when a global
run covers fewer than 3 regions.

## 9. Sparks from elsewhere
3–5 references from outside the client's region **and** category, in every brief, pitch and creative question. The aim
is a different conversation in the room, not more of the same. Where to look:
- **Award winners:** `"Cannes Lions" <year> Grand Prix <Direct|Media|Creative Strategy|Outdoor|Social>`, D&AD Black/Yellow
  Pencils, One Show Best of Show, Effies Grand. Mechanics and media ideas travel best.
- **Ads of the World lists outside home:** `aotw-list regions europe|north-america|latin-america|far-east|asia`,
  and industries far from the client's (`gaming`, `public-interest-ngo`, `fashion`, `sports`, `music`).
- **The same human truth, another world:** search the insight, not the category: "invitation", "hosting", "late night",
  "ritual", "waiting", "sound of".
Rank with `score.py <candidates> --brief brief.json --sparks`. Verify like any reference. Don't use a spark the client's
direct competitor in the region has already copied.
