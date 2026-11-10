# 02 · 日常操作：查、转、兑、调合约

所有命令都假设：

```bash
export W=~/aw/w1                       # 当前钱包目录
export CHAIN=56                        # BNB Smart Chain
alias bw='BINANCE_BAW_DIR=$W baw'
```

## 1. 查询

```bash
# 状态（是否在线）
baw wallet status --json

# 地址
baw wallet address --binanceChainId 56 --json

# 余额（多链多币，带 USD 估值）
baw wallet balance --json
# data: [{symbol, balance, value, chainId, tokenAddress}, ...]

# 交易记录
baw wallet tx-history --binanceChainId 56 --size 10 --json
```

**只读查询不花 gas，可以随便跑。** 但也别写死循环——RPC 和 CLI 都有速率限制。

## 2. 转账

### 2.1 原生币（BNB / ETH）

```bash
baw wallet send \
  --binanceChainId 56 \
  --amount 0.01 \
  --recipient 0x0000000000000000000000000000000000000001 \
  --gasLevel HIGH \
  --json
```

### 2.2 ERC20 / BEP20

```bash
baw wallet send \
  --binanceChainId 56 \
  --amount 100 \
  --tokenAddress 0x0000000000000000000000000000000000000002 \
  --recipient 0x0000000000000000000000000000000000000001 \
  --gasLevel HIGH \
  --json
```

### 2.3 地址簿拦截怎么办

CLI 可能因为"收款地址不在地址簿"直接拒绝。两个绕过方式，按安全性排序：

**方式 A（推荐）：走合约 transfer**

```bash
baw contract-call preview \
  --binanceChainId 56 --from <你的地址> \
  --to <代币合约> --value 0 \
  --inputData 0xa9059cbb000000000000000000000000<收款地址去0x补0到32字节><金额16进制补0到32字节> \
  --json
# simulationCode 必须为 "000000000"
baw contract-call execute --requestId <id> --json
```

**方式 B：经 WBNB 包装中转**（仅 BSC，原生币场景）

```
wrap BNB -> 转 WBNB 给中转地址 -> 中转地址 unwrap 给最终收款人
```
多花两笔 gas，但能绕过所有地址簿限制。**只在必要时用。**

### 2.4 转账前必查

| 检查 | 为什么 |
|---|---|
| 余额 ≥ 金额 + gas | 否则交易失败还烧 gas |
| gas 预留 ≥ 0.005 BNB | 后续操作需要 |
| 收款地址前后 4 位核对 | 防剪贴板木马 |
| 是否是朋友的钱包 | 是 → 一律不转出 |

## 3. 兑换（Swap）

大多数情况直接调 DEX Router。以 PancakeSwap V2 为例：

```bash
# 1) 先报价（只读）
#    getAmountsOut(uint256,address[]) 选择器 0xd06ca61f
# 2) 授权（精确额度，别用无限授权）
baw contract-call preview --binanceChainId 56 --from <me> \
  --to <token> --value 0 \
  --inputData 0x095ea7b3<router补0><amount补0> --json
# 3) 执行 swapExactTokensForTokens
```

**授权原则**：`approve` 的额度 = 本次要用多少批多少，不要 `uint256.max`。

## 4. 合约调用（最常用）

所有写操作都是同一个三段式：

```bash
# ① 预览（会做链上模拟）
baw contract-call preview \
  --binanceChainId 56 \
  --from 0xYourAddress \
  --to 0xContractAddress \
  --value 0 \
  --inputData 0x<selector><args> \
  --json

# ② 检查返回
#    success: true
#    data.simulationCode: "000000000"   ← 必须是这个
#    data.requestId: "..."              ← 2 分钟内有效

# ③ 执行
baw contract-call execute --requestId <requestId> --json
# {"success": true, "data": {"status": "BROADCASTED", "txHash": "0x..."}}
```

> **`simulationCode` 不是 `000000000` 就别执行。** 这是链上模拟的返回码，
> 非 0 通常代表会 revert，执行了也只会白烧 gas。

### 4.1 构造 calldata 的最小工具

```python
def sel(sig: str) -> str:
    from Crypto.Hash import keccak
    k = keccak.new(digest_bits=256)
    k.update(sig.encode())
    return k.hexdigest()[:8]

def word(x) -> str:
    return f"{x:064x}"

calldata = "0x" + sel("transfer(address,uint256)") + word(0xRecipient) + word(amount)
```

## 5. 批量操作的正确姿势

不要写"一个循环无脑发交易"。标准流程：

```
1. 先读全部状态，算出每个号要做什么（纯读，0 gas）
2. 打印计划表，人工/脚本二次确认
3. 逐个执行，每个之间 sleep 2-4s（避免 nonce 冲突）
4. 全部执行完后，重新读一遍状态做验证
5. 结果写入本地 ledger（jsonl），便于对账
```

## 6. 只读查询：直接打 RPC 更快

需要高频读（比如看板每 15 秒刷新）时，别调 CLI，直接 `eth_call`：

```python
def eth_call(to, data, rpc="https://bsc-dataseed.bnbchain.org"):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
               "params": [{"to": to, "data": data}, "latest"]}
    # POST -> result
```

常用选择器：

| 方法 | 选择器 |
|---|---|
| `balanceOf(address)` | `0x70a08231` |
| `transfer(address,uint256)` | `0xa9059cbb` |
| `approve(address,uint256)` | `0x095ea7b3` |
| `allowance(address,address)` | `0xdd62ed3e` |
| `getReserves()` | `0x0902f1ac` |
| `decimals()` | `0x313ce567` |

## 7. 一笔交易的生命周期（排错用）

```
preview 成功
  → execute 返回 BROADCASTED + txHash
    → 等 1-3 个块
      → eth_getTransactionReceipt(txHash)
        → status == "0x1" 才算真的成功
```

**`BROADCASTED` ≠ 成功**。一定要回读 receipt 的 `status`。

## 8. 幂等设计（防止重复执行）

每个写操作前先做一次"状态断言"：

```python
if already_done_onchain():
    print("已完成，跳过")
    return
```

例如：
- 领取前查 `position.claimed`
- 铸造前查 `quota.used < quota.cap`
- 转账前查 `balanceOf` 是否已为 0

再配合"本地记账 + 链上回读"双校验，基本不会重复扣钱。
