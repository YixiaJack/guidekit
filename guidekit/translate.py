"""`guidekit translate`: the Chinese edition (book_zh/), one locked agent per chapter, checked block by block.

    guidekit translate GUIDE [CH ...] [-j 4]       translate (missing or failing chapters), check, send failures back
    guidekit translate GUIDE --check [CH ...]      only run the checker

Each run gets templates/translate.md, may read the English book and write only book_zh/chapters/. After it, checkzh.py
compares the Chinese file with the English one (headings, quotes, tables, figures, code blocks, Mermaid count, math, links,
numbers, GitHub handles, untranslated runs); failures go back for up to three fix rounds. A chapter is done when the
checker reports nothing.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import agents, checkzh
from .agents import TEMPLATES
from .config import Guide

FIX = """The Chinese chapter `{out}` (translated from `{src}`) failed the block-by-block check. Fix every problem below by
editing the Chinese file only (open the English file to compare), then stop.

{problems}

Reply in at most 40 words: what you changed."""


def _brief(g: Guide, src: Path, out: Path) -> str:
    t = (TEMPLATES / "translate.md").read_text().replace("{{title}}", g.title).replace("{{root}}", str(g.root))
    return t + f"\n\n## Your file\n\nTranslate `{src}` into `{out}` (the whole chapter).\n"


def check(g: Guide, cid: str) -> list[str]:
    zh = g.root / "book_zh" / "chapters" / f"{cid}.md"
    if not zh.exists():
        return ["not translated yet"]
    return checkzh.check(g.root, zh)


def translate_one(g: Guide, cid: str, rounds: int = 3, log=print) -> dict:
    src = g.book / "chapters" / f"{cid}.md"
    outd = g.root / "book_zh" / "chapters"
    out = outd / f"{cid}.md"
    run = g.work / "runs" / f"zh-{cid}"
    roots = [g.book, outd]
    t0 = time.time()
    if not out.exists():
        r = agents.run("translate", _brief(g, src, out), cwd=run, read_roots=roots, write_roots=[outd], model=g.model, timeout_min=90)
        log(f"[{cid}] translate: ok={r.get('ok')} {r.get('elapsed_s')}s")
    probs = check(g, cid)
    for k in range(rounds):
        if not probs or probs == ["not translated yet"] and not out.exists():
            break
        r = agents.run(f"translate-fix{k + 1}", FIX.format(out=out, src=src, problems="\n".join("- " + p for p in probs)),
                       cwd=run, read_roots=roots, write_roots=[outd], model=g.model, timeout_min=40)
        probs = check(g, cid)
        log(f"[{cid}] fix {k + 1}: {len(probs)} problems left")
    return {"id": cid, "ok": not probs, "problems": probs, "minutes": round((time.time() - t0) / 60, 1)}


def run_many(g: Guide, ids: list[str], workers: int = 4) -> list[dict]:
    def one(cid):
        try:
            return translate_one(g, cid)
        except Exception as e:          # one chapter's failure must not stop the others
            return {"id": cid, "ok": False, "problems": [f"run failed: {e!r}"], "minutes": 0}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(one, ids))
