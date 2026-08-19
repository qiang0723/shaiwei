# RF-0C 字段与身份结果盲预检协议（2026-08-19，待用户批准）

- 机器真身：`config/rf_0c_field_identity_preflight_v1.yaml`，SHA-256
  `28c8524b96f726968a507d42ef661b435ca000746d218634d76b768d5cd5cc66`
- 状态：`RESULT_BLIND_DATA_AND_IDENTITY_PREFLIGHT_FROZEN_PENDING_USER_APPROVAL`
- 上位授权：RF-0B `BLOCKED_DATA` + 谱系诊断 `ALL_EXPLAINED` + 用户 2026-08-19 选择继续 RF

## 1. 与 RF-0B 的唯一口径差（谱系诊断证据支持）

无 bar 成员日的停牌确认改为两层并集：Tushare `suspend_d` 主层 **或** 独立 Baostock 交易状态
`'0'`。谱系诊断已证明历史上的 5 个缺口全部是 Baostock 确认的真实停牌、suspend_d 漏记。

**门槛逐字不动**（99%/99%/0 未解释、`.BJ`=0）；其余口径、期间（2019—2025）、面板、fixture、
执行边界与 RF-0B 完全一致。注册表必须与 RF-0B 封存注册表**逐字节相等**，不等即失败关闭。

## 2. 裁决

- `GO_FORMAL_PROTOCOL`：只授权起草正式单机制协议（RF-0A：8 响应小批、至多 3 候选、机械
  Top1/Top2、失败计入预算不补位），仍须 R2-1 检查点 + 你再次批准；
- `BLOCKED_DATA` / `REJECT_DUPLICATE`：本机制关闭。

## 3. 边界

零效果、零候选、零收益；断网、write-once、一次画像、一次独立审计、同 scope 不重跑。
批准即施工。
