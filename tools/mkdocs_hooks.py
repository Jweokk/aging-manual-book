"""MkDocs 钩子：把正文里的内部记号渲染成徽标。

正文里的记号是写作期的约定，读者面不该看到 〔待核〕 这种编辑用语的原样；
但也不能删——读者有权知道哪一条还没坐实。所以渲染成小徽标：

    【A】/【B】/【C】      证据分档（第 0 章有释义）
    〔待核〕              还没核实的条目
    〔转引〕              二手来源转述（版权规范要求）
    〔核对 2026-10-10〕   这一条已按该日期核对
    〔官方口径〕          以官方文件为准

只改渲染，不动源文件：源文件保持可 grep、可校对。
"""

from __future__ import annotations

import re

_GRADE_CLASS = {"A": "g-a", "B": "g-b", "C": "g-c"}
_GRADE_TITLE = {
    "A": "证据分档 A：有具体数字、可公开查到的出处",
    "B": "证据分档 B：有研究支持，但给不出具体数字",
    "C": "证据分档 C：通行做法（多数国家和地区都这么做）",
}

_pat_grade = re.compile(r"【([ABC])】")
_pat_pending = re.compile(r"〔待核〕")
_pat_quote = re.compile(r"〔转引〕")
_pat_official = re.compile(r"〔官方口径〕")
_pat_checked = re.compile(r"〔核对\s*([\d\-]{6,12})〕")


def _grade(m: re.Match) -> str:
    g = m.group(1)
    return (
        f'<span class="grade {_GRADE_CLASS[g]}" title="{_GRADE_TITLE[g]}">{g}</span>'
    )


def on_page_content(html: str, page, config, files) -> str:
    html = _pat_grade.sub(_grade, html)
    html = _pat_pending.sub('<span class="mk mk-pending" title="这一条还没核实到公开出处">待核</span>', html)
    html = _pat_quote.sub('<span class="mk mk-quote" title="来自二手来源的转述，不是一手原文">转引</span>', html)
    html = _pat_official.sub('<span class="mk mk-off" title="以官方文件口径为准">官方口径</span>', html)
    html = _pat_checked.sub(lambda m: f'<span class="mk mk-checked" title="已按该日期核对">核对 {m.group(1)}</span>', html)
    return html
