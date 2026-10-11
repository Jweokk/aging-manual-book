#!/usr/bin/env python3
"""从 site/manifest.json + book-en/README.md 生成 mkdocs-en.yml（英文站）。

英文站与中文站同域，挂在 /en/ 下：GitHub Pages 一个仓库只能绑一个自定义域名，
子路径比再开一套仓库+域名省事，也不动已有的中文链接。

只有**已经译好**的单元才进 nav：没译的不出现，读者不会点到空页。单元标题直接取
英文文件的一级标题，标题就不会在 manifest、README、nav 三处各写一份。

    python3 tools/gen_mkdocs_en.py
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "site" / "manifest.json"
MAP_DOC = ROOT / "book-en" / "README.md"
SRC_ASSETS = ROOT / "book" / "assets"
EN = ROOT / "book-en"
EN_ASSETS = EN / "assets"
OUT = ROOT / "mkdocs-en.yml"

# 篇名（中文 manifest 的 part 字符串）→ 英文。新篇在这里补一行。
PART_EN = {
    "先看这一页": "Start here",
    "篇一 · 存本钱：还没老的时候〔阶段一〕": "Part 1 · Build your reserves",
    "篇二 · 黑框警告：这三件事先看〔阶段二〕": "Part 2 · Three warnings to read first",
    "篇三 · 难以启齿与日常保养〔阶段二·续〕": "Part 3 · The awkward subjects, and everyday upkeep",
    "篇四 · 把家、钱、人、权限安排好〔阶段三〕": "Part 4 · Arranging the home, the money, the people, the authority",
    "篇五 · 最后一程与善后〔阶段四〕": "Part 5 · The last stretch, and what comes after",
    "结语与附录": "Afterword and appendices",
}

# 中文站与英文站互指，读者在两个站之间能来回跳。
ALTERNATE = """extra:
  alternate:
    - name: 中文（Chinese）
      link: https://aging.fly2ai.top/
      lang: zh
    - name: English
      link: https://aging.fly2ai.top/en/
      lang: en
"""

TEMPLATE = """site_name: The Ageing Manual
site_description: What you, or your parents, do next · a practical manual for growing old in China · free, open, updated every quarter
site_url: https://aging.fly2ai.top/en/
docs_dir: book-en
site_dir: build/site-en
repo_url: https://github.com/Jweokk/aging-manual-book
repo_name: GitHub
edit_uri: ""

hooks:
  - tools/mkdocs_hooks.py

# book-en/README.md 是翻译工作用的中英对应表，不面向读者：不进 nav，也不进站点。
# （它和 index.md 都会解析到站根，不排除会直接让 --strict 失败。）
exclude_docs: |
  README.md


theme:
  name: material
  language: en
  logo: assets/logo.svg
  favicon: assets/logo.svg
  features:
    - navigation.sections
    - navigation.top
    - navigation.footer
    - navigation.indexes
    - search.suggest
    - search.highlight
    - toc.follow
    - content.code.copy
  palette:
    - scheme: default
      primary: deep orange
      accent: amber
      toggle:
        icon: material/weather-night
        name: Switch to dark mode
    - scheme: slate
      primary: deep orange
      accent: amber
      toggle:
        icon: material/weather-sunny
        name: Switch to light mode

markdown_extensions:
  - tables
  - admonition
  - attr_list
  - md_in_html
  - toc:
      permalink: true
      toc_depth: 3
  - footnotes

extra_css:
  - assets/extra.css

extra_javascript:
  - assets/font-scale.js
  - assets/shelf-counter.js

""" + ALTERNATE + """
nav:
  - "The Ageing Manual": index.md
  - "中文版 · Chinese edition": https://aging.fly2ai.top/
  - "GitHub repository": https://github.com/Jweokk/aging-manual-book
"""

_pat_row = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|")
_pat_h1 = re.compile(r"^#\s+(.+?)\s*$", re.M)


def read_mapping() -> dict[str, str]:
    """book-en/README.md 的中英文件对应表 = 文件名的单一事实源。"""
    out: dict[str, str] = {}
    for line in MAP_DOC.read_text(encoding="utf-8").splitlines():
        m = _pat_row.match(line)
        if m and m.group(1).endswith(".md") and m.group(2).endswith(".md"):
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def h1_of(p: Path) -> str | None:
    m = _pat_h1.search(p.read_text(encoding="utf-8"))
    return m.group(1).strip() if m else None


def sync_assets() -> list[str]:
    """站点样式/脚本只维护一份：book/assets/ 是源，这里同步到 book-en/assets/。"""
    EN_ASSETS.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in sorted(SRC_ASSETS.iterdir()):
        if f.is_file():
            dst = EN_ASSETS / f.name
            if not dst.exists() or dst.read_bytes() != f.read_bytes():
                shutil.copy2(f, dst)
                copied.append(f.name)
    return copied


def main() -> int:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    mapping = read_mapping()
    copied = sync_assets()
    if copied:
        print(f"  同步站点资源 → book-en/assets/：{', '.join(copied)}")

    lines: list[str] = []
    n_units = 0
    n_parts = 0
    pending: list[str] = []
    for part in m["parts"]:
        avail = []
        for ch in part["chapters"]:
            en_name = mapping.get(ch["file"])
            if not en_name:
                print(f"  ! 对应表里没有这一条：{ch['file']}", file=sys.stderr)
                continue
            if (EN / en_name).exists():
                title = h1_of(EN / en_name) or ch["title"]
                avail.append((title, en_name))
            else:
                pending.append(en_name)
        if not avail:
            continue
        n_parts += 1
        lines.append(f"  - {PART_EN.get(part['part'], part['part'])}:")
        for title, en_name in avail:
            n_units += 1
            lines.append(f'      - "{title}": {en_name}')

    OUT.write_text(TEMPLATE + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写 {OUT.relative_to(ROOT)}：{n_units} 个单元、{n_parts} 个篇")
    if pending:
        print(f"  （未译，暂不进 nav：{len(pending)} 个单元）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
