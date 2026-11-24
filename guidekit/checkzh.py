"""Check a Chinese chapter against its English master (<root>/book_zh/<path> vs <root>/book/<path>).

    guidekit translate GUIDE --check [chapter ...]        (or: python3 -m guidekit.checkzh ROOT FILE ...)

The website pairs the two files block by block, so the structure must match exactly:
  * the same headings at the same levels, in the same order;
  * the same number of quotes, copied tables, figures (same files, same order) and fenced code blocks (identical text,
    except Mermaid diagrams, whose labels may be translated: only their number must match);
  * every math span identical; every link target present in both;
  * every number in the English appears in the Chinese and vice versa (as multisets, ignoring list markers);
  * no long runs of English prose left untranslated (identifiers, code, math and links are not counted).
"""
import re
import sys
from collections import Counter
from pathlib import Path

CODE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
MATH = re.compile(r"\$\$.+?\$\$|(?<![\\$])\$[^$\n]+?\$(?!\$)", re.S)


def blocks(s: str):
    code = [c for c in CODE.findall(s) if not re.match(r"(```|~~~)\s*mermaid", c)]
    mermaid = len(re.findall(r"^\s*(```|~~~)\s*mermaid", s, re.M))
    body = CODE.sub(" ", s)
    heads = [(len(m.group(1)), m.group(0)) for m in re.finditer(r"^(#{1,6})\s+.*$", body, re.M)]
    quotes = len(re.findall(r'^\s*>\s*"', body, re.M))
    tables = len(re.findall(r"(?:Table source:|表格来源：)", body))
    figs = re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", body)
    math = MATH.findall(body)
    links = set(re.findall(r"\]\(([^)\s]+)\)", body))
    return code, heads, quotes, tables, figs, math, links, body, mermaid


def numbers(body: str) -> Counter:
    t = MATH.sub(" ", body)
    t = re.sub(r"\]\([^)]*\)", "]", t)                    # link targets
    t = re.sub(r"@[A-Za-z0-9_-]+", " ", t)                 # GitHub handles (checked separately)
    t = re.sub(r"^\s*\d+\.\s", " ", t, flags=re.M)         # ordered-list markers
    t = re.sub(r"(?<![\d.])\d{1,2}\s*月", " ", t)            # Chinese month number ("2026 年 4 月" for "April 2026"); days stay
    return Counter(n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", t))


def english_runs(body: str) -> list[str]:
    t = MATH.sub(" ", body)
    t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"\]\([^)]*\)", "]", t)
    t = re.sub(r"https?://\S+", " ", t)
    return [m.group(0) for m in re.finditer(r"(?:\b[A-Za-z][a-z]+\b[ ,;:'’-]+){7,}[A-Za-z]+", t)]


def check(root: Path, zh_path: Path) -> list[str]:
    rel = zh_path.resolve().relative_to((root / "book_zh").resolve())
    en = (root / "book" / rel).read_text()
    zh = zh_path.read_text()
    ec, eh, eq, et, ef, em, el, eb, emm = blocks(en)
    zc, zhh, zq, zt, zf, zm, zl, zb, zmm = blocks(zh)
    out = []
    if emm != zmm:
        out.append(f"Mermaid diagrams: {emm} in English, {zmm} in Chinese")
    if [l for l, _ in eh] != [l for l, _ in zhh]:
        out.append(f"headings differ: {len(eh)} in English, {len(zhh)} in Chinese (levels must match in order)")
        for i, (a, b) in enumerate(zip(eh, zhh)):
            if a[0] != b[0]:
                out.append(f"  first mismatch at heading {i + 1}: EN {a[1][:70]!r} / ZH {b[1][:70]!r}")
                break
    if ec != zc:
        out.append(f"code blocks differ ({len(ec)} vs {len(zc)}, or their text changed)")
    if eq != zq:
        out.append(f"quotes: {eq} in English, {zq} in Chinese")
    if et != zt:
        out.append(f"copied tables: {et} in English, {zt} in Chinese")
    if ef != zf:
        out.append(f"figures differ: {ef} vs {zf}")
    if Counter(em) != Counter(zm):
        miss = list((Counter(em) - Counter(zm)).elements())[:3]
        extra = list((Counter(zm) - Counter(em)).elements())[:3]
        out.append(f"math spans differ: missing {miss}, extra {extra}")
    if el - zl:
        out.append(f"link targets missing in Chinese: {sorted(el - zl)[:5]}")
    en_n, zh_n = numbers(eb), numbers(zb)
    if en_n - zh_n:
        out.append(f"numbers missing in Chinese: {sorted((en_n - zh_n).elements())[:12]}")
    if zh_n - en_n:
        out.append(f"numbers added in Chinese: {sorted((zh_n - en_n).elements())[:12]}")
    eh_ = Counter(re.findall(r"@[A-Za-z0-9_-]+", MATH.sub(" ", eb)))
    zh_ = Counter(re.findall(r"@[A-Za-z0-9_-]+", MATH.sub(" ", zb)))
    if eh_ != zh_:
        out.append(f"GitHub handles differ (who did what must not change): missing {sorted((eh_ - zh_).elements())[:6]}, added {sorted((zh_ - eh_).elements())[:6]}")
    runs = english_runs(zb)
    if runs:
        out.append(f"{len(runs)} untranslated English passages, e.g. {runs[0][:90]!r}")
    return out


def main(root, paths):
    bad = 0
    for p in paths:
        errs = check(Path(root), Path(p))
        print(f"== {p}: {'ok' if not errs else str(len(errs)) + ' problems'}")
        for e in errs:
            print("   ", e)
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
