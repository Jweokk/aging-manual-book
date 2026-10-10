#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 book/*.md 合成一个单页校样站（site/dist/index.html）。

用法: python3 site/build.py
产物: site/dist/index.html   （自包含，无外部依赖，可直接双击打开或静态托管）
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "book"
OUT = ROOT / "site" / "dist"
MANIFEST = json.loads((ROOT / "site" / "manifest.json").read_text(encoding="utf-8"))

CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")


def cjk_count(text: str) -> int:
    return len(CJK.findall(text))


def esc_attr(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


URL_RE = re.compile(r'(?<!["\'=])https?://[^\s<>"）)，。；、]+')


def autolink(html: str) -> str:
    """把裸 URL 变成可点链接（python-markdown 默认不自动链接）。"""
    return URL_RE.sub(
        lambda m: f'<a href="{m.group(0)}" target="_blank" rel="noopener">{m.group(0)}</a>',
        html)


def decorate(html: str) -> str:
    """〔待核 1〕/〔转引 1〕 → 徽标；【A】/【B】/【C】 → 分档徽标。"""
    html = re.sub(r"〔([^〕]{1,30})〕", r'<span class="flag">\1</span>', html)
    html = re.sub(r"【([ABC])】", r'<span class="grade g\1">\1</span>', html)
    return html


BAN_WORDS = ["关爱", "呵护", "温馨", "夕阳红", "银发族", "赋能", "抓手", "闭环",
             "颗粒度", "值得一提的是", "综上所述", "由此可见", "在当今社会"]
# 这几类不需要「如果你是在替爸妈看」：前置页、结语、附录、以及全章即家属视角的第 22 章
NO_CHILD_SECTION = {"00", "01", "22", "30", "41", "43", "44", "45", "46"}


def style_lint(path, n) -> list:
    """每章一句话体检：结构缺项 / 禁用词 / 问句标题。"""
    raw = path.read_text(encoding="utf-8")
    bad = []
    if n not in NO_CHILD_SECTION and "替爸妈看" not in raw:
        bad.append("缺子女节")
    _raw = raw
    for _x in ("老年心理关爱", "体育科学研究所", "中国老龄科学研究中心",
               "系统综述", "神经系统", "系统重审", "科学普及部", "最有效", "有效期"):
        _raw = _raw.replace(_x, "〔专名〕")   # 官方专名与正常词义豁免
    hit = [w for w in BAN_WORDS if w in _raw]
    if hit:
        bad.append("禁用词:" + "/".join(hit))
    qh = [h for h in re.findall(r"(?m)^#{2,3}\s*(.+)$", raw) if h.strip().endswith("？")]
    if qh:
        bad.append(f"问句标题×{len(qh)}")
    return bad


def citation_check() -> str:
    script = ROOT / "tools" / "check_citation.py"
    if not script.exists():
        return "未运行"
    try:
        out = subprocess.run([sys.executable, str(script)], cwd=str(ROOT),
                             capture_output=True, text=True, timeout=120).stdout
    except Exception as exc:  # noqa: BLE001
        return f"运行失败：{exc}"
    for line in out.splitlines():
        if line.startswith("结论"):
            return line.split(":", 1)[-1].strip() or line
    return "已运行"


def build() -> dict:
    md = markdown.Markdown(extensions=["tables", "fenced_code", "attr_list",
                                       "sane_lists", "md_in_html", "toc"])
    nav_html, body_html = [], []
    stats = {"done": 0, "planned": 0, "chars": 0, "pending": 0, "grades": 0, "links": 0}
    chapters = []

    for part in MANIFEST["parts"]:
        nav_html.append(f'<div class="part">{esc_attr(part["part"])}</div>')
        for ch in part["chapters"]:
            stats["planned"] += 1
            path = BOOK / ch["file"]
            anchor = f'ch{ch["n"]}'
            if not path.exists():
                nav_html.append(
                    f'<a class="nav-link todo" href="#{anchor}">{esc_attr(ch["title"])}'
                    f'<em>写作中</em></a>')
                body_html.append(
                    f'<section class="chapter todo" id="{anchor}">'
                    f'<h1>{esc_attr(ch["title"])}</h1>'
                    f'<p class="todo-note">这一章还在写。写完会自动出现在这里。</p>'
                    f"</section>")
                chapters.append({**ch, "chars": 0, "status": "todo"})
                continue

            raw = path.read_text(encoding="utf-8")
            n_chars = cjk_count(raw)
            md.reset()
            html = autolink(decorate(md.convert(raw)))
            stats["done"] += 1
            stats["chars"] += n_chars
            stats["pending"] += len(re.findall(r"〔待核", raw))   # 只数真待核（原来把〔转引〕〔官方口径〕也算进来了）
            stats["grades"] += len(re.findall(r"[【](?:官方口径|第三方研究|厂商或机构宣称|本书核对)|【[ABC]】|来源", raw))
            stats["links"] += len(re.findall(r"https?://", raw))

            nav_html.append(
                f'<a class="nav-link" href="#{anchor}">{esc_attr(ch["title"])}'
                f'<em>{n_chars / 1000:.1f}k 字</em></a>')
            body_html.append(
                f'<section class="chapter" id="{anchor}">{html}</section>')
            chapters.append({**ch, "chars": n_chars, "status": "done"})

    lint = {c["n"]: style_lint(BOOK / c["file"], c["n"]) for c in chapters
            if c["status"] == "done"}
    lint_txt = "；".join(f'{c["title"].split("·")[0].strip()} {"、".join(v)}'
                        for c, v in ((c, lint[c["n"]]) for c in chapters
                                     if c["status"] == "done") if v) or "全部通过"
    cite = citation_check()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    done_list = "、".join(c["title"].split("·")[0].strip() for c in chapters
                          if c["status"] == "done")
    todo_list = "、".join(c["title"].split("·")[0].strip() for c in chapters
                          if c["status"] == "todo") or "无"

    panel = f"""
<div class="panel">
  <div class="panel-title">校样状态（自动生成 · {stamp}）</div>
  <div class="cards">
    <div class="card"><b>{stats['done']}<span>/{stats['planned']}</span></b><i>已完成章节</i></div>
    <div class="card"><b>{stats['chars'] / 10000:.1f}<span> 万</span></b><i>汉字</i></div>
    <div class="card"><b>{stats['pending']}</b><i>待核标记</i></div>
    <div class="card"><b>{stats['grades']}</b><i>办法条目</i></div>
    <div class="card"><b>{stats['links']}</b><i>外链</i></div>
  </div>
  <p class="panel-line"><b>版权与引用自检：</b>{esc_attr(cite)}</p>
  <p class="panel-line"><b>体例自检：</b>{esc_attr(lint_txt)}</p>
  <p class="panel-line"><b>已完成：</b>{esc_attr(done_list)}</p>
  <p class="panel-line"><b>写作中：</b>{esc_attr(todo_list)}</p>
  <p class="panel-line muted">读的时候请重点看四件事：① 语气像不像一个懂事的人在你旁边说，而不是说明书 ② 每条有没有写清「对谁成立」 ③ 数字和制度的出处 ④ 哪一节你觉得多余或不够。</p>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{MANIFEST['title']}（校样）</title>
<style>
:root {{
  --bg:#fbf8f3; --card:#fff; --ink:#262220; --muted:#6f665d; --line:#e8e0d4;
  --accent:#c6552f; --accent2:#2f7a6b; --wash:#fdf4ee;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:17px/1.85 "Noto Sans SC","PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,sans-serif; }}
#bar {{ position:fixed; top:0; left:0; height:3px; width:0; background:linear-gradient(90deg,var(--accent),var(--accent2)); z-index:99; }}
header.top {{ padding:34px 24px 10px; max-width:1180px; margin:0 auto; }}
.badge {{ display:inline-block; background:#fff4e6; color:var(--accent); border:1px solid #f2d9c2;
  border-radius:999px; font-size:13px; padding:2px 12px; margin-bottom:12px; }}
h1.book {{ font-size:30px; margin:0 0 6px; letter-spacing:.5px; }}
.sub {{ color:var(--muted); font-size:16px; margin:0 0 4px; }}
.note {{ color:var(--muted); font-size:14px; }}
.wrap {{ display:grid; grid-template-columns:288px minmax(0,1fr); gap:26px;
  max-width:1180px; margin:14px auto 80px; padding:0 24px; align-items:start; }}
nav {{ position:sticky; top:16px; max-height:calc(100vh - 32px); overflow:auto;
  background:var(--card); border:1px solid var(--line); border-radius:16px; padding:14px; }}
.part {{ font-size:12px; color:var(--accent2); letter-spacing:.6px; margin:14px 8px 6px; font-weight:700; }}
.part:first-child {{ margin-top:4px; }}
.nav-link {{ display:flex; justify-content:space-between; gap:8px; align-items:baseline;
  text-decoration:none; color:var(--ink); font-size:14px; padding:7px 9px; border-radius:9px; }}
.nav-link:hover {{ background:var(--wash); }}
.nav-link em {{ font-style:normal; font-size:11px; color:var(--muted); white-space:nowrap; }}
.nav-link.todo {{ color:#b3aaa0; }}
.nav-link.active {{ background:var(--wash); color:var(--accent); font-weight:600; }}
.panel {{ background:var(--card); border:1px solid var(--line); border-radius:18px;
  padding:22px 24px; margin:0 0 22px; }}
.panel-title {{ font-size:13px; letter-spacing:.5px; color:var(--accent2); font-weight:700; margin-bottom:14px; }}
.cards {{ display:flex; flex-wrap:wrap; gap:10px; }}
.card {{ flex:1 1 108px; background:var(--wash); border-radius:12px; padding:10px 14px; }}
.card b {{ font-size:22px; color:var(--accent); }}
.card b span {{ font-size:13px; color:var(--muted); }}
.card i {{ display:block; font-style:normal; font-size:12px; color:var(--muted); margin-top:2px; }}
.panel-line {{ font-size:14px; margin:10px 0 0; }}
.muted {{ color:var(--muted); }}
.chapter {{ background:var(--card); border:1px solid var(--line); border-radius:18px;
  padding:34px 44px; margin:0 0 22px; }}
.chapter h1 {{ font-size:25px; line-height:1.4; margin:0 0 18px; padding-left:14px;
  border-left:5px solid var(--accent); }}
.chapter h2 {{ font-size:20px; margin:34px 0 10px; color:var(--accent2); }}
.chapter h3 {{ font-size:17px; margin:24px 0 8px; }}
.chapter p, .chapter li {{ font-size:16.5px; }}
.chapter li {{ margin:5px 0; }}
.chapter blockquote {{ margin:16px 0; padding:12px 18px; background:var(--wash);
  border-left:4px solid #e6c9b4; border-radius:0 10px 10px 0; color:#4a423b; }}
.chapter a {{ color:var(--accent2); word-break:break-all; }}
.chapter code {{ background:#f4efe7; padding:1px 6px; border-radius:6px; font-size:14px; }}
.chapter table {{ border-collapse:collapse; width:100%; margin:16px 0; font-size:15px; }}
.chapter th, .chapter td {{ border:1px solid var(--line); padding:8px 10px; text-align:left; }}
.chapter th {{ background:var(--wash); }}
.chapter hr {{ border:0; border-top:1px solid var(--line); margin:30px 0; }}
.flag {{ display:inline-block; background:#fff6d9; border:1px solid #eed592; color:#8a6d16;
  border-radius:999px; font-size:12px; padding:0 9px; line-height:1.7; }}
.grade {{ display:inline-block; border-radius:6px; font-size:12px; padding:0 7px;
  font-weight:700; color:#fff; background:#8d8378; }}
.gA {{ background:#2f7a6b; }} .gB {{ background:#8a7bd8; }} .gC {{ background:#b08a5a; }}
.chapter.todo {{ background:#fdfbf7; border-style:dashed; }}
.chapter.todo h1 {{ color:#b3aaa0; border-left-color:#e2d9cc; }}
.todo-note {{ color:var(--muted); }}
footer {{ max-width:1180px; margin:0 auto 60px; padding:0 24px; color:var(--muted); font-size:13px; }}
#top {{ position:fixed; right:22px; bottom:22px; background:var(--accent); color:#fff;
  border:0; border-radius:999px; width:44px; height:44px; font-size:18px; cursor:pointer;
  box-shadow:0 6px 18px rgba(198,85,47,.3); opacity:0; transition:opacity .2s; }}
#top.show {{ opacity:1; }}
@media (max-width:900px) {{
  .wrap {{ grid-template-columns:1fr; }}
  nav {{ position:static; max-height:none; }}
  .chapter {{ padding:24px 20px; }}
}}
@media print {{
  nav, #top, .panel {{ display:none; }}
  .wrap {{ display:block; max-width:none; padding:0; margin:0; }}
  body {{ background:#fff; font-size:11.5pt; }}
  .chapter {{ border:0; padding:0; margin:0 0 18pt; break-before:page; }}
  .chapter h1 {{ break-after:avoid; }}
  a {{ color:inherit; text-decoration:none; }}
}}
</style>
</head>
<body>
<div id="bar"></div>
<header class="top">
  <div class="badge">校样 · 未定稿 · {stamp}</div>
  <h1 class="book">{MANIFEST['title']}</h1>
  <p class="sub">{MANIFEST['subtitle']}</p>
  <p class="note">{MANIFEST['note']}</p>
</header>
<div class="wrap">
  <nav>{''.join(nav_html)}</nav>
  <main>
    {panel}
    {''.join(body_html)}
  </main>
</div>
<footer>这是内部校样，未对外发布 · 生成脚本 site/build.py · 章节缺漏与待核标记见顶部面板</footer>
<button id="top" title="回到顶部">↑</button>
<script>
const bar = document.getElementById('bar'), top = document.getElementById('top');
const links = [...document.querySelectorAll('.nav-link')];
const secs = [...document.querySelectorAll('section.chapter')];
function onScroll() {{
  const h = document.documentElement;
  bar.style.width = (h.scrollTop / (h.scrollHeight - h.clientHeight) * 100) + '%';
  top.classList.toggle('show', h.scrollTop > 600);
  let cur = secs[0];
  for (const s of secs) if (s.getBoundingClientRect().top <= 120) cur = s;
  links.forEach(a => a.classList.toggle('active', a.hash === '#' + cur.id));
}}
document.addEventListener('scroll', onScroll, {{passive:true}}); onScroll();
top.onclick = () => window.scrollTo({{top:0, behavior:'smooth'}});
</script>
</body>
</html>"""

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    return {"stats": stats, "cite": cite, "out": str(OUT / "index.html"),
            "bytes": (OUT / "index.html").stat().st_size}


if __name__ == "__main__":
    r = build()
    print(f"已生成 {r['out']}（{r['bytes'] / 1024:.0f} KB）")
    s = r["stats"]
    print(f"章节 {s['done']}/{s['planned']}｜汉字 {s['chars']}｜待核 {s['pending']}"
          f"｜分档角标 {s['grades']}｜外链 {s['links']}")
    print(f"版权自检：{r['cite']}")
