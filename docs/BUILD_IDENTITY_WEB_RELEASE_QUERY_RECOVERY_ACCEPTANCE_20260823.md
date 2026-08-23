# A1-4C-R1 Web 查询与 successor release 恢复验收

- 协议：`a1-4c-r1-web-query-release-recovery-v1`
- 日期：2026-08-23（UTC+8）
- 当前裁决：`GO_RELEASE_READY_NOT_DEPLOYED`
- 策略效果：`NOT_EVALUATED`
- 生产授权：`none`

## 1. 通知证据语义恢复

查询层不再把跨日复用的稳定内容 `message_id` 误当成一条无限增长的重试链。纯解析模块
`web/notification_evidence.py` 以每个 `attempt=1` 开启一次 occurrence，并保持以下失败关闭门：

- 每个 occurrence 必须从 1 开始、连续递增，声明的 `max_attempts` 唯一且不超过硬上限 16；
- 相同内容身份必须始终绑定同一事件；重复尝试身份、字段越界、缺首项、跳号和跨事件均拒绝；
- 通知详情返回截止日期最新 occurrence，同日系统统计仍保留当天全部尝试；
- 不改通知日志、发送端、内容身份、重试实现或 scheduler。

20 个交易日复用同一内容身份的 fixture 已通过；真实本地证据截至 2026-08-21 可稳定生成：数据质量
`PASS`、系统运行 `PASS`、通知 `WARN`，其中 9 个消息、12 次尝试、3 次失败和 3 次恢复均保留，40 条
早期不可寻址记录仍如实披露。

## 2. 发布门与架构

- `operations.py` 从冻结的 1,160 行降至 1,060 行；新解析模块 172 行，未扩大热点文件；
- 真实 HTTP 门由健康/总览扩至数据质量、系统运行、策略工厂、因子、实验、模拟组合和信号等关键
  只读接口，并继续检查 UI 根路径与 CSP；
- release state 同时严格读取冻结 v1 和 successor v2；v2 记录发布代际、当前/前一候选和精确镜像；
- 新的显式 `prepare-successor` 动作先核对 deployed state 与旧 candidate 自哈希，再不可覆盖归档旧
  candidate；归档损坏或内容漂移会失败关闭；
- successor 提升固定为“新候选全接口 → 精确 previous 只读基线 → 同一新候选全接口”，任一步失败
  恢复 previous state 和镜像；不触碰 scheduler。

所有新增生产模块均低于 400 行；没有新增依赖、写接口、生产模型或交易授权。

## 3. 工程验证

- 通知/query/release/state/successor 专项：58 PASS；
- 架构宪法：13 PASS；
- 全仓：1,766 PASS，17 条均为既有第三方或 pandas 未来行为警告；
- 账本追加门：86 PASS；
- Ruff、compileall、pip check、Compose config、diff-check：PASS；
- 当前阶段未归档旧 candidate、未构建 successor、未重启 Web，scheduler 未改变。

## 4. 下一步边界

只有本实现提交并推送后，才允许执行一次显式 successor 准备、两角色各一次构建，以及
“新 → 当前 v2 → 同一新”本机只读演练。随后必须复核全关键 API、七页真实浏览器、前端单元、CSP、
本机端口/挂载/权限和 scheduler 身份；在这些证据完成前不把 A1-4C/R1 裁为最终发布 GO。
