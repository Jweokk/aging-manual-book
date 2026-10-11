#!/usr/bin/env python3
"""从 site/manifest.json 生成 mkdocs.yml（篇/章目录的单一事实源）。

改了篇名、章名、增删单元之后跑一次：

    python3 tools/gen_mkdocs.py

只重写 nav 段与 site_* 元信息，其余配置（主题、扩展、hooks）在下面的
TEMPLATE 里维护。manifest 里有但文件不存在、或文件存在却不在 manifest 里
的单元，都会打出来提醒——这两种漂移在 CI 上是静默的。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "site" / "manifest.json"
BOOK = ROOT / "book"
OUT = ROOT / "mkdocs.yml"

TEMPLATE = '''site_name: 变老说明书
site_description: 你或你父母的下一步 · 中国普通人的晚年使用与保养手册 · 免费公开、持续更新
site_url: https://aging.fly2ai.top
docs_dir: book
site_dir: build/site
repo_url: https://github.com/Jweokk/aging-manual-book
repo_name: GitHub
edit_uri: ""

hooks:
  - tools/mkdocs_hooks.py

theme:
  name: material
  language: zh
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
        name: 切换到深色模式
    - scheme: slate
      primary: deep orange
      accent: amber
      toggle:
        icon: material/weather-sunny
        name: 切换到浅色模式

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
  - assets/font-scale.js      # 左下角「字大小」调节（localStorage 持久化）
  - assets/shelf-counter.js   # 页脚：访问计数 + PDF 下载计数（counter.fly2ai.top）

extra:
  alternate:
    - name: 中文（Chinese）
      link: https://aging.fly2ai.top/
      lang: zh
    - name: English
      link: https://aging.fly2ai.top/en/
      lang: en

nav:
  - "变老说明书 · 封面": index.md
  - "English edition · 英文版": https://aging.fly2ai.top/en/
'''


def main() -> int:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    have = {p.name for p in BOOK.glob("*.md") if p.name != "index.md"}  # index.md = 封面，不入 manifest
    listed: set[str] = set()

    errors: list[str] = []
    lines: list[str] = []
    for part in m["parts"]:
        lines.append(f"  - {part['part']}:")
        for ch in part["chapters"]:
            f = ch["file"]
            listed.add(f)
            if f not in have:
                errors.append(f)
                print(f"  ! manifest 里有、book/ 里没有：{f}", file=sys.stderr)
            # 标题里的 " · " 在 nav 里换成全角冒号更好读；保持原样更贴近正文
            lines.append(f'      - "{ch["title"]}": {f}')

    missing = sorted(have - listed)
    if missing:
        print(f"  ! book/ 里有、manifest 里没登记：{missing}", file=sys.stderr)

    OUT.write_text(TEMPLATE + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写 {OUT.relative_to(ROOT)}：{len(listed)} 个单元、{len(m['parts'])} 个篇")
    if errors:  # 缺文件会让站点静默少一章，CI 上必须红
        print(f"  ✗ {len(errors)} 个单元在 manifest 里找不到文件，已中止", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
