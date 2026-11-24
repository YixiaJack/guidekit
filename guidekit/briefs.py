"""Fill the writing, review and fix templates from guide.toml."""
from __future__ import annotations

import re
from pathlib import Path

from .agents import TEMPLATES
from .config import Guide, _rel

STORE_TEXT = {
    "thread": "one JSON file per {kind} with its full discussion (`issue.title`, `issue.body`, `comments[].body`, "
              "`comments[].user.login`, `comments[].html_url`, dates)",
    "titlebody": "one JSON file per {kind} with its title and description",
    "file": "named files",
    "single": "a single document",
    "repo": "the repository at the pinned release",
    "latex": "one folder per paper with its LaTeX source (and code where available)",
}
CITE = {"thread": "`{kind} #N`", "titlebody": "`{kind} #N`", "file": "`{kind} <file name>`", "single": "`{kind}`",
        "repo": "a repository path such as `{prefix}/…`", "latex": "`{kind} <arXiv id>`"}


def render(text: str, flags: set[str], values: dict[str, str]) -> str:
    def cond(m):
        return m.group(2) if m.group(1) in flags else ""
    text = re.sub(r"\[\[if (\w+)\]\](.*?)\[\[end\]\]", cond, text, flags=re.S)
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{(\w+)\}\}", text)
    if left:
        raise KeyError(f"template values missing: {sorted(set(left))}")
    return text


def _material(g: Guide) -> str:
    out, seen = [], {}
    for s in g.stores:
        kind, fmt = s["kind"], s.get("format", "file")
        where = s.get("root") or s.get("dir") or s.get("file") or ", ".join(s.get("dirs", []))
        if where in seen:              # e.g. issues and PRs in one folder
            out[seen[where]] = out[seen[where]].rstrip(".") + f"; cite pull requests in it as `{kind} #N`."
            continue
        seen[where] = len(out)
        line = f"- `{kind}`: {STORE_TEXT.get(fmt, fmt).format(kind=kind)}, in `{where}`"
        if fmt == "repo":
            line += f" ({g.source.get('repo', '')} {g.source.get('tag', '')}, commit `{g.source.get('commit', '')}`). " \
                    "Files that coding agents load automatically were renamed `QUARANTINED__*`; ignore them"
        if s.get("note"):
            line += f". {s['note']}"
        out.append(line + ".")
    for note in g.source.get("notes", []):
        out.append(f"- {note}")
    if g.figures.get("manifest"):
        out.append(f"- Figures already downloaded, with `manifest.jsonl` (file, source, author, date, alt text, surrounding "
                   f"text): `{_rel(g, g.figures.get('dir', 'book/figures'))}`. Look at an image with Read before you use it.")
    return "\n".join(out)


def values(g: Guide, chapter, out: Path, pack: Path) -> tuple[set[str], dict[str, str]]:
    flags = {g.kind, "figures" if g.figures.get("manifest") else "nofigures"}
    repo = next((s for s in g.stores if s.get("format") == "repo"), None)
    ex = g.source.get("examples", {})
    cites = ", ".join(CITE.get(s.get("format", "file"), "`{kind}`").format(kind=s["kind"], prefix=(s.get("prefixes") or ["src"])[0])
                      for s in g.stores)
    words = chapter.words or g.words
    v = {
        "title": g.title, "intro": g.source.get("intro", "").strip(), "readers": g.source.get("readers", "").strip(),
        "material": _material(g), "pack": str(pack), "out": str(out), "chapters_dir": str(g.book / "chapters"),
        "pack_what": "files and line counts, design documents and matching issues" if g.kind == "code" else
                     "sources, candidate figures and orientation notes",
        "pin": f"{g.source.get('tag', '')}, commit {g.source.get('commit', '')}" if repo else "",
        "code_word": ", code excerpt" if repo else "", "words_min": words[0], "words_max": words[1],
        "code_limit": f"; at most {g.max_code} code excerpts, each 5–40 lines" if repo else "",
        "chapter_links": ", ".join(f"{c.id}.md ({c.title})" for c in g.chapters),
        "quote_example": ex.get("quote", "verbatim text from the source"),
        "source_example": ex.get("source", "[issue #123](https://github.com/OWNER/REPO/issues/123)"),
        "code_example": ex.get("code", "path/to/file.py#L10-L40"),
        "code_url_example": ex.get("code_url", f"https://github.com/{g.source.get('repo', 'OWNER/REPO')}/blob/{g.source.get('commit', 'COMMIT')}/path/to/file.py#L10-L40"),
        "figure_manifest": str(_rel(g, g.figures.get("manifest")) or ""),
        "cite_forms": cites, "rules": ("\n" + g.source["rules"].strip() + "\n") if g.source.get("rules") else "",
    }
    return flags, v


def writing(g: Guide, chapter, out: Path, pack: Path) -> str:
    flags, v = values(g, chapter, out, pack)
    brief = render((TEMPLATES / "brief.md").read_text(), flags, v)
    task = f"\n\n## Your chapter\n\nChapter `{chapter.id}`: **{chapter.title}**.\n\n{chapter.scope.strip()}\n" if chapter.scope else \
           f"\n\n## Your chapter\n\nChapter `{chapter.id}`: **{chapter.title}**.\n"
    return brief + task


def review(g: Guide, chapter, out: Path, pack: Path, log: Path, numbers: list[str]) -> str:
    flags, v = values(g, chapter, out, pack)
    v.update(review_log=str(log), numbers=", ".join(numbers) if numbers else "none", brief=writing(g, chapter, out, pack))
    return render((TEMPLATES / "review.md").read_text(), flags, v)


def fix(out: Path, failures: list, numbers: list[str]) -> str:
    fl = "\n".join(f"- line {ln}: {kind}: {msg}" for ln, kind, msg in failures) or "- (none)"
    return render((TEMPLATES / "fix.md").read_text(), set(), {"out": str(out), "failures": fl,
                                                              "numbers": ", ".join(numbers) if numbers else "none"})
