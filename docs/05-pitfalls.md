# 05 · 踩坑清单

都是真实踩过的坑，按"你会遇到"的概率排序。

---

## 1. Windows 中文乱码 / UnicodeEncodeError

**现象**：`UnicodeEncodeError: 'gbk' codec can't encode character`

**原因**：PowerShell 默认 GBK，Python 输出中文直接炸。

**修复**：

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
```

或者脚本开头：

```python
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
```

---

## 2. RPC 的 `eth_getLogs` 各种限制

| 症状 | 原因 | 解决 |
|---|---|---|
| `limit exceeded` | 单次区块范围太大 | 降到 5000~10000 块/次 |
| `403 Forbidden` | 公共节点封了 getLogs | 换节点（试 3 个以上） |
| 返回空数组 | 节点不支持该 topic 过滤 | 换 RPC |

**经验**：`eth_call` 和 `eth_getBalance` 用公共节点没问题，
`eth_getLogs` 最好单独准备一个稳定节点。

```python
RPCS = ["https://rpc-a.example", "https://rpc-b.example", "https://rpc-c.example"]

def rpc_with_fallback(payload):
    for url in RPCS:
        try:
            return post(url, payload)
        except Exception:
            continue
    raise RuntimeError("all rpcs failed")
```

---

## 3. 公共节点没有 archive 数据

**现象**：查几万块之前的状态，`eth_call` 报 `missing trie node` 或直接 revert。

**解决**：
- 只能查最近 ~3000 块内的历史状态
- 更早的数据用**事件扫描**重建（`eth_getLogs` + 自己算）
- 或者用第三方索引（Dune / Covalent / 项目方 API）

---

## 4. 地址簿阻止转账

**现象**：

```json
{"success": false, "error": {"code": "...", "message": "recipient not in address book"}}
```

**解决**：见 [02-daily-ops.md · 2.3](02-daily-ops.md)

- 首选：合约 `transfer(address,uint256)` 调用
- 备选：WBNB 包装 + 中转

---

## 5. `BROADCASTED` 不等于成功

```json
{"status": "BROADCASTED", "txHash": "0x..."}
```

这只是"已广播"。**必须**：

```bash
eth_getTransactionReceipt(txHash) → status == "0x1"
```

否则可能 revert 了你还以为成功。

---

## 6. nonce 冲突 / 交易卡住

**原因**：连续发多笔，前一笔还没上链就发下一笔。

**解决**：
- 每笔之间 `sleep 2~4` 秒
- 批量操作前先确认上一笔 receipt
- 卡住了就等，或用同 nonce 更高 gas 覆盖（谨慎）

---

## 7. 定时任务双跑（最坑的一种）

**现象**：明明 `systemctl stop` 了，脚本还在跑。

**原因**：`crontab` 里还留着一条。

**排查顺序**（缺一不可）：

```bash
systemctl list-timers --all | grep -i 你的任务名
crontab -l
sudo crontab -l
ps -ef | grep -E "bot|mint|loop" | grep -v grep
```

**清理**：

```bash
systemctl disable --now xxx.timer
crontab -l | grep -v xxx | crontab -
sudo rm -f /etc/systemd/system/xxx.service /etc/systemd/system/xxx.timer
sudo systemctl daemon-reload
```

---

## 8. "Day" 是按 UTC 算的

项目里的"每天额度重置"通常是 **UTC 00:00**：

| 时区 | 重置时间 |
|---|---|
| UTC | 00:00 |
| 北京（UTC+8） | **08:00** |
| 纽约（UTC-5） | 前一天 19:00 |

**别在北京时间 0 点去抢额度**，那时候还没重置。

---

## 9. 额度会变（邀请裂变）

很多项目的额度 = 基础额度 + 邀请人数。你今天打满 5 份，
邀请 3 个人后额度可能变成 8，**还能再打 3 份**。

打之前永远重新读一次 `quota`，不要用缓存值。

---

## 10. 小数精度

- 代币一般 18 位小数，USDT 在 BSC 是 18 位，在 TRON 是 6 位
- 计算金额一律用 **整数最小单位**，最后再除
- 浮点数直接乘 1e18 会精度丢失：

```python
amount_raw = int(Decimal("0.003") * 10**18)   # ✅
amount_raw = int(0.003 * 1e18)                # ❌ 可能差 1 wei
```

差 1 wei 也可能导致 `BadPayment` 类的 revert。

---

## 11. 时间戳/时区混用

链上时间戳是 UTC 秒。展示给用户时记得转换：

```python
from datetime import datetime, timezone, timedelta
TZ = timezone(timedelta(hours=8))
datetime.fromtimestamp(ts, TZ).strftime("%m-%d %H:%M")
```

**对账时统一用 UTC**，展示时再转本地时区，避免"差 8 小时"的对账灾难。

---

## 12. 看板缓存把新数据挡住了

浏览器缓存 + 反向代理缓存 + 后端缓存，三层都可能给你旧数据。

```python
# 后端：加 no-store
self.send_header("Cache-Control", "no-store")

# 前端：fetch 加 cache: 'no-store'
fetch(url, {cache: 'no-store'})
```

改完看板先 **Ctrl+Shift+R 强刷**，再怀疑代码。

---

## 13. 静态资源改了但页面没变

如果前端是**编译产物**（Next.js / Vite build），改了源码目录不等于生效：

- 确认服务实际运行目录（`readlink /proc/<pid>/cwd`）
- 如果跑在 Docker 里，宿主机改文件没用，要 `docker cp` 进去或重建镜像
- 改了 chunk 记得重启进程（服务端渲染的部分有内存缓存）

---

## 14. 编码类错误：`0x` 开头的 selector 传错

```python
call(contract, "0x70a08231", args)   # 有些工具会自动再哈希一次！
```

**症状**：明明对的函数却 revert 且返回 `0x`。

**排查**：打印最终 calldata，确认前 4 字节就是你要的 selector，
而不是 selector 的哈希。
