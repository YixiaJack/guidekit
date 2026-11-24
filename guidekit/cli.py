"""guidekit: turn a large body of technical material (an experiment log, a codebase, a literature) into a verified
reading guide: chapters written by locked-down agents, every quote, table, figure and code excerpt checked against
pinned sources, reviewed, and published as a website and a PDF.

  guidekit init DIR --id ID --title T --kind code|records|literature     new project: guide.toml, book skeleton, Pages workflow
  guidekit fetch GUIDE [code|issues|arxiv]      pin the sources (shallow clone at a tag; issues via GET; arXiv LaTeX)
  guidekit packs GUIDE [CHAPTER ...]            write work/packs/<chapter>.md: the sources each writer starts from
  guidekit brief GUIDE CHAPTER                  print the writing brief an agent would get (to read or adjust it)
  guidekit write GUIDE CHAPTER ... [--all] [--no-review] [--revise] [-j N]
                                                draft -> check -> fix -> review -> check -> into book/chapters/
  guidekit verify GUIDE [FILE ...]              check the evidence in the chapters
  guidekit status GUIDE                         one line per chapter: state, words, checks, numbers to look at
  guidekit stale GUIDE                          chapters whose sources changed since they were published
  guidekit build GUIDE [--pdf]                  Jupyter Book site (and PDF via tectonic)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import config


def _g(a):
    return config.load(a.guide)


def cmd_init(a):
    from . import scaffold
    for p in scaffold.init(Path(a.dir).expanduser().resolve(), a.id, a.title, a.kind, a.audience):
        print("wrote", p)
    print("Next: edit guide.toml (intro, readers, stores, chapters), then `guidekit fetch` and `guidekit packs`.")
    return 0


def cmd_fetch(a):
    from . import fetch
    g = _g(a)
    what = a.what or {"code": "code", "records": "issues", "literature": "arxiv"}[g.kind]
    if what == "code":
        repo = next(s for s in g.stores if s.get("format") == "repo")
        info = fetch.code(g.source["repo"], g.source["tag"], Path(repo["root"]).expanduser(), g.source.get("commit") or None)
        print(f"pinned {info['repo']} {info['tag']} at {info['commit']}; quarantined {len(info.get('quarantined', []))} agent files")
        if not g.source.get("commit"):
            print(f"set commit = \"{info['commit']}\" in {g.file}")
    elif what == "issues":
        st = next(s for s in g.stores if s.get("format") == "thread")
        got = fetch.issues(g.source["repo"], Path(st["dirs"][0]).expanduser(), label=g.source.get("label"),
                           title=g.source.get("title_filter"), numbers=g.source.get("issues"))
        print(f"fetched {len(got)} issues into {st['dirs'][0]}")
    elif what == "arxiv":
        st = next(s for s in g.stores if s.get("format") == "latex")
        ids = sorted({p for c in g.chapters for p in c.papers} | set(g.source.get("papers", [])))
        print("fetched", fetch.arxiv(ids, Path(st["dir"]).expanduser()))
    return 0


def cmd_packs(a):
    from . import packs
    for p in packs.build_all(_g(a), a.chapters or None):
        print("wrote", p)
    return 0


def cmd_brief(a):
    from . import briefs
    g = _g(a)
    c = g.chapter(a.chapter)
    print(briefs.writing(g, c, g.work / "runs" / c.id / "draft" / f"{c.id}.md", g.work / "packs" / f"{c.id}.md"))
    return 0


def cmd_write(a):
    from . import pipeline
    g = _g(a)
    ids = [c.id for c in g.chapters] if a.all else a.chapters
    if not ids:
        print("name chapters or pass --all")
        return 2
    res = pipeline.run_many(g, ids, workers=a.j, review=not a.no_review, revise=a.revise)
    bad = [r["id"] for r in res if not str(r.get("status", "")).startswith(("published", "verified"))]
    print(pipeline.status(g))
    return 1 if bad else 0


def cmd_verify(a):
    from . import verify
    res = verify.run(_g(a), a.files or None)
    failed = sum(len(r.failures) for r in res)
    print(f"total: {sum(r.passed for r in res)} passed, {failed} failed, {sum(len(r.numbers) for r in res)} numbers to look at")
    return 1 if failed else 0


def cmd_status(a):
    from . import pipeline
    print(pipeline.status(_g(a)))
    return 0


def cmd_stale(a):
    from . import pipeline
    s = pipeline.stale(_g(a))
    if not s:
        print("no chapter has changed sources (chapters never published through guidekit are not tracked)")
    for cid, files in s.items():
        print(f"{cid}: {len(files)} changed source files, e.g. {files[:3]}")
    return 0


def cmd_build(a):
    g = _g(a)
    jb = next((p for p in [g.root / ".venv/bin/jupyter-book", shutil.which("jupyter-book")] if p and Path(p).exists()), None)
    if not jb:
        print("jupyter-book not found: pip install 'guidekit[book]' (or into the guide's .venv)")
        return 2
    r = subprocess.run([str(jb), "build", str(g.book)])
    if r.returncode or not a.pdf:
        return r.returncode
    r = subprocess.run([str(jb), "build", str(g.book), "--builder", "latex"])
    if r.returncode:
        return r.returncode
    tex = next((g.book / "_build/latex").glob("*.tex"))
    s = tex.read_text()
    import re
    tex.write_text(re.sub("[\U0001F300-\U0001FAFF☀-➿️]", "", s))   # emoji have no glyph in the PDF fonts
    return subprocess.run(["tectonic", "-X", "compile", tex.name], cwd=tex.parent).returncode


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="guidekit", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init")
    s.add_argument("dir"); s.add_argument("--id", required=True); s.add_argument("--title", required=True)
    s.add_argument("--kind", required=True, choices=["code", "records", "literature"]); s.add_argument("--audience", default="researchers")
    s.set_defaults(fn=cmd_init)
    s = sub.add_parser("fetch"); s.add_argument("guide"); s.add_argument("what", nargs="?", choices=["code", "issues", "arxiv"]); s.set_defaults(fn=cmd_fetch)
    s = sub.add_parser("packs"); s.add_argument("guide"); s.add_argument("chapters", nargs="*"); s.set_defaults(fn=cmd_packs)
    s = sub.add_parser("brief"); s.add_argument("guide"); s.add_argument("chapter"); s.set_defaults(fn=cmd_brief)
    s = sub.add_parser("write"); s.add_argument("guide"); s.add_argument("chapters", nargs="*")
    s.add_argument("--all", action="store_true"); s.add_argument("--no-review", action="store_true"); s.add_argument("--revise", action="store_true")
    s.add_argument("-j", type=int, default=4, help="chapters in parallel (default 4)")
    s.set_defaults(fn=cmd_write)
    s = sub.add_parser("verify"); s.add_argument("guide"); s.add_argument("files", nargs="*"); s.set_defaults(fn=cmd_verify)
    s = sub.add_parser("status"); s.add_argument("guide"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("stale"); s.add_argument("guide"); s.set_defaults(fn=cmd_stale)
    s = sub.add_parser("build"); s.add_argument("guide"); s.add_argument("--pdf", action="store_true"); s.set_defaults(fn=cmd_build)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
