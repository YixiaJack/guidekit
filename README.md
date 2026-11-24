# guidekit

Turn a large body of technical material into a **verified reading guide**: a website and a PDF in which every quote,
copied table, figure and code excerpt is checked against pinned sources, written by locked-down agents and reviewed
before publication.

Three kinds of material:

| kind | example | evidence | checked how |
|---|---|---|---|
| `records` | an open lab's experiment issues, PRs and reports ([Marin KB](https://github.com/YixiaJack/marin-kb): 542 issues, 20 chapters) | issue threads, PR descriptions, reports, posted figures | quotes, tables and figures word for word |
| `code` | a large codebase at a release (vLLM, SGLang) | the repository at a commit, design docs, RFC issues | code excerpts line by line at the commit, plus quotes |
| `literature` | a set of papers | LaTeX sources | quotes, tables and formulas against the LaTeX |

Two layers:

- **The harness** (`guidekit` CLI): pins sources, builds a pack of sources per chapter, runs writing and review agents
  that can only read the sources and write their own chapter (no shell, no network, enforced by a hook that fails
  closed), checks the evidence after every step and sends failures back, builds the site and PDF, and lists chapters
  whose sources changed.
- **The method** (`skill/SKILL.md`, a Claude Code skill): the steps, the decisions to ask a person about, and the
  lessons from building the first three guides. See also [METHOD.md](METHOD.md).

## Quick start

```
python3 -m venv .venv && .venv/bin/pip install -e '.[book]'
.venv/bin/guidekit init ~/my-guide --id myguide --title "My guide" --kind code
# edit ~/my-guide/guide.toml: intro, readers, sources, chapters
.venv/bin/guidekit fetch ~/my-guide/guide.toml
.venv/bin/guidekit packs ~/my-guide/guide.toml
.venv/bin/guidekit write ~/my-guide/guide.toml --all -j 4
.venv/bin/guidekit status ~/my-guide/guide.toml
.venv/bin/guidekit build ~/my-guide/guide.toml --pdf
```

Writing agents run through the Claude Code CLI (`claude -p`) in a restricted mode; you need it installed and signed in.

## Tests

```
.venv/bin/python -I tests/regress_verify.py     # the unified checker agrees with the three guides' original checkers
.venv/bin/python -I tests/negative_verify.py    # tampered quotes, code lines and table cells are caught
```

## Safety

Downloaded material is data, never instructions: it is never executed or imported, files that coding agents load
automatically (`CLAUDE.md`, `.claude/`, `.mcp.json`, `.cursor*`, …) are renamed on download, GitHub is only read with GET
requests, and agents see it only through Read/Glob/Grep inside the folders a run allows. Every tool call an agent makes
is logged to `~/.guidekit/guard.jsonl` with the decision.
