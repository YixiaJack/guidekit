"""Where a guide's evidence lives, and how a citation in a chapter maps to source text.

Configured in guide.toml as a list of stores:

  [[store]]                      # a thread store: one JSON per issue/PR, {"issue": {title, body}, "comments": [{body}]}
  kind = "issue"                 # cited as "issue #123"
  dirs = ["~/research-kb/data/marin/raw", "~/research-kb/data/marin/extra"]
  format = "thread"

  [[store]]                      # PR descriptions, {"title", "body"}; falls back to thread dirs of the same kind
  kind = "pr"
  dirs = ["~/research-kb/data/marin/prbody"]
  format = "titlebody"
  fallback = "issue"             # "pr #12" is also looked up in the issue store's dirs (GitHub numbers are shared)

  [[store]]                      # a folder of named files: "report foo.md" -> dir/foo.md
  kind = "report"
  dir = "~/.../docs/reports"
  format = "file"

  [[store]]                      # a single file cited by a bare word: "blog"
  kind = "blog"
  file = "~/.../blog_architecture.md"
  format = "single"

  [[store]]                      # repository paths: "vllm/v1/core/sched/scheduler.py", also code excerpts "#L10-L20"
  kind = "path"
  root = "~/code-kb/src/vllm-v0.34.0"
  prefixes = ["vllm", "docs", "csrc", "benchmarks", "examples", "tests", "tools", "requirements"]
  format = "repo"

  [[store]]                      # papers: "paper 2604.21691" -> every .tex/.bib/.md file under dir/2604.21691/
  kind = "paper"
  dir = "~/research-kb/data/sources"
  format = "latex"
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


def norm(s: str) -> str:
    """Normalisation shared by every comparison: quotes, markup, tags and whitespace do not count."""
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("‑", "-")
    s = re.sub(r"[*`\\_]", "", s)
    s = re.sub(r"<[^>]{0,80}>", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def _x(p: str | None) -> Path | None:
    return Path(p).expanduser() if p else None


@dataclass
class Store:
    kind: str
    format: str
    dirs: list[Path] = field(default_factory=list)
    dir: Path | None = None
    file: Path | None = None
    root: Path | None = None
    prefixes: list[str] = field(default_factory=list)
    fallback: str | None = None


class Sources:
    def __init__(self, stores: list[dict], figure_manifest: str | None = None, figure_dir: str | None = None):
        self.stores: dict[str, Store] = {}
        for d in stores:
            s = Store(kind=d["kind"].lower(), format=d.get("format", "file"),
                      dirs=[_x(x) for x in d.get("dirs", [])], dir=_x(d.get("dir")), file=_x(d.get("file")),
                      root=_x(d.get("root")), prefixes=d.get("prefixes", []), fallback=d.get("fallback"))
            self.stores[s.kind] = s
        self.repo = next((s for s in self.stores.values() if s.format == "repo"), None)
        self.figure_manifest = _x(figure_manifest)
        self.figure_dir = _x(figure_dir)
        self._cache: dict[tuple[str, str], str | None] = {}
        named = [re.escape(k) for k, s in self.stores.items() if s.format not in ("single", "repo")]
        single = [re.escape(k) for k, s in self.stores.items() if s.format == "single"]
        parts = []
        if named:
            parts.append(r"\b(?P<kind>" + "|".join(named) + r")\s+#?(?P<id>[\w.\-]+)")
        if single:
            parts.append(r"\b(?P<single>" + "|".join(single) + r")\b")
        if self.repo and self.repo.prefixes:
            parts.append(r"(?<![\w/])(?P<path>(?:" + "|".join(re.escape(p) for p in self.repo.prefixes) + r")/[\w./\-]+)")
        self._ref = re.compile("|".join(parts), re.I) if parts else None

    # ---- citations ---------------------------------------------------------------------------------------------
    def refs_in(self, line: str) -> list[tuple[str, str]]:
        """Every source cited on a line, as (kind, id). Line anchors (#L10-L20) and trailing punctuation are dropped."""
        out = []
        if not self._ref:
            return out
        for m in self._ref.finditer(line):
            g = m.groupdict()
            if g.get("kind"):
                out.append((g["kind"].lower(), g["id"].rstrip(".")))
            elif g.get("single"):
                out.append((g["single"].lower(), ""))
            elif g.get("path"):
                out.append(("path", re.sub(r"#L\d+(-L\d+)?$", "", g["path"]).rstrip(".,;)")))
        return out

    def url_refs(self, line: str) -> list[tuple[str, str]]:
        """Issue and PR numbers cited as GitHub links."""
        out = []
        if "issue" in self.stores:
            out += [("issue", n) for n in re.findall(r"/issues/(\d+)", line)]
        if "pr" in self.stores:
            out += [("pr", n) for n in re.findall(r"/pull/(\d+)", line)]
        return out

    # ---- text ----------------------------------------------------------------------------------------------------
    @staticmethod
    def _thread(p: Path) -> str:
        d = json.loads(p.read_text())
        iss = d.get("issue") or d
        return "\n".join([iss.get("title") or "", iss.get("body") or ""] + [c.get("body") or "" for c in d.get("comments") or []])

    def raw(self, kind: str, ident: str) -> str | None:
        s = self.stores.get(kind)
        if not s:
            return None
        if s.format == "thread":
            for d in s.dirs:
                if (d / f"{ident}.json").exists():
                    return self._thread(d / f"{ident}.json")
        elif s.format == "titlebody":
            for d in s.dirs:
                p = d / f"{ident}.json"
                if p.exists():
                    j = json.loads(p.read_text())
                    return (j.get("title") or "") + "\n" + (j.get("body") or "")
            if s.fallback:
                return self.raw(s.fallback, ident)
        elif s.format == "file":
            p = (s.dir / ident).resolve() if s.dir else None
            if p and p.is_file() and str(p).startswith(str(s.dir.resolve())):
                return p.read_text(errors="replace")
        elif s.format == "single":
            return s.file.read_text(errors="replace") if s.file and s.file.exists() else None
        elif s.format == "repo":
            p = (s.root / ident).resolve()
            if p.is_file() and str(p).startswith(str(s.root.resolve())):
                return p.read_text(errors="replace")
        elif s.format == "latex":
            base = (s.dir / ident).resolve() if s.dir else None
            if base and base.is_dir() and str(base).startswith(str(s.dir.resolve())):
                files = sorted(p for p in base.rglob("*") if p.suffix in (".tex", ".bib", ".md", ".txt") and p.is_file())
                return "\n".join(p.read_text(errors="replace") for p in files) or None
        return None

    def text(self, kind: str, ident: str) -> str | None:
        key = (kind, ident)
        if key not in self._cache:
            t = self.raw(kind, ident)
            self._cache[key] = norm(t) if t is not None else None
        return self._cache[key]

    def repo_lines(self, path: str) -> list[str] | None:
        if not self.repo:
            return None
        p = (self.repo.root / path).resolve()
        if not (p.is_file() and str(p).startswith(str(self.repo.root.resolve()))):
            return None
        return [l.rstrip() for l in p.read_text(errors="replace").split("\n")]

    # ---- figures -------------------------------------------------------------------------------------------------
    def manifest(self) -> dict[str, dict] | None:
        if not self.figure_manifest or not self.figure_manifest.exists():
            return None
        out = {}
        for ln in self.figure_manifest.read_text().splitlines():
            r = json.loads(ln)
            if r.get("ok"):
                out[r["file"]] = r
        return out
