#!/usr/bin/env python3
"""出两张交付截图：手机首访（页眉按钮 + 引导气泡）、桌面（浮层展开、默认档）。"""
import asyncio, base64, json, os, shutil, struct, subprocess, time, urllib.parse, urllib.request
import websockets

CHROME = "/home/ubuntu/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
import os, socket


def _free_port() -> int:
    """独享空闲端口 + 独立 profile：固定端口会让并行两次互相 attach（踩过的坑）。"""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = int(os.environ.get("CDP_PORT", _free_port()))
PROFILE = os.environ.get("CDP_PROFILE", f"/tmp/cdp-fontscale-shot-{os.getpid()}")
BASE = os.environ.get("SITE_BASE", "http://127.0.0.1:8899/")
CH1 = BASE + urllib.parse.quote("12-第12章-每天怎么吃/")


async def main():
    shutil.rmtree(PROFILE, ignore_errors=True)
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", "--no-sandbox",
                             "--disable-dev-shm-usage", "--disable-gpu", f"--user-data-dir={PROFILE}",
                             "--window-size=1000,1200", "about:blank"],
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
        async with websockets.connect(ws_url, max_size=30_000_000) as ws:
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

            async def shot(path, mobile, w, h, scale_after=None):
                await cmd("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=2, mobile=mobile)
                await cmd("Page.navigate", url=CH1)
                await asyncio.sleep(2.0)
                if scale_after == "open":
                    await js("document.querySelector('.aging-font__toggle').click()")
                    await asyncio.sleep(0.6)
                r = await cmd("Page.captureScreenshot", format="png")
                data = base64.b64decode(r["data"])
                open(path, "wb").write(data)
                pw, ph = struct.unpack(">II", data[16:24])
                print(f"{path}  {pw}×{ph}  {len(data)//1024} KB  字号={await js('document.querySelector(\".aging-font .af-pct\").textContent')}")

            await cmd("Runtime.enable"); await cmd("Page.enable")
            await js("localStorage.clear()") if False else None
            await shot("/tmp/af-mobile.png", True, 390, 844, None)     # 手机首访：页眉「字号」+ 引导气泡
            await shot("/tmp/af-desktop.png", False, 1000, 1100, "open")  # 桌面：浮层展开，默认档
    finally:
        proc.terminate()


asyncio.run(main())
