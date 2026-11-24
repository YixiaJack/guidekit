"""Project configuration: one `guide.toml` per guide.

[guide]
id        short name, used for run folders            ("sglang")
title     book title
kind      "code" | "records" | "literature"
audience  "beginners" | "researchers"
root      project folder holding book/ and work/       ("~/sglang-kb")
words     [min, max] target words per deep chapter     ([5000, 7000])
max_code  most code excerpts per chapter (code kind)   (30)
model     model for writing agents                      ("opus")
review_model  model for review agents                   ("sonnet")

[figures]          manifest (jsonl: file, source, author, date, link; optional), dir (default book/figures)
[[store]]          where cited sources live; see sources.py
[source]           — depends on kind
  code:        repo, tag, commit, dir (pinned checkout), path_prefixes, issue_dirs (RFCs etc.), url_base
  records:     repo, label, issue_dirs (raw, extra), pr_dir (prbody), docs ({name = dir}), blogs ({name = file}),
               figure_dir, figure_manifest, url_base
  literature:  papers (arXiv ids), dir (one folder per paper with its LaTeX source)

[[chapter]]        id, title, paths (code), docs, issues (regex over titles), scope (free text for the brief)
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def _p(s: str | None) -> Path | None:
    return Path(s).expanduser() if s else None


@dataclass
class Chapter:
    id: str
    title: str
    scope: str = ""
    paths: list[str] = field(default_factory=list)
    docs: list[str] = field(default_factory=list)
    issues: str = ""
    include: list[int] = field(default_factory=list)
    papers: list[str] = field(default_factory=list)
    words: list[int] | None = None
    track: str = "deep"


@dataclass
class Guide:
    id: str
    title: str
    kind: str
    audience: str
    root: Path
    words: list[int]
    max_code: int
    model: str
    review_model: str
    source: dict
    chapters: list[Chapter]
    file: Path
    stores: list[dict] = field(default_factory=list)
    figures: dict = field(default_factory=dict)
    site: dict = field(default_factory=dict)

    @property
    def book(self) -> Path:
        return self.root / "book"

    @property
    def work(self) -> Path:
        return self.root / "work"

    def chapter(self, cid: str) -> Chapter:
        for c in self.chapters:
            if c.id == cid:
                return c
        raise KeyError(f"no chapter {cid!r} in {self.file}")

    def src_path(self, key: str) -> Path | None:
        return _p(self.source.get(key))

    def src_paths(self, key: str) -> list[Path]:
        return [_p(x) for x in self.source.get(key, []) if x]

    def src_map(self, key: str) -> dict[str, Path]:
        return {k: _p(v) for k, v in (self.source.get(key) or {}).items()}


def load(path: str | Path) -> Guide:
    path = Path(path).expanduser().resolve()
    d = tomllib.loads(path.read_text())
    g = d["guide"]
    if g["kind"] not in ("code", "records", "literature"):
        raise ValueError("guide.kind must be code, records or literature")
    chapters = [Chapter(**{k: v for k, v in c.items() if k in Chapter.__dataclass_fields__}) for c in d.get("chapter", [])]
    return Guide(id=g["id"], title=g["title"], kind=g["kind"], audience=g.get("audience", "researchers"),
                 root=_p(g["root"]), words=g.get("words", [5000, 7000]), max_code=g.get("max_code", 30),
                 model=g.get("model", "opus"), review_model=g.get("review_model", "sonnet"),
                 source=d.get("source", {}), chapters=chapters, file=path,
                 stores=d.get("store", []), figures=d.get("figures", {}), site=d.get("site", {}))


def _rel(guide: Guide, p: str | None) -> str | None:
    if not p:
        return None
    q = Path(p).expanduser()
    return str(q if q.is_absolute() else guide.root / q)


def sources_for(guide: Guide):
    from .sources import Sources
    return Sources(guide.stores, figure_manifest=_rel(guide, guide.figures.get("manifest")),
                   figure_dir=_rel(guide, guide.figures.get("dir", "book/figures")))
