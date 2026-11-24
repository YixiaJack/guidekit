"""Chapter packs: for each chapter, the list of sources the writer should start from (work/packs/<chapter>.md).

Built from the [[chapter]] entries of guide.toml:
  paths    globs relative to the repository root (code kind): listed with line counts
  docs     globs relative to the repository root: listed with line counts
  issues   a regular expression over issue titles in the thread stores: matching issues listed with date, state, size
  include  issue numbers to list whatever their title (records kind: the experiments assigned to the chapter)
  papers   paper ids (literature kind): their source folders and main .tex files
Figure candidates (when a figure manifest exists): every manifest image whose source is a listed issue.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .config import Guide, _rel


CODE_SUFFIXES = {".py", ".md", ".mdx", ".rst", ".cu", ".cuh", ".cpp", ".cc", ".c", ".h", ".hpp", ".rs", ".go", ".ts", ".js", ".toml", ".yaml", ".yml", ".lean", ".txt", ".bib"}


def _lines(p: Path) -> int:
    try:
        return p.read_text(errors="replace").count("\n") + 1
    except OSError:
        return 0


def _threads(g: Guide):
    seen = set()
    for s in g.stores:
        if s.get("format") == "thread":
            for d in s.get("dirs", []):
                for p in sorted(Path(d).expanduser().glob("*.json")):
                    if p not in seen:          # several stores may share one folder (GitHub numbers issues and PRs alike)
                        seen.add(p)
                        yield s["kind"], p


def build(g: Guide, chapter) -> str:
    out = [f"# Chapter pack: {chapter.id} — {chapter.title}", ""]
    repo = next((s for s in g.stores if s.get("format") == "repo"), None)
    root = Path(repo["root"]).expanduser() if repo else None
    if chapter.scope:
        out += ["## Scope", "", chapter.scope.strip(), ""]
    for label, globs in (("Code", chapter.paths), ("Docs", chapter.docs)):
        if globs and root:
            files = set()
            for gl in globs:
                base = root / gl
                if base.is_dir():          # a folder: every source or doc file under it
                    files |= {p for p in base.rglob("*") if p.is_file() and p.suffix in CODE_SUFFIXES}
                else:
                    files |= {p for p in root.glob(gl) if p.is_file()}
            files = sorted(p for p in files if "QUARANTINED__" not in str(p))
            out += [f"## {label} (path, lines)", ""] + [f"- `{p.relative_to(root)}` ({_lines(p)})" for p in files[:400]] + [""]
    listed = []
    rx = re.compile(chapter.issues, re.I) if chapter.issues else None
    want = set(chapter.include)
    if rx or want:
        rows = []
        for kind, p in _threads(g):
            try:
                d = json.loads(p.read_text())
            except ValueError:
                continue
            iss = d.get("issue") or d
            n = iss.get("number") or (int(p.stem) if p.stem.isdigit() else None)
            title = iss.get("title") or ""
            if (rx and rx.search(title)) or n in want:
                rows.append((iss.get("created_at", "")[:10], n, iss.get("state", ""), len(d.get("comments") or []), title, kind))
                listed.append(n)
        rows.sort()
        out += [f"## Issues ({len(rows)})", ""] + [f"- {k} #{n} ({d}, {st}, {c} comments): {t}" for d, n, st, c, t, k in rows] + [""]
    for pid in chapter.papers:
        for s in g.stores:
            if s.get("format") == "latex":
                base = Path(s["dir"]).expanduser() / pid
                tex = sorted(base.rglob("*.tex")) if base.is_dir() else []
                out += [f"## Paper {pid}", ""] + ([f"- `{t}` ({_lines(t)} lines)" for t in tex[:30]] or ["- (source not downloaded)"]) + [""]
    man = _rel(g, g.figures.get("manifest"))
    if man and Path(man).exists() and listed:
        srcs = {f"issue #{n}" for n in listed} | {f"pr #{n}" for n in listed}
        figs = [json.loads(l) for l in Path(man).read_text().splitlines()]
        figs = [f for f in figs if f.get("ok") and f.get("source") in srcs]
        if figs:
            out += [f"## Figure candidates ({len(figs)})", ""] + [
                f"- `{f['file']}` from {f['source']} ({f.get('date', '')}, @{f.get('author', '')}): {(f.get('before') or '')[-120:]!r}"
                for f in figs] + [""]
    return "\n".join(out)


def build_all(g: Guide, only: list[str] | None = None) -> list[Path]:
    d = g.work / "packs"
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for c in g.chapters:
        if only and c.id not in only:
            continue
        p = d / f"{c.id}.md"
        p.write_text(build(g, c))
        out.append(p)
    return out
