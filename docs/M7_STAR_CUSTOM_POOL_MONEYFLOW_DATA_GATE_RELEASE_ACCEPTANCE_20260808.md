# M7 三自建科创池资金流键级数据门 release 验收（2026-08-08）

## 1. 终态

`RELEASE_READY_NOT_APPROVED`。

精确 release scope 已形成，但 approval、真实输入束、runner 输出和 auditor 输出均不存在。真实证券键
读取 0，资金流数值列读取 0，候选/效果/尝试增量 0，生产授权 `none`。

这不是 `GO_M7_0_DATA_COMPATIBILITY_ONLY`，也不是策略有效。唯一下一动作是用户对下述完整 scope SHA
明确批准；没有批准时必须停止。

## 2. 精确身份

- action：`M7_STAR_CUSTOM_POOL_MONEYFLOW_DATA_GATE_ONCE`；
- release scope canonical SHA-256：
  `f47100687eabe09959a6a1746e742a274e8e77ba3c9e6e90c58a43542b4b24e1`；
- release scope physical SHA-256：
  `31446aff477fd1d9b784c81c9f35eb53690ac36ac8ebcf7bd80474ab5e0b6466`；
- implementation Git / pushed `origin/main`：
  `2aabf207f236eecd0856126f1003734317f8ea0d`；
- code bundle SHA-256：
  `fc0a341df0b355c71ed8db5cddb85f1fd2604b67d25a47de7fc167ee9a0dcf0a`；
- metadata-only input manifest canonical SHA-256：
  `8a1333888c3abd20d1a4c003018ec81dc22ccf8629372266e6833a8cc750e27a`；
- input manifest physical SHA-256：
  `6522e5802b3d51f16c7ed48aac5afb4f10368716dc38201121a8417a170673ee`；
- image ID / repo digest：
  `sha256:893e90f4bef497189033093010ccf342d727e451f1e1c5f11c0c955be693c616`；
- platform/user：`linux/arm64` / `65532:65532`；
- approval builder SHA-256：
  `8f1842abc14aff13da506d44d783cab03e976e773311b4c10d9bd96fe454eb52`。

## 3. 输入与容器绑定

release 只允许以下内容寻址挂载：

- `/inputs:ro`：`data/control/m7/input-bundles/8a133388...0e27a-2aabf20`；
- `/outputs:rw`：`data/control/m7/outputs/8a133388...0e27a-2aabf20`；
- `/audit:rw`：`data/control/m7/audits/8a133388...0e27a-2aabf20`。

网络、项目根、`.env`、`.git`、Docker socket、模型、标签、效果、生产数据和自然账本均未挂载。容器
固定非 root、只读根、cap drop all、no-new-privileges、pids 128；runner 2 CPU/4 GiB，auditor
1 CPU/2 GiB。

release authority 中只有 `release_ready=true`；`release_approval_recorded`、`execution_authorized`、
`real_security_key_read_authorized`、`numeric_moneyflow_value_read_authorized`、网络、候选、效果、模型、
回测、前瞻、scheduler/Web 变更全部为 false，生产为 `none`。

## 4. 批准时的额外 fail-closed 条件

用户批准不能直接由手填 JSON 转录。内容寻址的 host-side approval builder 必须：

1. 收到精确 action 和完整 release scope SHA；
2. 只读打开项目内冻结路径的 proposal SQLite，复算 schema、proposal、事件链和回执完整性；
3. 证明 proposal 仍为 `REVIEW_REQUIRED`、event seq 仍为 2、head SHA 仍为
   `da38d05a...b1f0a`，且批准与当前时间都早于 `2026-08-15T04:05:02+00:00`；
4. 生成 write-once approval，随后才允许物化精确输入束；
5. 任一身份、状态、时钟或文件漂移立即停止，同 scope 不得重跑。

## 5. release 验证

- 最终镜像在已推送 Git 后重建；断网、非 root、零真实挂载的合成 fixture PASS；
- clean/duplicate/sparse core SHA 与工程验收一致，内部 replay 和独立 DuckDB audit 一致；
- release CLI 复核 HEAD=`origin/main`、固定文件均已跟踪且无差异；
- DataReleaseScope 规范反序列化和最小权限门 PASS；
- approval 文件、正式输入束、正式输出、独立 audit 输出均不存在；
- scheduler 仍为原容器 `183b8c6c5edd`、原镜像内容 ID `722f63de...13b76`、healthy，未重启；
- 七个自然账本保持未暂存，release 未写任何自然账本。

## 6. 停止线

本节点到此停止。若用户决定执行，批准句必须同时包含完整 scope SHA 与动作名：

`批准 M7 release scope f47100687eabe09959a6a1746e742a274e8e77ba3c9e6e90c58a43542b4b24e1 按动作 M7_STAR_CUSTOM_POOL_MONEYFLOW_DATA_GATE_ONCE 运行一次断网真实键级 DATA_GATE；只读 ts_code/trade_date 与冻结 M3 成员键，不授权资金流数值、候选、标签、收益、模型、回测、外网、前瞻、模拟仓或生产，同 scope 不得重跑。`
