# 脚本组织方式

不要把逻辑塞进"一次性命令"，也不要写"跑一次就忘"的脚本。
推荐这套结构，每个文件只做一件事。

```
tools/
├── kit.py          基础设施：钱包切换、RPC、calldata 构造、预览/执行
├── w.py            单钱包操作：status / balance / send / swap / approve
├── mint.py         铸造：幂等、额度感知、gas 预留
├── claim.py        领取：扫描到期仓位、批量领取
└── cycle.py        日常循环：领取 → 归集 → 出金
```

## kit.py 必须提供的 6 个函数

```python
def ssh_run(cmd: str) -> str:          # 远程执行（或本地直跑）
def baw(wallet: str, *args) -> dict:   # 切换 BINANCE_BAW_DIR 后调 CLI
def rpc(method: str, params: list):    # JSON-RPC，多节点回退
def call(to, data, rpc=None) -> str:   # eth_call 简写
def preview(wallet, to, value, data) -> dict:   # contract-call preview
def fire(wallet, request_id) -> dict:           # contract-call execute
```

## 每个业务脚本必须遵守的四条

### 1. 默认只读，`--fire` 才动钱

```python
ap.add_argument("--fire", action="store_true", help="不加这个参数只预览")
```

跑一次不带 `--fire`，看输出对不对，再带 `--fire` 执行。
这条规则能挡掉 90% 的误操作。

### 2. 幂等：先查状态再决定做不做

```python
if position["claimed"]:
    print("已领取，跳过")
    continue
```

### 3. 金额精确 + gas 预留

```python
GAS_RESERVE = 0.005
cap = int((balance - GAS_RESERVE) / unit_price)
shares = min(quota_left, cap)
if shares <= 0:
    print("余额不足，跳过")
    continue
```

### 4. 每步都打印结构化结果

```python
print(json.dumps({"wallet": w, "action": "mint", "shares": n,
                  "tx": tx_hash, "status": status}, ensure_ascii=False))
```

方便你事后 grep，也方便 AI 读取。

## 日志

```bash
/opt/wallet-tools/logs/
├── mint.log       每次铸造一行 JSON
├── claim.log
└── ledger.jsonl   所有资金变动（收入/支出/手续费）
```

`ledger.jsonl` 是最值钱的：三个月后你会感谢现在的自己。

## 定时任务

```ini
# /etc/systemd/system/wallet-claim.timer
[Timer]
OnCalendar=*-*-* *:07:00
Persistent=true
```

**原则**：

- 只自动做"只赚不亏"的事（领取、保活、对账）
- 涉及花钱的，永远手动
- 每个定时任务都要能 `systemctl disable --now` 一键停

## 给 AI 读的脚本接口

如果你想让 AI 调你的脚本，给每个脚本加 `--json`：

```bash
python mint.py --wallet w1 --shares 5 --json
# {"ok": true, "tx": "0x...", "spent": 0.01, "left": 0.42}
```

AI 解析 JSON 比解析人类可读文本稳定得多。
