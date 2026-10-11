#!/usr/bin/env python3
"""验收「字大小」功能：真实 Chromium + CDP。

覆盖：默认档 / A+ A− 改档 / 存 localStorage / 换章节保持 / 刷新保持 /
恢复默认 / 极限档桌面与手机的横向溢出 / 控制台报错数 / 截图。
"""
import asyncio, base64, json, os, shutil, struct, subprocess, time, urllib.parse, urllib.request
import websockets

CHROME = "/home/ubuntu/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
PORT, PROFILE = 9361, "/tmp/cdp-fontscale"
BASE = os.environ.get("SITE_BASE", "http://127.0.0.1:8899/")   # SITE_BASE=https://aging.fly2ai.top/ 可跑线上验收
CH0 = BASE + urllib.parse.quote("00-第0章-这份说明书怎么用/")
CH1 = BASE + urllib.parse.quote("12-第12章-每天怎么吃/")
CONSOLE = []

SNAP = """(() => {
  const de = document.documentElement;
  const t = document.querySelector('.md-typeset');
  const pill = document.querySelector('.aging-font');
  const btn = s => pill ? pill.querySelector(s) : null;
  return {
    pill: !!pill,
    pct: pill ? pill.querySelector('.af-pct').textContent : null,
    varScale: de.style.getPropertyValue('--aging-scale'),
    htmlFont: getComputedStyle(de).fontSize,
    textFont: t ? getComputedStyle(t).fontSize : null,
    ls: (() => { try { return localStorage.getItem('aging-font-scale'); } catch (e) { return 'ERR'; } })(),
    decOff: btn('.af-dec') ? btn('.af-dec').disabled : null,
    incOff: btn('.af-inc') ? btn('.af-inc').disabled : null,
    hintOn: !!document.querySelector('.af-hint.af-on'),
    overX: de.scrollWidth - de.clientWidth,
    pillBox: pill ? (r => ({l: Math.round(r.left), b: Math.round(r.bottom), w: Math.round(r.width), h: Math.round(r.height)}))(pill.getBoundingClientRect()) : null,
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
                        CONSOLE.append(msg["params"]["exceptionDetails"].get("text"))
                    elif msg.get("id") == mid:
                        return msg.get("result", {})

            async def js(expr):
                r = await cmd("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
                return r.get("result", {}).get("value")

            async def goto(url, wait=1.5):
                await cmd("Page.navigate", url=url)
                await asyncio.sleep(wait)

            async def snap():
                return await js(SNAP)

            def chk(label, cond, extra=""):
                nonlocal ok
                ok = ok and bool(cond)
                results.append(f"{'✅' if cond else '❌'} {label}{(' — ' + extra) if extra else ''}")

            await cmd("Runtime.enable"); await cmd("Page.enable")
            await cmd("Emulation.setDeviceMetricsOverride", width=1280, height=900, deviceScaleFactor=2, mobile=False)

            # ① 首次访问（全新 profile，无 localStorage）
            await goto(CH0, 2.0)
            s = await snap()
            results.append("① 首次访问 " + json.dumps(s, ensure_ascii=False))
            chk("首次访问有「字大小」控件", s["pill"])
            chk("默认档 115%（读者反馈默认偏小）", s["pct"] == "115%", f"pct={s['pct']} html={s['htmlFont']} 正文={s['textFont']}")
            chk("未设置时不写 localStorage", s["ls"] in (None, ""), f"ls={s['ls']}")
            chk("默认档还能继续调小（100% 档存在）", s["decOff"] is False, f"decOff={s['decOff']}")
            chk("默认档桌面无横向溢出", s["overX"] <= 1, f"overX={s['overX']}")

            # ② 提示气泡
            await asyncio.sleep(1.6)
            s = await snap()
            chk("首次访问出现引导气泡", s["hintOn"])

            # ③ 点两次 A+
            await js("document.querySelector('.aging-font .af-inc').click()")
            await js("document.querySelector('.aging-font .af-inc').click()")
            await asyncio.sleep(0.4)
            s = await snap()
            results.append("③ 点两次 A+ " + json.dumps(s, ensure_ascii=False))
            chk("档位到 145%", s["pct"] == "145%", f"pct={s['pct']} html={s['htmlFont']} 正文={s['textFont']}")
            chk("localStorage 已记 1.45", s["ls"] == "1.45", f"ls={s['ls']}")
            chk("点过之后引导气泡收起", not s["hintOn"])

            # ④ 换章节（整页导航）
            await goto(CH1, 2.0)
            s = await snap()
            results.append("④ 换到第 12 章 " + json.dumps(s, ensure_ascii=False))
            chk("换章节后仍是 145%", s["pct"] == "145%", f"pct={s['pct']} varScale={s['varScale']}")
            _exp = round(20 * float(s["varScale"]))
            chk("换章节后 html 字号 == 20px×倍率（内联脚本先设过）", abs(float(s["htmlFont"][:-2]) - _exp) < 0.6, f"html={s['htmlFont']} 期望≈{_exp}px")

            # ⑤ 刷新
            await goto(CH1, 2.0)
            s = await snap()
            chk("刷新后仍是 145%", s["pct"] == "145%" and s["ls"] == "1.45", f"pct={s['pct']} ls={s['ls']}")

            # ⑤b 调到最小档，A− 应禁用
            for _ in range(6):
                await js("document.querySelector('.aging-font .af-dec').click()")
            await asyncio.sleep(0.4)
            s = await snap()
            chk("最小档 100% 且 A− 禁用", s["pct"] == "100%" and s["decOff"] is True, f"pct={s['pct']} decOff={s['decOff']} html={s['htmlFont']}")

            # ⑥ 顶到最大档
            for _ in range(8):
                await js("document.querySelector('.aging-font .af-inc').click()")
            await asyncio.sleep(0.4)
            s = await snap()
            results.append("⑥ 最大档 " + json.dumps(s, ensure_ascii=False))
            chk("最大档 185% 且 A+ 禁用", s["pct"] == "185%" and s["incOff"] is True, f"pct={s['pct']} incOff={s['incOff']}")
            chk("最大档桌面无横向溢出", s["overX"] <= 1, f"overX={s['overX']}")

            # ⑦ 手机视口
            await cmd("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
            await asyncio.sleep(0.6)
            s = await snap()
            results.append("⑦ 手机 390×844 @185% " + json.dumps(s, ensure_ascii=False))
            chk("手机最大档无横向溢出", s["overX"] <= 1, f"overX={s['overX']}")
            chk("控件在视口内可见", s["pillBox"] and s["pillBox"]["l"] >= 0 and s["pillBox"]["b"] <= s["vh"] + 1, f"{s['pillBox']} vh={s['vh']}")

            # ⑧ 恢复默认 + 手机默认档
            await js("document.querySelector('.aging-font .af-reset').click()")
            await asyncio.sleep(0.4)
            s = await snap()
            chk("点「字大小」回到默认 115%", s["pct"] == "115%" and s["ls"] == "1.15", f"pct={s['pct']} ls={s['ls']}")
            chk("手机默认档无横向溢出", s["overX"] <= 1, f"overX={s['overX']}")

            # ⑨ 截图（交给用户扫一眼）
            await cmd("Emulation.setDeviceMetricsOverride", width=1000, height=1100, deviceScaleFactor=2, mobile=False)
            await goto(CH1, 2.0)
            await js("document.querySelector('.aging-font .af-inc').click(); document.querySelector('.aging-font .af-inc').click();")
            await asyncio.sleep(0.5)
            shot = await cmd("Page.captureScreenshot", format="png")
            data = base64.b64decode(shot["data"])
            open("/tmp/fontscale-desktop.png", "wb").write(data)
            w, h = struct.unpack(">II", data[16:24])
            results.append(f"⑨ 截图 /tmp/fontscale-desktop.png {w}×{h} {len(data)//1024} KB")

            results.append(f"控制台 error/warning/异常：{len(CONSOLE)} 条 {CONSOLE[:3]}")
            chk("控制台 0 报错", len(CONSOLE) == 0)
    finally:
        proc.terminate()
        print("\n".join(results))
        print("判定：", "✅ 全部通过" if ok else "❌ 有未通过项")


asyncio.run(main())
