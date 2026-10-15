# 沿用日停牌目标 manifest 合同 v3 · 实现前冻结协议

> 协议 ID：`shadow-carry-suspended-v1`
>
> 状态：`FROZEN_BEFORE_IMPLEMENTATION`
>
> 冻结日：2026-10-15（Asia/Shanghai）
>
> 裁决来源：`docs/ADR_0015_SHADOW_CARRY_DAY_SUSPENDED_TARGETS_20261014.md`，于提交 `71c9545c468158a6ed17d2a87fcb356962e6c1f7`
> 接受；冻结时文件 SHA-256 `5388bdec154621b37d20f9199990661c5436102e32b64e8dea779fdcfbf20841`。
>
> 本协议提交并推送之前，不写任何实现代码。本协议不读取、不比较任何策略效果或模拟仓数值；它是信号合同的工程变更，
> 不是因子或模型变更。

## 1. 目的与范围

只修一件事：非调仓日（`rebalance_due=False`）沿用的 30 个目标中，若有目标在信号日**全天无行情 bar**（典型为全天停牌），
不再让整日前瞻信号失败，而是按“持仓不变”的原意沿用其权重，并在 manifest 中显式标注。

不在范围内：调仓日选股逻辑；G0–G9/C0、`g1-v1`、`g8-v1`；`paper-v1`/`paper-top20-v1` 执行规则；股票池、标签、模型、
超参、调仓周期；20260929 缺失信号（不补造、不改账）；Web 以外的展示层改动；生产发布（见第 8 节）。

## 2. 冻结决策（来自 ADR 0015，不得在实现中变动）

| 项 | 值 |
|---|---|
| 方案 | B：可解释缺口沿用 |
| 可解释的定义 | 沿用目标的 Tushare 代码不在信号日 `tushare.daily`（`trade_date=信号日` 的最新已提交精确请求）中 |
| 上限 | `max_carried_without_score = 3`（Top30 的 10%）；第 4 只起整日失败 |
| 不可解释 | 有 bar 却无评分 → 仍 `DataClockError`，与今日行为相同 |
| 调仓日 | 行为不变：仍要求当日评分 Top30 足额，任何缺口照旧失败 |
| 生产生效 | 只随 ADR 0016（R2D-lite）的新候选镜像进入生产，不单独发布 |

## 3. Manifest 合同 v3（精确字段）

所有**新生成**的 manifest 一律为 v3（含调仓日），旧文件不改。

- 顶层 `schema_version: 3`（v2→v3）。
- 顶层新增 `carried_without_score: [instrument, ...]`：按 `orders` 中出现顺序排列的 qlib 代码列表；调仓日与无缺口的沿用日为 `[]`。
- 顶层新增 `carry_explanation`：`carried_without_score` 非空时为 `"NO_SIGNAL_DATE_BAR"`，否则为 `null`。
- 每个 `orders[i]` 新增 `score_status`：`"LIVE"`（有当日评分）或 `"CARRIED_NO_SCORE"`；后者 `score` 为 JSON `null`。
- `rank`、`instrument`、`target_weight` 语义与 v2 完全相同：沿用日 `rank` 为上一 manifest 的目标顺序（现有 reindex 行为，不变）。
- 签名算法不变：`signal_sha256 = sha256(规范化 JSON(除 signal_sha256 外全部字段))`；`null` 以 JSON `null` 参与。
- `verify_signal_manifest` 不变，对 v2/v3 均适用。

## 4. 判定规则（伪代码，实现须逐字对应）

