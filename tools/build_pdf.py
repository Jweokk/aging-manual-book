#!/usr/bin/env python3
"""生成《变老说明书》整本 PDF。

流程：book/*.md（顺序取自 site/manifest.json）→ python-markdown → HTML → weasyprint → PDF
验证：pdftotext 数页、抽查关键句是否在正文里。

用法：
    .venv/bin/python tools/build_pdf.py [版本号] [--lang zh|en]
    版本号缺省读 VERSION 文件。
    --lang en 读 book-en/，输出到仓库根目录（英文版不进中文域名站）。
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 徽标渲染复用站点钩子里的正则，避免站点与 PDF 两套记法
sys.path.insert(0, os.path.join(BASE, "tools"))
from mkdocs_hooks import _pat_checked, _pat_grade, _pat_official, _pat_pending, _pat_quote  # noqa: E402

LANGS = {
    "zh": {
        "dir": "book",
        "out": "book",
        "fname": "aging-manual",
        "title": "变老说明书",
        "subtitle": "你或你父母的下一步",
        "meta": "整理者 Jweokk · {today} · v{version}",
        "blurb": '中国普通人用得上的晚年手册：23 章正文、6 个附录，按"你或你父母的下一步"排。<br>不教你养老，只让你出问题的时候能翻到那一页——每条都写清要花多少、可以怎么做、来源在哪一档。',
        "disclaimer": "本书著作权归整理者 Jweokk 所有，免费阅读与非商业性分享，商业用途须事先获得书面许可。<br>内容为公开资料整理，不构成医疗建议。纠错与建议：weokk2025@gmail.com",
        "font_body": '"Noto Serif SC", "Songti SC", serif',
        "font_head": '"Noto Sans SC", "Heiti SC", sans-serif',
        "toc_title": "目录",
        "lang_attr": "zh-CN",
    },
    "en": {
        "dir": "book-en",
        "out": ".",
        "fname": "aging-manual-en",
        "title": "The Getting-Older Manual",
        "subtitle": "Your next step, or your parents'",
        "meta": "Compiled by Jweokk · {today} · v{version}",
        "blurb": "A practical handbook for growing older in China: 22 chapters and 6 appendices, organised by what you are facing next.<br>Every entry tells you what it costs, what you can do, and where the claim comes from.",
        "disclaimer": "Copyright © Jweokk. Free for reading and non-commercial sharing; commercial use requires prior written permission.<br>Compiled from public sources; not medical advice. Corrections: weokk2025@gmail.com",
        "font_body": '"Noto Serif", "DejaVu Serif", serif',
        "font_head": '"Noto Sans", "DejaVu Sans", sans-serif',
        "toc_title": "Contents",
        "lang_attr": "en",
    },
}


def read_version() -> str:
    vf = os.path.join(BASE, "VERSION")
    return open(vf).read().strip() if os.path.exists(vf) else "1.0.0"


def badges(html: str) -> str:
    """把内部记号渲染成徽标（与站点同一套）。"""
    html = _pat_grade.sub(lambda m: f'<span class="grade g{m.group(1).lower()}">{m.group(1)}</span>', html)
    html = _pat_pending.sub('<span class="tag-pending">待核</span>', html)
    html = _pat_quote.sub('<span class="tag-quote">转引</span>', html)
    html = _pat_official.sub('<span class="tag-off">官方口径</span>', html)
    html = _pat_checked.sub(lambda m: f'<span class="tag-checked">核对 {m.group(1)}</span>', html)
    return html


def md_to_html(md_text: str) -> str:
    import markdown

    html = markdown.markdown(
        md_text, extensions=["tables", "toc", "admonition", "fenced_code", "footnotes", "attr_list"]
    )
    return badges(html)


def units(lang: str):
    """产出 [(kind, title, html)]，kind ∈ {part, chapter}。

    顺序、篇划分、标题全部取自 site/manifest.json（英文版取 book-en/README.md
    的中英对应表）。
    """
    if lang == "zh":
        m = json.loads(open(os.path.join(BASE, "site", "manifest.json"), encoding="utf-8").read())
        plan = [(p["part"], [(c["title"], c["file"]) for c in p["chapters"]]) for p in m["parts"]]
        mdir = os.path.join(BASE, "book")
    else:
        mdir = os.path.join(BASE, "book-en")
        table = os.path.join(mdir, "README.md")
        plan = [("", [])]
        for line in open(table, encoding="utf-8"):
            mm = re.match(r"\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|", line)
            if mm:
                plan[0][1].append((mm.group(2), mm.group(2)))

    for part, chs in plan:
        if part:
            yield ("part", part, "")
        for title, fname in chs:
            path = os.path.join(mdir, fname)
            if not os.path.exists(path):
                print(f"  ! 缺少文件：{fname}", file=sys.stderr)
                continue
            raw = open(path, encoding="utf-8").read()
            raw = re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.S)
            m = re.search(r"^#\s+(.+)$", raw, flags=re.M)
            if m:  # 去掉正文首个 H1，标题由模板统一排版
                raw = raw[: m.start()] + raw[m.end():]
            yield ("chapter", title, md_to_html(raw))


def build() -> int:
    lang = "en" if "--lang" in sys.argv and sys.argv[sys.argv.index("--lang") + 1] == "en" else "zh"
    L = LANGS[lang]
    version = next((a for a in sys.argv[1:] if not a.startswith("--") and a != "en"), None) or read_version()
    today = datetime.now().strftime("%Y-%m-%d" if lang == "en" else "%Y年%m月%d日")
    head_font, body_font = L["font_head"], L["font_body"]

    items = list(units(lang))
    chapters = [it for it in items if it[0] == "chapter"]
    if not chapters:
        print("没有找到章节，检查 manifest / book-en 对应表")
        return 1

    # 目录带页码：每单元一个锚点，页码由 CSS 的 target-counter 取（weasyprint 支持）。
    # 首段（"先看这一页"这组前置件）不单独占扉页——否则全书第一页是一张只有标题的白页。
    toc = ""
    body = ""
    for i, (k, t, h) in enumerate(items):
        if k == "part":
            if not t.startswith("篇"):
                continue
            aid = f"part-{i}"
            toc += f'<p class="toc-part"><a href="#{aid}">{t}</a><a class="pg" href="#{aid}"></a></p>'
            body += f'<section class="part-page"><h1 id="{aid}">{t}</h1></section>\n'
        else:
            aid = f"ch-{i}"
            toc += f'<p class="toc-entry"><a href="#{aid}">{t}</a><a class="pg" href="#{aid}"></a></p>'
            body += f'<h2 class="chapter-title" id="{aid}">{t}</h2>\n{h}\n'

    html = f"""<!DOCTYPE html>
