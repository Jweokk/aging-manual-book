#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《变老说明书》书稿编辑台。

设计：改动先落在「草稿层」(drafts/)，绝不直接改 book/ 的现稿。
  · 自动每 5 分钟存档 + 手动保存（Ctrl+S）
  · 保留每次保存的历史（drafts/history/<时间>-<文件>），可回退
  · 「交稿」→ 写 .submitted.json 并 POST Hermes webhook，唤醒 agent 做「草稿 vs 现稿」比对
  · 右侧实时预览复用 site/build.py 的渲染与自检

用法: python3 editor/editor.py   （配置见 editor/config.json）
"""
import hashlib
import hmac
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

EDITOR = Path(__file__).resolve().parent
ROOT = EDITOR.parent
BOOK = ROOT / "book"
DRAFTS = ROOT / "drafts"
HISTORY = DRAFTS / "history"
MANIFEST = ROOT / "site" / "manifest.json"
CONFIG = EDITOR / "config.json"
STATE = DRAFTS / ".state.json"
SUBMITTED = DRAFTS / ".submitted.json"

# ── 复用主构建脚本的渲染与自检 ────────────────────────────────────────
_spec = importlib.util.spec_from_file_location("bookbuild", ROOT / "site" / "build.py")
bookbuild = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bookbuild)

import markdown  # noqa: E402

MD = markdown.Markdown(extensions=["tables", "fenced_code", "attr_list", "sane_lists"])
CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")


def cfg():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_front(text: str) -> str:
    """取第一行非空标题做显示名。"""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()
        if s:
            return s[:40]
    return ""


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(st: dict):
    DRAFTS.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def units() -> list:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = []
    for part in m.get("parts", []):
        for ch in part.get("chapters", []):
            out.append({"part": part.get("part", ""), "n": ch.get("n", ""),
                        "title": ch.get("title", ""), "file": ch.get("file", "")})
    have = {u["file"] for u in out}
    for p in sorted(BOOK.glob("*.md")):  # manifest 没收进去的也列出来
        if p.name not in have:
            out.append({"part": "（未列入目录）", "n": "", "title": p.name, "file": p.name})
    return out


def book_text(f: str) -> str:
    p = BOOK / f
    return p.read_text(encoding="utf-8") if p.exists() else ""


def draft_path(f: str) -> Path:
    return DRAFTS / f


def current_text(f: str) -> tuple:
    d = draft_path(f)
    if d.exists():
        return d.read_text(encoding="utf-8"), "draft"
    return book_text(f), "book"


def render(text: str) -> str:
    MD.reset()
    html = MD.convert(text)
    return bookbuild.decorate(bookbuild.autolink(html))


def lint(text: str) -> list:
    bad = []
    for w in bookbuild.BAN_WORDS:
        if w in text:
            if not any(x in text for x in ("老年心理关爱", "科学普及", "科学研究中心", "系统综述", "神经系统", "系统和更新")):
                bad.append(f"疑似禁用词：{w}")
    for h in re.findall(r"(?m)^#{2,4}\s*(.+)$", text):
        if h.strip().endswith("？") or h.strip().endswith("?"):
            bad.append(f"标题是问句（应改成动作/判断句）：{h.strip()[:24]}")
    if text.count("“") != text.count("”"):
        bad.append("中文引号不成对")
    if text.count("【") != text.count("】"):
        bad.append("【】不成对（分档角标）")
    if text.count("〔") != text.count("〕"):
        bad.append("〔〕不成对（待核/转引角标）")
    return bad[:8]


def git_commit(msg: str):
    try:
        subprocess.run(["git", "-C", str(ROOT), "add", "-A"], capture_output=True, timeout=20)
        subprocess.run(["git", "-C", str(ROOT), "-c", "user.email=editor@local",
                        "-c", "user.name=editor", "commit", "-qm", msg], capture_output=True, timeout=20)
    except Exception:
        pass


def post_webhook(payload: dict):
    c = cfg()
    url, secret = c.get("webhook_url", ""), c.get("webhook_secret", "")
    if not (url and secret):
        return "未配置 webhook"
    body = json.dumps(payload, ensure_ascii=False).encode()
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "X-Webhook-Timestamp": ts,
        "X-Webhook-Signature-V2": sig})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return f"HTTP {r.status}"
    except Exception as e:
        return f"推送失败：{e}"


PAGE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>变老说明书 · 书稿编辑台</title>
<style>
:root{--bg:#f7f6f2;--ink:#1e1c18;--line:#ddd8cc;--acc:#8a6d3b;--warn:#b45f06;--ok:#2f7d4f}
*{box-sizing:border-box}
body{margin:0;font:15px/1.7 -apple-system,"PingFang SC","Noto Sans SC",sans-serif;color:var(--ink);background:var(--bg)}
header{display:flex;align-items:center;gap:12px;padding:10px 14px;background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:9;flex-wrap:wrap}
header b{font-size:15px}
#stat{color:#6b6558;font-size:13px}
button{font:inherit;padding:6px 14px;border:1px solid var(--line);background:#fff;border-radius:8px;cursor:pointer}
button.primary{background:var(--acc);color:#fff;border-color:var(--acc)}
button.warn{color:var(--warn)}
main{display:grid;grid-template-columns:250px 1fr 1fr;height:calc(100vh - 53px)}
#list{overflow:auto;border-right:1px solid var(--line);background:#fff;padding:6px 0}
.part{padding:8px 12px;font-size:12px;color:#8a8377;background:#faf9f5;position:sticky;top:0}
.u{padding:6px 12px;cursor:pointer;font-size:13.5px;display:flex;gap:6px;align-items:center}
.u:hover{background:#f3f1ea}.u.on{background:#efe9dc;font-weight:600}
.dot{width:7px;height:7px;border-radius:50%;background:#ded9cc;flex:none}
.dot.d{background:#e0a000}.dot.s{background:var(--ok)}
#edit{display:flex;flex-direction:column;border-right:1px solid var(--line)}
textarea{flex:1;border:0;padding:16px 18px;font:14px/1.75 ui-monospace,Menlo,Consolas,monospace;resize:none;outline:none;background:#fffdf9}
#prev{overflow:auto;padding:18px 22px;background:#fff}
#prev h2{font-size:19px;margin:22px 0 8px}#prev h3{font-size:16px;margin:18px 0 6px}
#prev ul{padding-left:20px}#prev li{margin:3px 0}
.flag{background:#ffeec2;border-radius:4px;padding:0 4px;font-size:12px}
.grade{display:inline-block;border-radius:4px;padding:0 5px;font-size:12px;background:#e8eef7}
.gA{background:#d9ecd9}#prev a{color:#2d6cdf;word-break:break-all}
#msg{font-size:13px;color:var(--warn)}
#lint{font-size:12.5px;color:#8a6d3b;white-space:pre-wrap}
</style></head><body>
<header>
  <b>变老说明书 · 书稿编辑台</b>
  <button class="primary" onclick="save(false)">保存 (Ctrl+S)</button>
  <button onclick="revert()">撤掉本篇改动</button>
  <button class="primary" onclick="submitAll()">交稿</button>
  <span id="stat">读入中…</span><span id="msg"></span>
</header>
<main>
  <div id="list"></div>
  <div id="edit"><textarea id="ta" spellcheck="false"></textarea></div>
  <div id="prev"></div>
</main>
<script>
let units=[], cur=null, dirty=false, timer=null;
const ta=document.getElementById('ta'), prev=document.getElementById('prev');
const stat=document.getElementById('stat'), msg=document.getElementById('msg');
const lintBox=document.createElement('div'); lintBox.id='lint';
function setStat(t){stat.textContent=t}
async function j(url,opt){const r=await fetch(url,opt); if(!r.ok) throw new Error(await r.text()); return r.json()}
async function boot(){
  const d=await j('/api/units'); units=d.units;
  const list=document.getElementById('list'); list.innerHTML='';
  let last='';
  for(const u of units){
    if(u.part!==last){const p=document.createElement('div');p.className='part';p.textContent=u.part;list.appendChild(p);last=u.part}
    const el=document.createElement('div'); el.className='u'; el.dataset.f=u.file;
    el.innerHTML='<span class="dot"></span><span>'+(u.title||u.file)+'</span>';
    el.onclick=()=>open_($(u.file));
    el._file=u.file; list.appendChild(el);
  }
  refreshState(); setStat('共 '+units.length+' 个单元');
}
function $(f){return units.find(x=>x.file===f)}
async function open_(f){
  cur=f; document.querySelectorAll('.u').forEach(e=>e.classList.toggle('on',e._file===f));
  const d=await j('/api/doc?f='+encodeURIComponent(f));
  ta.value=d.text; dirty=false; paint(); setStat(f+'（'+(d.source==='draft'?'草稿':'现稿')+'）'+d.cjk+' 字');
}
function paint(){ prev.innerHTML=document.getElementById('__tpl').innerHTML; render() }
async function render(){
  if(!cur) return;
  const d=await j('/api/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:ta.value})});
  prev.innerHTML=d.html; lintBox.innerHTML=d.lint.length?('自检：'+d.lint.join('；')):'';
  prev.appendChild(lintBox);
  stat.textContent=cur+' ｜ '+d.cjk+' 字'+(dirty?'（未保存）':'');
}
ta.addEventListener('input',()=>{dirty=true; clearTimeout(timer); timer=setTimeout(render,900)});
document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key==='s'){e.preventDefault();save(false)}});
async function save(auto){
  if(!cur) return;
  const d=await j('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({f:cur,text:ta.value,auto:!!auto})});
  dirty=false; msg.textContent='已保存 '+d.saved_at+(auto?'（自动）':''); setTimeout(()=>msg.textContent='',2500); refreshState();
}
setInterval(()=>{if(dirty) save(true)}, 300000);
async function revert(){ if(!cur||!confirm('撤掉本篇的草稿改动，回到现稿？')) return; await j('/api/revert',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({f:cur})}); open_(cur); refreshState() }
async function submitAll(){
  const n=Object.values(state).filter(x=>x.draft).length;
  if(!confirm('交稿？共 '+n+' 个单元有草稿改动。交稿后我会拿你的版本和现稿逐条比对，再跟你确认。')) return;
  if(dirty) await save(false);
  const d=await j('/api/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  msg.textContent='已交稿 '+d.at+'，'+d.files.length+' 个单元；'+d.hook; refreshState();
}
let state={};
async function refreshState(){
  const s=await j('/api/state'); state=s.state||{};
  document.querySelectorAll('.u').forEach(e=>{
    const st=state[e._file]||{}; const dot=e.querySelector('.dot');
    dot.className='dot'+(st.submitted?' s':(st.draft?' d':''));
    e.title=st.draft?('草稿 '+(st.saved_at||'')+(st.submitted?'（已交稿）':'')):'';
  });
}
boot();
</script><div id="__tpl" style="display:none"></div></body></html>"""


