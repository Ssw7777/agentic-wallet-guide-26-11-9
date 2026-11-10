# 看板部署：单文件 Python + Caddy + systemd

目标：10 分钟把多钱包资产看板挂到自己的域名下，手机也能看。

## 架构

```
浏览器
  │  HTTPS
  ▼
Caddy（自动 HTTPS + 基础认证）
  │  reverse_proxy 127.0.0.1:8098
  ▼
server_example.py（http.server，单文件）
  │  eth_call / baw CLI
  ▼
BSC RPC
```

**关键设计**：

- 服务只监听 `127.0.0.1`，**绝不直接暴露公网端口**
- 认证放在 Caddy，Python 不管登录
- 数据用 60 秒内存缓存，避免刷爆 RPC
- 前端纯静态 HTML，无构建步骤

## 1. 准备

```bash
sudo apt update && sudo apt install -y python3-venv
mkdir -p /opt/wallet-dash /opt/wallet-dash/logs
python3 -m venv /opt/wallet-dash/venv
/opt/wallet-dash/venv/bin/pip install requests
```

## 2. 放代码

```bash
cp server_example.py /opt/wallet-dash/server.py
# 编辑 WALLETS 列表，填入你自己的地址（或用占位地址先跑通）
vim /opt/wallet-dash/server.py
```

## 3. systemd 常驻

`/etc/systemd/system/wallet-dash.service`：

```ini
[Unit]
Description=Wallet dashboard
After=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/wallet-dash
ExecStart=/opt/wallet-dash/venv/bin/python /opt/wallet-dash/server.py
Restart=always
RestartSec=5
StandardOutput=append:/opt/wallet-dash/logs/access.log
StandardError=append:/opt/wallet-dash/logs/error.log

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now wallet-dash
systemctl status wallet-dash --no-pager
curl -s http://127.0.0.1:8098/data | head -c 300
```

## 4. Caddy 反代 + 认证

`/etc/caddy/Caddyfile`：

```caddyfile
wallet.example.com {
    handle_path /dash/* {
        reverse_proxy 127.0.0.1:8098
    }
    handle {
        respond "not found" 404
    }
}
```

加基础认证（强烈建议）：

```bash
caddy hash-password --plaintext '你的密码'
# 把输出的 hash 填到下面的 basicauth 里
```

```caddyfile
wallet.example.com {
    basicauth {
        admin <上一步生成的hash>
    }
    handle_path /dash/* {
        reverse_proxy 127.0.0.1:8098
    }
}
```

```bash
sudo systemctl reload caddy
```

访问 `https://wallet.example.com/dash/` 即可。

> Caddy 会自动申请证书。域名要先解析到服务器 IP。

## 5. 前端刷新策略

| 层 | 策略 |
|---|---|
| 浏览器 | `fetch(url, {cache: 'no-store'})` + 前端 `setInterval` 轮询 |
| 后端 | `Cache-Control: no-store` + 60s 内存缓存 |
| 代理 | Caddy 默认不缓存动态响应，不用管 |

## 6. 多页面扩展

同一个 `http.server` 可以挂多个路径：

```
/          项目看板
/balances  钱包余额明细
/other     另一个项目
/data      各页面的 JSON（/balances/data 等）
```

路由用一个 `if self.path.startswith(...)` 链即可，不需要框架。

## 7. 安全清单

- [ ] 只监听 `127.0.0.1`
- [ ] 有 HTTPS（Caddy 自动）
- [ ] 有认证（basicauth 或 IP 白名单）
- [ ] 不展示完整地址（只展示前 6 后 4）
- [ ] 日志里不打印私钥 / session
- [ ] 服务器防火墙只开 22 / 80 / 443

## 8. 排错

| 现象 | 原因 | 解决 |
|---|---|---|
| 502 | 服务没起 | `systemctl status` + 看 error.log |
| 页面 200 但数据空 | 缓存没刷 / RPC 挂了 | `curl 127.0.0.1:8098/data` |
| 数据一直是旧的 | 浏览器缓存 | Ctrl+Shift+R / 加 no-store |
| 证书报错 | 域名没解析 / 80 被墙 | 检查 DNS 和防火墙 |
