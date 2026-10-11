#!/usr/bin/env python3
"""验收页眉里的「字号」控件：真实 Chromium + CDP。

覆盖：挂在页眉且与白天黑夜按钮同区 / 浮层默认收起 / 加减档与边界禁用 /
localStorage 持久化 / 换章节与刷新后保持 / 点外部与 Esc 收起 / 恢复默认 /
三种视口在最大档无横向溢出、页眉不溢出 / 书名截断情况 / 控制台报错数 / 截图。

本地：先 `mkdocs build --strict`，再在 build/site 起 http.server 8899。
线上：SITE_BASE=https://aging.fly2ai.top/ python3 tools/verify_fontscale.py
"""
import asyncio, base64, json, os, shutil, struct, subprocess, time, urllib.parse, urllib.request
import websockets

CHROME = "/home/ubuntu/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
PORT, PROFILE = 9361, "/tmp/cdp-fontscale"
BASE = os.environ.get("SITE_BASE", "http://127.0.0.1:8899/")
CH0 = BASE + urllib.parse.quote("00-第0章-这份说明书怎么用/")
CH1 = BASE + urllib.parse.quote("12-第12章-每天怎么吃/")
CONSOLE = []

SNAP = """(() => {
  const de = document.documentElement;
  const t = document.querySelector('.md-typeset');
  const box = document.querySelector('.aging-font');
  const pop = box ? box.querySelector('.aging-font__pop') : null;
  const head = document.querySelector('.md-header__inner');
  const opt = document.querySelector('.md-header__option');
  const title = document.querySelector('.md-header__title');
  const r = el => el ? el.getBoundingClientRect() : null;
  const q = s => box ? box.querySelector(s) : null;
  return {
    mounted: !!box,
    place: box ? box.dataset.place : null,
    inHeader: !!(box && head && head.contains(box)),
    isSiblingOfPalette: !!(box && opt && box.parentNode === opt.parentNode && box.nextElementSibling === opt),
    toggleText: box ? box.querySelector('.aging-font__toggle').textContent.trim() : null,
    expanded: box ? box.querySelector('.aging-font__toggle').getAttribute('aria-expanded') : null,
    popHidden: pop ? pop.hidden : null,
    popVisible: pop ? (!pop.hidden && r(pop).width > 10) : null,
    pct: q('.af-pct') ? q('.af-pct').textContent : null,
    resetText: q('.af-reset') ? q('.af-reset').textContent : null,
    varScale: de.style.getPropertyValue('--aging-scale'),
    htmlFont: parseFloat(getComputedStyle(de).fontSize),
    textFont: t ? getComputedStyle(t).fontSize : null,
    ls: (() => { try { return localStorage.getItem('aging-font-scale'); } catch (e) { return 'ERR'; } })(),
    decOff: q('.af-dec') ? q('.af-dec').disabled : null,
    incOff: q('.af-inc') ? q('.af-inc').disabled : null,
    hintOn: !!document.querySelector('.af-hint.af-on'),
    headerOverflow: head ? head.scrollWidth - head.clientWidth : null,
    pageOverflow: de.scrollWidth - de.clientWidth,
    titleTruncated: title ? title.scrollWidth > title.clientWidth + 1 : null,
    titleW: title ? Math.round(r(title).width) : null,
    hintBox: (() => { const h = document.querySelector('.af-hint'); if (!h || !h.classList.contains('af-on')) return null;
      const b = r(h); return {l: Math.round(b.left), r: Math.round(b.right), t: Math.round(b.top)}; })(),
    popBox: pop && !pop.hidden ? (b => ({l: Math.round(b.left), r: Math.round(b.right), b: Math.round(b.bottom)}))(r(pop)) : null,
    popHit: (pop && !pop.hidden) ? (() => {
      const b = r(pop);
      const x = Math.round(b.left + b.width / 2), y = Math.round(b.top + Math.min(18, b.height / 2));
      const el = document.elementFromPoint(x, y);
      return !!(el && pop.contains(el));
    })() : null,
    vw: de.clientWidth, vh: de.clientHeight
  };
})()"""