```text
write_signal_manifest(..., target_instruments, explained_missing: frozenset[str] = ∅, max_carried_without_score: int = 0)
  若 target_instruments is None（调仓日）:
      旧逻辑；全部 order 的 score_status = LIVE；carried_without_score = []；carry_explanation = null
  否则（沿用日）:
      数量/唯一性检查不变
      missing = [i for i in target_instruments if 当日评分缺失(i)]
      unexplained = [i for i in missing if i ∉ explained_missing]
      若 unexplained 非空 → DataClockError("carried targets missing current scores: {unexplained}")   # 文案保留旧前缀
      若 len(missing) > max_carried_without_score → DataClockError("carried targets without signal-date bar exceed cap: …")
      missing 中的目标：score=null，score_status=CARRIED_NO_SCORE；其余 LIVE
```

`explained_missing` 的计算只在生成编排层：`shadow_cycle.run_once` 读取信号日 `tushare.daily` 精确请求的 `ts_code` 集合
（已有 `_exact_daily`），作为 `signal_day_bar_codes` 传给 `generate_forward_signal`；后者在沿用日计算
`{i ∈ carried_targets : tushare_code(i) ∉ signal_day_bar_codes}` 并传入 `write_signal_manifest`。`manifest.py` 保持纯函数、
不做任何 I/O。信号日 `daily` 读取失败时不猜：`signal_day_bar_codes=None` → `explained_missing=∅` → 等同旧合同。

`max_carried_without_score` 为 `config/settings.yaml` 的 `shadow_pipeline.max_carried_without_score: 3`，
`ShadowPipeline` 模型新增 `Field(ge=0, le=5)`。说明：`config.py` 现 408 行（>400 软线、未入 600 行热点清单），本变更只在既有
`ShadowPipeline` 模型内增加 1 个字段，不新增职责；拆分 `config.py` 属另立目标。

## 5. 实现边界与文件清单

**阶段 A · 后台（一个提交，协议推送之后）**

| 文件 | 改动 | 行数预算 |
|---|---|---|
| `src/shaiwei/shadow/manifest.py` | v3 字段、§4 判定 | 145 → ≤185 |
| `src/shaiwei/shadow/generation.py` | 新参数 `signal_day_bar_codes`，沿用日计算 `explained_missing`，转发 cap | 269 → ≤300 |
| `src/shaiwei/pipeline/shadow_cycle.py` | 读取信号日 `daily` 代码集合并传入 | 378 → ≤395 |
| `src/shaiwei/config.py` / `config/settings.yaml` | 新字段 | +1 / +1 |
| `tests/test_shadow.py` 等 | 见第 6 节 | — |

`generation._reuse_existing` 的绑定字段不变（同 HEAD/快照重跑仍复用已存在 manifest）。

**阶段 B · Web（单独提交，可在阶段 A 之后任意时点，但必须在新 scheduler 候选启动前完成 Web 发布）**

| 文件 | 改动 | 约束 |
|---|---|---|
| `src/shaiwei/web/query_signal.py` | `score` 原样透传（含 `null`），不推断、不补 0 | 查询层不得 import config/notify/pipeline（架构门） |
| `web-ui/src/types.ts` | `SignalTarget.score: number` 原行改为 `number \| null` | 该文件为 719 行冻结热点，**只改原行，不得新增行** |
| `web-ui/src/pages/SignalsPage.tsx` | `score === null` 时显示“停牌沿用（无当日分数）”，否则原格式 | 现 `formatNumber(null)` 会经 `Number(null)=0` 静默显示 0，必须修 |
| `web-ui` 测试 | 新增 null 渲染用例 | — |

Web 发布走既有双镜像内容寻址发布门（`make docker-web-build` / `docker-web-release-promote`），另行逐字批准。

**不改的消费者（已只读核对，实现时各加一条回归断言）**：`shadow/reconciliation.py`、`paper/engine.py`、`paper/projection.py`
（只读 instrument/rank/target_weight，`score` 原样复制）、`web/query_evidence.py`（只校验数量/唯一/`.BJ`）、`audit/g0.py`
（只接受 `schema_version == 1` 的阶段 0 冻结信号，与前瞻 v3 无关）、`paper/risk_exit_engine.py`（未接生产）。

