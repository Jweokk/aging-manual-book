#!/usr/bin/env python3
"""把英文稿里「圆括号包标签」「两个标记挤进一个括号」的写法，统一成方括号标签形态。

    python3 tools/normalize_en_markers.py            # 只报告
    python3 tools/normalize_en_markers.py --write    # 落盘

规则（只动这些形态，别的一个字不碰）：
  (official wording: X)            -> ([official wording: X])
  ([official wording]: X)          -> ([official wording: X])
  (third-party research: X)        -> ([third-party research: X])
  ([official wording]: X; third-party research: Y)
                                   -> ([official wording: X]; [third-party research: Y])
括号里套一层括号（书名/年份）照样处理；更深的嵌套不碰。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EN = ROOT / "book-en"
LABELS = ("official wording", "third-party research")
# 一层嵌套的括号组
GROUP = re.compile(r"\((?![^(]*$)([^()]*(?:\([^()]*\)[^()]*)*)\)")
SPLIT = re.compile(r";\s*(third-party research)\s*[：:]\s*")


def fix_group(body: str) -> str | None:
    b = body.strip()
    m = re.match(r"\[?(official wording|third-party research)\]?\s*[：:]\s*(.+)$", b, re.S)
    if not m:
        return None
    label, rest = m.group(1), m.group(2).strip()
    parts = SPLIT.split(rest)
    if len(parts) == 3:
        head, tail = parts[0].rstrip().rstrip(";").strip(), parts[2].strip()
        return f"([{label}: {head}]; [third-party research: {tail}])"
    return f"([{label}: {rest}])"


def main(argv: list[str]) -> int:
    write = "--write" in argv
    total = 0
    for f in sorted(EN.glob("*.md")):
        t = f.read_text(encoding="utf-8")
        out, changes = [], 0
        pos = 0
        for m in GROUP.finditer(t):
            new = fix_group(m.group(1))
            if new is None:
                continue
            out.append(t[pos:m.start()])
            out.append(new)
            pos = m.end()
            changes += 1
            if total < 24:
                print(f"[{f.name[:28]}]\n   旧: {m.group(0)[:150]}\n   新: {new[:150]}")
        out.append(t[pos:])
        if changes:
            total += changes
            if write:
                f.write_text("".join(out), encoding="utf-8")
    print(f"\n共 {total} 处{'（已落盘）' if write else '（仅报告，加 --write 落盘）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
