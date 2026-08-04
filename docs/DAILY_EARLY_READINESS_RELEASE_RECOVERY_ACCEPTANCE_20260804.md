# 日增量早探测生产发布恢复守护预执行验收

> 日期：2026-08-04（Asia/Shanghai）
>
> 协议：`daily-early-readiness-release-guard-20260805`
>
> 裁决：`GO_EARLY_READINESS_RELEASE_RECOVERY_PREEXECUTION_ONLY`
>
> 生产状态：`NOT_PROMOTED_NOT_STARTED`

## 1. 权威结论

2026-08-05 日期绑定的 P0-E 恢复守护已完成结果前冻结、最小激活、对抗 fixture、全仓和断网只读
Docker 预执行。旧 20260804 配置及证据永久保留；当前默认入口只读取新的 v2 配置，并精确绑定同一
候选、同一旧生产和 20260804 两账户最新 FORWARD 产物。

该裁决不代表候选已经提升或生产已经切换。2026-08-04 晚间实际运行入口只返回
`BLOCKED / guard target date does not equal the local date`，日期校验发生在 Git、Docker、release 状态
读取和任何变更之前；没有 promote、start、rollback、scheduler 重启或手工日跑批。

## 2. 冻结与实现顺序

- `1fece49`：先行提交并推送恢复协议和 v2 精确配置；目标日、窗口、候选、旧生产、双账户产物和
  恢复语义均在默认入口切换前冻结。
- `ff51020`：随后提交并推送最小实现；只把默认配置指针和 Makefile 文案从 20260804 切到
  20260805，并把测试迁到 v2，同时新增旧 v1 配置不可改写回归断言。
- 守护状态机、执行动作、恢复逻辑和生产候选均未修改；没有重新 build 候选。

## 3. 当前冻结边界

| 对象 | 冻结证据 |
|---|---|
| 目标日 | `20260805`，项目内冻结交易日历中为 `20260804` 后首个开市日 |
| 窗口 | 16:05:00（含）—19:00:00（不含），Asia/Shanghai |
| 候选 | `shaiwei:scheduler-0640574ba7353c3e` |
| 候选 image ID | `sha256:85711ae0b4c3b19de1554f778cb0ff2ee10f5b1e962e2ef79e1d0953a6a5e79f` |
| 候选代码快照 | `0640574ba7353c3eef888eac2f706a29606db728319d3717b7ecdfc25de40c40` |
| 当前生产代码快照 | `4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708` |
| Top30 最新边界 | `20260804` / artifact `691987e0...e89f` |
| Top20 最新边界 | `20260804` / artifact `26de5b7f...afec` |

真实执行时 readiness 仍必须精确返回 `CROSS_SNAPSHOT_WITH_NEW_DATA` 和唯一新日 `["20260805"]`；
没有新日、多个新日、身份漂移或双账户边界变化均在变更前 BLOCKED。

## 4. 验证证据

- 宿主恢复守护/release 专项：47 PASS。
- 宿主全仓：563 PASS；唯一 warning 为既有 Starlette/httpx 弃用提示。
- Ruff、`compileall`、`pip check`、三套 Compose 解析和 `git diff --check` PASS。
- 独立预执行镜像：`shaiwei:early-release-guard-recovery-preflight-ff51020`，image ID
  `sha256:f2a4c2f7fe8251fad33996bef4a56b13c0cbbb3e7c2e4506f940a43850f80fc2`；运行时代码快照
  `76e408aa379811268af975ce229423dcf941e65036d5f4160b7a22fd23911624`，嵌入 Git
  `ff51020e7bebbed1debad1f008d285cfdefeaa8b`。
- 该镜像在 `--network none`、只读根、`cap-drop ALL`、`no-new-privileges`、无项目挂载、无凭据下
  47 PASS；唯一 warning 是只读根阻止 pytest 写缓存。

独立预执行镜像使用测试标签，没有调用 `release build/promote`，不属于生产候选，也不进入发布审计。

## 5. 生产不变性

终验时 release 审计仍为 24 行，tip 仍是
`aa64d960d64be6d403b53b9018a8a1cb00f25be2a8c46bc9f35e9dd9b48ee05f`。current 仍是：

- image `shaiwei:scheduler-4e5244b6b02739dd`；
- image ID `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`；
- code snapshot `4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708`；
- scheduler `Up 28 hours (healthy)`，预执行未重启。

## 6. 目标日动作与后验收

只有在 2026-08-05 16:05—19:00 且所有实时门仍通过时，才允许执行一次
`make docker-early-release-guard`。BLOCKED 时不得改配置、改日期、改锚点或重复追成功。

若返回 STARTED，仍须等待自然链并独立核验早探测/就绪/正式完成时点、日增量 PASS、实际 raw
`.BJ=0`、S1—S10、信号、开盘对账、Top30/Top20、飞书、重放、幂等、零人工修数和新生产身份。
单日通过只证明恢复发布和一次自然闭环，不证明稳定 SLA 或策略效果。
