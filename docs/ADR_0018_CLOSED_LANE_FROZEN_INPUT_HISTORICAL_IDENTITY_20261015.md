# ADR 0018 · 已关闭研究线的冻结输入改按冻结提交的历史版本核验

- 日期：2026-10-15
- 状态：**ACCEPTED 2026-10-15**（用户对“走 A：解耦，ADR-003 先例”回复“按建议走A”）。本 ADR 推送即冻结；实现提交不得早于推送。
- 节点：服务于 `shadow-carry-suspended-v1` 阶段 A（ADR 0015）；先例 ADR-002（封存注册表权威）、ADR-003（封存组件身份）
- 范围：只改“已关闭研究线冻结协议如何核验其前置/冻结输入文件”的方式；不改任何协议、scope、裁决、账本、镜像或生产

## 1. 问题与结果目标

已关闭的 M6 线有两份冻结协议把**仍在演进的活文件**整文件哈希写死，并由代码/测试读取**当前工作树**比对：

| 冻结协议（冻结提交） | 钉住的活文件 | 核验位置 |
|---|---|---|
| `config/m6_csi800_production_head30_v1.yaml`（`bf0aafa`，2026-08-20） | `src/shaiwei/shadow/manifest.py`，另有 `paper/engine.py`、`backtest/strategy.py` 等 7 个前置 | `research/production_conversion/contract.py::_validate_predecessors`（读活文件） |
| `config/m6_csi800_model_attribution_v1.yaml`（`262d941`，2026-08-06） | `config/settings.yaml` | `tests/test_m6_csi800_model_attribution_protocol.py`（读活文件） |

两文件自 7 月起未改，耦合从未暴露。ADR 0015 阶段 A 按冻结协议修改 `manifest.py` 与 `settings.yaml` 后，全仓回归出现
19 项失败，全部在 M6 冻结协议测试（生产链与新功能测试全部通过）。今后任何对 `settings.yaml`、`paper/engine.py` 等的合法修改
都会再次撞上同一处，等于让一条已关闭的研究线永久冻结主线的活代码。

**结果目标。** 已关闭协议的证据仍可离线复核、篡改仍失败关闭；同时活文件可以按各自协议正常演进，不再牵连已关闭证据。

## 2. 现状证据

- 两文件在各自协议冻结提交里的历史版本哈希与冻结值逐字节一致：`settings.yaml@262d941` = `23dfbcd6…e242`，
  `manifest.py@bf0aafa` = `0c5b1b74…8839`。
- 生产转换器的其余 M6 恢复协议（entrypoint/price/release/audit 各 recovery）都经同一 `_validate_predecessors` 加载 head30 协议，
  故 19 项失败的根源只有两处核验点。
- 项目内大量其他研究线也采用“活文件哈希 = 冻结值”的写法，但未钉住本次修改的文件；不在本 ADR 范围。

## 3. 候选方案

| 方案 | 判断 |
|---|---|
| 1. 回退/绕开活文件修改 | 合同本身写在 `manifest.py`，做不到；且会让关闭的研究线永久冻结主线 |
| 2. 跳过或标记这 19 项为预期失败 | 隐藏坏消息，违反宪法第 10 条；拒绝 |
| **3. 历史身份核验** | 活文件仍等于冻结值则照旧通过；不等时改读**冻结提交**里的历史版本，其哈希必须等于冻结值，且冻结提交必须是 HEAD 的祖先；冻结提交以版本化权威配置固定，不在运行时推导。**采用** |

## 4. 冻结设计

**4.1 权威配置** `config/closed_lane_frozen_input_authority_v1.yaml`（新增，只增条目、不改旧条目）：

