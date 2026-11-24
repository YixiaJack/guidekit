---
name: guidekit
description: Turn a large body of technical material (an open lab's experiment log, a big codebase, or a set of papers) into a verified reading guide (a website and PDF in which every quote, table, figure and code excerpt is checked against pinned sources). Use when the user wants to "make a knowledge base / reading guide / docs" out of a GitHub repo, its issues and PRs, or a literature; when they want a beginner's guide to a large codebase; or when continuing, reviewing, updating or publishing a guide built with guidekit.
---

# guidekit: verified reading guides

The method behind Marin KB (542 experiment issues → 20 chapters), vLLM explained and SGLang explained. The harness
(`guidekit` CLI, this repo) does the mechanical parts: pinning sources, building chapter packs, running locked-down
writing and review agents, checking every piece of evidence, building the site and PDF. This skill is the judgment:
what to decide, in what order, and what has gone wrong before.

## The guarantee, and its limit

- **Machine-checked:** every quote, copied table, figure and code excerpt matches a pinned source; numbers in the prose
  that appear in no cited source are listed for a human.
- **Not machine-checked:** paraphrases, causal claims, who decided what, what a source does *not* say. That is what the
  review pass is for; in the three guides it changed 10–50 places per chapter. Never ship a chapter that only passed
  the checker.

## The eight steps

1. **Scope and readers** (ask the user; these decide everything else).
   - What material: a repo's code at a release (`kind = "code"`), a project's issues/PRs/reports (`records`), or papers (`literature`).
   - Who reads it: researchers who want the record, or beginners who want a way in. Beginners need a short front-door
     track (5 chapters of 2–3.5k words) *before* the deep chapters; researchers need "Read first" lines and reading paths.
   - Private or public; licence (CC BY 4.0 for text worked well); whether to credit and notify the upstream project.
2. **Pin the sources** — `guidekit init`, edit `guide.toml`, `guidekit fetch`.
   - Code at an exact tag and commit (a lock file records it). Issues and PRs downloaded once with their comments.
   - Downloaded material is untrusted: never run, install or import it; agent config files in it are renamed
     `QUARANTINED__*` automatically. Only GET requests to GitHub.
   - Follow references: key decisions often sit in issues *without* the label you fetched (Marin's Snowball design
     issue was unlabelled). Grep the fetched threads for `#N` links to unfetched issues and add the important ones.
3. **Plan chapters and packs** — `[[chapter]]` entries, then `guidekit packs`.
   - One question per chapter. 12–20 chapters for a big subject. A synthesis chapter (pitfalls) and a "start here"
     chapter come last, written from the others.
   - Each pack lists the sources the writer starts from (code paths with line counts, docs, matching issues, figure
     candidates). Read two or three packs yourself before writing: a bad pack makes a bad chapter.
4. **Write** — `guidekit write GUIDE ch1 ch2 … -j 4`.
   - Each chapter is drafted by a locked agent: Read/Glob/Grep/Write/Edit only, no shell, no network, reads limited to
     the sources and the book, writes limited to its own staging file. The harness checks, sends failures back
     (up to three fix rounds), then runs a review agent, then checks again.
   - Use `guidekit brief GUIDE ch` to read the exact brief first. Put project-specific facts in `guide.toml`
     (`intro`, `readers`, `notes`, `rules`, `scope`), not in ad-hoc prompts, so the next chapter gets them too.
   - Set lengths. Without limits agents write 10–14k-word chapters that beginners cannot use.
5. **Check** — `guidekit verify`. Zero failures is required; look at the listed numbers (worked examples and "our
   arithmetic" are expected there; anything else is a likely error).
6. **Review** — automatic in `write`; for a second opinion, a fresh review with a different model, and for
   beginner material a persona review ("you know PyTorch, you have never read an inference engine: where did you get
   lost?"). Read the review logs in `work/reviews/`.
7. **Whole-book consistency** — after all chapters exist: one pass for contradictions between chapters (the same gate,
   date or number stated differently), shared terms (a glossary), people's handles, and cross-links. Then add the
   front door: an intro with the main findings, a "start here" page, reading paths for different readers, and
   "Read first" lines at the top of long chapters.
8. **Publish and keep it current** — `guidekit build --pdf`; private first; public only with the user's explicit OK.
   `guidekit stale` lists chapters whose sources changed since publication; re-run `write --revise` on them.

## Decision points: stop and ask the user

- Scope, readers, privacy and licence (step 1). Creating any GitHub repository. Making anything public.
- Downloading third-party images or redistributing third-party text beyond short quotes.
- When the evidence contradicts something the user or a collaborator believes: say so with the source before acting.
- When a chapter's review finds the record does not support the chapter's main claim.

## Lessons (each one cost a rewrite once)

- **Attribution:** an agent's write-up is not a maintainer's decision; a bot's comment is not a person's. Name people
  only by the handle the source uses, never infer real names or pronouns (use they/them), and only credit a decision
  to someone whose own words show it.
- **Docs lag code.** In code guides the pinned code is the truth; list doc/code mismatches in the pitfalls section.
- **Closed is not answered.** Issues closed by a stale bot or "superseded" left questions open; say so.
- **Inference is labelled.** Anything not stated in a source is marked "Inference:" with its basis.
- **Numbers keep their meaning:** right model, scale, metric, direction. No unit conversions.
- **Publishing traps (Jupyter Book 1.x):** one-line `$$…$$` needs `myst_dmath_double_inline` under `sphinx.config`;
  Mermaid needs the ESM build via `mermaid_use_local`; every script in `_static` is injected into every page; a site
  behind a CSP needs hashes for Sphinx's inline scripts; emoji break the PDF; `secnumdepth 0` stops double numbering.
- **Running many agents:** about 6 at a time; cheaper models for review; when a usage limit stops agents, resume the
  same agents rather than restarting (drafts on disk survive).
- **Give the book a front door that looks like a knowledge base**, not only a table of contents: topic tiles with
  counts and verdicts, the main findings, and a searchable card per item, linking into the long chapters.

## Lessons from publishing and translating (Marin KB, 2026-11)

- **Formulas shown out of context.** A formula copied from a sentence keeps its punctuation (`…,$$`): strip trailing
  `, . ;` and spacing for display, after checking the formula matches the chapter verbatim. A display that joins several
  statements with `,\qquad` (a law and its R², a definition and its condition) reads as one garbled line: split it into
  one centred line per statement (`\begin{gathered} … \\ … \end{gathered}`). Render every formula with KaTeX
  `throwOnError: true` before publishing; a formula that parses can still look wrong, so look at the page.
- **Real names.** Never pair a GitHub handle with a real name unless a source links them (a profile link, a signed email
  quote). A blog byline "Larry Dial" does not prove that @ClassicLarry is that person. Scan the book for
  `Name (@handle)` and `@handle (Name)` and check each pairing against the sources.
- **Summaries from other pipelines can be wrong.** Before translating or reusing a summary, check its dates and claims
  against the source (a refit "in July" was an issue opened July 31 with results on August 5).
- **Translation is checked block by block**, not trusted: same headings at the same levels, the same quotes, tables,
  figures (same files), code blocks (identical), math spans (identical), link targets, every number, every GitHub handle
  (same counts: who did what must not change), and no long untranslated runs. Calibrate the checker or translators will
  game it: ignore month numbers (`4 月` for April) but count days; take digits inside handles (`@Helw150`) and metrics
  (`pass@16`) out of the number check and check handles separately; treat `1,764,777` as one number and `0,1,2` as
  three; let number words become digits ("seven" → 7) and only fail on missing multi-digit numbers. When a translator
  reports a workaround ("dropped 日", "replaced a handle with 他们"), fix the checker, not the text.
- **Bilingual sites.** One switch for the whole site, English by default; both languages are the same pages with the
  same features, and each language shows only that language (original quotes as a hover tooltip). One renderer for both;
  the second language's chapters are paired with the master block by block (headings take the master's anchors).
- **Generated content needs an English mirror too** (daily digests, review items, answers, status words): a translation
  memory keyed by the source string's hash, with the same number and reference checks; do not skip whole subtrees by
  key name (`status` objects hold display text).
- **Reviews must be real.** A cheap model with a soft brief returned 47-second reviews; requiring every cited source in
  the summary, tables, decisions and pitfalls to be opened gave 5-minute reviews that fixed 3–10 claims per chapter. Check
  that the review log was written (an agent can only write its cwd and `--add-dir` folders).
- **Front door and UI.** Readers want the knowledge-base view (topic tiles with counts and verdict bars, main findings,
  searchable cards) and each topic opening into its full chapter with tabs: overview (summary, findings, open questions,
  key formulas and figures, "inside the chapter" outline), full chapter (sticky contents, progress bar, issue links open
  the experiment card in a drawer), process and pitfalls, and all cards. No reading-time labels.
- **Jupyter Book traps.** Every file in `_static` is injected into every page (scripts run twice); standalone pages go
  in `html_extra_path`; a page behind a CSP needs hashes for Sphinx's inline scripts; `only html / only latex` keeps
  interactive pages out of the PDF.

## Commands

```
guidekit init DIR --id ID --title "T" --kind code|records|literature
guidekit fetch GUIDE            # code / issues / arxiv, by kind
guidekit packs GUIDE [CH ...]
guidekit brief GUIDE CH
guidekit write GUIDE CH ... [--all] [--revise] [--no-review] [-j 4]
guidekit verify GUIDE [FILE ...]
guidekit status GUIDE
guidekit stale GUIDE
guidekit build GUIDE [--pdf]
```

Worked examples: `examples/marin`, `examples/vllm`, `examples/sglang` (their guide.toml files).
