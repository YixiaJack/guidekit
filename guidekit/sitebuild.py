"""`guidekit site`: the knowledge-base website for a guide, in English and (when book_zh/ exists) Chinese.

Writes <root>/book/_extra/ (served at the site root by Jupyter Book's html_extra_path):
  kb.html, kb/kb.js, kb/kb-standalone.js, kb/*.css        the shared bilingual renderer (guidekit/site/)
  kb/data.json, kb/data_zh.json                            topics, documents and the guide's site texts
  kb/ch/*.md, kb/ch_zh/*.md                                the chapters, rendered by the page (the same files the book uses)

A code guide's chapters become topics grouped by the table of contents; chapters with track = "beginner" (or in a part
whose caption starts with "Start here") are listed as guides. Texts come from [site] in guide.toml:

  [site]
  short = "vLLM, explained"                     name = {en = "...", zh = "..."}
  project = {name = "vLLM", url = "https://github.com/vllm-project/vllm"}
  lead = {en = "...", zh = "..."}               footer = {en = "...", zh = "..."}
  process_tab = {en = "Design and pitfalls", zh = "设计和踩坑"}
  process = [["design decision", "Design decisions and why", "设计取舍"], ["^knobs", "Knobs", "可调参数"], ...]
  nav = [{doc = "intro-engine", en = "Start here", zh = "从这里开始"}]
  groups_zh = {"The engine core" = "引擎核心", ...}
  repo_readme = {en = "https://github.com/OWNER/REPO#run-it", zh = "..."}
  public_name = "vllm-kb"                        (the public site's Vercel project, see publish.py)
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .config import Guide

SITE = Path(__file__).resolve().parent / "site"
MATH_D = re.compile(r"\$\$(.+?)\$\$", re.S)


def toc_order(g: Guide) -> list[tuple[str, str]]:
    """(part caption, chapter id) in table-of-contents order."""
    out, cap = [], ""
    for line in (g.book / "_toc.yml").read_text().splitlines():
        m = re.match(r"\s*-\s*caption:\s*(.+)$", line)
        if m:
            cap = m.group(1).strip().strip('"')
            continue
        m = re.match(r"\s*-\s*file:\s*chapters/([\w-]+)", line)
        if m:
            out.append((cap, m.group(1)))
    return out


def title_of(text: str, fallback: str) -> str:
    return next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), fallback)


def summary_of(text: str) -> str:
    """The chapter's opening blockquote ("> Summary: …" / "> 摘要：…"), as plain text."""
    lines, on = [], False
    for l in text.splitlines()[1:40]:
        if l.startswith(">"):
            on = True
            lines.append(l.lstrip("> ").strip())
        elif on:
            break
    t = " ".join(lines)
    t = re.sub(r"^\**(Summary|摘要|概要|总结)\s*[:：.。]?\**\s*[:：.。]?\s*", "", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t).replace("**", "").replace("`", "")
    return t[:1].upper() + t[1:]


TEX = {r"\\le": "≤", r"\\ge": "≥", r"\\leq": "≤", r"\\geq": "≥", r"\\cdot": "·", r"\\times": "×", r"\\infty": "∞",
       r"\\varepsilon": "ε", r"\\epsilon": "ε", r"\\zeta": "ζ", r"\\rho": "ρ", r"\\sigma": "σ", r"\\gamma": "γ",
       r"\\chi": "χ", r"\\Lambda": "Λ", r"\\psi": "ψ", r"\\pi": "π", r"\\ne": "≠", r"\\neq": "≠", r"\\to": "→",
       r"\\approx": "≈", r"\\sum": "Σ", r"\\in": "∈"}


def plain_math(t: str) -> str:
    """Inline $...$ as plain text for card blurbs, which are not typeset: G(x)≤x^{1/2+ε} becomes G(x)≤x^(1/2+ε)."""
    def one(m):
        x = m.group(1)
        for k, v in TEX.items():
            x = re.sub(k + r"(?![A-Za-z])", v, x)
        x = re.sub(r"\\(?:mathrm|operatorname|text|mathbf|tfrac|frac)\s*", "", x)
        x = re.sub(r"\^\{([^{}]*)\}", r"^(\1)", x).replace("{", "").replace("}", "").replace("\\", "")
        return x
    return re.sub(r"\$([^$]+)\$", one, t)


def blurb(t: str, n: int = 220) -> str:
    t = plain_math(t)
    if len(t) <= n:
        return t
    cut = t[:n]
    if cut.count("$") % 2:                   # never stop inside an untypeset formula
        cut = cut[:cut.rfind("$")]
    return cut.rstrip() + "…"


def clean_group(cap: str) -> str:
    cap = re.sub(r"^Deep dive\s*[—–-]\s*", "", cap)
    return cap[:1].upper() + cap[1:]


def display_tex(t: str) -> str:
    t = t.strip()
    while True:
        u = re.sub(r"(\\[,;:!]|\\q?quad|\s)+$", "", t)
        u = re.sub(r"[,.;]$", "", u).rstrip()
        if u == t:
            break
        t = u
    parts = [x.strip() for x in re.split(r",\s*\\q?quad\s*", t) if x.strip()]
    return "\\begin{gathered}" + " \\\\[4pt] ".join(parts) + "\\end{gathered}" if len(parts) > 1 else t


def words(text: str) -> int:
    return len(re.sub(r"```.*?```", " ", text, flags=re.S).split())