```yaml
schema_version: closed-lane-frozen-input-authority-v1
entries:
  - protocol_path: config/m6_csi800_production_head30_v1.yaml
    protocol_sha256: 16d2b92116864da01f6a734d3a4f17a5ac2f02d522dd17ef1048890eda8815fa
    freeze_commit: bf0aafad509a47e47d1523fbd3e32c5063a6dbfa
  - protocol_path: config/m6_csi800_model_attribution_v1.yaml
    protocol_sha256: 6c170d991df1ef75f18208837301b545fe50518c028a65c814d425fc36d7a22a
    freeze_commit: 262d941baa97c4aae4ddf57ed2950529d307dca3
```

`protocol_sha256` 必须等于协议文件当前哈希（冻结协议本身不可变，改动即失败）。

**4.2 核验器** 新增单一职责模块 `src/shaiwei/frozen_input_identity.py`：

```text
verify_frozen_input(relative, expected_sha256, *, protocol_path, root, git_runner, authority) -> "LIVE" | "HISTORICAL"
  1. relative 必须是 root 内的规范相对路径（拒绝绝对路径、..、符号链接逃逸）
  2. 活文件存在且 sha256 == expected → "LIVE"（容器内/未漂移时行为与现状完全相同）
  3. 否则：authority 中须有 protocol_path 条目，且协议文件当前哈希 == protocol_sha256
     freeze_commit 须为 HEAD 祖先（git merge-base --is-ancestor）
     git show <freeze_commit>:<relative> 的字节 sha256 == expected → "HISTORICAL"
  4. 任何一步不满足（含 git 不可用、条目缺失、非祖先、历史内容不符）→ FrozenInputIdentityError
```

git 调用经可注入的 `git_runner`（默认 `subprocess.run(["git", ...], cwd=root)`），便于离线测试；不读 `.env`、不联网、不写文件。

**4.3 首批消费者（只迁这两处，同 ADR-003 “不批量改写其他历史入口”）**

1. `research/production_conversion/contract.py::_validate_predecessors`：把 `sha256_file(path) != expected` 换成
   `verify_frozen_input(..., protocol_path="config/m6_csi800_production_head30_v1.yaml")`，异常适配为原 `ProtocolError`
   （文案保留 `production-converter predecessor hash differs: {name}`）。hash addendum 对 `m6_result_protocol` 的修正值逻辑不变。
2. `tests/test_m6_csi800_model_attribution_protocol.py`：`settings` 冻结输入改用核验器，断言结果 ∈ {LIVE, HISTORICAL}。

`price_recovery_validation.py` 有一份同名私有 `_validate_predecessors`；若全仓回归显示它也受影响，按同一方式迁移并在提交说明中列出，
否则不动。

## 5. 影响边界

- 不改任何冻结协议、scope、approval、claim、裁决、账本、镜像、容器、生产代码路径。
- 不改 M6 已执行结果的任何证据；不重跑 M6 任何 runner/auditor。
- 容器内（无 `.git`）行为：活文件等于冻结值时与现状相同；漂移时失败关闭（M6 已关闭，不再运行镜像）。
- 新 release / 新协议仍必须使用当前文件哈希；本核验器只服务已冻结协议的离线复核，不得用来签发新的执行授权。

## 6. 失败关闭与回滚

见 4.2 第 4 步。回滚为 revert 实现提交；权威配置文件保留无害。

## 7. 验收指标

- 核验器单元测试：活文件匹配→LIVE；活文件漂移+历史匹配→HISTORICAL；历史内容不符、冻结提交非祖先、条目缺失、协议哈希被改、
  路径逃逸、git 不可用 → 全部 `FrozenInputIdentityError`。
- 真实仓库只读断言：两条权威条目的历史 blob 哈希等于各自冻结值。
- 全仓回归：此前 19 项转绿，且无新增失败；`make architecture-check`、Ruff、`git diff --check`、脱敏通过。
- 本 ADR 推送时间早于实现提交。

## 8. 退出 / 复审触发器

其他已关闭研究线若因活文件演进出现同类失败，以新增权威条目 + 迁移该消费者的方式处理，每次单独提交并在 STATE 记录；
不得为通过测试而修改任何冻结协议或冻结哈希。
