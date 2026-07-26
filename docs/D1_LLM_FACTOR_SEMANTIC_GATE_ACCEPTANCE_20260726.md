# D1 复核语义合同恢复工程验收（2026-07-26）

> 协议：`d1-review-semantic-gate-v1`
>
> 工程裁决：`GO_SEMANTIC_GATE_ENGINEERING_ONLY`
>
> 旧 D1-3A 权威裁决：`STOP_SEMANTIC_CONTRACT_VIOLATION`（不变）
>
> DeepSeek 调用/新增费用：`0 / $0`
>
> 生产授权：`none`

## 1. 结论

自由文本与结构字段一致性门已经补齐。新门在 JSON/schema 之后同时检查结构布尔值、四类正文、完整
冻结 DSL、回看期字面量、公式/窗口/估计量变更建议、业绩与准入声称；明确违约为
`FAIL_SEMANTIC_CONTRACT`，非英文、不完整 DSL 或无法确定的修改语言为
`MANUAL_REVIEW_REQUIRED`。两种状态都必须在人工闸前停止，不能把“机器看不懂”当成通过。

旧 8 份响应在零网络、零 provider 调用下双跑，稳定复现权威纠错的 5 PASS / 3 FAIL，且三份失败身份
与原纠错完全一致。此结果只验证工程门能拦住已知错误模式，不回溯挽救旧批，不改变两候选未准入、
未运行 G1、策略未评价和零生产授权。

## 2. 冻结与实现身份

| 项目 | 身份 |
|---|---|
| 协议冻结提交 | `45734b1a8992d530be4a60b01bbd3692e866c4bf` |
| 实现提交 | `8d3ee9775a33e3a9887e00e528b51476cd3cec2c` |
| 协议 SHA-256 | `8faf36d33744aec06ec4331266dccf4d96dee904bac0a3d0fb603940e6aef15a` |
| 受控代码快照 | `50c3af0f20e5746dfff834144d534178de34ffcef8d8909ff1c331c6c3d714ae` |
| 对抗 fixture SHA-256 | `977666411d87801205f8ee3c4ff81bb20ecfcb67fc65d009255e8841e320ce1b` |
| 离线审计 stdout SHA-256 | `3446e874b8d88859875ac47aa00e8132c2de874a1c8da1a414626124099e672a` |
| 脱敏验收 JSON SHA-256 | `9f0f2c20ea90f1f226d65e34c76b3d4e8978b2d68c19eb943327e849f52855d5` |
| 原 review ledger SHA-256 | `9029ea65490711dbd6bddc592d2f3116ad1b7e811059cad926caca283d13e280` |
| 原语义纠错 SHA-256 | `de8b331cd8c923bb3b7b3f3a9e8c0aeb342db410cda647be72981f69a34917b2` |

机器可读脱敏验收为 `docs/D1_LLM_FACTOR_SEMANTIC_GATE_ACCEPTANCE_20260726.json`；只含哈希、状态、
原因码和计数，不含响应正文、业绩数值、绝对路径或凭据。

## 3. 门的行为

- 明确建议替换公式/算子、调整窗口、尝试变体或替代估计量：`FAIL`；
- 与冻结式不同的完整 DSL、不同 `Nd` 回看期：`FAIL`；
- 业绩、准入或生产声称：`FAIL`；
- 模糊建议、非英文或不完整 DSL：`MANUAL_REVIEW_REQUIRED`，同样停止；
- “拒绝原式”“保持原式”和显式否定修改可以通过，但通过只表示正文合同一致，不表示经济含义正确；
- 输出不返回或跟踪自由文本，只返回正文哈希、状态和稳定原因码。

专项 fixture 覆盖 9 个冻结类别，并补充命令式替代、计算替代、业绩/准入声称和不完整 DSL；最终本机
专项 13 PASS。第一次断网容器自证为 8/9，唯一失败是未只读挂载最新 `compose.research.yaml`，导致
容器看到镜像内旧配置；补上该单文件只读挂载后，终版断网容器 13/13 PASS。失败未隐藏，也未触发
provider、费用或生产修改。

## 4. 完整验证与隔离

- 本机全仓：339 PASS；唯一 warning 为既有 FastAPI TestClient/httpx2 迁移提示；
- Ruff、compileall、`pip check`、Compose 展开和 `git diff --check`：PASS；
- staged secret hygiene + append-only：18 PASS；
- 断网 Docker：只读根、`network_mode=none`、无 `.env`/DeepSeek key/Docker socket，所有挂载只读，
  512MiB/1 CPU，终版 13 PASS；
- scheduler 前后均为容器 `fd8e96152b53`、镜像内容 ID
  `sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`、创建时间
  `2026-07-24 20:25:27 +0800`，持续 running/healthy，未重建或重启。

## 5. 后续边界

本工程 GO 不是新的 D1 批次授权。未来只有用户再次明确指令并冻结新批协议，才可调用 DeepSeek；新批
必须在“有效响应”记账前调用本门，`FAIL` 或 `MANUAL_REVIEW_REQUIRED` 均计 N 且不得补发。独立盲态
人工闸、W1—W6、压力期、G1、前瞻和生产仍未获授权。确定性词法门不是完整自然语言理解器，因此
保留模糊即停和独立人工复核是设计边界，而不是待偷偷放宽的门槛。