def build(g: Guide, lang: str) -> dict | None:
    site = json.loads(json.dumps(g.site or {}))
    base = g.book if lang == "en" else g.root / "book_zh"
    order = toc_order(g)
    beginner = {c.id for c in g.chapters if getattr(c, "track", "") == "beginner"}
    topics, docs = [], []
    zhmap = site.get("groups_zh", {})
    rf = g.root / "site" / "related.json"           # curated links to other guides (Marin KB, vLLM, SGLang…)
    related = json.loads(rf.read_text()) if rf.exists() else {}
    for cap, cid in order:
        src = base / "chapters" / f"{cid}.md"
        if not src.exists():
            if lang == "zh":
                return None              # a chapter is not translated yet: no Chinese edition
            continue
        text = src.read_text()
        en_text = (g.book / "chapters" / f"{cid}.md").read_text()
        title = title_of(text, cid)
        is_guide = cid in beginner or cap.lower().startswith("start here")
        group = clean_group(cap)
        if lang == "zh":
            group = zhmap.get(group, group)
        doc = {"id": cid, "title": title, "file": f"kb/{'ch' if lang == 'en' else 'ch_zh'}/{cid}.md", "rel": f"chapters/{cid}.md",
               "book": f"chapters/{cid}.html", "words": words(en_text), "topic": None if is_guide else cid, "part": None,
               "kind": (("Start here" if lang == "en" else "从这里开始") if is_guide else None), "blurb": blurb(summary_of(text))}
        if lang == "zh":
            doc["file_en"] = f"kb/ch/{cid}.md"
        docs.append(doc)
        if is_guide:
            continue
        formulas = [{"tex": display_tex(m.group(1)), "what": ""} for m in MATH_D.finditer(en_text)][:3]
        topics.append({"id": cid, "name": title, "group": group, "count": 0, "verdicts": {}, "summary": summary_of(text),
                       "findings": [], "open": [], "key": [], "formulas": formulas, "figures": [],
                       "chapters": [{"id": cid, "title": title}], "date": "", "fresh": [], "chapter_date": "",
                       "related": [{"kb": r["kb"], "id": r["id"], "title": r["title"][lang], "why": r["why"][lang]} for r in related.get(cid, [])]})
    pin = f"{g.source.get('tag', '')}"
    n_g = sum(1 for d in docs if not d["topic"])
    site["stats"] = {"en": f"{len(topics)} chapters · {n_g} beginner chapters" + (f" · pinned to {g.source.get('repo', '')} {pin}" if pin else ""),
                     "zh": f"{len(topics)} 章深入篇 · {n_g} 章入门篇" + (f" · 对应 {g.source.get('repo', '')} {pin}" if pin else "")}
    return {"n": len(topics), "first": "", "last": "", "snapshot": pin, "npr": 0, "prs": 0, "headline": [], "topics": topics,
            "cards": [], "docs": docs, "site": site, "lang": lang}


def display_cites(text: str, lang: str, cmap: dict) -> str:
    """Citation keys such as `note draft.md` (what the checker reads) become readable linked names on the website
    ([site.cite]: {"note draft.md": {en, zh, url}}). A source line that already links the source drops the key."""
    if not cmap:
        return text
    keys = {k.split(" ", 1)[1]: v for k, v in cmap.items() if " " in k}
    names = "|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True))
    word = r"(?:note|笔记|注释)\s*"
    def link(m):
        v = keys[m.group(1)]
        return f"[{v.get(lang) or v['en']}]({v['url']})"
    out = []
    for line in text.split("\n"):
        if re.match(r"\s*—\s*(Source|Table source|来源|表格来源)\s*[:：]", line) and "](" in line:
            line = re.sub(r"\s*[（(]\s*`?" + word + r"(?:" + names + r")`?\s*[)）]", "", line)
        line = re.sub(r"`" + word + r"(" + names + r")`", link, line)
        line = re.sub(word + r"(" + names + r")", link, line)
        out.append(line)
    return "\n".join(out)


def ensure_extra_path(g: Guide):
    cfg = g.book / "_config.yml"
    s = cfg.read_text()
    if "html_extra_path" in s:
        return
    if "\nsphinx:\n" in s and "\n  config:\n" in s:
        s = s.replace("\n  config:\n", '\n  config:\n    html_extra_path: ["_extra"]        # the knowledge-base site (guidekit site)\n', 1)
    else:
        s += '\nsphinx:\n  config:\n    html_extra_path: ["_extra"]\n'
    cfg.write_text(s)


def run(g: Guide) -> str:
    out = g.book / "_extra"
    kb = out / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SITE / "kb.html", out / "kb.html")
    for f in (SITE / "kb").iterdir():
        shutil.copy2(f, kb / f.name)
    msgs = []
    for lang in ("en", "zh"):
        d = build(g, lang)
        if d is None:
            msgs.append("no Chinese edition yet (book_zh/ incomplete)")
            continue
        (kb / ("data.json" if lang == "en" else "data_zh.json")).write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")))
        chd = kb / ("ch" if lang == "en" else "ch_zh")
        if chd.exists():
            shutil.rmtree(chd)
        chd.mkdir()
        base = g.book if lang == "en" else g.root / "book_zh"
        cmap = (g.site or {}).get("cite", {})
        for doc in d["docs"]:
            (chd / f"{doc['id']}.md").write_text(display_cites((base / doc["rel"]).read_text(), lang, cmap))
        msgs.append(f"{lang}: {len(d['topics'])} topics, {len(d['docs'])} documents")
    ensure_extra_path(g)
    return "; ".join(msgs)
