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
    quotes = len(re.findall(r'^\s*>\s*["“]', body, re.M))   # Chinese quote marks are fine
    tables = len(re.findall(r"(?:Table source:|表格来源：)", body))
    figs = re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", body)
    math = MATH.findall(body)
    links = set(re.findall(r"\]\(([^)\s]+)\)", body))
    return code, heads, quotes, tables, figs, math, links, body, mermaid


def drop_list_markers(t: str) -> str:
    """Remove "3. " at the start of a list item: after a blank line, another item, or an indented continuation line.
    A prose line that merely wraps before "256. The …" keeps its number."""
    out, prev = [], ""
    for line in t.split("\n"):
        m = re.match(r"(\s*)\d+\.\s", line)
        if m and (not prev.strip() or re.match(r"\s*\d+\.\s", prev) or prev[:1].isspace()):
            line = m.group(1) + " " + line[m.end():]
        out.append(line)
        prev = line if not m else "1. "
    return "\n".join(out)


def numbers(body: str) -> Counter:
    t = MATH.sub(" ", body)
    t = re.sub(r"\]\([^)]*\)", "]", t)                    # link targets
    t = re.sub(r"@[A-Za-z0-9_-]+", " ", t)                 # GitHub handles (checked separately)
    t = drop_list_markers(t)                               # ordered-list markers (not a wrapped line that starts "256. ")
    t = re.sub(r"(?<![\d.])\d{1,2}\s*月", " ", t)            # Chinese month number ("2026 年 4 月" for "April 2026"); days stay
    t = scale_words(t)
    return Counter(n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", t))


SCALE = {"thousand": 10**3, "million": 10**6, "billion": 10**9, "trillion": 10**12,
         "万亿": 10**12, "千亿": 10**11, "百亿": 10**10, "十亿": 10**9, "千万": 10**7, "百万": 10**6, "亿": 10**8, "万": 10**4, "千": 10**3,
         "k": 10**3, "K": 10**3, "M": 10**6, "B": 10**9, "T": 10**12}


def scale_words(t: str) -> str:
    """"17 million", "17-million", "1700 万", "17 百万" and "17M" are the same number: write each as 17000000 before
    counting, on both sides. Letter suffixes count only when attached (40B, 1.3B, 18T, 40k)."""
    def one(m):
        v = float(m.group(1).replace(",", "")) * SCALE[m.group(2) or m.group(3)]
        return str(int(round(v))) if abs(v - round(v)) < 1e-6 else str(v)
    t = re.sub(r"(\d[\d,]*(?:\.\d+)?)(?:[\s-]*(thousand|million|billion|trillion|万亿|千亿|百亿|十亿|千万|百万|亿|万|千)|([kKMBT])(?![A-Za-z0-9]))", one, t)
    return t


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
