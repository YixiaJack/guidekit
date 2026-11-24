"""Write, check, fix and review chapters with locked agents; promote verified chapters into the book.

One chapter goes through:  draft  ->  verify  ->  fix (up to N rounds)  ->  review  ->  verify  ->  fix  ->  published
Each step is a fresh, locked agent run (agents.py): it can read the sources, the pack and the book, and write only the
chapter's staging copy (and, for review, its review log). The harness runs the checker between steps and sends the
failures back. A chapter is copied into book/chapters/ only when the checker reports no failures; the previous version
is kept in work/runs/<id>/previous.md. State per chapter: work/state/<id>.json.
"""
from __future__ import annotations

import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import agents, briefs, packs, verify
from .config import Guide, sources_for


def _state_path(g: Guide, cid: str) -> Path:
    return g.work / "state" / f"{cid}.json"


def load_state(g: Guide, cid: str) -> dict:
    p = _state_path(g, cid)
    return json.loads(p.read_text()) if p.exists() else {"id": cid, "status": "planned", "history": []}


def save_state(g: Guide, st: dict):
    p = _state_path(g, st["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, indent=1, ensure_ascii=False))


def read_roots(g: Guide) -> list[Path]:
    roots = [g.book, g.work / "packs"]
    for s in g.stores:
        for k in ("root", "dir", "file"):
            if s.get(k):
                p = Path(s[k]).expanduser()
                roots.append(p if p.is_dir() else p.parent)
        roots += [Path(d).expanduser() for d in s.get("dirs", [])]
    seen, out = set(), []
    for r in roots:
        r = r.resolve()
        if r not in seen and r.exists():
            seen.add(r)
            out.append(r)
    return out


def _words(p: Path) -> int:
    import re
    t = p.read_text() if p.exists() else ""
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    return len(t.split())


def run_chapter(g: Guide, cid: str, review: bool = True, fix_rounds: int = 3, revise: bool = False, log=print) -> dict:
    ch = g.chapter(cid)
    st = load_state(g, cid)
    run = g.work / "runs" / cid
    draft_dir = run / "draft"
    out = draft_dir / f"{cid}.md"
    pack = g.work / "packs" / f"{cid}.md"
    if not pack.exists():
        packs.build_all(g, [cid])
    roots = read_roots(g)
    src = sources_for(g)
    ck = verify.Checker(src, g.book / "figures")

    def step(stage: str, prompt: str, writes: list[Path], model: str) -> dict:
        st["status"] = stage
        save_state(g, st)
        t0 = time.time()
        r = agents.run(stage, prompt, cwd=run, read_roots=roots, write_roots=writes, model=model)
        st["history"].append({"stage": stage, "ok": r.get("ok"), "s": r.get("elapsed_s"), "cost": r.get("cost_usd"),
                              "turns": r.get("turns"), "denials": r.get("denials"), "reply": (r.get("result") or "")[:1500],
                              "at": time.strftime("%Y-%m-%d %H:%M", time.localtime(t0))})
        save_state(g, st)
        log(f"[{cid}] {stage}: ok={r.get('ok')} {r.get('elapsed_s')}s turns={r.get('turns')}")
        return r

    def check_and_fix(tag: str) -> verify.Result:
        res = ck.check(out)
        for k in range(fix_rounds):
            if not res.failures:
                break
            log(f"[{cid}] {tag}: {len(res.failures)} failures, fix round {k + 1}")
            step(f"{tag}-fix{k + 1}", briefs.fix(out, res.failures, res.numbers), [draft_dir], g.model)
            res = ck.check(out)
        st.update(checks=res.passed, failures=len(res.failures), numbers=res.numbers, words=_words(out))
        save_state(g, st)
        return res

    existing = g.book / "chapters" / f"{cid}.md"
    if st.get("status") == "published" and existing.exists() and not revise:
        log(f"[{cid}] published; use --revise to check, fix and review it again")
        return st
    if not out.exists():
        if existing.exists() and not revise:
            log(f"[{cid}] already in the book; use --revise to check, fix and review it, or delete it to redraft")
            return st
        if existing.exists():
            draft_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(existing, out)        # revise the chapter in the book rather than start over
        else:
            step("draft", briefs.writing(g, ch, out, pack), [draft_dir], g.model)
    if not out.exists():
        st["status"] = "failed: no draft"
        save_state(g, st)
        return st
    res = check_and_fix("draft")
    if res.failures:
        st["status"] = "needs attention: checker failures after fixes"
        save_state(g, st)
        return st
    if review:
        logp = g.work / "reviews" / f"{cid}.md"
        step("review", briefs.review(g, ch, out, pack, logp, res.numbers), [draft_dir, logp.parent], g.review_model)
        res = check_and_fix("review")
        if res.failures:
            st["status"] = "needs attention: checker failures after review"
            save_state(g, st)
            return st
    dest = g.book / "chapters" / f"{cid}.md"
    if dest.exists():
        shutil.copy2(dest, run / "previous.md")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, dest)
    st["status"] = "published" if review else "verified (not reviewed)"
    st["published"] = time.strftime("%Y-%m-%d %H:%M")
    st["sources"] = source_stamp(g, cid)
    save_state(g, st)
    log(f"[{cid}] {st['status']}: {st['words']} words, {st['checks']} checks, {len(st['numbers'])} numbers to look at")
    return st


def run_many(g: Guide, ids: list[str], workers: int = 4, review: bool = True, revise: bool = False) -> list[dict]:
    def one(cid):
        try:
            return run_chapter(g, cid, review=review, revise=revise)
        except Exception as e:          # one chapter's failure must not stop the others (but say why)
            import sys, traceback
            print(f"[{cid}] run failed:\n" + traceback.format_exc(), file=sys.stderr, flush=True)
            return {"id": cid, "status": f"run failed: {e!r}"}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(one, ids))


