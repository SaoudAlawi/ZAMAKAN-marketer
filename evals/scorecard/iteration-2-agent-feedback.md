## s3 with_skill (competitor watch)
- web search shared budget (200/turn) ran out; skill silent on search budget
- competitor-watch: Meta Ad Library 403, Instagram blocked, TikTok shell → live_ad never fillable; say so + manual checklist
- AotW useless for brand names; no brand.md in design system (only DESIGN.md/spec)
- board: "What they own" shows long notes; hero subtitle "other ·"; empty grey tile without thumbnail; competitor photos as Rawaq territory visuals / hero = Starbucks ad
- fetch_meta wrong body text (LBB), off-market images; verify lenient (homepage title); no field "owned channel seen on date"
- mode rules unclear: territories/sparks/time window in competitor-watch; brief schema lacks time window
## s2 with_skill (global question)
- stale thumbs cache by id; fetch_meta takes generic logos/slates (Drum, lovethework, D&AD) and check_outputs doesn't flag
- redirects change URL → thumb lookup misses; verify passes nav-only pages (lovethework, D&AD)
- AotW thin descriptions; noisy single keywords; no alcohol rule; web search budget ran out
- library add without client undocumented; shell quoting with parentheses
## s1 with_skill (GCC brief)
- fetch_meta --out overwrites, discover --out appends (lost batch)
- deck shows only 3 insights (board 5): silent truncation
- brand.md missing in design system (prompt + skill point to it)
- score.py brief mode noisy: Saudi+GCC outweigh moment/category
- verify title-matching wording-dependent (trade press headline w/o campaign name) → invites gaming
- adsoftheworld.com without www fails DNS: normalise
- arabnews 403; clios 404; adland generic title
- shared web-search budget; re-running build clears verification (undocumented)
- cover crop of burned-in subtitles; no option to pick cover image
## s5 with_skill (global brief)
- LEAK: thumbnail.local absolute path (clients/rawaq/jobs) in shared library → FIXED immediately (neutral() keeps url only)
- stale thumb cache by id; fetch_meta --text wrong text (lbb, arabnews, verdict)
- verify marks unwatched YouTube as verified → board "checked live" overstates
- brand.md missing; no manual job path convention; search budget out after ~15 searches
- AotW 'opening' noisy; score.py first ranking irrelevant
- no competitors in brief → what goes in competitor_summary? (nearest benchmarks)
- global: country = brand home or campaign country? ; YouTube thumbs letterboxed in arch
## s3 without_skill: found MORE 2026 activity than with-skill (Half Million Oct 2026 ads, ND96, Barn's X) → competitor-watch mode weaker than baseline
## s4 with_skill (pitch)
- search budget out after ~13; no guidance when search unavailable but fetch works
- fetch_meta returned no title/thumb for some YouTube URLs in --text batch → grey tiles; hand-built i.ytimg URLs
- lovethework pages 200 + title but boilerplate → "verified" doesn't confirm award level
- duplicate-URL error clashes with shared award round-up as source for several refs
- pitch: award-only vs ring shares conflict; score.py can't tell award-level
- skill folder contains evals/ (ambiguous for test rules) — check it doesn't leak
- deck territory images default to first ref (Starbucks 3x) — lead_order should help; check
