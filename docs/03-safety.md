# 03 · 安全铁律

这一页是红线。可以少赚，不能踩雷。

## 铁律 1：所有写操作必须先模拟

```bash
baw contract-call preview ... --json
→ data.simulationCode == "000000000"   才允许 execute
```

- `preview` 内部会做一次链上模拟，能提前暴露 revert
- `requestId` 通常 **2 分钟**内有效，过期重新 preview
- 预览成功 ≠ 一定会成功（状态可能在两块之间变化），但能挡掉 95% 的低级错误

**绝对禁止**：跳过 preview 直接构造并广播交易。

## 铁律 2：授权只批"这一次"

| 做法 | 评价 |
|---|---|
| `approve(router, 本次金额)` | ✅ 推荐 |
| `approve(router, uint256.max)` | ❌ 无限授权，被利用就是全部余额 |
| 先 `approve(0)` 再 `approve(amount)` | ✅ 改额度时用 |

每次任务结束，把不需要的授权 `approve(spender, 0)` 清掉。

## 铁律 3：金额与 gas 双重预留

```python
GAS_RESERVE = 0.005        # BNB，单笔任务至少留这么多
shares = int(min(quota_left, (balance - GAS_RESERVE) / unit_price))
```

**常见事故**：把余额全部投进去，结果连 claim 的 gas 都没有，
资产卡在合约里干着急。

## 铁律 4：朋友的钱包，只进不出

| 操作 | 自己的号 | 朋友号 |
|---|---|---|
| 查余额 | ✅ | ✅ |
| 项目交互（mint/claim/approve） | ✅ | ✅（需本人知情） |
| 转出到我的地址 | ✅ | ❌ **绝对禁止** |
| 转出到他本人地址 | — | ✅（需本人明确指令） |

给朋友代管前，先用一句话把边界说清楚：
> "我只帮你做项目交互，不会动你的币；要转出必须你本人说。"

## 铁律 5：私钥 / session 永不进仓库

`.gitignore` 必备：

```gitignore
aw/
.secrets/
*.session
*.key
.env
*.json.bak
logs/
```

上传 GitHub 前，跑一遍关键词扫描：

```bash
grep -rniE "0x[a-fA-F0-9]{40}|ghp_|sk-|mnemonic|private.?key|token" . \
  --include="*.md" --include="*.py" --include="*.json" | grep -v "0x000000000000000000000000000000000000000"
```

**只放占位地址**：`0x0000000000000000000000000000000000000001` 这种。

## 铁律 6：单笔 & 单日限额

给自己定硬上限，写进脚本里而不是脑子里：

```python
MAX_PER_TX = 0.05      # BNB
MAX_PER_DAY = 0.20
```

超过就抛异常，强制人工确认。

## 铁律 7：不要在情绪里加仓

这条不是技术，是保命：

- 看到"最后一小时"、"额度快满了" → 先算回本周期，再决定
- 项目方越急着让你打，越要慢
- **只用亏得起的钱**，且分散在不同项目，别把鸡蛋放一个篮子

## 铁律 8：自动化的边界

| 可以自动 | 不要自动 |
|---|---|
| 查询、对账、看板刷新 | 加仓 / 打新 |
| 领取（claim） | 转账给非白名单地址 |
| 保活（renew session） | 修改授权额度 |
| 通知推送 | 任何"看到余额就花掉"的逻辑 |

**"看到余额就自动打满"是最危险的一种自动化。** 一旦脚本还在跑、
你又忘了它，充值到账的下一秒钱就没了。

## 铁律 9：所有自动化必须可一键停

```bash
# 一键停所有定时任务
systemctl disable --now mybot.timer
crontab -l | grep -v mybot | crontab -
```

**并且要验证真的停了**：

```bash
systemctl list-timers --all | grep mybot     # 应该没有输出
ps -ef | grep -E "bot|mint" | grep -v grep   # 应该没有输出
```

> 排查自动化时，**crontab 和 systemd 要一起查**。
> 只停 systemd 而 crontab 里还留着一条 `*/2 * * * * python bot.py`，
> 你会以为停了，其实每 2 分钟还在跑。

## 铁律 10：每笔交易后回读

```bash
eth_getTransactionReceipt(txHash) → status == "0x1"
```

再读一次业务状态（余额、仓位、额度），确认链上真的变了。
**只信链上，不信返回值。**
