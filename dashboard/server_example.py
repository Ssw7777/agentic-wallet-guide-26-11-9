#!/usr/bin/env python3
"""多钱包资产看板 —— 单文件示例（脱敏版）。

启动：
    python3 server_example.py
    curl -s http://127.0.0.1:8098/data

自定义：
    1) 改 WALLETS（地址用你自己的，仓库里只放占位符）
    2) 改 TOKENS（要看哪些代币）
    3) 改 PORT（默认 8098）

设计要点：
    - 只监听 127.0.0.1，公网访问交给反向代理（Caddy/Nginx）
    - 60 秒内存缓存，避免刷爆 RPC
    - 前端纯静态，无构建
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import request

# ------------------------------------------------------------------ 配置

PORT = int(os.environ.get("DASH_PORT", "8098"))
TZ = timezone(timedelta(hours=8))

RPC_URLS = [
    "https://bsc-dataseed.bnbchain.org",
    "https://bsc-rpc.publicnode.com",
]

# 占位地址，换成自己的
WALLETS = [
    ("w1", "主号", "0x0000000000000000000000000000000000000001"),
    ("w2", "子号A", "0x0000000000000000000000000000000000000002"),
]

# (显示名, 合约地址, 小数位)
TOKENS = [
    ("USDT", "0x55d398326f99059fF775485246999027B3197955", 18),
]

CACHE_TTL = 60
_cache: dict = {"t": 0.0, "data": None}


# ------------------------------------------------------------------ RPC

def rpc(method: str, params: list, timeout: int = 15):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last = None
    for url in RPC_URLS:
        try:
            req = request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode())
            if "error" in body:
                last = body["error"]
                continue
            return body["result"]
        except Exception as exc:  # noqa: BLE001
            last = exc
            continue
    raise RuntimeError(f"rpc failed: {last}")


def word(value: int) -> str:
    return f"{value:064x}"


def word_addr(addr: str) -> str:
    return "0" * 24 + addr.lower().replace("0x", "")


def eth_call(to: str, data: str) -> str:
    return rpc("eth_call", [{"to": to, "data": data}, "latest"])


def native_balance(addr: str) -> float:
    return int(rpc("eth_getBalance", [addr, "latest"]), 16) / 1e18


def token_balance(token: str, addr: str, decimals: int) -> float:
    raw = eth_call(token, "0x70a08231" + word_addr(addr))
    return int(raw, 16) / 10 ** decimals if raw and raw != "0x" else 0.0


def bnb_price_usd() -> float:
    """BNB 价格：用 WBNB/USDT 池子现算，避免依赖外部 API。"""
    try:
        pair = "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE"  # WBNB/USDT
        reserves = eth_call(pair, "0x0902f1ac")
        body = reserves[2:]
        r0 = int(body[0:64], 16)
        r1 = int(body[64:128], 16)
        # token0 一般是 WBNB
        bnb, usdt = r0 / 1e18, r1 / 1e18
        return usdt / bnb if bnb else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


# ------------------------------------------------------------------ 数据

def build() -> dict:
    bu = bnb_price_usd()
    rows = []
    total_usd = 0.0
    for key, name, addr in WALLETS:
        bnb = native_balance(addr)
        tokens = []
        usd = bnb * bu
        for sym, token_addr, dec in TOKENS:
            bal = token_balance(token_addr, addr, dec)
            if bal > 0:
                tokens.append({"symbol": sym, "balance": bal})
                usd += bal  # 稳定币按 1:1
        total_usd += usd
        rows.append({
            "key": key, "name": name, "address": addr,
            "bnb": bnb, "tokens": tokens, "usd": usd,
        })

    now = int(time.time())
    return {
        "updated": now,
        "updatedText": datetime.fromtimestamp(now, TZ).strftime("%m-%d %H:%M:%S"),
        "bnbUsd": bu,
        "wallets": rows,
        "totals": {"usd": total_usd},
    }


def get_data() -> dict:
    if time.time() - _cache["t"] > CACHE_TTL or _cache["data"] is None:
        try:
            _cache["data"] = build()
            _cache["t"] = time.time()
        except Exception:  # noqa: BLE001
            if _cache["data"] is None:
                raise
    return _cache["data"]


# ------------------------------------------------------------------ HTML

HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>钱包看板</title>
<style>
:root{--bg:#f6f6f3;--card:#fff;--line:#e6e4dd;--txt:#16160f;--mut:#7a7a70;--acc:#b4530a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:20px;margin:0 0 4px}h1 span{color:var(--acc)}
.sub{color:var(--mut);font-size:12px;margin-bottom:18px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{padding:9px 11px;text-align:right;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums;white-space:nowrap}
th{color:var(--mut);font-weight:500;font-size:12px;background:#fbfbf9}
th:first-child,td:first-child{text-align:left}
tfoot td{background:#fbfbf9;font-weight:650}
.mono{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:var(--mut)}
</style></head><body><div class="wrap">
<h1>钱包看板 <span>·</span> 多号资产</h1>
<div class="sub">每 30 秒刷新 · 最后更新 <b id="up">--</b></div>
<table><thead><tr><th>钱包</th><th>BNB</th><th>代币</th><th>合计 USD</th></tr></thead>
<tbody id="tb"><tr><td colspan="4" style="text-align:center;color:#7a7a70;padding:18px">读取中…</td></tr></tbody>
<tfoot id="tf"></tfoot></table>
</div>
<script>
function fmt(n,d){d=d===undefined?2:d;return Number(n||0).toLocaleString('en-US',{maximumFractionDigits:d});}
async function tick(){
  var d;
  try{var r=await fetch('data',{cache:'no-store'});d=await r.json();}catch(e){return;}
  document.getElementById('up').textContent=d.updatedText;
  document.getElementById('tb').innerHTML=d.wallets.map(function(w){
    var t=w.tokens.length?w.tokens.map(function(x){return x.symbol+' '+fmt(x.balance,2);}).join(' · '):'—';
    return '<tr><td>'+w.name+'<div class="mono">'+w.address.slice(0,6)+'\\u2026'+w.address.slice(-4)+'</div></td>'
      +'<td>'+fmt(w.bnb,6)+'</td><td>'+t+'</td><td>$'+fmt(w.usd,2)+'</td></tr>';
  }).join('');
  document.getElementById('tf').innerHTML='<tr><td>合计</td><td colspan="2"></td><td>$'+fmt(d.totals.usd,2)+'</td></tr>';
}
tick();setInterval(tick,30000);
</script></body></html>"""


# ------------------------------------------------------------------ 服务

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 静默
        return

    def do_GET(self):  # noqa: N802
        try:
            if self.path.startswith("/data"):
                body = json.dumps(get_data(), ensure_ascii=False).encode()
                ctype = "application/json"
            else:
                body = HTML.encode()
                ctype = "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:  # noqa: BLE001
            msg = json.dumps({"error": str(exc)[:200]}).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"dashboard on http://127.0.0.1:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
