# M7-0R3-P2 精确网络恢复 release 验收

## 裁决

最终 release 状态为 `GO_M7_RECOVERY_EXACT_NETWORK_RELEASE_READY_ONLY`。scope 已绑定完整输入、请求身份、
已推送代码、最终镜像、四角色命令/挂载/资源和请求上限，但 `execution_authorized=false`；没有生成批准
envelope，也没有读取 token 或执行任何 provider 请求。

## 最终身份

- release scope：`a701e9ceb9bb77634a4feaa62fc640c3447555ef089bc7448577d48e5d68cb73`。
- scope 文件物理 SHA-256：`8d3e237c1f4126e17adb005db158680bb9971b76033c88720ecdbbe45ce8f1af`。
- Git / origin main：`2741a09e26242bd339b3296370fd35290b991a6e`。
- 代码束：`a65cb9fabeceb31d6b9fc88f71dc15b16f1bbd0794567ff0006d8160be969a24`。
- linux/arm64 镜像：
  `sha256:5b15e23f78f3a71e60390b50a8e3f2a74da8b4247c19fade88137002f030b3da`。
- request plan manifest：`dcc2a78d8d399321bbd042acba009e9e39b428beb6640756c605e2498859bf43`。
- 独立 request plan audit：`4f63bfe8ccaee68195f37f82c57db038cf948311695ad9c74a2c973364bb7dd5`。

## 精确执行上限

- Baostock 状态请求：75 次，覆盖 527 个必需键。
- Tushare 全市场按日请求：541 次。
- Tushare 单票单日请求：541 次。
- 精确 provider 请求总数：1,157；每个已 claim 请求最多 3 次传输尝试，因此最坏传输尝试上限 3,471。
- 语义空响应不重试，已 claim 失败不在同 release 重试，同 scope 不得重跑。

## 四角色边界

status collector 与 moneyflow collector 串行运行且不共享可写目录；只有后者可窄挂载单独 Tushare token
文件，禁止挂载 `.env`。evaluator 与 auditor 均为 `network=none`。四个角色的 plan mount 与
`--plan-root` 都保留 `/plans/<plan_id>`，避免先前 basename 身份阻断；所有角色非 root、只读根、
`cap_drop=ALL`、`no-new-privileges`，不挂载项目根、Docker socket 或生产 data/ledger/logs。

## 当前停止点

当前 `approval_recorded=false`，网络、provider、secret、调整覆盖率、候选、效果、模型、回测、前瞻、
模拟仓和生产均未授权。只有用户逐字绑定完整 scope 并批准动作
`M7_MONEYFLOW_EVIDENCE_RECOVERY_ONCE` 后，才能创建一次性批准 envelope、准备窄 secret 文件并按四角色
顺序执行；不能复用此前任何授权。
