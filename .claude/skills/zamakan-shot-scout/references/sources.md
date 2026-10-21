# Sources: what each is good at (tested 2026-10-18)

`$SHOT/scripts/discover_shots.py <source> ...` covers the ones marked *script*; they cost no web searches.

| Need | Source | How | Notes from testing |
|---|---|---|---|
| A technique or effect | **Eyecannndy** (eyecannndy.com) | *script* `eyecannndy-technique <slug>` | Best source. Each clip has title, year, techniques, director, DOP, editor, colourist and (usually) the original YouTube/Vimeo link. Slugs are in `techniques.json` → `eyecannndy`. |
| Subject words | Eyecannndy search | *script* `eyecannndy-search <word>` | Tag-based: **single words** work ("sunset", "desert", "taxi", "prayer"); phrases find nothing (the script falls back to the words). Several clips often come from one video (different shots, all kept). |
| Who does this well | Eyecannndy people pages | *script* `eyecannndy-person dop/<slug>` or `director/<slug>` | Slugs are the name in lowercase-kebab (`dop/james-laxton`). Clip credits link there. |
| Film stills by look or title | **Film-Grab** | *script* `filmgrab <word>`, then `filmgrab-stills <film URL>` | Search matches titles and tags. Film pages are galleries (60+ stills): perfect for palettes. Credits are not on the page. |
| Film stills | Shot.cafe | *script* `shotcafe <word>` | Search is loose (results can be unrelated); check titles. |
| Commercials with credits | **shots.net**, LBB, Campaign ME, Ads of the World | web search, then *script* `page <url>` | shots.net articles name the director and often the DP; good for Ramadan/regional spots. |
| Short films | Directors Notes | *script* `directorsnotes <words>` | Articles with director interviews; good for craft detail. |
| Motion design / VFX | Motionographer, Stash | *script* `motionographer` / `stash <words>` | Their site search is weak; prefer web search + `page`. |
| Any video | YouTube | *script* `youtube <words> --min-views 20000` | Good for breakdowns ("how it's done") and Arabic ads; noisy for looks. |
| Vimeo | Vimeo | web search for links, then *script* `vimeo <url> ...` | Vimeo's own search blocks us (403, even in a browser). `site:vimeo.com` web searches return few results. The oEmbed check gives title, maker, date, duration, thumbnail and description, including timestamps the maker mentions ("look at 00:32"). A free Vimeo developer key would enable direct search later. |
| Documentaries | Short of the Week (genre Documentary), YouTube channels: Guardian Documentaries, NYT Opinion (Op-Docs), Al Jazeera Documentary الجزيرة الوثائقية (Arabic), Al Jazeera English (Witness), BBC Stories, POV | *script* `docs <words>`, `channel-search @handle <words>`, `shortoftheweek <w> --genre documentary` | Channel search only keeps titles containing your words (a no-match search lists the latest uploads). Short of the Week answers HTTP 414 when nothing matches. Feature docs: `film_facts.py` (Wikidata says "documentary film"). Reachable but no script yet: IDFA, POV (pbs.org/pov), Al Jazeera Witness pages, documentary.org; NYT site 403. |
| Blocked | ShotDeck, Behance, FilmFreeway | none | Login/403. Don't spend effort on them. |

## Search tips
- Run `expand.py` first; then add your own words. The dictionary can't know every subject.
- Arabic requests: translate the subject to English for Eyecannndy, Film-Grab and Shot.cafe (English-only); keep Arabic for YouTube.
- Gulf/Arab work is thin on Eyecannndy and Film-Grab: find it via YouTube (Arabic queries), shots.net and Campaign ME, then `page`/`vimeo`.
- Make a **contact sheet** (`contact_sheet.py`) of 12–24 candidates and choose by eye: one image costs far less than reading pages.
