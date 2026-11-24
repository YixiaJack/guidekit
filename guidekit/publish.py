"""`guidekit publish`: put a built guide (book/_build/html, with the knowledge-base site from `guidekit site`) online.

    guidekit publish GUIDE public                       a static public site on Vercel (project = [site] public_name)
    guidekit publish GUIDE private --web DIR --path P   a path P/ inside an existing site (e.g. research-kb-web, behind its login)

Public: the build is copied to ~/.cache/guidekit-sites/<name> (outside any git checkout: a folder inside one makes Vercel
connect the project to the GitHub repository and build every push from the repository root), kb.html becomes the home
page, and vercel.json gets a Content-Security-Policy that allows only this build's own inline scripts (sha256 hashes),
cdnjs (MathJax, KaTeX, marked, DOMPurify, Mermaid) and nothing else.
Private: the build is copied to DIR/public/P and DIR/vercel.json gets a CSP rule for /P/ alone; the site-wide rule is
narrowed to exclude every guide path. Deploying DIR is left to the caller (or pass --deploy).
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from .config import Guide

CACHE = Path.home() / ".cache" / "guidekit-sites"
HEADERS = [{"key": "X-Content-Type-Options", "value": "nosniff"}, {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"},
           {"key": "X-Frame-Options", "value": "DENY"}, {"key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()"}]


def _sha(s: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode() + "'"


def csp_for(html_dir: Path, connect: list[str] | None = None) -> str:
    hashes, handlers = set(), set()
    for f in html_dir.rglob("*.html"):
        t = f.read_text(encoding="utf-8", errors="replace")
        hashes |= {_sha(s) for s in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", t, re.S)}
        handlers |= {_sha(s) for s in re.findall(r' on[a-z]+="([^"]*)"', t)}
    return ("default-src 'none'; script-src 'self' https://cdnjs.cloudflare.com " + " ".join(sorted(hashes))
            + (" 'unsafe-hashes' " + " ".join(sorted(handlers)) if handlers else "") + "; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; font-src 'self' https://cdnjs.cloudflare.com data:; "
            "img-src 'self' data:; connect-src 'self' https://cdnjs.cloudflare.com" + "".join(" " + c for c in (connect or [])) +
            "; frame-ancestors 'none'; form-action 'none'; base-uri 'self'")


def _html(g: Guide) -> Path:
    html = g.book / "_build" / "html"
    if not (html / "kb.html").exists():
        raise SystemExit("build first: guidekit site GUIDE && guidekit build GUIDE")
    return html


def public(g: Guide, deploy: bool = True) -> str:
    name = (g.site or {}).get("public_name") or f"{g.id}-kb"
    dest = CACHE / name
    keep = dest / ".vercel"
    saved = CACHE / f".{name}-vercel"
    if keep.exists():
        if saved.exists():
            shutil.rmtree(saved)
        shutil.move(str(keep), str(saved))
    if dest.exists():
        shutil.rmtree(dest)
    html = _html(g)
    shutil.copytree(html, dest, ignore=shutil.ignore_patterns(".buildinfo", "_sources", ".doctrees"))
    if saved.exists():
        shutil.move(str(saved), str(keep))
    shutil.copy2(html / "kb.html", dest / "index.html")
    connect = [c for c in (g.site or {}).get("connect", []) if re.match(r"^https://[a-z0-9.-]+$", c)]   # e.g. a live page reading api.github.com
    vj = {"trailingSlash": False, "headers": [{"source": "/(.*)", "headers": [{"key": "Content-Security-Policy", "value": csp_for(dest, connect)}] + HEADERS}]}
    (dest / "vercel.json").write_text(json.dumps(vj, indent=2))
    if not deploy:
        return f"public site staged in {dest}"
    r = subprocess.run(["npx", "vercel", "deploy", "--prod", "--yes"], cwd=dest, capture_output=True, text=True, timeout=900)
    if r.returncode:
        return "deploy failed: " + (r.stderr or r.stdout)[-400:]
    if not keep.exists():
        return "deployed, but the project link is missing"
    subprocess.run(["npx", "vercel", "git", "disconnect", "--yes"], cwd=dest, capture_output=True, text=True, timeout=120)
    return f"deployed: https://{name}.vercel.app (if the name was free; see `vercel project ls`)"


def private(g: Guide, web: Path, path: str, deploy: bool = False) -> str:
    html = _html(g)
    path = path.strip("/")
    dest = web / "public" / path
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(html, dest, ignore=shutil.ignore_patterns(".buildinfo", "_sources", ".doctrees"))
    vjf = web / "vercel.json"
    vj = json.loads(vjf.read_text())
    rules = [r for r in vj.get("headers", []) if r.get("source") != f"/{path}/(.*)"]
    guide_paths = sorted({re.match(r"/([^/]+)/\(\.\*\)$", r["source"]).group(1) for r in rules if re.match(r"/([^/]+)/\(\.\*\)$", r["source"])} | {path})
    base = next((r for r in rules if r["source"] == "/(.*)" or r["source"].startswith("/((?!")), None)
    if base is None:
        raise SystemExit(f"{vjf} has no site-wide header rule to narrow")
    base["source"] = "/((?!" + "|".join(p + "/" for p in guide_paths) + ").*)"
    hdrs = [dict(h) for h in base["headers"]]
    for h in hdrs:
        if h["key"] == "Content-Security-Policy":
            h["value"] = csp_for(dest)
    rules.append({"source": f"/{path}/(.*)", "headers": hdrs})
    vj["headers"] = rules
    vjf.write_text(json.dumps(vj, ensure_ascii=False, indent=2) + "\n")
    msg = f"copied to {dest}; CSP rule for /{path}/"
    if deploy:
        r = subprocess.run(["npx", "vercel", "deploy", "--prod", "--yes"], cwd=web, capture_output=True, text=True, timeout=900)
        msg += ", deployed" if r.returncode == 0 else ", deploy failed"
    return msg
