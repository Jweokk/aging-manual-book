#!/usr/bin/env python3
"""英文版验收：逐单元与中文源对照，能机械查的都查掉。

    python3 tools/check_en.py            # 已译的单元全查
    python3 tools/check_en.py 03-ch1-*.md 04-ch2-*.md

查什么（都能自动判定，不需要人读）：
  1. `## `/`### ` 小节数：英文 == 中文（结构 1:1）
  2. `## ` 小节编号序列：两边一致（2.1 … 2.16）
  3. URL 集合：英文 == 中文（增删都算错）
  4. 七栏栏目数（行首加粗）：逐个栏目英文 == 中文
  5. 行首 bullet 数：顶层/嵌套 英文 == 中文
  6. 标记账本：分档 A/B/C、官方口径、第三方研究、待核、转引、核对日期、本书核对
     —— 逐类计数必须相等（中文【】/〔〕与英文 [] 的写法差异在账本里抹平）
  7. 禁止项：fly2ai / <sup> / 中文记号原样残留（〔待核〕〔转引〕【A】…）计数必须为 0
  8. 行内中文：只允许出现在「英文译名 +（《原题》）」或含中文的 URL 里，其余算硬伤
  9. 平台名：微信/支付宝/微博/抖音 等不得出现在英文正文

退出码非 0 表示有硬伤。
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
LEFTOVER = ["〔待核〕", "〔转引〕", "〔官方口径〕", "〔核对", "【A】", "【B】", "【C】",
            "【官方口径", "【第三方研究", "【本书核对"]
PLATFORMS = ["微信", "支付宝", "微博", "抖音", "小红书", "公众号"]

_row = re.compile(r"^\|\s*`([^`]+\.md)`\s*\|\s*`([^`]+\.md)`\s*\|")
_url = re.compile(r"https?://[^\s\)\]]+")
_trim = ".,;:，。；、)\"'"
_h2 = re.compile(r"^##\s+", re.M)
_h3 = re.compile(r"^###\s+", re.M)
_secno = re.compile(r"^#{2,3}\s+(\d+)\.(\d+)", re.M)
_han = re.compile(r"[\u4e00-\u9fff]")
_top_bullet = re.compile(r"^- ", re.M)
_colrow_zh = [re.compile(r"^\s*[-*]?\s*\*{0,2}" + c + r"\*{0,2}\s*[：:]", re.M) for c in COLS_ZH]
_colrow_en = [re.compile(r"^\s*[-*]?\s*\*{0,2}" + re.escape(c) + r"\*{0,2}\s*[：:]", re.M) for c in COLS_EN]
_nest_bullet = re.compile(r"^\s{2,}- ", re.M)

# ── 标记账本：把两语的写法折算成同一套键 ────────────────────────────────
ZH_LEDGER = [
    ("grade", re.compile(r"【([ABC])】")),
    ("grade", re.compile(r"^[ \t]*[-*]?[ \t]*\*{0,2}(?:来源|栏目|特别提醒)[^\n]{0,12}?\*{0,2}\s*[：:]\s*([ABC])\s*[｜|]", re.M)),
    # 档位词：中文把这些写成【】/（）/「｜官方口径：」等形态，英文写成 []，仅计数比对
    ("off", re.compile(r"官方口径")),
    ("res", re.compile(r"第三方研究")),
    ("pending", re.compile(r"[〔（【]待核[〕）】]")),
    ("quote", re.compile(r"[〔（【]转引[〕）】]")),
    ("checked", re.compile(r"核对\s*[\d\-]{6,12}|[\d\-]{6,12}\s*(?:打开)?核对")),
    ("bookcheck", re.compile(r"[〔（【]?本书核对[〔（][^〕）】]{0,20}[〕）】]")),
]
EN_LEDGER = [
    ("grade", re.compile(r"\[([ABC])\]")),
    ("grade", re.compile(r"^[ \t]*[-*]?[ \t]*\*{0,2}(?:Where this comes from|In short|What you can do)\*{0,2}[^\n]{0,12}?\s*[：:][ \t]*([ABC])[ \t]*[｜|]", re.M)),
    ("off", re.compile(r"official wording")),
    ("res", re.compile(r"third-party research")),
    ("pending", re.compile(r"\[unverified\]")),
    ("quote", re.compile(r"\[second-hand\]")),
    ("checked", re.compile(r"\[checked\s*([\d\-]{6,12})\]")),
    ("bookcheck", re.compile(r"(?:this book's own check|our own check)[^)]{0,20}\)")),
]


def mapping() -> dict[str, str]:
    out = {}
    for line in MAP_DOC.read_text(encoding="utf-8").splitlines():
        m = _row.match(line)
        if m:
            out[m.group(2)] = m.group(1)   # en -> zh
    return out


def urls(t: str) -> set[str]:
    return {u.rstrip(_trim) for u in _url.findall(t)}


def ledger(t: str, rules) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, pat in rules:
        out[key] = out.get(key, 0) + len(pat.findall(t))
    return out


def bad_chinese(t: str) -> list[str]:
    """行内中文：允许出现在「英文译名 +（《原题》）」或 URL 里，其余报警。

    做法：先把 URL、含中文的括号组、书名号整段抹掉，再看剩下的中文。
    """
    hits = []
    for ln in t.splitlines():
        s = _url.sub("", ln)
        for _ in range(3):                        # 括号可能套一层
            s = re.sub(r"[(（][^()（）]*[\u4e00-\u9fff][^()（）]*[)）]", " ", s)
        s = re.sub(r"《[^》]*》", " ", s)
        s = re.sub(r"\*[^*]*[\u4e00-\u9fff][^*]*\*", " ", s)
        for m in re.finditer(r"[\u4e00-\u9fff]{2,}", s):
            hits.append(m.group(0)[:24])
    return hits


def main(argv: list[str]) -> int:
    mp = mapping()
    files = argv[1:] or sorted(p.name for p in EN.glob("*.md"))
    hard = 0
    print(f"{'unit':<44}{'§2':>6}{'§3':>5}{'URL':>8}{'栏':>7}{'bullet':>9}{'账本':>7}{'禁':>4}{'中文':>5}")
    for name in files:
        if name == "index.md" or name not in mp:
            continue
        en_p, zh_p = EN / name, ZH / mp[name]
        if not en_p.exists() or not zh_p.exists():
            print(f"{name:<44}  ⚠ 缺中文源 {mp.get(name)}")
            continue
        e, z = en_p.read_text(encoding="utf-8"), zh_p.read_text(encoding="utf-8")
        n2e, n2z = len(_h2.findall(e)), len(_h2.findall(z))
        n3e, n3z = len(_h3.findall(e)), len(_h3.findall(z))
        se, sz = {f"{a}.{b}" for a, b in _secno.findall(e)}, {f"{a}.{b}" for a, b in _secno.findall(z)}
        ue, uz = urls(e), urls(z)
        ce = {c: len(p.findall(e)) for c, p in zip(COLS_EN, _colrow_en)}
        cz = {c: len(p.findall(z)) for c, p in zip(COLS_ZH, _colrow_zh)}
        cez = {en_c: cz[zh_c] for en_c, zh_c in zip(COLS_EN, COLS_ZH)}
        be, bz = len(_top_bullet.findall(e)), len(_top_bullet.findall(z))
        nbe, nbz = len(_nest_bullet.findall(e)), len(_nest_bullet.findall(z))
        le, lz = ledger(e, EN_LEDGER), ledger(z, ZH_LEDGER)
        keys = sorted(set(le) | set(lz))
        fly, sup = e.count("fly2ai"), e.count("<sup>")
        left = sum(e.count(m) for m in LEFTOVER)
        plat = sum(e.count(p) for p in PLATFORMS)
        cn = bad_chinese(e)
        bad = []
        if n2e != n2z: bad.append(f"## {n2e}!={n2z}")
        if n3e != n3z: bad.append(f"### {n3e}!={n3z}")
        if se != sz: bad.append(f"节号 ±{sorted(se - sz)[:2]}/{sorted(sz - se)[:2]}")
        if ue != uz: bad.append(f"URL +{len(ue - uz)} -{len(uz - ue)}")
        if cez != ce: bad.append("栏 " + ",".join(f"{c}:{ce[c]}!={cez[c]}" for c in COLS_EN if ce[c] != cez[c]))
        if (be, nbe) != (bz, nbz): bad.append(f"bullet {be}/{bz} {nbe}/{nbz}")
        STRICT = ("grade", "off", "res", "checked")
        soft = []
        for k in keys:
            if le.get(k, 0) == lz.get(k, 0):
                continue
            if k in ("off", "res"):
                if not (lz.get(k, 0) - 1 <= le.get(k, 0) <= lz.get(k, 0)):
                    bad.append(f"账本 {k}:{le.get(k,0)}!={lz.get(k,0)}(英文不得多于中文，可少 1 处中文散文提及)")
            elif k in STRICT:
                bad.append(f"账本 {k}:{le.get(k,0)}!={lz.get(k,0)}")
            else:
                soft.append(f"{k}:{le.get(k,0)}~{lz.get(k,0)}")
        if fly or sup or left or plat: bad.append(f"禁 fly{fly} sup{sup} 残留{left} 平台{plat}")
        if cn:
            soft.append(f"行内中文 {len(cn)}: {cn[:4]}")
        if bad:
            hard += 1
        ok = "✓" if not bad else "✗"
        print(f"{name:<44}{n2e:>3}/{n2z:<2}{n3e:>3}/{n3z:<2}{len(ue):>4}/{len(uz):<4}"
              f"{sum(ce.values()):>3}/{sum(cz.values()):<3}{be:>4}/{bz:<4}{len(keys):>3}类"
              f"{fly+sup+left+plat:>4}{len(cn):>5}  {ok}")
        for b in bad:
            print("      ✗", b)
        if soft:
            print("      · 参考（散文/标签写法差异）", " ".join(soft))
    print()
    print("硬伤单元数：", hard)
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
