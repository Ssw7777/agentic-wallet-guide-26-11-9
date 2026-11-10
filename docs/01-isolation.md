# 01 · 钱包隔离：一个目录 = 一个钱包

## 为什么用目录隔离

大多数钱包 App（含浏览器插件）是"一个 App 管多个账户"，切换在 UI 里。
Agentic Wallet 是 CLI，隔离粒度是 **数据目录**：

```bash
BINANCE_BAW_DIR=~/aw/w1  baw <命令>
BINANCE_BAW_DIR=~/aw/w2  baw <命令>
```

每个目录里独立保存：钱包身份、MPC 密钥分片缓存、session token、网络配置。
**目录之间互不可见**，一个目录被盗不会连带其它目录。

## 推荐目录结构

```
~/aw/                     chmod 700
├── w1/                   主号
├── w2/                   子号 / 朋友 A
├── w3/                   子号 / 朋友 B
├── w4/
├── w5/
└── _archive_20260101/    历史钱包归档（改名即可，别删）
```

约定：

| 编号 | 用途 | 特点 |
|---|---|---|
| `w1` | 主号 | 出金、对外收款、执行主要操作 |
| `w2`..`wN` | 子号 / 朋友号 | 只做项目交互，余额尽量留少 |
| `_archive_*` | 退役钱包 | 改名保留，不再操作，防止误用 |

**为什么保留归档而不删除**：钱包地址在链上是永久的，删了目录等于丢掉访问权，
但历史记录、可能存在的空投快照仍与地址相关。改名归档是最安全的"退役"方式。

## 会话与登录状态

```bash
# 看是否在线（每个目录独立）
BINANCE_BAW_DIR=~/aw/w1 baw wallet status --json
# {"success": true, "data": {"status": "CONNECTED"}}
```

- `CONNECTED`：session 有效，可以直接签名
- 其它状态：需要重新登录 / 重新授权

**session 过期是常态**，尤其是不常操作的号。建议配一个**保活定时任务**（见
[dashboard/README.md](../dashboard/README.md) 的 systemd 示例），每 2 小时轮询一次
`wallet status` 和 `wallet balance`，既能续期，也能及早发现掉线。

## 多钱包并行操作

因为隔离粒度是环境变量，**同一个脚本可以顺序操作多个钱包**，互不干扰：

```bash
for w in w1 w2 w3; do
  BINANCE_BAW_DIR=~/aw/$w baw wallet balance --json
done
```

写脚本时的标准做法：

```python
PROFILES = {
    "w1": os.path.expanduser("~/aw/w1"),
    "w2": os.path.expanduser("~/aw/w2"),
}

def run(wallet: str, *args: str) -> dict:
    env = {**os.environ, "BINANCE_BAW_DIR": PROFILES[wallet]}
    out = subprocess.run(["baw", *args, "--json"],
                         capture_output=True, text=True, env=env, timeout=60)
    return json.loads(out.stdout[out.stdout.index("{"):])
```

## 转账权限的分级思路

不要给所有号同等权限。实践中的分级：

| 层级 | 钱包 | 允许动作 | 余额上限 |
|---|---|---|---|
| L1 主号 | `w1` | 全部操作、对外转账、出金 | 较高 |
| L2 子号 | `w2`..`w5` | 项目交互、领取、小额兑换 | 只留 gas + 单项目所需 |
| L3 朋友号 | `w6`+ | **只做项目交互，绝不转出** | 只留 gas |

> 铁律：**朋友的钱包只做"帮他交互"，不做"帮他转账"**。
> 任何涉及转出的操作，必须由本人确认。

## 备份什么、不备份什么

| 项 | 要不要备份 | 说明 |
|---|---|---|
| 钱包目录整体（`~/aw/wN`） | **要** | 离线加密备份（7z + 密码 / age） |
| session token | 不用单独备 | 会过期，重新登录即可 |
| 助记词 / 私钥 | 按官方机制 | MPC 钱包通常无完整私钥导出，务必看清官方说明 |
| 地址清单 | 要 | 明文即可，用于对账和看板 |

备份命令示例（加密后上传网盘/私有仓库）：

```bash
tar czf - ~/aw | age -p > aw-backup-$(date +%F).tar.gz.age
```

## 常见错误

| 错误 | 后果 | 正确做法 |
|---|---|---|
| 两个钱包用同一个目录 | 身份串号，A 的 session 覆盖 B | 每个号独立目录 |
| 目录权限 755 | 同机其它用户可读 session | `chmod 700 ~/aw ~/aw/w*` |
| 直接 `rm -rf` 退役钱包 | 永久失去该地址控制权 | 改名到 `_archive_*` |
| 把目录塞进 Git 仓库 | session 泄露 = 钱包被接管 | `.gitignore` 掉 `aw/`、`.secrets/` |
| 用 root 跑钱包 CLI | 权限过大、日志泄露 | 用普通用户 + sudo 只给必要命令 |
