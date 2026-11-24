"""`guidekit init`: a new guide project with guide.toml, a Jupyter Book skeleton, a licence and a Pages workflow."""
from __future__ import annotations

from pathlib import Path

GUIDE = '''# {title} (kind = {kind})
[guide]
id = "{id}"
title = "{title}"
kind = "{kind}"                     # code | records | literature
audience = "{audience}"             # beginners | researchers
root = "{root}"
words = [5000, 7000]               # target words of prose per chapter
max_code = 30                      # code kind: most excerpts per chapter
model = "opus"                     # writing agents
review_model = "sonnet"            # review agents

[source]
intro = """
One paragraph: what the subject is, why it is hard to read, and what this guide does for the reader.
"""
readers = """
Who the readers are, what they already know, and what they want to come away with.
"""
rules = ""                         # extra project-specific rules for writers (optional)
notes = []                         # extra material bullets for the brief, e.g. "Key decision issues: #12, #34"
{source_extra}
# Where cited sources live (see guidekit/sources.py). Examples:
{stores}

# One entry per chapter.
[[chapter]]
id = "overview"
title = "Overview"
scope = "What the chapter must cover."
'''
STORES = {
    "code": '''[[store]]
kind = "path"
format = "repo"
root = "~/guide-sources/REPO-TAG"
prefixes = ["src", "docs", "tests", "examples"]

[[store]]
kind = "issue"
format = "thread"
dirs = ["~/guide-sources/REPO-issues"]''',
    "records": '''[[store]]
kind = "issue"
format = "thread"
dirs = ["~/guide-sources/REPO-issues"]

[[store]]
kind = "pr"
format = "thread"
dirs = ["~/guide-sources/REPO-issues"]

# [figures]
# manifest = "book/figures/manifest.jsonl"''',
    "literature": '''[[store]]
kind = "paper"
format = "latex"
dir = "~/guide-sources/papers"''',
}
SOURCE_EXTRA = {"code": 'repo = "OWNER/REPO"\ntag = "vX.Y.Z"\ncommit = ""                        # filled by guidekit fetch',
                "records": 'repo = "OWNER/REPO"\nlabel = "experiment"', "literature": 'papers = []                        # arXiv ids'}
CONFIG = '''title: "{title}"
author: ""
copyright: "{year}"
only_build_toc_files: true
execute:
  execute_notebooks: "off"
parse:
  myst_enable_extensions: [dollarmath, amsmath, colon_fence, deflist, linkify, substitution]
sphinx:
  extra_extensions: [sphinxcontrib.mermaid]
  config:
    myst_heading_anchors: 3
    myst_dmath_double_inline: true
    myst_fence_as_directive: ["mermaid"]
    mermaid_version: ""
    mermaid_use_local: "https://cdnjs.cloudflare.com/ajax/libs/mermaid/11.4.0/mermaid.esm.min.mjs"
    mathjax_path: "https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.js"
    latex_elements:
      preamble: "\\\\setcounter{{secnumdepth}}{{0}}"
    suppress_warnings: ["myst.header", "myst.xref_missing"]
latex:
  latex_engine: xelatex
'''
PAGES = '''name: pages
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install "jupyter-book>=1.0.4,<2" sphinxcontrib-mermaid
      - run: jupyter-book build book/
      - uses: actions/upload-pages-artifact@v3
        with:
          path: book/_build/html
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
    steps:
      - uses: actions/deploy-pages@v4
'''


def init(root: Path, gid: str, title: str, kind: str, audience: str = "researchers") -> list[Path]:
    import time
    if (root / "guide.toml").exists():
        raise SystemExit(f"{root / 'guide.toml'} exists; not overwriting")
    files = {
        "guide.toml": GUIDE.format(id=gid, title=title, kind=kind, audience=audience, root=str(root).replace(str(Path.home()), "~"),
                                   stores=STORES[kind], source_extra=SOURCE_EXTRA[kind]),
        "book/_config.yml": CONFIG.format(title=title, year=time.strftime("%Y")),
        "book/_toc.yml": "format: jb-book\nroot: intro\nparts:\n  - caption: Chapters\n    chapters:\n      - file: chapters/overview\n",
        "book/intro.md": f"# {title}\n\nWhat this guide is, who it is for, how to read it, and how every claim is checked.\n",
        "book/chapters/.keep": "",
        "book/figures/.keep": "",
        ".gitignore": "work/\nbook/_build/\n.venv/\n__pycache__/\n.DS_Store\n",
        ".github/workflows/pages.yml": PAGES,
    }
    out = []
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        out.append(p)
    return out
