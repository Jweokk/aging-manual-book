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

# 英文版把中文记号写成方括号（见 assets/glossary-en.md），这里一并渲染成同样的徽标。
# 只加规则、不改源文件；中文页里不会出现这些串，互不影响。
_pat_en_pending = re.compile(r"\[unverified\]")
_pat_en_quote = re.compile(r"\[second-hand\]")
_pat_en_official = re.compile(r"\[official wording\]")
_pat_en_checked = re.compile(r"\[checked\s*([\d\-]{6,12})\]")

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
    html = _pat_en_pending.sub('<span class="mk mk-pending" title="This entry has not been traced to a public source yet">unverified</span>', html)
    html = _pat_en_quote.sub('<span class="mk mk-quote" title="Somebody else\'s account of the source, not the original text">second-hand</span>', html)
    html = _pat_en_official.sub('<span class="mk mk-off" title="Per the wording of the official document">official wording</span>', html)
    html = _pat_en_checked.sub(lambda m: f'<span class="mk mk-checked" title="Checked on this date">checked {m.group(1)}</span>', html)
    return html


# ── 字号：在 <head> 里先按存下来的大小设一遍 ─────────────────────────────
# extra_javascript 里的脚本在 <body> 末尾才跑，那时浏览器可能已经画过一帧，
# 会看到标题先小后大地闪。这里在 head 里补一段内联脚本，只读 localStorage 设变量，
# 默认值仍由 extra.css 的 :root 决定（所以两边不用同步常量）。
_HEAD_SNIPPET = """<script>/* 变老说明书：首次绘制前先把上次调好的字大小设上 */
(function(){try{var v=parseFloat(window.localStorage.getItem("aging-font-scale"));if(v>=1&&v<=3){document.documentElement.style.setProperty("--aging-scale",String(v));}}catch(e){}})();
</script>"""


def on_post_page(output: str, page, config) -> str:
    if "</head>" in output:
        return output.replace("</head>", _HEAD_SNIPPET + "</head>", 1)
    return output