# ---- staleness -------------------------------------------------------------------------------------------------------
def _pack_sources(g: Guide, cid: str) -> list[Path]:
    """Files a chapter was built from: everything its pack lists (code/doc paths, issue files)."""
    import re
    pack = g.work / "packs" / f"{cid}.md"
    if not pack.exists():
        return []
    text = pack.read_text()
    out = []
    repo = next((s for s in g.stores if s.get("format") == "repo"), None)
    if repo:
        root = Path(repo["root"]).expanduser()
        out += [root / m for m in re.findall(r"^- `([^`]+)` \(\d+\)", text, re.M)]
    for kind, n in re.findall(r"^- (\w[\w-]*) #(\d+) \(", text, re.M):
        for s in g.stores:
            if s["kind"] == kind:
                for d in s.get("dirs", []):
                    p = Path(d).expanduser() / f"{n}.json"
                    if p.exists():
                        out.append(p)
    return out


def source_stamp(g: Guide, cid: str) -> dict:
    import hashlib
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in _pack_sources(g, cid) if p.exists()}


def stale(g: Guide) -> dict[str, list[str]]:
    """Chapters whose source files changed (or appeared) since they were published, with the changed files."""
    out = {}
    for c in g.chapters:
        st = load_state(g, c.id)
        old = st.get("sources")
        if not old:
            continue
        packs.build_all(g, [c.id])
        new = source_stamp(g, c.id)
        changed = [p for p, h in new.items() if old.get(p) != h]
        if changed:
            out[c.id] = changed
    return out


def status(g: Guide) -> str:
    rows = ["| chapter | status | words | checks | failures | numbers to check | last step |", "|---|---|---|---|---|---|---|"]
    for c in g.chapters:
        st = load_state(g, c.id)
        book = g.book / "chapters" / f"{c.id}.md"
        if st["status"] == "planned" and book.exists():
            r = verify.Checker(sources_for(g), g.book / "figures").check(book)
            st.update(status="in book (not run through guidekit)", words=_words(book), checks=r.passed, failures=len(r.failures), numbers=r.numbers)
        last = st["history"][-1] if st.get("history") else {}
        rows.append(f"| {c.id} | {st['status']} | {st.get('words', '')} | {st.get('checks', '')} | {st.get('failures', '')} | "
                    f"{len(st.get('numbers') or [])} | {last.get('stage', '')} {last.get('at', '')} |")
    return "\n".join(rows)
