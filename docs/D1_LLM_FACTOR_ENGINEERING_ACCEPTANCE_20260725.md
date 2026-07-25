# D1-1 LLM 因子研究零调用工程门验收

日期：2026-07-25（UTC+8）

## 1. 裁决

`GO_ENGINEERING_ONLY`

- `engineering_complete=true`
- `llm_api_calls=0`
- `real_market_data_read=false`
- `market_results_inspected=false`
- `g1_run=false`
- `strategy_effective=NOT_EVALUATED`
- `d1_2_authorized=false`
- `production_authorization=none`

本裁决只证明 D1 的受限生成控制面、账本、DSL 安全门和一次性 Docker fixture 可用。它不证明
DeepSeek 能产生有效因子，不允许调用真实 API、读取发现期行情、运行 W1-W6/G1、修改生产模型或接入
scheduler。

## 2. 已完成工程真身

- `CandidateProposal` 使用额外字段拒绝的严格 JSON schema；一个响应只能携带一个主题、一个表达式和
  有界谱系。
- 固定五主题、每主题 8 次、合计 40 次的确定性 attempt 编号与独立/变异排程；D1-1 CLI 只暴露
  `--fixture`，不存在真实 provider 客户端。
- 输出经现有 AlphaGen parser、字段/算子白名单、token/AST/50 日回溯、PIT 与 shift 哨兵审计；不使用
  `eval`、任意 Python、文件/网络/环境或 shell 执行。
- 返回模型身份、结束原因、usage、cache hit/miss 和费用均 fail closed；敏感输出只留哈希，不落原文。
- 新增追加式 `ledger/llm_factor_attempts.csv`。每个完成响应分配确定性 `experiment_id`，并在
  `ledger/experiments.csv` 形成一条对应的生成阶段试验记录；重放先核对双账本，孤儿或哈希不一致时
  不再次调用 provider 并直接阻断。
- 原始响应与 manifest 使用 write-once 写入项目内 Git 忽略研究区；Git 只跟踪空账本表头、代码、配置、
  测试和本文档。
- 独立 `compose.research.yaml` 仅用于一次性研究 fixture：非 root、只读根、`network_mode=none`、
  `cap_drop=ALL`、no-new-privileges、CPU/内存/PID 限额、无端口、无重启、无 Docker socket、无 `.env`，
  只读挂载项目内 AlphaGen vendor，不挂生产数据、账本、模型或信号。

## 3. 不可变证据

| 证据 | SHA-256 / 身份 |
|---|---|
| 完成态协议 | `23ca57f0c349df08839e5141b46855ac91cc82fb2b05d2866872860a975ca195` |
| candidate schema | `71617286887eec810735a22651d7ade9d9eb58aa5a3eb1650ee833f9adacf217` |
| 空尝试账本表头 | `e981f60ffec92ae536cd3e9864a6b34a7cc02eccec282b54e55599f48dc90801` |
| research compose | `136839db885ff7fc1c8fa7bc549115831be53f3b38f133cc1327c15c6daea090` |
| Docker 受控代码快照 | `4b8a624e249f5938b7119d056c19cdda9b2e084518af435deaf6c9ab9763fae5` |
| Docker 镜像 | `sha256:5d1e8c11dc15b334810632c2546ff9d17259dc9fb05bec2e8068a03975b12aec` |
| 最终 fixture 产物树 | `5e068fd1f2d895a7ccd5944af7e99b94a3dea819989eb17307df4fc615a3b8e7` |
| 最终 synthetic attempt | `66d845323d0c645a` |

最终断网 fixture：`fixture_pass=true`、attempt 1 行、experiment 1 行、`ledger_one_to_one=true`、
`idempotent_replay=true`、mock 响应只消费 1 次、`external_api_calls=0`、`real_market_data_read=false`、
`g1_run=false`。

## 4. 验证

- 本地全仓：232 passed；已知 FastAPI/Starlette 测试兼容警告 1 条，不影响本次裁决。
- 本地 D1/账本/表达式/发布专项：57 passed。
- 断网、只读 Docker 对抗测试：17 passed；覆盖 schema、谱系、恶意表达式、重复 AST、模型身份、
  截断输出、usage 错误、敏感输出、双账本孤儿、幂等和 compose 隔离。
- Ruff、compileall、pip check、Compose config、`git diff --check` 均 PASS。
- D1 控制面和 Docker fixture 均未加载或读取 `.env`；全仓脱敏测试仅在宿主项目内将已配置秘密与
  Git 跟踪内容作不回显比对。未调用 DeepSeek，未读取市场数据、G1 结果或项目外业务文件。

## 5. 生产隔离

D1 施工前后生产 scheduler 均为容器 `fd8e96152b53`、镜像内容
`sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`、受控代码快照
`eb8e752132ac1fbe6a9557d26b4c7a65df36f6169d617b6e1e10db88d46b7fbd`，启动时间仍为
2026-07-24 20:25:27+08:00，状态 `healthy`。没有重建、重启或修改生产 scheduler。

## 6. D1-2 仍未满足的门

若继续 D1-2，必须另立授权并在首次 API 调用前完成：

1. 联网复核真实可用的 DeepSeek 模型标识、JSON 输出能力和最新官方价格；若与草案不一致先改协议；
2. 冻结并先推送 system prompt、五主题模板、schema、反馈序列化规则和知识 manifest；
3. 只做环境变量存在性检查，不打印密钥，并把真实 provider 的网络出口限制到冻结 API 端点；
4. 用户再次明确确认最多 40 个完成响应和累计 `$0.75` 硬熔断；
5. 为真实运行单独建立发布快照、超时/429/5xx/BILLING_UNCERTAIN 恢复 fixture，确认后才允许串行调用。

D1-2 完成后也只可停止在发现期 Top2 之前；W1-W6/G1 属于另行授权的 D1-3。
