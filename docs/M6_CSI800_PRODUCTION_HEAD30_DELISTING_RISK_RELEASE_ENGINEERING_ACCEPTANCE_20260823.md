# M6-5C-C 退市风险恢复 release 工程验收

- 日期：2026-08-23（UTC+8）
- 裁决：`GO_IMPLEMENTATION_READY_FOR_ONE_OFFLINE_IMAGE`
- 策略权限：`POST_HOC_METHOD_RECOVERY_DIAGNOSTIC_ONLY`
- 生产授权：`none`

## 1. 交付边界

本节点只实现结果盲 release 工程，不读取真实 R2 目标、raw 行情或历史效果，不创建 approval，不向
canonical experiment ledger 追加真实尝试，也不运行真实 runner/auditor。旧 M6-5B-R1 scope 继续永久
关闭，旧 `paper-v1`、生产信号、模拟仓、Web 和 scheduler 均未改变。

新增职责按模块拆分为：PIT 风险回放、冻结门包装、独立风险重建、claim-first runner、artifact-only
auditor、release 合同、metadata builder 与 synthetic fixture；全部生产模块低于 400 行。独立
Dockerfile/Compose 已登记为组件资产，没有扩大全局 `CONTROLLED_FILES` 或基础 Dockerfile。

## 2. claim-first 与容器边界

- runner 在 effect reader 前调用共享 `read_effect_after_claim`，先 fsync canonical ledger，再 fsync
  内容寻址 receipt；失败后保守消费尝试，同 scope 不得重开；
- 新入口进入自发现 claim registry，原 8 个关闭入口及源码 SHA 不变；
- runner 只对单个 `ledger/experiments.csv`、专用 claim 目录和 effect 根具写权限；R2/raw 只读；
- auditor 只读 effect、claim 与 ledger，只有独立 audit 根可写，不挂 raw 或 R2；
- 三个角色均断网、只读根、非 root、drop all capabilities、禁止提权且不挂 `.env`/Docker socket/整仓。

## 3. 合成证据

合成 30 只、六窗口路径中，一只股票在持仓后形成连续 10 个有效收盘严格低于 1 元；每窗口恰好产生
一次锁存卖出，共 6 个风险退出订单。风险 `as_of` 始终为执行日前一官方开市日；first/replay 逐内容
一致，独立实现不导入主 simulation、主 evaluator 或 `evaluate_risk_overlay`，并逐项复算同结果。

临时账本 fixture 证明 reader 进入时账本已有唯一 claim 且 receipt 已存在；第二次同 scope 调用失败
关闭。fixture 未触碰 canonical ledger，也未读取真实目标、价格或效果。

## 4. 验证

- M6-5C/claim/build 专项：34 PASS；
- 全仓：1,814 PASS，17 条既有第三方/弃用提示；
- architecture-check：13 PASS；
- Ruff、compileall、Compose 合同与 `git diff --check`：PASS；
- 新组件构建资产：93/93 唯一登记；效果入口：9/9 自发现登记，其中旧入口 8 个、claim-first 新入口 1 个。

## 5. 下一步与停止点

实现提交推送后，才允许基于该已推送 revision 生成 source manifest，断网构建一次独立镜像，并让
daemon synthetic fixture 运行一次；随后只生成 metadata-only release scope。scope 与最终验收推送后
必须停止，等待用户逐字绑定 scope SHA 与冻结动作授权唯一真实运行。
