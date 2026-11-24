"""`guidekit update`: is the guide behind its project's latest release, and which chapters does the new release touch?

    guidekit update GUIDE            check (GET the latest release; if newer, shallow-clone it next to the pinned checkout)
    guidekit update GUIDE --weekly   print a launchd plist that runs the check every Monday 09:00

For a code guide, every excerpt is a fenced code block followed by "— Code: [path#Lx-Ly](…)". The check looks for each
excerpt, verbatim (ignoring indentation), in the same file of the new release. Excerpts that are gone or changed are
listed per chapter in work/update-<tag>.md. Nothing in the book changes: to move the guide, set tag/commit in guide.toml,
`guidekit fetch`, then `guidekit write CH ... --revise` for the listed chapters (the reviewer sees the new code).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from . import fetch
from .config import Guide
from .verify import ELIDE

REF = re.compile(r"—\s*(?:Code|代码)[:：]\s*\[([^\]#]+)(?:#L(\d+))?")


def _norm(s: str) -> str:
    return "\n".join(l.strip() for l in s.strip().splitlines() if l.strip())


def still_there(code: str, new_text: str) -> bool:
    """Every piece of the excerpt (pieces are separated by "..." / "# ..." cut lines, as in verify.py) is in the new
    file, in order; line numbers may have moved, indentation is ignored."""
    pieces, cur = [], []
    for l in code.splitlines():
        if ELIDE.match(l):
            if cur:
                pieces.append(cur)
            cur = []
        elif l.strip():
            cur.append(l.strip())
    if cur:
        pieces.append(cur)
    hay = [l.strip() for l in new_text.splitlines() if l.strip()]
    pos = 0
    for piece in pieces:
        for i in range(pos, len(hay) - len(piece) + 1):
            if hay[i:i + len(piece)] == piece:
                pos = i + len(piece)
                break
        else:
            return False
    return True


def excerpts(text: str) -> list[tuple[str, str, int]]:
    """(file, code, line) for each code excerpt: a fenced block whose next non-blank line is "— Code: [path#L…]"
    (the same rule as verify.py; diagrams and other blocks without a Code line are skipped)."""
    lines, out, i = text.split("\n"), [], 0
    while i < len(lines):
        m = re.match(r"\s*(```+|~~~+)", lines[i])
        if not m:
            i += 1
            continue
        fence, body, i = m.group(1), [], i + 1
        while i < len(lines) and not lines[i].strip().startswith(fence):
            body.append(lines[i])
            i += 1
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        r = REF.search(lines[j]) if j < len(lines) else None
        if r:
            out.append((r.group(1).strip().strip("`"), "\n".join(body), int(r.group(2) or 0)))
        i += 1
    return out


def latest(repo: str) -> str:
    r = fetch._gh(f"repos/{repo}/releases/latest")       # --slurp wraps a single object in a list
    return (r[0] if isinstance(r, list) else r)["tag_name"]


def check(g: Guide) -> dict:
    repo, pinned = g.source["repo"], g.source.get("tag", "")
    tag = latest(repo)
    if tag == pinned:
        return {"pinned": pinned, "latest": tag, "current": True}
    store = next(s for s in g.stores if s.get("format") == "repo")
    old_root = Path(store["root"]).expanduser()
    new_root = old_root.with_name(old_root.name + "-next") / tag
    fetch.code(repo, tag, new_root)
    report, total = {}, 0
    for c in g.chapters:
        f = g.book / "chapters" / f"{c.id}.md"
        if not f.exists():
            continue
        gone = []
        for path, code, line in excerpts(f.read_text()):
            total += 1
            nf = new_root / path
            if not nf.exists():
                gone.append(f"{path}#L{line}: file removed or moved")
            elif not still_there(code, nf.read_text(errors="replace")):
                gone.append(f"{path}#L{line}: excerpt changed")
        if gone:
            report[c.id] = gone
    out = g.work / f"update-{tag}.md"
    lines = [f"# {g.title}: {pinned} → {tag}", "", f"{total} code excerpts checked; {sum(map(len, report.values()))} changed or gone "
             f"in {len(report)} chapters.", ""]
    for cid, items in report.items():
        lines += [f"## {cid} ({len(items)})", ""] + [f"- {x}" for x in items] + [""]
    lines += ["To move the guide: set tag/commit in guide.toml, `guidekit fetch GUIDE`, then "
              f"`guidekit write GUIDE {' '.join(report)} --revise`, `guidekit translate GUIDE`, `guidekit site`, `build`, `publish`."]
    out.write_text("\n".join(lines) + "\n")
    return {"pinned": pinned, "latest": tag, "current": False, "chapters": report, "excerpts": total, "report": str(out)}


def plist(guide_file: Path, label: str) -> str:
    exe = Path(sys.executable).parent / "guidekit"
    log = Path(guide_file).resolve().parent / "update.log"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array><string>{exe}</string><string>update</string><string>{Path(guide_file).resolve()}</string></array>
  <key>StartCalendarInterval</key><dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>{log}</string><key>StandardErrorPath</key><string>{log}</string>
</dict></plist>
"""
