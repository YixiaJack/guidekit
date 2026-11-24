# Brief for reviewing one chapter of {{title}} before release

The chapter `{{out}}` was drafted by an agent. A script already proves that every quote, copied table, figure{{code_word}}
matches its source. What it cannot prove is that the **prose** is right: paraphrases, numbers outside quotes, who did or
decided what, causal claims, and what the sources do not say. Check the prose against the sources and fix it in place.

The writing brief is below; everything in it still applies (sources, formats, rules).

## What to check, in order

1. **Numbers outside quotes.** Every number in the prose and in compiled tables must appear in a cited source with the
   same meaning (right model, scale, metric, direction, default). The checker could not find these numbers in the
   chapter's cited sources: {{numbers}}. Resolve each one: fix it, add the missing citation, or label it "(our
   arithmetic)" or as an assumption of the example.
2. **Paraphrases.** For each paragraph that summarises a source, open it and confirm the summary says what the source
   says: no stronger claim, no missing condition (scale, seeds, baseline, configuration, hardware), no merged events.
   Start with the summary, the at-a-glance table, the current-state section and the pitfalls.
3. **Attribution.** Decisions credited to a person must be in that person's own words in the source; agent-written
   reports and bot comments must not be presented as human conclusions.
4. **Inferences.** Anything not stated in a source is marked "Inference:" with its basis, or removed.
5. **Dates, versions, defaults, line numbers.**
6. **Consistency.** The summary, tables and body agree; links point to chapters that exist in `{{chapters_dir}}`.
7. **Tone.** Plain and precise; no hype, no claims about people's motives; they/them for anyone whose pronouns the
   sources do not state.

Fix problems with small edits. Do not rewrite correct sections, add topics, or lengthen the chapter except for a missing
caveat or citation. Keep every evidence format intact.

## Finish

Write a log to `{{review_log}}`: one line per change (section — what was wrong — what you changed — source), then one
line on what you checked and found correct, then anything you could not resolve. Reply in at most 100 words: number of
fixes by type, and unresolved items.

---

{{brief}}
