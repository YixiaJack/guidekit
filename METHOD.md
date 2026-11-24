# The method in one page

**Goal.** Make a large, public body of technical work readable: an open lab's experiment record, a codebase too big for
a newcomer, or a literature. The output is a book (website and PDF) organised by question, with the original tables,
figures, formulas and code, and a front door for people who are new to the subject.

**The guarantee.** Every quote, copied table, figure and code excerpt is checked by a script against a pinned copy of
its source (a commit, a downloaded issue thread, a paper's LaTeX). Numbers in the prose that appear in no cited source
are listed for a person to check. What a script cannot check (paraphrase, attribution, causal claims) goes through a
review pass that reads the sources again; in our three guides that pass changed 10 to 50 places per chapter.

**The steps.**

1. *Scope and readers.* Which material, which readers (researchers or beginners), private or public, licence.
2. *Pin the sources.* Code at an exact commit; issues, PRs and reports downloaded once; papers' LaTeX. Treated as data:
   never executed, agent configuration files quarantined. Follow references to unlabelled issues that carry decisions.
3. *Plan chapters.* One question per chapter; a pack per chapter listing the sources to start from.
4. *Write.* One agent per chapter, with a shared brief that fixes structure, evidence formats, length and rules
   (attribution, labelled inferences, no invented numbers). Agents can only read the sources and write their chapter.
5. *Check.* The script checks every piece of evidence; failures go back to the agent until there are none.
6. *Review.* A second agent checks the prose against the sources and fixes it in place, with a log of every change.
7. *Whole-book pass.* Contradictions between chapters, shared terms, a glossary; then the front door: main findings,
   a one-hour introduction, reading paths, and a searchable knowledge-base page (topic tiles, one card per item).
8. *Website and translation.* A knowledge-base site (topic tiles, beginner track, each chapter as overview / full
   chapter / design-and-pitfalls, formulas and diagrams) in English and Chinese with one switch. The Chinese edition is
   written by locked agents and checked block by block against the English (headings, quotes, tables, figures, code,
   math, links, numbers, handles), so nothing is added, dropped or changed in translation.
9. *Publish.* A public static site per guide and a path on the private research site, where the guides sit side by
   side with curated links between them (a Marin finding about vLLM's sampling links to the vLLM chapter on sampling)
   and questions can draw on all of them.
10. *Update.* Records guides follow new issues daily; code guides follow releases: a weekly check finds the chapters
   whose code excerpts changed in the latest release.

**What we learned building Marin KB, vLLM explained and SGLang explained.**

- Without length limits, agents write chapters nobody finishes; beginners need a short track before the deep chapters.
- An agent's write-up is not a maintainer's decision; names and decisions are credited only where the source shows them.
- Documentation lags code; in code guides the pinned code is the truth and mismatches are listed for the reader.
- Key decisions often sit outside the labelled issues; following references found them.
- "Closed" is not "answered": many questions were closed by a stale bot or as superseded.

**Reuse.** A new guide is a `guide.toml` (sources, readers, chapters, `[site]` texts) and five commands:
`write`, `translate`, `site`, `build`, `publish`. The SGLang guide's later chapters, the review of all 36 vLLM and SGLang
chapters, their Chinese editions and both websites were produced this way, with no hand-written prompts.