<html lang="{L['lang_attr']}">
<head>
<meta charset="utf-8">
<title>{L['title']}</title>
<meta name="author" content="Jweokk">
<meta name="description" content="{L['subtitle']}">
<style>
  @page {{
    size: A4;
    margin: 2.1cm 2.2cm 1.9cm 2.2cm;
    @bottom-center {{ content: counter(page); font-family: {head_font}; font-size: 9pt; color: #9a9a9a; }}
  }}
  @page:first {{ @bottom-center {{ content: none; }} }}
  body {{ font-family: {body_font}; font-size: 10.5pt; line-height: 1.8; color: #1f2328;
         text-align: justify; orphans: 3; widows: 3; }}
  .cover {{ page-break-after: always; background: #c2410c; color: #fff;
            padding: 5.5cm 1.6cm 2cm 1.6cm; margin: -2.1cm -2.2cm; width: 21cm; height: 29.7cm;
            box-sizing: border-box; }}
  .cover h1 {{ font-family: {head_font}; font-size: 34pt; text-align: center; margin: 0 0 10pt 0; letter-spacing: 6pt; }}
  .cover .subtitle {{ font-size: 13pt; text-align: center; color: #ffe4d3; margin-bottom: 1.6cm; }}
  .cover .meta {{ font-size: 10pt; text-align: center; color: #ffd0b8; margin-top: 3.2cm; }}
  .cover .blurb {{ font-size: 10pt; text-align: center; color: #ffe9dd; line-height: 1.75; max-width: 13.5cm; margin: 1.4cm auto; }}
  .cover .disclaimer {{ font-size: 8pt; text-align: center; color: #ffd9c6; line-height: 1.6; position: absolute; bottom: 2cm; width: 17.8cm; }}
  .toc-page {{ page-break-after: always; }}
  .toc-page h2 {{ font-family: {head_font}; font-size: 18pt; color: #c2410c; border-bottom: 2px solid #fdba74;
                  padding-bottom: 6pt; margin-bottom: 12pt; }}
  .toc-part, .toc-entry {{ display: flex; justify-content: space-between; align-items: baseline; }}
  .toc-part {{ font-family: {head_font}; font-size: 11pt; font-weight: 700; color: #c2410c; margin: 12pt 0 4pt 0; }}
  .toc-entry {{ font-size: 10.5pt; line-height: 1.75; margin: 0 0 0 14pt; }}
  .toc-part a, .toc-entry a {{ color: inherit; text-decoration: none; }}
  .toc-part a.pg, .toc-entry a.pg {{ flex: 0 0 2.2cm; text-align: right; color: #78716c; }}
  .toc-part a.pg::after, .toc-entry a.pg::after {{ content: target-counter(attr(href), page); }}
  .part-page {{ page-break-before: always; page-break-after: always; padding-top: 9cm; text-align: center; }}
  .part-page h1 {{ font-family: {head_font}; font-size: 20pt; color: #c2410c; border: none; }}
  .chapter-title {{ font-family: {head_font}; font-size: 15.5pt; color: #9a3412; page-break-before: always;
                    border-bottom: 1.5px solid #fdba74; padding-bottom: 4pt; margin: 0 0 12pt 0; }}
  h1 {{ font-family: {head_font}; font-size: 13.5pt; color: #9a3412; margin-top: 16pt; }}
  h2 {{ font-family: {head_font}; font-size: 12pt; color: #333; margin-top: 13pt; }}
  h3 {{ font-family: {head_font}; font-size: 11pt; color: #444; }}
  p {{ margin: 5pt 0; text-indent: 2em; }}
  li {{ margin: 3pt 0; }}
  strong {{ color: #9a3412; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 9pt; margin: 8pt 0; }}
  th, td {{ border: 0.5pt solid #d6d3d1; padding: 3pt 5pt; text-align: left; vertical-align: top; }}
  th {{ background: #fff7ed; font-family: {head_font}; }}
  blockquote {{ border-left: 2.5pt solid #fdba74; margin: 8pt 0; padding: 2pt 0 2pt 10pt; color: #44403c; }}
  a {{ color: #9a3412; text-decoration: none; }}
  .grade {{ font-family: {head_font}; font-size: 7.5pt; font-weight: 700; padding: 0.5pt 2.5pt; border-radius: 2pt; color: #fff; }}
  .grade.ga {{ background: #2563eb; }}
  .grade.gb {{ background: #0d9488; }}
  .grade.gc {{ background: #78716c; }}
  .tag-pending, .tag-quote, .tag-checked, .tag-off {{
    font-family: {head_font}; font-size: 7.5pt; padding: 0.5pt 3pt; border-radius: 2pt; border: 0.5pt solid currentColor; }}
  .tag-pending {{ color: #b45309; }} .tag-quote {{ color: #7c3aed; }}
  .tag-checked {{ color: #0f766e; }} .tag-off {{ color: #475569; }}
</style>
</head>
<body>
<div class="cover">
  <h1>{L['title']}</h1>
  <div class="subtitle">{L['subtitle']}</div>
  <div class="blurb">{L['blurb']}</div>
  <div class="meta">{L['meta'].format(today=today, version=version)}</div>
  <div class="disclaimer">{L['disclaimer']}</div>
</div>
<div class="toc-page"><h2>{L['toc_title']}</h2>{toc}</div>
{body}
</body>
</html>
"""

    tmp = os.path.join(BASE, ".build-pdf.html")
    open(tmp, "w", encoding="utf-8").write(html)
    out_dir = os.path.join(BASE, L["out"])
    os.makedirs(out_dir, exist_ok=True)
    latest = os.path.join(out_dir, f"{L['fname']}.pdf")
    versioned = os.path.join(out_dir, f"{L['fname']}-v{version}.pdf")

    from weasyprint import HTML

    HTML(string=html, base_url=BASE).write_pdf(latest)
    HTML(string=html, base_url=BASE).write_pdf(versioned)

    txt = subprocess.run(["pdftotext", latest, "-"], capture_output=True, text=True).stdout
    # 页数以 pdfinfo 为准；pdftotext 用 \f 数会多算 1 页（末页无分页符）
    info = subprocess.run(["pdfinfo", latest], capture_output=True, text=True).stdout
    mpg = re.search(r"^Pages:\s+(\d+)", info, flags=re.M)
    pages = int(mpg.group(1)) if mpg else txt.count("\f") + 1
    print(f"{L['title']} v{version} → {os.path.relpath(latest, BASE)}（{pages} 页，{len(txt)} 字）")
    # 抽查：首章、末章、附录都要在正文里
    for probe in (chapters[0][1][:8], chapters[-1][1][:8], "120"):
        if probe.replace(" ", "") not in txt.replace(" ", ""):
            print(f"  ! 抽查失败，PDF 里找不到：{probe}")
    os.remove(tmp)
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