async def main():
    shutil.rmtree(PROFILE, ignore_errors=True)
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", "--no-sandbox",
                             "--disable-dev-shm-usage", "--disable-gpu", f"--user-data-dir={PROFILE}",
                             "--window-size=1280,900", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    results, ok = [], True
    try:
        ws_url = None
        for _ in range(80):
            time.sleep(0.5)
            try:
                pages = [t for t in json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=5).read())
                         if t.get("type") == "page"]
                if pages:
                    ws_url = pages[0]["webSocketDebuggerUrl"]; break
            except Exception:
                pass
        async with websockets.connect(ws_url, max_size=30_000_000) as ws:
            i = [0]

            async def cmd(method, **params):
                i[0] += 1; mid = i[0]
                await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
                while True:
                    msg = json.loads(await ws.recv())
                    m = msg.get("method")
                    if m == "Runtime.consoleAPICalled":
                        p = msg["params"]
                        if p.get("type") in ("error", "warning"):
                            CONSOLE.append(" ".join(str(a.get("value", a.get("description", ""))) for a in p.get("args", [])))
                    elif m == "Runtime.exceptionThrown":
                        _d = msg["params"]["exceptionDetails"]
                        CONSOLE.append(((_d.get("exception") or {}).get("description") or _d.get("text") or "")[:200])
                    elif msg.get("id") == mid:
                        return msg.get("result", {})

            async def js(expr):
                r = await cmd("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
                return r.get("result", {}).get("value")

            async def goto(url, wait=1.8):
                await cmd("Page.navigate", url=url)
                await asyncio.sleep(wait)

            def chk(label, cond, extra=""):
                nonlocal ok
                ok = ok and bool(cond)
                results.append(f"{'✅' if cond else '❌'} {label}{(' — ' + extra) if extra else ''}")

            await cmd("Runtime.enable"); await cmd("Page.enable")
            await cmd("Emulation.setDeviceMetricsOverride", width=1280, height=900, deviceScaleFactor=2, mobile=False)

            # ① 首次访问
            await goto(CH0, 2.0)
            s = await js(SNAP)
            results.append("① 首次访问 " + json.dumps(s, ensure_ascii=False))
            chk("控件已挂上", s["mounted"])
            chk("挂在页眉里", s["inHeader"] and s["place"] == "header", f"place={s['place']}")
            chk("就在白天黑夜按钮前面", s["isSiblingOfPalette"])
            chk("按钮文字是「字号」", s["toggleText"] == "字号", f"text={s['toggleText']}")
            chk("浮层默认收起（不常驻）", s["popHidden"] is True)
            chk("默认档 115%", s["pct"] == "115%" and abs(s["htmlFont"] - 23) < 0.6, f"pct={s['pct']} html={s['htmlFont']}px 正文={s['textFont']}")
            chk("未设置时不写 localStorage", s["ls"] in (None, ""))
            chk("恢复默认按钮写明了默认值", s["resetText"] and "115%" in s["resetText"], f"{s['resetText']}")

            await asyncio.sleep(1.6)
            s = await js(SNAP)
            chk("首次访问出现引导气泡", s["hintOn"])

            # ② 点开浮层 + 调两档
            await js("document.querySelector('.aging-font__toggle').click()")
            await asyncio.sleep(0.3)
            s = await js(SNAP)
            chk("点「字号」展开浮层", s["popVisible"] is True and s["expanded"] == "true", f"popVisible={s['popVisible']}")
            chk("浮层没跑出视口", s["popBox"] and s["popBox"]["l"] >= 0 and s["popBox"]["r"] <= s["vw"], f"{s['popBox']} vw={s['vw']}")
            chk("浮层没被页眉裁掉", s["popHit"] is True, f"popHit={s['popHit']}")
            chk("展开后引导气泡收起", not s["hintOn"])

            await js("document.querySelector('.aging-font .af-inc').click()")
            await js("document.querySelector('.aging-font .af-inc').click()")
            await asyncio.sleep(0.4)
            s = await js(SNAP)
            results.append("② 点两次 A+ " + json.dumps(s, ensure_ascii=False))
            chk("到 145%（html 字号 = 20px×倍率）", abs(s["htmlFont"] - 29) < 0.6 and s["pct"] == "145%", f"pct={s['pct']} html={s['htmlFont']}px 正文={s['textFont']}")
            chk("localStorage 记 1.45", s["ls"] == "1.45")

            # ③ 点外部 / Esc 收起
            await js("document.querySelector('.md-header__title').click()")
            await asyncio.sleep(0.3)
            chk("点控件外部自动收起", (await js(SNAP))["popHidden"] is True)
            await js("document.querySelector('.aging-font__toggle').click()")
            await asyncio.sleep(0.2)
            await js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
            await asyncio.sleep(0.3)
            chk("按 Esc 也收起", (await js(SNAP))["popHidden"] is True)

            # ④ 换章节
            await goto(CH1, 2.0)
            s = await js(SNAP)
            results.append("④ 换到第 12 章 " + json.dumps(s, ensure_ascii=False))
            chk("换章节后仍是 145%", s["pct"] == "145%" and s["ls"] == "1.45", f"pct={s['pct']}")
            chk("换章节后控件仍在页眉", s["inHeader"] and s["isSiblingOfPalette"])
            await js("document.querySelector('.aging-font__toggle').click()")
            await asyncio.sleep(0.3)
            s = await js(SNAP)
            chk("换章节后展开仍显示 145%", s["pct"] == "145%" and s["popVisible"] is True)

            # ⑤ 刷新
            await goto(CH1, 2.0)
            s = await js(SNAP)
            chk("刷新后仍是 145%", s["pct"] == "145%" and s["ls"] == "1.45", f"pct={s['pct']} ls={s['ls']}")

            # ⑥ 最小档
            await js("document.querySelector('.aging-font__toggle').click()")
            for _ in range(6):
                await js("document.querySelector('.aging-font .af-dec').click()")
            await asyncio.sleep(0.4)
            s = await js(SNAP)
            chk("最小档 100% 且 A− 禁用", s["pct"] == "100%" and s["decOff"] is True, f"pct={s['pct']} html={s['htmlFont']}px")
            chk("100% 时 = Material 原字号", abs(s["htmlFont"] - 20) < 0.6, f"html={s['htmlFont']}px")

            # ⑦ 最大档 + 三种视口
            for _ in range(8):
                await js("document.querySelector('.aging-font .af-inc').click()")
            await asyncio.sleep(0.4)
            for label, w, h, mobile in [("桌面 1280", 1280, 900, False), ("平板 960", 960, 900, False), ("手机 390", 390, 844, True)]:
                await cmd("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=2, mobile=mobile)
                await asyncio.sleep(0.6)
                s = await js(SNAP)
                results.append(f"⑦ {label} @185% " + json.dumps(s, ensure_ascii=False))
                chk(f"{label}：页眉不溢出", s["headerOverflow"] <= 0, f"headerOverflow={s['headerOverflow']}")
                chk(f"{label}：整页无横向溢出", s["pageOverflow"] <= 1, f"pageOverflow={s['pageOverflow']}")
                chk(f"{label}：浮层没跑出视口", s["popBox"] and s["popBox"]["l"] >= 0 and s["popBox"]["r"] <= s["vw"], f"{s['popBox']}")
                chk(f"{label}：浮层没被页眉裁掉", s["popHit"] is True, f"popHit={s['popHit']}")
            s = await js(SNAP)
            chk("最大档 185% 且 A+ 禁用", s["pct"] == "185%" and s["incOff"] is True, f"pct={s['pct']}")

            # ⑧ 恢复默认
            await js("document.querySelector('.aging-font .af-reset').click()")
            await asyncio.sleep(0.4)
            s = await js(SNAP)
            chk("点「恢复默认」回到 115%", s["pct"] == "115%" and s["ls"] == "1.15", f"pct={s['pct']} ls={s['ls']}")

            # ⑩ 手机首次访问：引导气泡必须整个在屏幕里（这次踩过的坑：居中定位在小屏顶出右侧 69px）
            await cmd("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
            await js("localStorage.removeItem('aging-font-scale-hint')")
            await cmd("Page.navigate", url=CH1)
            await asyncio.sleep(2.4)
            s = await js(SNAP)
            results.append("⑩ 手机首次访问气泡 " + json.dumps(s, ensure_ascii=False))
            chk("手机首访出现气泡", s["hintBox"] is not None)
            chk("气泡整个在视口内（不顶出屏幕）", s["hintBox"] and s["hintBox"]["l"] >= 0 and s["hintBox"]["r"] <= s["vw"], f"{s['hintBox']} vw={s['vw']}")
            chk("手机首访无横向溢出", s["pageOverflow"] <= 1, f"pageOverflow={s['pageOverflow']}")

            # ⑨ 截图（交用户扫一眼）
            await cmd("Emulation.setDeviceMetricsOverride", width=1000, height=1100, deviceScaleFactor=2, mobile=False)
            await goto(CH1, 2.0)
            await js("document.querySelector('.aging-font__toggle').click(); document.querySelector('.aging-font .af-inc').click(); document.querySelector('.aging-font .af-inc').click();")
            await asyncio.sleep(0.6)
            shot = await cmd("Page.captureScreenshot", format="png")
            data = base64.b64decode(shot["data"])
            open("/tmp/fontscale-header.png", "wb").write(data)
            pw, ph = struct.unpack(">II", data[16:24])
            results.append(f"⑨ 截图 /tmp/fontscale-header.png {pw}×{ph} {len(data)//1024} KB")

            results.append(f"控制台 error/warning/异常：{len(CONSOLE)} 条 {CONSOLE[:3]}")
            chk("控制台 0 报错", len(CONSOLE) == 0)
    finally:
        proc.terminate()
        print("\n".join(results))
        print("判定：", "✅ 全部通过" if ok else "❌ 有未通过项")


asyncio.run(main())
