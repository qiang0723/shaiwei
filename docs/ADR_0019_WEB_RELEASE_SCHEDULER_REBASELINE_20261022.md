# ADR 0019 · Web 发布门认可有 START_PASS 记录的 scheduler 合法更换

- 日期：2026-10-22
- 状态：**ACCEPTED 2026-10-22**（用户在 O4 受阻后选择“照常切换，Web 验收后再发”，其选项内容即“写 ADR 修 Web 发布门：认可有
  START_PASS 记录的合法 scheduler 更换”；并定于 2026-10-23 上午发布）。本 ADR 推送即冻结，实现提交不得早于推送。
- 关联：STATE 2026-10-22 O4 条目；`src/shaiwei/build_identity/web_release_deploy.py::_deployed_baseline`；
  `src/shaiwei/release.py` 发布审计哈希链；docs/BUILD_IDENTITY_WEB_RELEASE_PROTOCOL_20260823.md

## 1. 问题与结果目标

Web 后继发布（`promote_with_rollback_drill`）在部署前调用 `_deployed_baseline`，要求“当前 scheduler 容器身份 == 上次 Web 发布时
记录的 scheduler 身份”。上次 Web 发布为 08-23，记录容器 `183b8c6c`；08-28 R2D-R2 的启动与回滚、10-22 R2D-lite 的切换都合法地更换了
scheduler 容器（均有 scheduler 发布审计 `START_PASS`）。因此该门自 08-28 起永久不可通过，10-22 O4 在部署前失败关闭。

该检查的本意是发现“Web 发布期间或之外有人绕过发布流程改动了 scheduler”，而不是禁止 scheduler 走正规发布。**结果目标**：scheduler 经
正规发布（有哈希链校验通过的 `START_PASS`）更换后，Web 后继发布可以重设基线；任何无发布记录的 scheduler 变化仍失败关闭。

## 2. 现状证据

- Web 状态 `scheduler_identity`：容器 `183b8c6c`、镜像 722f63de、快照 4e5244b6、revision 210af4d。
- scheduler 发布审计 `START_PASS`：08-03 `183b8c6c`；08-28 `a2f2393f`（候选，随后回滚）与 `7a55151d`（旧生产）；10-22 `98d1f84c`
  （新候选，镜像 ce1a1351、快照 8b5b8877、revision f6d3b70）。审计为 SHA-256 链，`release._validate_audit_chain` 逐条校验。
- `scheduler_identity()` 字段：container_id、image_id、health（须 healthy）、snapshot、revision。
- 本发布门文件未被任何冻结配置钉住，也不属于 R2D 13 个控制器组件。

## 3. 候选方案

| 方案 | 判断 |
|---|---|
| 手工改 Web 状态中的 scheduler 身份 / 删状态走首次迁移 | 篡改发布证据、绕过门禁；拒绝 |
| 去掉该检查 | 失去“发现绕过发布流程的 scheduler 变化”的能力；拒绝 |
| **按 scheduler 发布审计重设基线** | 身份不同时，要求当前 scheduler 的五元身份在已校验哈希链的发布审计中有对应 `START_PASS`；有则重设基线并留痕，无则失败关闭。**采用** |

## 4. 冻结设计

- 新增纯函数 `scheduler_rebaseline(previous, current, records) -> dict | None`（放在 `web_release_runtime.py`）：
  - `previous == current` → `None`（无更换，行为与现状相同）；
  - 否则在 `records` 中找 `event == "START_PASS"` 且 `details.container_id == current.container_id`、`details.image_id ==
    current.image_id`、`details.code_snapshot_sha256 == current.snapshot`、`details.git_head == current.revision` 的记录；取最后一条，
    返回 `{"from_container_id", "to_container_id", "start_pass_record_sha256", "start_pass_recorded_at"}`；
  - 找不到 → `WebReleaseError("scheduler identity differs from previous Web release state and lacks a START_PASS release record")`。
- `records` 由 `release._validate_audit_chain()` 读取（哈希链不通过即抛错，失败关闭）；不修改 `release.py`（控制器组件）。
- `_deployed_baseline` 改为调用上述函数；返回的重设基线证据写入本次 Web 发布审计的开始事件（`scheduler_rebaseline` 字段）与新
  Web 状态。发布过程中的“前后 scheduler 身份不变”检查（`scheduler_identity_before` 与 `scheduler_after`）保持不变。
- `start_deployed_release`、`verify_deployed_release` 的严格相等检查**不变**：scheduler 再次发布后，须再做一次 Web 后继发布来重设基线。

## 5. 影响边界

只改 Web 发布门的基线判定；不改 scheduler、发布原语、R2D 守卫、Web 查询/页面、任何账本或冻结判据。

## 6. 失败关闭与回滚

审计链校验失败、无匹配 `START_PASS`、scheduler 不健康 → 失败关闭，不部署。回滚为 revert 实现提交。

## 7. 验收

单元测试：未更换返回 `None`；有匹配 `START_PASS` 返回证据；无记录、镜像/快照/revision 任一不符均失败；多条匹配取最后一条；
`_deployed_baseline` 使用该函数并把证据带回。全仓测试、架构门、Ruff、diff-check、脱敏通过。之后重建 Web 候选并完成后继发布（每步用户批准）。
