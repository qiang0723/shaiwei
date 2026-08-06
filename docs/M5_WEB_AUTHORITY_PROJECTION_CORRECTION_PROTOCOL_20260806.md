# M5 最新权威状态 Web 投影补正协议

- 协议 ID：`m5-web-authority-projection-correction-v1`
- 冻结时间：2026-08-06T17:30:40+08:00
- 适用范围：本机只读策略工厂查询与展示
- 权限：只读投影施工；不授权研究、外网、模型、回测、生产或写 API

## 1. 结果目标与用户决策

`strategy_factory_v2` 生成于 2026-08-05，早于 M5-2B-R2 的真实来源谱系门。Web 必须让用户直接看到
该批次已经因历史版本证据不足进入 `BLOCKED_DATA`，且策略仍为 `NOT_EVALUATED`。页面用于决定暂停、
补权威来源或转向其他研究批次，不能把数据门失败显示成策略拒绝、活跃任务或第九个效果工作包。

## 2. 权威输入与不可触碰边界

唯一权威输入冻结为：

1. `config/m5_dynamic_fundamental_source_lineage_release_scope_v2.json`；
2. `docs/M5_DYNAMIC_FUNDAMENTAL_SOURCE_LINEAGE_SCOPE_RECOVERY_REAL_RUN_ACCEPTANCE_20260806.md`；
3. `docs/PLATFORM_ROUTE_REVIEW_20260806.md`；
4. 既有 M5 策略工厂目录、计数修正 addendum 及其全部证据。

旧 `strategy_factory_v2` 的 pointer、快照和哈希永久保留，不覆盖、不改写。自然 scheduler、生产模型、
门禁、账本、原始数据和研究产物均不在本任务触碰面。北交所仍为 0。

## 3. 复用与新增职责

- 复用既有目录验证、M1 身份核对、正式因子准入核对、内容寻址快照、GET/HEAD API 和 Web 证据抽屉。
- 新增一个窄 authority overlay，只校验固定文件哈希并输出一条终态数据门裁决。
- 新输出目录为 `data/web/research_snapshots/strategy_factory_v3`；旧 v2 是回滚真身。
- 不新增常驻服务、依赖、缓存、队列、Worker、数据库、写接口或第二套业务计算。

## 4. 输出合同

策略工厂 `data` 新增：

- `authority_projection_version=m5-strategy-factory-authority-projection-v1`；
- `recent_gate_decisions`，本版必须恰好一条，字段固定为：
  `decision_id/display_name/family_id/universe_ids/gate_stage/terminal_state/evidence_tier/verdict/`
  `strategy_effective/effect_read/real_gate_run_count/conflict_group_count/forward_only_group_count/`
  `pit_resolved_group_count/route_status/blocked_reason/next_action/release_scope_sha256/run_id/`
  `independent_audit_sha256/registry_event_sha256/evidence_commit/route_review_commit/`
  `production_authorization/evidence_ids`。

固定业务事实为：三池动态基本面来源谱系门、一次真实断网数据门运行、23 个冲突组、23 个仅本地观察、
0 个历史 PIT 版本链可恢复、`BLOCKED_DATA / LINEAGE_NO_GO_ONLY`、
`NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION`、`NOT_EVALUATED`、`effect_read=false`、
`route_status=PAUSE`、`production_authorization=none`。

`active_tasks` 必须继续为空；既有 8 个工作包和冻结计数不得改变。该裁决不得进入收益排序、因子准入或
效果工作包计数。

## 5. 时间、来源与失败关闭

- `generated_at` 取本 addendum 的冻结时间，`as_of` 为 2026-08-06，时区为 `Asia/Shanghai`。
- 投影生成时核验所有固定来源的 SHA-256；查询时核验 pointer、快照哈希、内容身份和全部固定事实。
- 缺文件、符号链接、路径越界、哈希漂移、字段/计数/终态漂移或出现 `.BJ` 时失败关闭。
- v3 不存在时返回 `NOT_READY`；v3 无效时返回 `EVIDENCE_MISMATCH`。禁止自动回退 v2。

## 6. 页面最小展示

页面在现有首屏与研究地图之间增加一个紧凑的“最新权威数据门”区块，必须展示：

- 结论：历史来源谱系不足，当前批次阻断；
- 范围：科创50、科创板中盘 PIT、科创板小盘 PIT；
- 23 / 23 / 0 三项聚合计数；
- `未评价策略效果`、`未授权生产`；
- 下一合法动作：本支线暂停，只有补齐权威历史版本与生效链后才可另立协议。

技术枚举、release、run、commit 和哈希只放入可展开的技术证据，不在主视图制造噪声。页面不增加执行、
重跑、补数、调参或提交按钮。

## 7. 验证、迁移与回滚

- 后端：确定性双构建、write-once、来源篡改、固定事实漂移、pointer/快照篡改、API GET/HEAD only。
- 前端：类型与运行时验证、坏消息不可隐藏、技术标识默认隐藏、无写控件。
- 页面：1440/1024/768/390/320 宽度无页面级横向溢出，键盘和 WCAG 既有门继续通过。
- 全仓：相称测试、`make architecture-check`、Ruff、compileall、`git diff --check` 和脱敏检查。
- 部署：只更新 Web 镜像/只读投影，证明 scheduler 容器和镜像身份不变。
- 回滚：恢复查询默认目录至 v2 并恢复旧 Web 镜像；v3 证据保留，不删除。

## 8. 停止条件

本任务在 v3 真身、API、页面和真实本机部署一致后结束。不借机重做视觉、不扩展 M5 控制面，也不自动
进入权威数据采购、M5-2C 或中证800模型归因研究。
