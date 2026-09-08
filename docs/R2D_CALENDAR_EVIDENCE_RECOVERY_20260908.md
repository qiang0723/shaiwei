# R2D 冻结日历证据恢复（2026-09-08）

状态：CALENDAR_BYTES_RECOVERED / NATURAL_CLOSE_NOT_VERIFIED / R2D_OPEN。

## 现场及原因边界

R3F的20260908 16:40—19:00窗口已过期。晚间授权核验在读取旧日历路径时失败：
`data/qlib_forward/versions/4e5244b6b027-f4430e0fdc0f/calendars/day.txt`及其版本目录不存在。
已读release/health/账本/双账户产物的汇总未在进程失败前输出，不能宣称当天自然闭环PASS，
亦未自动重跑该部分。后续须单独补齐有明确边界的只读核验。

同轮尚未执行的记录与Docker检查确认：`.release/r2d-execution-scopes`和
`.release/r2d-executions`均不存在。这仅说明标准入口没有文件，不全面排除其他旁路执行。
旧容器`7a55151d...80c4`仍运行旧镜像`722f63de...13b76`，healthy、restart=0、只读根及四挂载
符合协议；Compose project为`shaiwei_init`。旧镜像snapshot/revision匹配、lock-authority标签
缺省；候选三个发布标签匹配。此前用project=shaiwei查询为空不能证明容器漂移。

`config/settings.yaml`设置`qlib_versions_to_keep=2`。当前代码及旧生产提交
`210af4dab33c85b38c05b28f56c176b7970c41db`中的`_prune_versions`按目录mtime保留current与
最近keep个版本，删除其余目录，不识别发布协议对文件的引用。现场恰好保留20260907/20260908
两版，与此清理机制吻合；没有删除日志，不能宣称证明了具体删除事件。

## 日历谱系与独立副本

原冻结SHA-256：`c9916944c6865cf4e1e6b15af7ac90a54d2275320d25353873071f08d892b114`。
以下两份现存日历哈希均与之相同：

- `data/qlib_forward/versions/4e5244b6b027-ec09aa149dca/calendars/day.txt`；对应manifest SHA为
  `7b2e52c856f1921654ffad3a9c513d2a7170d676914d127993bba5fb35b253aa`，generated_at为
  `2026-09-07T11:50:26.979041+00:00`。
- `data/qlib_forward/versions/4e5244b6b027-b7d19d335588/calendars/day.txt`；对应manifest SHA为
  `40c040bf8f152dff314db2a1f083380d86b0b4f44ca3c855c67339143e7cfa67`，generated_at为
  `2026-09-08T12:21:39.173064+00:00`；本次以此作为封存来源。

两份manifest purpose均为forward-shadow，code snapshot均为旧生产4e5244b6...2708。
只验证manifest身份/文件哈希和日历，不重新计算完整qlib树，不评价行情或策略效果。

独立副本路径：
`data/control/r2d-calendar-evidence/c9916944c6865cf4e1e6b15af7ac90a54d2275320d25353873071f08d892b114/day.txt`。
共23,652字节。新增前检查路径无符号链接、目标不存在、来源哈希匹配；通过apply_patch新增后
复读核验与来源逐字节一致。副本被Git忽略，日历业务数据不提交。
独立路径不在qlib版本清理范围，但不是操作系统不可变文件；以后每次使用须校验冻结SHA，
不覆盖已有证据，缺失或漂移即失败关闭。原缓存路径、旧R3F协议和生产保留规则均未改。

日历确认20260908后首个交易日为20260909。这只证明日期，不证明readiness或自然闭环，
不授权新的scope或生产动作。

## 验证与唯一下一节点

验证范围：来源/副本字节一致、原冻结SHA一致、日期顺序与唯一性、Git忽略规则及文档差异。
本节点仅证据/文档恢复，不改生产代码，不运行需要真实密钥的测试。

下一节点先单独补齐20260908自然闭环元数据核验，随后才能冻结新的start-only协议，引用独立
日历并重绑最新双账户FORWARD、实际Compose project、Git/13组件身份及有效窗口。
旧R3F不覆盖、不顺延，Phase A不重跑。候选首自然日验收后才关闭R2D，继而进入G1正控、
Style Attribution v1、W7及资金梯度。
