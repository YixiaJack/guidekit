"""Check every piece of evidence in a guide's chapters against the pinned sources.

    guidekit verify guide.toml [chapter.md ...]          (exit code 1 if anything fails)

Evidence formats (link markup around source names is fine):
  quote    > "verbatim text"            then within two lines   — Source: issue #123   (any store kind, or a repo path)
           "..." or "[…]" inside the quote marks a cut; every piece must appear in one cited source, in any order.
  table    a markdown table copied from a source, then        — Table source: <source>   (every cell must appear in it)
           tables the author compiled say "Compiled from" and are not checked cell by cell.
  figure   ![caption](../figures/<file>)  then within three lines   *Figure source: <source>*
           with a figure manifest, the file must be in it and come from that source; otherwise the file must exist.
  code     a fenced block copied from the repository, then on the next non-empty line   — Code: path/to/file.py#L10-L40
           the lines must match the pinned file (trailing spaces ignored); a line "..." or "# ..." / "// ..." marks a cut,
           and the pieces must appear in order inside the line range.
  numbers  numbers in the prose (decimals, or three or more digits) that appear in no source the chapter cites are listed
           for a human to look at (worked examples and our own arithmetic show up here and should be marked as such).

This one engine replaces the per-guide scripts of Marin KB, vLLM explained and SGLang explained; the stores configured
in guide.toml decide what "issue #123", "report x.md" or "vllm/foo.py" resolve to (see sources.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .sources import Sources, norm

ELIDE = re.compile(r"^\s*(\.\.\.|#\s*\.\.\.|//\s*\.\.\.|--\s*\.\.\.|/\*\s*\.\.\.\s*\*/)\s*$")
NUM = re.compile(r"(?<![\w.#/@-])[-−]?\d[\d,]*(?:\.\d+)?(?:e[-−]?\d+)?%?(?![\w/])")
QUOTE = re.compile(r'\s*>\s*"(.*)"\s*$')
FIGURE = re.compile(r"!\[[^\]]*\]\(\.\./figures/([^)\s]+)\)")
FENCE = re.compile(r"^\s*(```+|~~~+)(.*)$")


@dataclass
class Result:
    path: Path
    passed: int = 0
    failures: list[tuple[int, str, str]] = field(default_factory=list)
    numbers: list[str] = field(default_factory=list)

    def line(self) -> str:
        return f"== {self.path.name}: {self.passed} checks passed, {len(self.failures)} failed, {len(self.numbers)} numbers to look at"


def numbers(prose: str) -> list[str]:
    prose = re.sub(r"\]\([^)]*\)", "]", prose)                 # link targets
    prose = re.sub(r"`[^`]*`", " ", prose)                      # inline code
    prose = re.sub(r"\$[^$\n]+\$", " ", prose)                  # inline math is checked by eye
    prose = re.sub(r"#L?\d+|\b(?:issue|PR|pr)\s+#\d+", " ", prose)
    prose = re.sub(r"\b(19|20)\d\d(-\d\d){0,2}\b|\bv?\d+\.\d+\.\d+\b", " ", prose)   # years, dates, versions
    out = []
    for t in NUM.findall(prose):
        t = t.rstrip("%").replace(",", "").replace("−", "-").lstrip("-")
        if "." in t or len(t) >= 3:
            out.append(t)
    return out


class Checker:
    def __init__(self, src: Sources, figure_dir: Path | None = None):
        self.src = src
        self.figure_dir = figure_dir
        self.figs = src.manifest()

    def _texts(self, refs):
        return [self.src.text(k, v) for k, v in refs]

    def check_code(self, block: list[str], ref: str) -> str | None:
        if not self.src.repo:
            return "code excerpt in a guide without a repository store"
        m = re.search(r"((?:" + "|".join(re.escape(p) for p in self.src.repo.prefixes) + r")/[\w./\-]+)#L(\d+)(?:-L(\d+))?", ref)
        if not m:
            return "code reference not understood"
        path, a, b = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))
        lines = self.src.repo_lines(path)
        if lines is None:
            return f"no such file in the pinned source: {path}"
        window = lines[max(0, a - 1):b]
        pieces, cur = [], []
        for l in block:
            if ELIDE.match(l):
                if cur:
                    pieces.append(cur)
                cur = []
            else:
                cur.append(l.rstrip())
        if cur:
            pieces.append(cur)
        pos = 0
        for piece in pieces:
            for i in range(pos, len(window) - len(piece) + 1):
                if window[i:i + len(piece)] == piece:
                    pos = i + len(piece)
                    break
            else:
                return f"lines not found in order in {path}#L{a}-L{b}: {piece[0][:60]!r}"
        return None

    def check(self, path: Path) -> Result:
        res = Result(path)
        lines = path.read_text().split("\n")
        cited: set[tuple[str, str]] = set()
        copied_rows: set[int] = set()
        in_code, code, fence = False, [], ""
        for i, ln in enumerate(lines):
            if not in_code:
                cited.update(self.src.refs_in(ln))
                cited.update(self.src.url_refs(ln))
            fm = FENCE.match(ln)
            if fm and not in_code:
                in_code, code, fence = True, [], fm.group(1)
                continue
            if in_code:
                if ln.strip().startswith(fence):
                    in_code = False
                    j = i + 1
                    while j < len(lines) and not lines[j].strip():
                        j += 1
                    if j < len(lines) and "Code:" in lines[j]:
                        err = self.check_code(code, lines[j])
                        if err:
                            res.failures.append((j + 1, "code", err))
                        else:
                            res.passed += 1
                else:
                    code.append(ln)
                continue
            # quotes
            m = QUOTE.match(ln)
            if m:
                refs = []
                for j in range(i + 1, min(i + 3, len(lines))):
                    if "Source:" in lines[j]:
                        refs = self.src.refs_in(lines[j].split("Source:", 1)[1])
                        break
                q = norm(m.group(1)).replace("…", "...")
                parts = [p.strip() for p in re.split(r"\.\.\.|\[…\]|\[\.\.\.\]", q) if p.strip()]
                if not refs:
                    res.failures.append((i + 1, "quote without source", m.group(1)[:80]))
                elif any(t and all(p in t for p in parts) for t in self._texts(refs)):
                    res.passed += 1
                else:
                    res.failures.append((i + 1, f"quote not found in {refs}", m.group(1)[:90]))
            # tables copied from a source
            if "Table source:" in ln:
                refs = self.src.refs_in(ln.split("Table source:", 1)[1])
                texts = [t for t in self._texts(refs) if t]
                j = i - 1
                while j >= 0 and not lines[j].strip():
                    j -= 1
                bad = []
                while j >= 0 and lines[j].strip().startswith("|"):
                    copied_rows.add(j)
                    if not re.fullmatch(r"[\s|:\-]+", lines[j]):
                        for cell in [c.strip() for c in lines[j].strip().strip("|").split("|")]:
                            c = norm(cell)
                            if c and c not in ("—", "-") and not any(c in t for t in texts):
                                bad.append(cell[:40])
                    j -= 1
                if not texts:
                    res.failures.append((i + 1, "table source not found", ln[:80]))
                elif bad:
                    res.failures.append((i + 1, f"table cells not in {refs}", "; ".join(bad[:5])))
                else:
                    res.passed += 1
            # figures
            fg = FIGURE.search(ln)
            if fg:
                f = fg.group(1)
                src_line = next((lines[j] for j in range(i + 1, min(i + 4, len(lines))) if "Figure source:" in lines[j]), "")
                if self.figs is not None:
                    refs = self.src.refs_in(src_line.split("Figure source:", 1)[1]) if src_line else []
                    r = self.figs.get(f)
                    if not r:
                        res.failures.append((i + 1, "figure not in manifest", f))
                    elif not refs or f"{refs[0][0]} #{refs[0][1]}" != r["source"]:
                        res.failures.append((i + 1, f"figure source should be {r['source']}", f))
                    else:
                        res.passed += 1
                elif self.figure_dir is not None and not (self.figure_dir / f).exists():
                    res.failures.append((i + 1, "figure file missing", f))
                elif not src_line:
                    res.failures.append((i + 1, "figure without source line", f))
                else:
                    res.passed += 1
        body = "\n".join(l for k, l in enumerate(lines) if k not in copied_rows and not QUOTE.match(l)
                         and "Source:" not in l and "Code:" not in l)
        body = re.sub(r"```.*?```|~~~.*?~~~", " ", body, flags=re.S)
        pool = " ".join(t for t in self._texts(sorted(cited)) if t).replace(",", "")
        res.numbers = sorted({n for n in numbers(body) if n not in pool})
        return res


def run(guide, paths: list[str] | None = None, quiet: bool = False) -> list[Result]:
    from .config import sources_for
    src = sources_for(guide)
    ck = Checker(src, guide.book / "figures")
    if not paths:
        paths = sorted(str(p) for p in (guide.book / "chapters").glob("*.md"))
    out = []
    for p in paths:
        r = ck.check(Path(p))
        out.append(r)
        if not quiet:
            print(r.line())
            for e in r.failures:
                print("   FAIL", e)
            if r.numbers:
                print("   numbers not found in cited sources:", " ".join(r.numbers[:40]))
    return out