class H(BaseHTTPRequestHandler):
    server_version = "BookDesk/1.0"

    def log_message(self, *a):
        pass

    # ── auth ──
    def ok(self):
        t = cfg().get("token", "")
        q = parse_qs(urlparse(self.path).query).get("t", [""])[0]
        ck = self.headers.get("Cookie", "")
        if q == t:
            return True
        return f"bk={t}" in ck

    def send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw or b"{}")
        except Exception:
            return {}

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            if not self.ok():
                return self.send(401, LOGIN, "text/html; charset=utf-8")
            c = cfg()
            return self.send(200, PAGE, "text/html; charset=utf-8",
                             {"Set-Cookie": f"bk={c['token']}; Path=/; Max-Age=2592000; SameSite=Lax"})
        if not self.ok():
            return self.send(401, '{"error":"unauthorized"}')
        if u.path == "/api/units":
            return self.send(200, json.dumps({"units": units()}, ensure_ascii=False))
        if u.path == "/api/doc":
            f = parse_qs(u.query).get("f", [""])[0]
            t, src = current_text(f)
            return self.send(200, json.dumps({"text": t, "source": src, "cjk": len(CJK.findall(t))}, ensure_ascii=False))
        if u.path == "/api/state":
            st = load_state()
            for f in st:
                st[f]["draft"] = draft_path(f).exists()
            return self.send(200, json.dumps({"state": st}, ensure_ascii=False))
        return self.send(404, '{"error":"not found"}')

    def do_POST(self):
        if not self.ok():
            return self.send(401, '{"error":"unauthorized"}')
        p = urlparse(self.path).path
        d = self.body()
        if p == "/api/render":
            t = d.get("text", "")
            return self.send(200, json.dumps({"html": render(t), "cjk": len(CJK.findall(t)), "lint": lint(t)}, ensure_ascii=False))
        if p == "/api/save":
            f, text = d.get("f", ""), d.get("text", "")
            if not f or not (BOOK / f).exists():
                return self.send(400, '{"error":"unknown file"}')
            DRAFTS.mkdir(parents=True, exist_ok=True)
            HISTORY.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            draft_path(f).write_text(text, encoding="utf-8")
            (HISTORY / f"{stamp}__{f}").write_text(text, encoding="utf-8")
            st = load_state()
            st[f] = {"saved_at": now(), "auto": bool(d.get("auto")), "chars": len(CJK.findall(text)),
                     "submitted": st.get(f, {}).get("submitted", False)}
            save_state(st)
            git_commit(f"草稿：{f} {st[f]['saved_at']}{'（自动）' if d.get('auto') else ''}")
            return self.send(200, json.dumps({"ok": True, "saved_at": st[f]["saved_at"]}, ensure_ascii=False))
        if p == "/api/revert":
            f = d.get("f", "")
            if draft_path(f).exists():
                draft_path(f).unlink()
            st = load_state()
            st.pop(f, None)
            save_state(st)
            git_commit(f"撤稿：{f} {now()}")
            return self.send(200, '{"ok":true}')
        if p == "/api/submit":
            st = load_state()
            changed = []
            for f in {u["file"] for u in units()}:
                if draft_path(f).exists() and draft_path(f).read_text(encoding="utf-8") != book_text(f):
                    changed.append(f)
                    st.setdefault(f, {})["submitted"] = True
            save_state(st)
            at = now()
            SUBMITTED.write_text(json.dumps({"at": at, "files": changed}, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
            git_commit(f"交稿：{at}（{len(changed)} 个单元）")
            hook = post_webhook({"event_type": "submitted", "at": at, "files": "、".join(changed)})
            return self.send(200, json.dumps({"ok": True, "at": at, "files": changed, "hook": hook}, ensure_ascii=False))
        return self.send(404, '{"error":"not found"}')


LOGIN = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<body style="font:16px/1.7 -apple-system,'PingFang SC',sans-serif;padding:12vh 6vw;color:#1e1c18;background:#f7f6f2">
<h2>变老说明书 · 书稿编辑台</h2><p>请输入访问口令（口令在我发给你的那条消息里）。</p>
<form method=get onsubmit="location='/?t='+encodeURIComponent(document.getElementById('t').value);return false">
<input id=t style="font:inherit;padding:8px 12px;border:1px solid #ddd8cc;border-radius:8px" placeholder="口令">
<button style="font:inherit;padding:8px 16px;border-radius:8px;border:1px solid #8a6d3b;background:#8a6d3b;color:#fff">进入</button>
</form></body>"""


def main():
    if not CONFIG.exists():
        CONFIG.write_text(json.dumps({"token": os.environ.get("BK_TOKEN", "change-me"),
                                      "port": 8792, "webhook_url": "", "webhook_secret": ""},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
        os.chmod(CONFIG, 0o600)
    port = int(cfg().get("port", 8792))
    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    print(f"编辑台已起：http://0.0.0.0:{port}/?t=<token>")
    srv.serve_forever()


if __name__ == "__main__":
    main()
