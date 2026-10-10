#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键把校样站发布/更新到 https://aging.fly2ai.top（幂等，可反复跑）。

用法: python3 site/deploy.py [--skip-build]

流程：构建 → rsync → 容器 → （首次才）隧道入口 + DNS → 验证。
关键纪律：改隧道配置**先校验 YAML 再重启**；插条目要整行匹配（含缩进），
否则 cloudflared 会解析失败进入重启循环，把该隧道托管的全部站点打成 530。
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REMOTE = "dockervps"
REMOTE_DIR = "/home/ubuntu/aging-manual"
HOST = "aging.fly2ai.top"
PORT = 8099
TUNNEL = "e6dcc5d0-5a89-4af1-9181-e1999b663fe4"
ZONE = "a79e9241a26834e33effd858a68ee828"          # fly2ai.top
CFG = "~/.cloudflared/config.yml"
CATCH = "  - service: http_status:404"              # 注意：含两格缩进


def sh(cmd, host=REMOTE, timeout=120):
    r = subprocess.run(["ssh", host, cmd], capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()


def step(msg):
    print(f"\n=== {msg} ===")


def build():
    step("构建")
    subprocess.run([sys.executable, str(ROOT / "site" / "build.py")], check=True, cwd=str(ROOT))


def sync():
    step("同步到 dockervps")
    sh(f"mkdir -p {REMOTE_DIR}")
    subprocess.run(["rsync", "-a", "--delete", f"{ROOT}/site/dist/",
                    f"{REMOTE}:{REMOTE_DIR}/site/"], check=True)
    subprocess.run(["rsync", "-a",
                    f"{ROOT}/site/deploy/docker-compose.yml",
                    f"{ROOT}/site/deploy/nginx.conf",
                    f"{ROOT}/site/deploy/security-headers.conf",
                    f"{REMOTE}:{REMOTE_DIR}/"], check=True)
    print("已同步 site/index.html + nginx 配置")


def container():
    step("容器")
    print(sh(f"cd {REMOTE_DIR} && docker compose up -d 2>&1 | tail -3"))
    time.sleep(3)
    print(sh("docker ps --filter name=aging-preview --format '{{.Names}} {{.Status}} {{.Ports}}'"))
    print("回环:", sh(f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{PORT}/"))


def ingress():
    step("隧道入口")
    cfg = sh(f"cat {CFG}")
    if HOST in cfg:
        print("入口已存在，跳过")
        return
    assert CATCH in cfg, "找不到 catch-all，中止（不动配置）"
    assert HOST not in cfg, "入口已存在"
    new = cfg.replace(CATCH, f"  - hostname: {HOST}\n    service: http://localhost:{PORT}\n{CATCH}", 1)
    sh(f"cp {CFG} {CFG}.bak-{HOST.split('.')[0]}-$(date +%Y%m%d%H%M) && echo 已备份")
    subprocess.run(["ssh", REMOTE, f"cat > {CFG}"], input=new, text=True, check=True)
    # 先校验，再重启：校验不过就不重启
    val = sh(f"cloudflared --config {CFG} tunnel ingress validate 2>&1 | tail -2")
    print(val)
    if not val.strip().endswith("OK"):
        sh(f"cp {CFG}.bak-{HOST.split('.')[0]}-* {CFG} && echo 已回滚")
        sys.exit("YAML 校验未通过，配置已回滚，未重启隧道")
    sh("sudo systemctl stop cloudflared")
    time.sleep(3)
    sh("sudo systemctl start cloudflared")
    time.sleep(10)
    print("active:", sh("systemctl is-active cloudflared"),
          "| MainPID:", sh("systemctl show cloudflared -p MainPID --value"),
          "| 注册连接:", sh("journalctl -u cloudflared --since '40 sec ago' --no-pager "
                            "| grep -c 'Registered tunnel connection'"))


def dns():
    step("DNS")
    env = dict(l.strip().split("=", 1) for l in
               open(os.path.expanduser("~/.hermes/tokens.env"))
               if "=" in l and not l.startswith("#"))
    tok = env["CF_ZONE_TOKEN"]

    def cf(method, path, body=None):
        req = urllib.request.Request(
            "https://api.cloudflare.com/client/v4" + path,
            data=json.dumps(body).encode() if body else None, method=method,
            headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except urllib.error.HTTPError as e:
            return json.loads(e.read().decode())

    found = cf("GET", f"/zones/{ZONE}/dns_records?name={HOST}").get("result", [])
    body = {"type": "CNAME", "name": "aging", "content": f"{TUNNEL}.cfargotunnel.com",
            "proxied": True, "ttl": 1}
    if found:
        cf("PUT", f"/zones/{ZONE}/dns_records/{found[0]['id']}", {**body, "name": HOST})
        print("DNS 已更新")
    else:
        r = cf("POST", f"/zones/{ZONE}/dns_records", body)
        print("DNS 已创建:", r.get("success"), r.get("errors") or "")


def verify():
    step("验证")
    for url in [f"https://{HOST}/", "https://wolf.fly2ai.top/", "https://bgm.fly2ai.top/"]:
        code = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                               "--max-time", "30", url], capture_output=True, text=True).stdout
        print(f"  {url:34s} {code}")
    body = subprocess.run(["curl", "-s", "--max-time", "30", f"https://{HOST}/"],
                          capture_output=True, text=True).stdout
    print(f"  页面 {len(body.encode())} 字节"
          f"｜章节 {body.count(chr(60) + 'section class=\"chapter\"')}"
          f"｜外链 {body.count('href=\"http')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-build", action="store_true")
    a = ap.parse_args()
    if not a.skip_build:
        build()
    sync()
    container()
    ingress()
    dns()
    verify()
    print(f"\n完成：https://{HOST}/")
