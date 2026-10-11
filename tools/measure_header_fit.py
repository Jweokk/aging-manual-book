#!/usr/bin/env python3
"""测量：把字号控件放进 Material 头部（白天黑夜按钮旁边）会不会挤坏。

做法：加载真实页面 → 记录头部各元素宽度 → 注入两个 32px 的模拟按钮 → 再量一次：
头部是否溢出、书名是否被截断、手机上是否仍够用。桌面 1280 / 平板 960 / 手机 390 三种视口。
"""
import asyncio, json, shutil, subprocess, time, urllib.parse, urllib.request
import websockets

CHROME = "/home/ubuntu/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
PORT, PROFILE = 9363, "/tmp/cdp-header-fit"
BASE = "https://aging.fly2ai.top/"
CH = BASE + urllib.parse.quote("12-第12章-每天怎么吃/")

MEASURE = """(() => {
  const inner = document.querySelector('.md-header__inner');
  const title = document.querySelector('.md-header__title');
  const opt = document.querySelector('.md-header__option');
  const search = document.querySelector('.md-search');
  const r = el => el ? el.getBoundingClientRect() : null;
  const kids = [...inner.children].map(el => ({
    cls: el.className.toString().slice(0, 28),
    w: Math.round(el.getBoundingClientRect().width),
    x: Math.round(el.getBoundingClientRect().left)
  }));
  return {
    vw: document.documentElement.clientWidth,
    innerW: Math.round(r(inner).width),
    overflow: inner.scrollWidth - inner.clientWidth,
    kids,
    titleTruncated: title ? title.scrollWidth > title.clientWidth + 1 : null,
    titleW: title ? Math.round(r(title).width) : null,
    optW: opt ? Math.round(r(opt).width) : null,
    searchW: search ? Math.round(r(search).width) : null,
    searchVisible: search ? r(search).width > 1 : null,
    gapBetweenTitleAndRight: title && opt ? Math.round(r(opt).left - (r(title).left + r(title).width)) : null
  };
})()"""


async def main():
    shutil.rmtree(PROFILE, ignore_errors=True)
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", "--no-sandbox",
                             "--disable-dev-shm-usage", "--disable-gpu", f"--user-data-dir={PROFILE}",
                             "--window-size=1280,900", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        async with websockets.connect(ws_url, max_size=20_000_000) as ws:
            i = [0]

            async def cmd(method, **params):
                i[0] += 1; mid = i[0]
                await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == mid:
                        return msg.get("result", {})

            async def js(expr):
                r = await cmd("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
                return r.get("result", {}).get("value")

            await cmd("Runtime.enable"); await cmd("Page.enable")

            for label, w, h, mobile in [("桌面 1280", 1280, 900, False), ("平板 960", 960, 900, False), ("手机 390", 390, 844, True)]:
                await cmd("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=2, mobile=mobile)
                await cmd("Page.navigate", url=CH)
                await asyncio.sleep(2.0)
                before = await js(MEASURE)
                # 注入两个 32px 的模拟按钮到头部右区（和白天黑夜按钮同一容器里，排它前面）
                await js("""(() => {
                  const inner = document.querySelector('.md-header__inner');
                  const opt = document.querySelector('.md-header__option');
                  const box = document.createElement('div');
                  box.id = '__mock_af';
                  box.style.cssText = 'display:flex;gap:2px;align-items:center;';
                  box.innerHTML = '<button style="width:32px;height:32px;padding:0;border:0;border-radius:4px;background:rgba(255,255,255,.12);color:#fff;font-size:13px;font-weight:700">A−</button>'
                                + '<button style="width:32px;height:32px;padding:0;border:0;border-radius:4px;background:rgba(255,255,255,.12);color:#fff;font-size:13px;font-weight:700">A+</button>';
                  opt.parentNode.insertBefore(box, opt);
                  return true;
                })()""")
                await asyncio.sleep(0.4)
                after = await js(MEASURE)
                print(f"── {label}（视口 {w}）")
                print("   加之前:", json.dumps(before, ensure_ascii=False))
                print("   加之后:", json.dumps(after, ensure_ascii=False))
                print(f"   → 头部溢出 {before['overflow']}px → {after['overflow']}px；书名被截断 {before['titleTruncated']} → {after['titleTruncated']}")
    finally:
        proc.terminate()


asyncio.run(main())
