#!/usr/bin/env python3
"""英文版验收：逐单元与中文源对照，能机械查的都查掉。

    python3 tools/check_en.py            # 已译的单元全查
    python3 tools/check_en.py 03-ch1-*.md

查什么（都能自动判定，不需要人读）：
  1. `## ` 级小节数：英文 == 中文（结构 1:1）
  2. URL 集合：英文 == 中文（增删都算错）
  3. 七栏栏目数：英文的 What it costs / In short / ... 计数 == 中文的对应栏目计数
  4. 证据分档计数：英文 A/B/C 标记数 == 中文 【A】/【B】/【C】计数
  5. 记号残留：英文里不得再有 〔待核〕〔转引〕〔官方口径〕〔核对 …〕（应已转成 [unverified] 等）
  6. 禁止项：fly2ai / <sup> 计数必须为 0
  7. 中文字符：列出行内中文 >6 字的行（只应是书名、人名、机构名的原题），供人工过一眼

退出码非 0 表示有硬伤（1–6 任一项不过）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EN = ROOT / "book-en"
ZH = ROOT / "book"
MAP_DOC = EN / "README.md"

COLS_ZH = ["要花多少", "简单说", "可以怎么做", "来源", "特别提醒", "换回来的", "在中国怎么落地"]
COLS_EN = ["What it costs", "In short", "What you can do", "Where this comes from",
           "Who this is for", "What you get back", "How this works in China"]
LEFTOVER = ["〔待核〕", "〔转引〕", "〔官方口径〕", "〔核对"]

_row = re.compile(r"^\|\s*`([^`]+\.md)`\s*\|\s*`([^`]+\.md)`\s*\|")
_url = re.compile(r"https?://[^\s\)\]]+")
_trim = ".,;:，。；、)\"'"
_h2 = re.compile(r"^##\s+", re.M)
_han = re.compile(r"[\u4e00-\u9fff]")


def mapping() -> dict[str, str]:
    out = {}
    for line in MAP_DOC.read_text(encoding="utf-8").splitlines():
        m = _row.match(line)
        if m:
            out[m.group(2)] = m.group(1)   # en -> zh
    return out


def urls(t: str) -> set[str]:
    return {u.rstrip(_trim) for u in _url.findall(t)}


def grade_counts(t: str) -> dict[str, int]:
    """中文用【A】，英文用 A（档位标记）——两种写法都数。"""
    out = {}
    for g in "ABC":
        out[g] = len(re.findall(r"【" + g + r"】", t))
    # 英文：常见写法 **A** / (A) / 【A】 / A（在来源栏里）
    for g in "ABC":
        out[g] = max(out[g], len(re.findall(r"(?:\*\*|\(){0,2}" + g + r"(?:\*\*|\))", t)))
    return out


def main(argv: list[str]) -> int:
    mp = mapping()
    files = argv[1:] or sorted(p.name for p in EN.glob("*.md"))
    hard = 0
    print(f"{'unit':<46}{'§':>7}{'URL':>7}{'栏':>7}{'档A/B/C':>16}  fly2ai sup 残留 中文行")
    for name in files:
        if name == "index.md" or name not in mp:
            continue
        en_p, zh_p = EN / name, ZH / mp[name]
        if not en_p.exists() or not zh_p.exists():
            continue
        e, z = en_p.read_text(encoding="utf-8"), zh_p.read_text(encoding="utf-8")
        ne, nz = len(_h2.findall(e)), len(_h2.findall(z))
        ue, uz = urls(e), urls(z)
        ce = sum(len(re.findall(r"\*\*" + re.escape(c) + r"\*\*", e)) for c in COLS_EN)
        cz = sum(len(re.findall(r"\*\*" + re.escape(c) + r"\*\*", z)) for c in COLS_ZH)
        ge, gz = grade_counts(e), grade_counts(z)
        fly = e.count("fly2ai")
        sup = e.count("<sup>")
        left = sum(e.count(m) for m in LEFTOVER)
        hanlines = [ln for ln in e.splitlines() if len(_han.findall(ln)) > 6]
        bad = []
        if ne != nz: bad.append(f"§{ne}!={nz}")
        if ue != uz: bad.append(f"URL+{len(ue - uz)}-{len(uz - ue)}")
        if ce != cz: bad.append(f"栏{ce}!={cz}")
        if ge != gz: bad.append(f"档{ge}!={gz}")
        if fly: bad.append("fly2ai")
        if sup: bad.append("<sup>")
        if left: bad.append(f"残留{left}")
        if bad:
            hard += 1
        print(f"{name:<46}{ne:>3}/{nz:<3}{len(ue):>3}/{len(uz):<3}{ce:>3}/{cz:<3}"
              f"{str(ge):>16}  {fly:>5} {sup:>3} {left:>4} {len(hanlines):>6}"
              + ("   ✗ " + " ".join(bad) if bad else ""))
        for ln in hanlines[:3]:
            print(f"      中文行：{ln.strip()[:96]}")
    print()
    print("硬伤单元数：", hard)
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
