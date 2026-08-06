# ADR-0005：M6 审计入口失败使用原镜像薄恢复层

- 状态：`ACCEPTED_FOR_RECOVERY_PROTOCOL_FREEZE`
- 日期：2026-08-06
- 决策范围：M6-2 runner 已完成但 auditor 未进入函数时的独立审计恢复、镜像和权限边界
- 不授权：原 runner 重跑、Qlib/标签读取、训练、预测、回测、指标或裁决变更、实验账本、前瞻、
  模拟仓、Web、生产或 scheduler 修改

## 1. 问题与结果目标

M6-2 唯一 runner 已生成两遍完全封存的真实效果产物；唯一 auditor 进程却在
`audit(**vars(args))` 的 Python 参数绑定阶段失败，尚未进入独立审计函数。原 release 已消费两个研究
尝试且禁止重跑，但没有独立 audit PASS 就不能把 runner 暂定标签当作权威结果。

结果目标是：在不重新计算 runner、不改变原独立审计算法、也不扩大数据权限的前提下，对已封存的
199 文件 effect 树执行恰好一次独立审计，并留下可证明恢复授权、原算法身份和输入前后未变的证据。

## 2. 不可触碰事实

- 原 scope、approval、镜像、report、两遍 manifest 和完整 effect 树均已内容寻址；
- audit 函数、reader、统计和终态逻辑没有被首次 auditor 调用；audit 输出目录为空；
- 原 runner 不得再次启动，任何新审计必须另立 scope 和明确授权；
- 当前已经看到 runner 输出的暂定终态标签，因此恢复只能修基础设施，不能修改任何研究语义。

## 3. 方案比较

### A. 直接再次运行原 Compose auditor

技术上只需把 `main()` 参数映射修正，但原 scope 固定 auditor 进程调用一次且禁止同 release 重试；
第二次运行会突破用户明确授权和封存合同。拒绝。

### B. 用当前代码重建完整 M6 镜像并让旧 audit 验证新运行身份

完整重建会改变 `/workspace` 代码快照和发布清单，而旧 runner report 绑定原镜像运行身份；若放宽身份
校验会掩盖证据漂移，若不放宽则必然失败。拒绝。

### C. 以原镜像为不可变 base，在 `/workspace` 外增加薄控制入口

原 `/workspace`、Git 身份、发布清单以及 audit/reader/statistics 字节保持不变。新入口只验证恢复
scope/approval和完整 effect 树，再用显式关键字调用原 `audit()`；新薄镜像、入口 SHA、命令、挂载和
资源全部由新 scope 绑定。选择本方案。

## 4. 决策与边界

恢复实现分成三个单一职责：恢复合同验证、封存树身份计算、薄入口编排。未来主 CLI 同时做最小显式
参数映射修复并增加回归测试，但恢复运行不使用修改后的 `/workspace`；它调用原镜像内的原函数。

恢复容器只挂载原 scope/approval、新 recovery scope/approval、effect 只读和空 audit 可写。无 Qlib、
网络、secret、Docker socket、整仓或生产账本。输出只允许原 `audit.json` 和包含恢复身份、audit SHA、
effect 前后 SHA 的 receipt；任何其他写入或输入漂移失败关闭。

新恢复 scope 不继承旧批准。用户必须明确批准完整 scope SHA 和动作
`M6_INDEPENDENT_AUDIT_ENTRYPOINT_RECOVERY_ONCE`；失败后不允许第二次恢复调用。

## 5. 迁移、回滚与停用

没有数据库、账本或公共 API 迁移。原 scope、approval、effect 和失败记录永久保留。恢复失败时只保留
新 scope/approval及可能的 write-once 失败证据，不修改原 effect；恢复成功后薄镜像和 Compose 仅作为
该事故的可复算证据，不成为通用服务，也不接生产。

未来 M6 或其他研究 release 使用已修复并有 CLI 回归测试的主入口，不复用本次恢复 wrapper；当原
审计 PASS、receipt 完整且验收文档提交后，本恢复能力退出活动路线。

## 6. 验收

- 对 recovery scope/approval 的未知字段、错误 SHA、扩大权限、额外挂载/命令和非空 audit 失败关闭；
- 对 effect 缺文件、一字节篡改、增删文件、原 release/approval 漂移失败关闭；
- 合成 fixture 证明薄入口恰好调用一次原 audit，前后 effect 树一致且 receipt write-once；
- 新薄镜像为断网、非 root、只读根和窄挂载，原镜像 ID 与发布身份可复核；
- `make architecture-check`、全仓测试、Ruff、Compose、脱敏与 scheduler 身份门通过；
- 真实恢复执行仍须新完整 scope 的用户批准。
