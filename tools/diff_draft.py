#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交稿比对：草稿层 drafts/ vs 现稿层 book/。

用法:
  python3 tools/diff_draft.py            # 全部有改动的单元，逐条 diff + 风险提示
  python3 tools/diff_draft.py <file.md>  # 只比一个单元

输出三部分：
  ① 概览：哪些单元改了、汉字增减、改了哪些栏目
  ② 逐单元 unified diff（上下文 1 行，便于贴给用户看）
  ③ 风险提示：动过「数字 / 文号 / 来源(链接) / 待核标记 / 分档角标」的行，逐条列出
     —— 这些是必须回源核实的，不是措辞问题。
"""
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK, DRAFTS = ROOT / "book", ROOT / "drafts"
CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")
FIELDS = ["要花多少", "简单说", "可以怎么做", "来源", "特别提醒", "换回来的", "在中国怎么落地", "怎么算", "怎么认出来"]
RISK = [("数字", re.compile(r"\d")), ("文号", re.compile(r"〔\d{4}〕|第\d+号|国发|国办发|民发|医保发|发改价格|国卫")),
        ("链接", re.compile(r"https?://")), ("待核", re.compile(r"待核")),
        ("分档", re.compile(r"【[ABC]】")), ("电话", re.compile(r"\b(120|12345|12356|12393|96110|95188)\b"))]


def fields_of(line: str) -> str:
    for f in FIELDS:
        if re.match(rf"^\s*-\s*\*{{0,2}}{re.escape(f)}\*{{0,2}}：", line):
            return f
    return ""


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    files = sorted(p.name for p in DRAFTS.glob("*.md"))
    if only:
        files = [only]
    if not files:
        print("草稿层是空的（还没人在编辑台改过东西）。")
        return
    rows, diffs, risks = [], [], []
    for f in files:
        dp, bp = DRAFTS / f, BOOK / f
        if not dp.exists():
            continue
        new = dp.read_text(encoding="utf-8").splitlines()
        old = bp.read_text(encoding="utf-8").splitlines() if bp.exists() else []
        if new == old:
            continue
        a, b = len(CJK.findall("\n".join(old))), len(CJK.findall("\n".join(new)))
        touched = sorted({fields_of(l) for l in difflib.unified_diff(old, new, n=0, lineterm="")
                          if l.startswith(("+", "-")) and fields_of(l)} - {""})
        rows.append((f, len(old), len(new), b - a, "、".join(touched) or "—"))
        diffs.append(f"\n{'='*70}\n【{f}】\n{'-'*70}\n" + "\n".join(
            difflib.unified_diff(old, new, fromfile="现稿", tofile="你的稿", n=1, lineterm="")))
        for l in difflib.unified_diff(old, new, n=0, lineterm=""):
            if not l.startswith(("+", "-")) or l.startswith(("+++", "---")):
                continue
            hits = [name for name, rx in RISK if rx.search(l)]
            # 纯新增链接/角标也算风险；只报告带风险特征的行
            if hits:
                risks.append(f"[{f}] {'/'.join(hits)} :: {l.strip()[:150]}")
    if not rows:
        print("草稿和现稿一致，没有改动。")
        return
    print("① 概览（共 %d 个单元有改动）\n" % len(rows))
    print(f"{'单元':44s} {'行数':>12s} {'汉字增减':>9s}  改到的栏目")
    for f, lo, ln, dc, tf in rows:
        print(f"{f[:42]:44s} {lo:>5d}→{ln:<5d} {dc:>+9d}  {tf}")
    print("\n② 逐单元 diff" + "".join(diffs))
    print("\n③ 风险提示（这些行必须回源核实，不是措辞问题）")
    if risks:
        for r in risks[:60]:
            print("  " + r)
        if len(risks) > 60:
            print(f"  …另有 {len(risks)-60} 行")
    else:
        print("  无（改动不含数字/文号/链接/待核/分档）")


if __name__ == "__main__":
    main()
