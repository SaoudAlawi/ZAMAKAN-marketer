# Iteration 3 agent feedback
## s3 with_skill (competitor watch)
- REGRESSION: GENERIC_THUMB matches "default" → every YouTube hqdefault/maxresdefault thumbnail dropped (fix after the round: match path segments, not substrings; never for i.ytimg.com)
- competitors.py channel suggestions mostly noise; Arabic YouTube search found official channels (use Arabic brand names + "اعلان"); plan search terms weak ("Half حملة 2026": first word only)
- youtube-channel dates from relative ages are coarse (2y ago → same date); view counts truncated ("7" vs 7026: "7K" parsing)
- validate window compares years only (June 2025 passes 12-month window); plan window start off by days (30*months)
- dated/Arabic web searches return off-topic (US elections); site: trade press works
- competitor-watch: 12/16 refs evidence=video → board headline "links checked/verified" overstates; cover rule ("not a competitor ad") impossible in this mode; territory panels show competitor ads
- no helper to turn detail.jsonl line into a reference stub (manual JSON for 16 refs is heavy)
- build_outputs: no warning about missing brand.md
- board: territory panels empty cells; mixed-direction Arabic hashtag titles out of order
## s2 with_skill (global question)
- verify summary counts thin pages as verified (board shows "details unconfirmed" but headline overstates) → summary should split: page read / page exists / video
- Cannes Lions, WARC, D&AD return only footer to --text; WebFetch DNS errors everywhere → results claims rest on search snippets
- avoid-list flag matches single words ("waiting", "bank") → flag useless; match whole avoid phrases / ignore words that are in the question
- score.py noisy for this topic (hold-music compilations, tutorials)
- YouTube thumbnails labelled generic (same "default" regression); publisher logo / black slate thumbnails dropped by hand
- AotW pages with credits only (no description)
- direct ring rule vs "no Saudi work" brief: allow empty direct ring when the brief says so
- validate_run region map: Jordan counted separately from GCC flatters spread (fine: mena ≠ gcc, but "7 regions" claim includes Jordan as region) 
## s1 with_skill (GCC brief)
- LEAKAGE (important): SKILL.md + analysis-framework.md examples are Rawaq/Ramadan-specific (taraweeh pour spark, arch signal, "after-taraweeh coffee run" white space, 9-11pm insight). They anchor the s1 answer → s1 with-skill result is contaminated. Fix: rewrite all examples for a different client/category not in any scenario.
- fetch_meta --text: Arab News returns wrong 37-char text without warning (doesn't follow internal redirect / amp); should flag text_chars tiny + title mismatch
- score.py noisy (vlogs, recipe channels; many ties at 2.7)
- YouTube thumbnails "generic" (same regression)
- verify: bilingual titles "Wanasa Mkamela (الوناسة مكمّلة)" fail match → strip parenthesised/Arabic parts before matching
- AotW descriptions truncated with "…" in detail.jsonl
- competitors.py useful in brief mode too: document it
