"""Negative test: tampered evidence must fail. Copies one chapter per guide, changes one quote word, one code line and
one table cell, and expects exactly those to fail.    python3 -I tests/negative_verify.py"""
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from guidekit import config, verify  # noqa: E402


def tamper(text: str, kind: str) -> str:
    lines = text.split("\n")
    if kind == "quote":
        for i, l in enumerate(lines):
            m = re.match(r'(\s*>\s*")(.*)("\s*)$', l)
            if m and len(m.group(2).split()) > 4:
                w = m.group(2).split()
                w[2] = "zzqx" + w[2]
                lines[i] = m.group(1) + " ".join(w) + m.group(3)
                return "\n".join(lines)
    if kind == "code":
        for i, l in enumerate(lines):
            if "Code:" in l:
                j = i - 1
                while j > 0 and not lines[j].strip().startswith("```"):
                    j -= 1
                k = j - 1
                while k > 0 and not lines[k].strip().startswith("```"):
                    k -= 1
                for t in range(k + 1, j):
                    if lines[t].strip() and not re.match(r"^\s*(#|//)?\s*\.\.\.\s*$", lines[t]):
                        lines[t] = lines[t] + "  # zzqx"
                        return "\n".join(lines)
    if kind == "table":
        for i, l in enumerate(lines):
            if "Table source:" in l:
                j = i - 1
                while j > 0 and not lines[j].strip():
                    j -= 1
                lines[j] = lines[j].replace("|", "| zzqx", 1) if lines[j].count("|") > 1 else lines[j]
                return "\n".join(lines)
    return None


ok = True
for gid, chap in [("marin", "opt.md"), ("vllm", "scheduler.md"), ("sglang", "scheduler.md")]:
    g = config.load(ROOT / "examples" / gid / "guide.toml")
    src = (g.book / "chapters" / chap).read_text()
    for kind in ("quote", "code", "table"):
        t = tamper(src, kind)
        if t is None:
            print(f"{gid} {kind}: nothing to tamper in {chap} (skipped)")
            continue
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / chap
            p.write_text(t)
            r = verify.run(g, [str(p)], quiet=True)[0]
        base = verify.run(g, [str(g.book / "chapters" / chap)], quiet=True)[0]
        good = len(r.failures) == len(base.failures) + 1
        ok &= good
        print(f"{gid} {kind}: {'caught' if good else 'MISSED'} ({len(r.failures)} failures: {r.failures[:1]})")
sys.exit(0 if ok else 1)
