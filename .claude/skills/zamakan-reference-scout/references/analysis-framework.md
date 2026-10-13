# Analysis framework: cards, teardowns, scores, patterns, territories

The creative team should be able to brief from this without opening every link.
Write plainly and specifically, and never claim more than the source says.

## Card (every reference)
- **idea**: what they actually did, in one sentence, concrete enough to picture.
  - Good: "Two groups of men on Al Khobar's Corniche compete to invite one lonely stranger to iftar."
  - Weak: "An emotional Ramadan film about togetherness."
- **why_relevant**: why it matters for *this* client and brief (inspiration, contrast, competitor benchmark, mechanic to borrow).
  - Good: "Saudi hospitality rivalry played as comedy: the Najdi generosity Rawaq stands for."
  - Weak: "Relevant Ramadan campaign."

## Evidence you haven't seen
Videos you couldn't watch and pages you only know by title can still be listed, but say so:
`provenance.confidence: "medium"` plus a note ("known from title/channel only; watch before the client deck").
Don't write a teardown from a title, and don't put such a reference in `top`.

## Scores (0–5, one decimal allowed)
| Score | 5 means | 1 means |
|---|---|---|
| relevance | squarely on the brief's audience, moment and objective | only loosely connected |
| craft | idea and execution are award-level | generic or poorly made |
| transferability | a clear principle this client can borrow | tied to that brand's specifics |
| cultural_fit | right for Saudi/GCC audiences as is (see gulf-culture.md) | would offend or feel foreign |
| freshness | last 2 years, not yet copied by everyone | old or already a category cliché |

## Teardown (top 3–5)
| Field | Write |
|---|---|
| insight | the human truth underneath, in one sentence and in people's language, not marketing language |
| idea | the creative leap that dramatises the insight |
| execution | what was made: format, length, cast, location, craft people (only those named in the credits) |
| channels | where it ran, if stated |
| tone | 2–4 words |
| visual_devices | recurring visual tricks (POV, single take, split screen, archive footage…) |
| results | only published results, with `results[].source_url`; otherwise leave it out |
| transferable | 2–3 **principles** this client can use. Never "do the same ad". |
| cultural_fit | a score plus a note: who it works for in KSA and what to adapt |
| risks | what could go wrong if borrowed (sensitivity, cliché, competitor already owns it) |

## Patterns (3–5)
An observation that holds across **at least two** references, phrased as a fact about the category or the moment:
"Coffee brands in the region stay generic ('savour', 'every moment', seasonal packaging)."
Cite the references in `reference_ids`.

## White space (2–4)
What nobody in the category does, phrased as an opportunity the client could take:
"No Saudi coffee brand owns suhoor or the after-taraweeh coffee run."
Check this against your direct-ring references, because a white space someone already owns isn't one.

## Territories (3–5 in brief/pitch mode)
A territory is a space for ideas, not one execution. Each one needs:
- **name** in English and **name_ar** in Arabic. Write the Arabic natively; a Saudi colloquial phrase often works
  better than a literal translation (*مين يعزم الليلة؟* rather than *من يستضيف الليلة*).
- **thesis**: 1–2 sentences on what the brand will own.
- **why_this_client**: the brand truth or asset it stands on (use brand.md if available).
- **reference_ids**: the 2–3 references that prove it can work. Use different rings if possible.
- **example_executions**: 2–3 quick sketches across the brief's channels.
- **risks**: cultural, competitive or practical.

Make territories distinct from each other: a safe one, a bold one, and an unexpected one is a good spread.

## Insights (3–5, they open the board and deck)
A truth about the audience or the market that a strategist would put on slide 2, with a source a client can check:
- Good: "Saudi Ramadan engagement peaks at night: CST points to 9:00–11:00pm as peak usage hours." (Campaign ME, 2026-02-05)
- Not an insight: "Ramadan is a time of togetherness." (no source, and everybody knows it)
Only use pages you opened. Mix kinds: culture (how people behave), data (a number), category (what brands do and why).
Give the date; a 2019 statistic in a 2027 plan needs saying.

## Competitors
One `competitor_summary` entry per named competitor: what you checked and when, whether you found a campaign for this
moment, what they own (one line), messaging pillars, and the reference ids. "None found" is a result to report.

## Recommendation
Pick. Name the lead territory, what supports it, and why, citing an insight or a white space and the competitor gap:
"Brief 'The after-taraweeh run' as the idea, with 'Who hosts tonight?' as its social engine…" A list of all territories
is not a recommendation.

## Before kickoff
The honest to-do list: videos nobody has watched yet, social feeds web search can't see, client policies an idea
depends on, rights questions. Short, concrete, owner-able.

## Sparks (3–5)
A spark is a far-away reference plus one provocation for this client. Write the provocation as a question that borrows
the **mechanic or thinking**, never the execution:
- Good: "What if the Rawaq arch became the wordless 'coffee after taraweeh?' signal between friends?" (from McDonald's
  *Raise Your Arches*: a brand shape turned into an invitation)
- Weak: "Do a funny film like Burger King." (copies a surface, says nothing about the client)
A good spark makes the room argue. If it couldn't possibly work in the client's market, say why in `why_relevant`;
it can still be useful as the outer edge of the conversation.