## 6. 测试清单（全部合成数据、tmp_path，零真实读取，阶段 A 必须全部通过）

1. 调仓日：v3 字段齐全，`carried_without_score=[]`、`carry_explanation=null`、全部 `LIVE`；除新增字段与 `schema_version` 外与 v2 逻辑一致。
2. 沿用日 1 只无 bar 目标：产出 manifest；该目标 `score=null`、`CARRIED_NO_SCORE`、`rank`/`target_weight` 沿用；签名可验证。
3. 沿用日 3 只无 bar：通过；4 只无 bar：`DataClockError`（cap 文案）。
4. 沿用日 1 只有 bar 无评分：`DataClockError`，文案保留 `carried targets missing current scores` 前缀。
5. 无 bar 与有 bar 无评分并存：按 4 失败（不可解释优先）。
6. `explained_missing` 未提供（`None`/空）：与旧合同行为相同。
7. v2 旧 manifest 仍可 `verify_signal_manifest`。
8. `generation`：沿用日按 `signal_day_bar_codes` 正确求 `explained_missing`；调仓日忽略该参数；`signal_day_bar_codes=None` 时为空集。
9. `shadow_cycle`：信号日 `daily` 代码集合被传入；读取异常时传 `None` 且不吞掉后续合同失败。
10. 下游回归：Top20 投影对含 `null` 的 30 只信号产出 20 只且保留 `null`；对账与 `paper/engine._target_weights` 不读 `score`；
    `query_evidence` 对 v3 文档通过。
11. Web（阶段 B）：`query_signal` 透传 `null`；页面渲染“停牌沿用”，不显示 0。

## 7. 一次性只读验收重放（阶段 A 合并后、提交验收文档前执行一次）

以环境变量 `SHAIWEI_ACCEPTANCE_REPLAY=1` 门控、默认跳过的测试：读取 20260928 PASS manifest 的目标列表与 20260929
`tushare.daily` 精确请求（只读），以确定性合成分数（有 bar 的证券按代码字典序赋值，模型不运行）调用新合同，输出写入
`tmp_path`。断言：`carried_without_score == ["SH600363"]`，`schema_version == 3`，其余 29 只 `LIVE`。只记录日期/状态/身份，
不输出任何分数或模拟仓数值；不写 `data/ ledger/ logs/`；不补造 20260929 历史信号。

## 8. 交付与生产生效

1. 本协议提交并推送（冻结）。
2. 阶段 A 实现 → 全仓测试、Ruff、`make architecture-check`、`git diff --check`（限定路径）、脱敏 → 本地提交 → 用户放行推送。
3. §7 验收重放一次 → `docs/SHADOW_CARRY_SUSPENDED_ACCEPTANCE_<日期>.md`（`GO_ENGINEERING_ONLY`）。
4. 阶段 B Web 实现 → 同上门禁 → 本地提交 → 放行推送；Web 发布另行逐字批准，须早于新 scheduler 候选启动。
5. 生产生效仅随 ADR 0016 新候选。在此之前生产仍运行 210af4d 旧合同，沿用日停牌仍可能整日失败，由巡检
   `SHADOW_SIGNAL_MISSING` / `SHADOW_SIGNAL_REPEATED_FAIL` 报告。

## 9. 失败关闭与回滚

不可解释缺口、超上限、日历/行情读取失败一律失败关闭，不降级为“看似成功”。回滚为 revert 实现提交；已生成的 v3 manifest
保留不改，v3 读取兼容保留。无数据迁移。

## 10. 验收门（全部满足才 `GO_ENGINEERING_ONLY`）

第 6 节 1–10 全部通过；全仓测试无新增失败；架构门 PASS（含 `web-ui/src/types.ts` 不超过 719 行）；§7 重放断言成立；
三个后台文件不超出第 5 节行数预算；协议提交时间早于任何实现提交。本门不授权任何生产动作。
