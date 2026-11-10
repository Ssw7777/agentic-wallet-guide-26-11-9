# Agentic Wallet 实战手册

> 用 **Binance Agentic Wallet（BAW）CLI** 管理多个隔离的链上钱包：
> 怎么隔离、怎么管、怎么转、AI 提示词怎么写、看板怎么部署、有哪些坑。
>
> 面向：想让 AI 帮自己管多个钱包的人；想给朋友的 AI 直接喂一套规则的人。

**English:** A battle-tested, sanitized playbook for isolated multi-wallet operations with Binance Agentic Wallet, AI prompts and self-hosted dashboards.

> **仅自用，搞着玩，DYOR。** Personal use only, experimental; do your own research. Nothing here is financial advice. The examples are sanitized; never commit real keys, sessions or seed phrases.

---

## 这个仓库是什么

一套经过实战打磨的 **多钱包 + AI 代管 + 自建看板** 方法论，包含：

| 内容 | 说明 |
|---|---|
| **钱包隔离** | 一个目录 = 一个独立钱包，互不干扰，可并行操作 |
| **日常操作** | 查询 / 转账 / 兑换 / 合约调用，都有固定套路 |
| **安全铁律** | 先模拟后执行、精确授权、金额与 gas 的双重校验 |
| **AI 提示词** | 直接复制给 Claude / GPT / DeepSeek 用的系统提示词与任务模板 |
| **看板部署** | 单文件 Python 看板 + Caddy 反代 + systemd 常驻，10 分钟上线 |
| **踩坑清单** | 编码、RPC、地址簿、nonce、时区……能省你几小时 |
| **习惯清单** | 每天 5 分钟、每周 15 分钟要做什么 |

> ⚠️ 本仓库全部为**脱敏示例**：地址为占位符，域名为 `example.com`，无任何真实私钥/助记词/session。
> 不构成投资建议，链上操作风险自负。

---

## 目录

```
docs/
  01-isolation.md    钱包隔离：一个目录一个钱包
  02-daily-ops.md    日常操作：查、转、兑、调合约
  03-safety.md       安全铁律：模拟、授权、限额
  04-ai-prompts.md   AI 提示词：系统提示词 + 任务模板
  05-pitfalls.md     踩坑清单
  06-habits.md       操作习惯清单
dashboard/
  README.md          看板从零部署
  server_example.py  单文件看板骨架（可直接改）
scripts/
  README.md          脚本组织方式（幂等、可预览、可回滚）
```

---

## 30 秒理解核心思想

**1）隔离靠目录，不靠多个 App**

```
~/aw/w1/    ← 钱包 A 的全部身份数据（session、配置）
~/aw/w2/    ← 钱包 B，完全独立
~/aw/w3/    ← 钱包 C
```

调用时只改一个环境变量，就切换了"人"：

```bash
BINANCE_BAW_DIR=~/aw/w1 baw wallet status --json
BINANCE_BAW_DIR=~/aw/w2 baw wallet status --json
```

**2）所有写操作都走同一条流水线**

```
读状态 → 算参数 → 本地模拟 → CLI 预览 → 校验 → 执行 → 回读验证
```

少任何一步都可能烧钱。详见 [docs/03-safety.md](docs/03-safety.md)。

**3）AI 不需要"聪明"，需要"守规矩"**

给 AI 一份固定工作流 + 硬性禁令，比让它自由发挥可靠得多。
直接抄 [docs/04-ai-prompts.md](docs/04-ai-prompts.md)。

---

## 快速开始

```bash
# 1. 安装（按官方文档装好 BAW CLI，确认能跑）
baw --version

# 2. 初始化第一个钱包
mkdir -p ~/aw/w1 && chmod 700 ~/aw
BINANCE_BAW_DIR=~/aw/w1 baw wallet init

# 3. 看状态
BINANCE_BAW_DIR=~/aw/w1 baw wallet status --json
BINANCE_BAW_DIR=~/aw/w1 baw wallet address --binanceChainId 56 --json

# 4. 加第二个钱包
mkdir -p ~/aw/w2 && chmod 700 ~/aw/w2
BINANCE_BAW_DIR=~/aw/w2 baw wallet init
```

> 目录权限务必 `700`，session 文件等同半个私钥。

---

## 适合谁

- 有 2 个以上链上钱包，嫌切来切去麻烦的人
- 想让 AI 帮自己盯额度、领空投、对账，但又不敢给它太大权限的人
- 想给朋友一套"开箱即用"的 AI 指令模板的人

## 不适合谁

- 只想持币不动的人（没必要）
- 想找"一键暴富脚本"的人（这里没有，也不提供）

---

## License

MIT
