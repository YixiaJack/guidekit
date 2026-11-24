"""Fetch and pin sources. Everything downloaded is untrusted data: it is never executed, imported or installed, and
files that coding agents load automatically are renamed so no agent session picks them up.

  code    git clone --depth 1 of a tag; the commit is checked against guide.toml and written to <dir>.lock.json
  issues  GitHub issues (and their comments) matching a label or a title pattern, via `gh api` (GET only), one JSON per issue
  arxiv   the LaTeX source of each paper (arxiv.org/e-print/<id>), unpacked into its own folder
"""
from __future__ import annotations

import gzip
import io
import json
import re
import shutil
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path

AGENT_FILES = re.compile(r"^(CLAUDE\.md|AGENTS\.md|GEMINI\.md|\.mcp\.json|\.cursorrules|\.cursor.*|\.windsurfrules|\.clinerules|\.claude|\.github/copilot-instructions\.md)$", re.I)


def quarantine(root: Path) -> list[str]:
    """Rename files and folders that coding agents load automatically (CLAUDE.md, .claude/, .mcp.json, .cursor*, …)."""
    moved = []
    for p in sorted(root.rglob("*"), key=lambda x: -len(x.parts)):
        if AGENT_FILES.match(p.name) and not p.name.startswith("QUARANTINED__"):
            q = p.with_name("QUARANTINED__" + p.name)
            p.rename(q)
            moved.append(str(q.relative_to(root)))
    return moved


def code(repo: str, tag: str, dest: Path, commit: str | None = None) -> dict:
    """Shallow clone of one tag. Refuses to reuse a folder whose lock names a different commit."""
    lock = dest.with_name(dest.name + ".lock.json")
    if dest.exists() and lock.exists():
        old = json.loads(lock.read_text())
        if commit and old.get("commit") != commit:
            raise SystemExit(f"{dest} is pinned to {old.get('commit')}, guide.toml says {commit}")
        return old
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "clone", "--depth", "1", "--branch", tag, "--no-recurse-submodules",
                    f"https://github.com/{repo}.git", str(dest)], check=True)
    head = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    if commit and head != commit:
        raise SystemExit(f"tag {tag} is at {head}, guide.toml says {commit}; refusing to continue")
    moved = quarantine(dest)
    info = {"repo": repo, "tag": tag, "commit": head, "fetched": time.strftime("%Y-%m-%d"), "quarantined": moved}
    lock.write_text(json.dumps(info, indent=1))
    return info


def _gh(path: str) -> list | dict:
    r = subprocess.run(["gh", "api", "--method", "GET", "-H", "Accept: application/vnd.github+json", "--paginate", "--slurp", path],
                       capture_output=True, text=True, check=True)
    data = json.loads(r.stdout)
    if isinstance(data, list) and data and isinstance(data[0], list):
        return [x for page in data for x in page]
    return data


def issues(repo: str, dest: Path, label: str | None = None, title: str | None = None, since: str | None = None,
           numbers: list[int] | None = None) -> list[int]:
    """Download issues (and PRs, which GitHub numbers alike) with their comments. GET requests only."""
    dest.mkdir(parents=True, exist_ok=True)
    found = list(numbers or [])
    if label or title:
        q = f"issues?state=all&per_page=100" + (f"&labels={label}" if label else "") + (f"&since={since}" if since else "")
        rx = re.compile(title, re.I) if title else None
        for it in _gh(f"repos/{repo}/{q}"):
            if rx is None or rx.search(it.get("title") or ""):
                found.append(it["number"])
    got = []
    for n in sorted(set(found)):
        iss = _gh(f"repos/{repo}/issues/{n}")
        if isinstance(iss, list):
            iss = iss[0]
        com = _gh(f"repos/{repo}/issues/{n}/comments?per_page=100")
        rec = {"issue": iss, "comments": com, "kind": "pr" if iss.get("pull_request") else "issue",
               "fetched": time.strftime("%Y-%m-%d %H:%M")}
        (dest / f"{n}.json").write_text(json.dumps(rec, ensure_ascii=False))
        got.append(n)
    return got


ARXIV = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")


def arxiv(ids: list[str], dest: Path, delay_s: float = 3.0) -> list[str]:
    """LaTeX source of each paper into dest/<id>/. Archive members are extracted only as plain files inside the folder."""
    got = []
    for pid in ids:
        if not ARXIV.match(pid):
            raise SystemExit(f"not an arXiv id: {pid}")
        out = dest / pid
        if out.exists():
            continue
        req = urllib.request.Request(f"https://arxiv.org/e-print/{pid}", headers={"User-Agent": "guidekit/0.1 (reading-guide builder)"})
        data = urllib.request.urlopen(req, timeout=60).read()
        out.mkdir(parents=True)
        try:
            with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                for m in tf.getmembers():
                    target = (out / m.name).resolve()
                    if not m.isfile() or not str(target).startswith(str(out.resolve()) + "/"):
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(tf.extractfile(m).read())
        except tarfile.ReadError:
            try:
                (out / "main.tex").write_bytes(gzip.decompress(data))
            except OSError:
                shutil.rmtree(out)
                raise SystemExit(f"{pid}: no LaTeX source available")
        quarantine(out)
        got.append(pid)
        time.sleep(delay_s)
    return got
