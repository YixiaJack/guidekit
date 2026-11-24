"""Regression: the unified checker must agree with each guide's original verify.py, file by file.

    python3 -I tests/regress_verify.py        (needs the three guide repos and their sources on this machine)
Compares passed and failed counts per chapter. Number warnings may differ slightly (the unified checker pools cited
sources from every line and URL) and are reported, not compared.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from guidekit import config, verify  # noqa: E402

CASES = [("marin", "~/marin-kb", ["book/chapters/*.md", "book/catalog/*.md", "book/start.md", "book/paths.md"]),
         ("vllm", "~/vllm-kb", ["book/chapters/*.md"]), ("sglang", "~/sglang-kb", ["book/chapters/*.md"])]
bad = 0
for gid, root, globs in CASES:
    root = Path(root).expanduser()
    files = sorted(str(p) for g in globs for p in root.glob(g))
    old = subprocess.run([sys.executable, "-I", str(root / "scripts/verify.py"), *files], capture_output=True, text=True).stdout
    want = [(int(m.group(2)), int(m.group(3))) for m in re.finditer(r"== (\S+): (\d+) checks passed, (\d+) failed", old)]
    g = config.load(ROOT / "examples" / gid / "guide.toml")
    res = verify.run(g, files, quiet=True)
    got = [(r.passed, len(r.failures)) for r in res]
    diff = {files[i]: (w, x) for i, (w, x) in enumerate(zip(want, got)) if w != x} if len(want) == len(got) else {"count": (len(want), len(got))}
    nw = sum(len(r.numbers) for r in res)
    print(f"{gid}: {len(files)} files, old {sum(v[0] for v in want)}/{sum(v[1] for v in want)}, "
          f"new {sum(v[0] for v in got)}/{sum(v[1] for v in got)} (passed/failed), {nw} number warnings"
          + ("" if not diff else f"  MISMATCH {diff}"))
    for r in res:
        for f in r.failures:
            print("   FAIL", r.path.name, f)
    bad += bool(diff)
sys.exit(1 if bad else 0)
