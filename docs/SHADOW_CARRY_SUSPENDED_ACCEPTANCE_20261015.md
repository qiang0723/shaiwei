# 沿用日停牌目标 manifest 合同 v3 · 阶段 A 工程验收

> 协议：`shadow-carry-suspended-v1`（`docs/SHADOW_CARRY_SUSPENDED_PROTOCOL_20261015.md`，冻结提交 `6e69551`，
> 推送于 2026-10-15T15:46:33+08:00，早于任何实现提交）
>
> 终态：`GO_ENGINEERING_ONLY`（仅阶段 A 后台）。阶段 B Web 未施工；不授权任何生产动作；生产生效只随 ADR 0016 新候选。

## 1. 交付内容

| 文件 | 改动 | 行数（预算） |
|---|---|---|
| `src/shaiwei/shadow/manifest.py` | `SCHEMA_VERSION=3`、`CARRY_EXPLANATION`、`_carried_without_score`（§4 判定）、v3 字段 | 145→176（≤185） |
| `src/shaiwei/shadow/generation.py` | `carried_without_bar`；`signal_day_bar_codes` 参数；沿用日计算 `explained_missing` 并转发上限 | 269→291（≤300） |
| `src/shaiwei/pipeline/shadow_cycle.py` | `_signal_day_bar_codes`（读取失败返回 `None`）并传入生成 | 378→387（≤395） |
| `src/shaiwei/config.py` | `ShadowPipeline.max_carried_without_score: int = Field(default=0, ge=0, le=5)` | +1 |
| `config/settings.yaml` | `shadow_pipeline.max_carried_without_score: 3` | +1 |
| `tests/test_shadow_carry_suspended.py` | 协议 §6 第 1–10 项与 §7 重放（默认跳过） | 新增 |
| `tests/test_shadow.py` | `schema_version` 断言 2→3（预期变更） | 1 行 |
| `tests/test_shadow_cycle.py` | 补丁 `_signal_day_bar_codes` 并断言其被传入生成（不读真实数据） | 小改 |

模型默认值取 0（缺省即旧合同、失败关闭），生产值由 `settings.yaml` 给出 3，与协议 §2 一致。

## 2. 测试结果

- 协议 §6 第 1–10 项：新测试 14 项通过；连同 `test_shadow*`、`test_paper_projection` 共 31 通过、1 跳过（§7 门控）。
- 全仓回归：首次叠加运行出现 19 项失败，全部为已关闭 M6 线冻结协议对活文件 `config/settings.yaml`、
  `src/shaiwei/shadow/manifest.py` 的整文件哈希核验；生产链与新功能测试全部通过。经用户裁决另立 ADR 0018（冻结推送 `9b7cb1a`，
  实现 `65f26cd`，单独全量 2,465 通过）改为按冻结提交历史版本核验后，本阶段叠加全量 **2,478 通过、1 跳过（§7 门控）、0 失败**；
  `make architecture-check` 13 通过；Ruff 全仓通过；`git diff --check` 通过；脱敏通过。
- 协议 §7 一次性只读验收重放（`SHAIWEI_ACCEPTANCE_REPLAY=1`，2026-10-15 执行一次）：以 20260928 PASS manifest 的 30 个目标、
  20260929 `tushare.daily` 精确请求（只读）与确定性合成分数调用新合同，输出写入 `.test-tmp`。结果 **PASS**：
  `schema_version=3`，`carried_without_score=["SH600363"]`，其余 29 只 `LIVE`。未运行模型，未输出任何分数或模拟仓数值，
  未写 `data/ ledger/ logs/`，未补造 20260929 历史信号。

## 3. 下游核对（只读 + 回归断言）

Top20 投影对含 `null` 的 30 只信号产出 20 只并原样保留 `null`；`paper/engine._target_weights` 与
`shadow/reconciliation._target_weights` 不读 `score`；`web/query_evidence._read_signal` 对 v3 文档哈希/日期/快照/数量校验通过。
`audit/g0.py` 只接受 `schema_version == 1` 的阶段 0 冻结信号，与前瞻 v3 无关，未改。

## 4. 阶段 B · Web（同日追加）

| 文件 | 改动 |
|---|---|
| `web-ui/src/types.ts` | `SignalTarget.score: number` 原行改为 `number \| null`（冻结热点，仍 719 行，未新增行） |
| `web-ui/src/validation/paper.ts` | 客户端校验对 `score` 允许 `null`，非 null 仍须为有限数值 |
| `web-ui/src/pages/SignalsPage.tsx` | `formatSignalScore`：`null` 显示“停牌沿用”；详情页显示完整说明；非 null 保持 6 位小数 |
| `web-ui/src/test/signal-score.test.ts`、`validation.test.ts` | null 显示、0 分仍显示 `0.000000`、null 通过校验、畸形分数仍拒绝 |
| `tests/test_web_query.py` | 查询层对 v3 null 分数原样透传（`web/query_signal.py` 本就 `"score": value["score"]`，无需改代码） |

**协议文件清单勘误（实现时发现，如实记录）。** 协议 §5 阶段 B 只列了 `types.ts` 与 `SignalsPage.tsx`，漏列客户端校验
`web-ui/src/validation/paper.ts`：其 `numberLike` 对 `null` 抛“数值无效”，会使整个信号页校验失败（比显示 0 更严重）。本阶段一并修改；
不改变协议任何判定规则或合同字段。

**验证。** 本机无 Node，按 `Dockerfile.web` 同一钉死镜像 `node:22-bookworm-slim@sha256:6c74…f6b3` 起一次性容器，源码只读挂入、容器内
`npm ci --ignore-scripts`：`tsc -b` 通过；vitest 5 文件 36 项通过（新增 3 项）。Python：`test_web_query`、`test_web_modularity`
15 项通过；`make architecture-check` 13 通过；Ruff、`git diff --check`、脱敏通过。

**终态（阶段 B）：** `GO_ENGINEERING_ONLY`。Web 发布（`make docker-web-build` → `docker-web-release-promote`）另行逐字批准，
须早于新 scheduler 候选启动。

## 5. 已知限制与后续

- 生产仍运行 210af4d 旧合同：沿用日目标停牌仍会整日失败，由巡检 `SHADOW_SIGNAL_MISSING` / `SHADOW_SIGNAL_REPEATED_FAIL` 报告。
- 阶段 B（Web）代码已完成（见第 4 节），但运行中的 Web 容器仍是 08-23 发布的镜像：对 `score: null` 会校验失败。v3 manifest 只会随
  新候选出现，故 Web 发布须早于新 scheduler 候选启动（协议 §5、§8）。
- 本验收不授权候选构建、提升、切换或 Web 发布；这些各自另行逐字批准。
