"""guidekit: turn a large body of technical material into a verified reading guide.

    guidekit verify GUIDE [chapter.md ...]     check quotes, tables, figures and code excerpts against the pinned sources
"""
from __future__ import annotations

import argparse
import sys

from . import config


def cmd_verify(a) -> int:
    from . import verify
    g = config.load(a.guide)
    res = verify.run(g, a.files or None)
    failed = sum(len(r.failures) for r in res)
    print(f"total: {sum(r.passed for r in res)} passed, {failed} failed, {sum(len(r.numbers) for r in res)} numbers to look at")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="guidekit", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="check the evidence in the chapters")
    v.add_argument("guide", help="path to guide.toml")
    v.add_argument("files", nargs="*", help="chapter files (default: book/chapters/*.md)")
    v.set_defaults(fn=cmd_verify)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
