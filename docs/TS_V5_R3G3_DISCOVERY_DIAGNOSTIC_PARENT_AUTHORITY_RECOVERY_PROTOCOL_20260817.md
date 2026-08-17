# TS-v5 R3G-3 父裁决状态恢复协议（2026-08-17）

## 阻断事实

第一入口恢复 scope 已唯一调用。它写入授权后，在读取明细 Parquet 之前校验父裁决失败：R3G-2 的
runner 报告在独立审计前合法记录 `strategy_effective=PENDING_INDEPENDENT_AUDIT`，独立 audit 才记录
最终 `strategy_effective=REJECT`；R3G-3 错把 runner 报告也要求为最终状态。

失败前只对四份已绑定文件复算哈希，并读取父 report/audit 的聚合 JSON；未进入 first-pass manifest
校验，未读取 NAV/orders/trades，未计算诊断，输出根只有一份授权文件，效果尝试增量为0。第一恢复
scope 已关闭，不重跑。

## R2 唯一修复

R2 只把父权威校验拆成两个合法阶段：runner report 必须是
`REJECT_TS_V5_R3G2_DISCOVERY + PENDING_INDEPENDENT_AUDIT + holdout=null`；independent audit 必须是
`PASS + REJECT_TS_V5_R3G2_DISCOVERY + REJECT`。R2 绑定第一恢复 scope 和授权文件哈希，使用独立
machine/audit 输出根。

四个诊断问题、三点、2021—2023 发现期、分母、成本场景、父输入哈希和全部禁区均不变。R2 仍只
允许一次 runner、内部 replay 与独立 auditor；零新增策略尝试、零外网、零模型/回测/搜索、零
DeepSeek、零留出期/2026、零模拟仓/Web/生产授权。同 scope 不得重跑。

机器 scope：`config/ts_v5_r3g3_discovery_diagnostic_parent_authority_recovery_v1.yaml`。
