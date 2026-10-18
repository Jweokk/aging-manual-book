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
from pathlib import Path

_GRADE_CLASS = {"A": "g-a", "B": "g-b", "C": "g-c"}
_GRADE_TITLE = {
    "A": "证据分档 A：有具体数字、可公开查到的出处",
    "B": "证据分档 B：有研究支持，但给不出具体数字",
    "C": "证据分档 C：通行做法（多数国家和地区都这么做）",
}
_GRADE_TITLE_EN = {
    "A": "Grade A: a specific figure from a publicly checkable source",
    "B": "Grade B: supported by research, but no specific figure",
    "C": "Grade C: common practice, not evidence",
}

# 内联出处：正文里的数字后面常紧跟「【官方口径：某部委】」这种即时出处，中文与英文
# 各有一套写法，两套都渲染成同样的徽标（中文用【】，英文用 []，见 assets/glossary-en.md）。
# 带内容的形态保留内容当正文，只把标签本身变成徽标。
_pat_off_inline = re.compile(r"【官方口径(?:[：:]\s*([^】]{1,200}))?】")
_pat_res_inline = re.compile(r"【第三方研究(?:[：:]\s*([^】]{1,200}))?】")

# 英文版把中文记号写成方括号，这里一并渲染成同样的徽标。
# 只加规则、不改源文件；中文页里不会出现这些串，互不影响。
_pat_en_pending = re.compile(r"\[unverified\]")
_pat_en_quote = re.compile(r"\[second-hand\]")
_pat_en_official = re.compile(r"\[official wording(?:[：:]\s*([^\]]{1,200}))?\]")
_pat_en_research = re.compile(r"\[third-party research(?:[：:]\s*([^\]]{1,200}))?\]")
_pat_en_checked = re.compile(r"\[checked\s*([\d\-]{6,12})\]")
# 英文版的分档用 ASCII 方括号放在来源行首（中文是【A】），后随空格或竖线
_pat_en_grade = re.compile(r"\[([ABC])\](?=[\s|，。;:).,])")

_pat_grade = re.compile(r"[【〔]([ABC])[】〕]")
_pat_pending = re.compile(r"〔待核〕")
_pat_quote = re.compile(r"〔转引〕")
_pat_official = re.compile(r"〔官方口径〕")
_pat_checked = re.compile(r"〔核对\s*([\d\-]{6,12})〕")


def _grade(m: re.Match) -> str:
    g = m.group(1)
    return (
        f'<span class="grade {_GRADE_CLASS[g]}" title="{_GRADE_TITLE[g]}">{g}</span>'
    )


def _grade_en(m: re.Match) -> str:
    g = m.group(1)
    return (
        f'<span class="grade {_GRADE_CLASS[g]}" title="{_GRADE_TITLE_EN[g]}">{g}</span>'
    )


def _off(m: re.Match) -> str:
    body = (m.group(1) or "").strip()
    chip = '<span class="mk mk-off" title="以官方文件口径为准 / per the official document">官方口径</span>'
    return chip + (" " + body if body else "")


def _res(m: re.Match) -> str:
    body = (m.group(1) or "").strip()
    chip = '<span class="mk mk-res" title="第三方研究，不是官方文件 / third-party research">第三方研究</span>'
    return chip + (" " + body if body else "")


def _en_off(m: re.Match) -> str:
    body = (m.group(1) or "").strip()
    chip = '<span class="mk mk-off" title="Per the wording of the official document">official wording</span>'
    return chip + (" " + body if body else "")


def _en_res(m: re.Match) -> str:
    body = (m.group(1) or "").strip()
    chip = '<span class="mk mk-res" title="Third-party research, not an official document">third-party research</span>'
    return chip + (" " + body if body else "")


def on_page_content(html: str, page, config, files) -> str:
    html = _pat_grade.sub(_grade, html)
    html = _pat_off_inline.sub(_off, html)
    html = _pat_res_inline.sub(_res, html)
    html = _pat_pending.sub('<span class="mk mk-pending" title="这一条还没核实到公开出处">待核</span>', html)
    html = _pat_quote.sub('<span class="mk mk-quote" title="来自二手来源的转述，不是一手原文">转引</span>', html)
    html = _pat_official.sub('<span class="mk mk-off" title="以官方文件口径为准">官方口径</span>', html)
    html = _pat_checked.sub(lambda m: f'<span class="mk mk-checked" title="已按该日期核对">核对 {m.group(1)}</span>', html)
    html = _pat_en_pending.sub('<span class="mk mk-pending" title="This entry has not been traced to a public source yet">unverified</span>', html)
    html = _pat_en_quote.sub('<span class="mk mk-quote" title="Somebody else\'s account of the source, not the original text">second-hand</span>', html)
    html = _pat_en_grade.sub(_grade_en, html)
    html = _pat_en_official.sub(_en_off, html)
    html = _pat_en_research.sub(_en_res, html)
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


# ── 旧地址：新增第 20 章后，原 20/21/22 章顺延，旧链接不能断 ─────────
_REDIRECTS = {
    "20-第20章-怎么开口": "21-第21章-怎么开口",
    "21-第21章-走下坡之前": "22-第22章-走下坡之前",
    "22-第22章-谢幕之后": "23-第23章-谢幕之后",
}


def on_post_build(config) -> None:
    site = Path(config["site_dir"])
    for old, new in _REDIRECTS.items():
        p = site / old / "index.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "<!doctype html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
            f'<meta http-equiv="refresh" content="0; url=../{new}/">'
            f'<link rel="canonical" href="https://aging.fly2ai.top/{new}/">'
            "<title>这一章已顺延</title></head><body>"
            f'<p>这一章顺延了，新地址是 <a href="../{new}/">{new}</a>。</p>'
            "</body></html>",
            encoding="utf-8",
        )
