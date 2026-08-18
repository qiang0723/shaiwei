# TS-v6-3 R2 效果读取恢复协议（2026-08-18）

- 机器真身：`config/ts_v6_3_ranked_subset_effect_recovery_r2.yaml`，SHA-256
  `26a4c84ed4ee3371a05f423f05d8d45dd5559fe1cf135fd37d398821e32192d4`
- 状态：`RESULT_BLIND_EFFECT_RECOVERY_SCOPE_FROZEN_ZERO_NEW_ATTEMPT`；生产授权 `none`
- 用户裁决（2026-08-18）：按选项 A，失败 scope 消耗 0 次效果尝试，本恢复 scope 消耗 1 次

## 1. 失败事实（全部留痕）

- 原 scope（输出根 `ts-v6-3-ranked-subset-effect-v1`）在唯一效果读取中，于父产物谱系校验
  处失败关闭：`TS-v6-3 bound R3G-2 first-pass bundle differs`。
- 根因：实现常量把 R3G-2 first-pass 的 `manifest.json` 文件哈希（`d00f2fce…`）误用作产物树
  bundle 哈希；真实 bundle 哈希为 `f36bc46f…`（已重算验证，38 个文件完整）。
- 失败发生在 `simulate` 之前：`first_pass/`、`replay/` 从未创建，**没有任何候选事件的收益
  被计算或读取**；语义标记 `effect_read_started.json`（SHA `2a866ca3…`）与失败回执
  `failure.json`（SHA `bf4639dd…`）永久保留并绑定进本协议。
- 原 scope 关闭，不得同 scope 重跑。

## 2. 会计裁决

仓库先例（R3G-2 原始效果入口恢复、R3G-3 runner 恢复）：未发生真实结果读取的技术失败记
零新增效果尝试。用户 2026-08-18 批准按同一原则处理：失败 scope 记 0 次，本 R2 为唯一一次
真实发现期读取、消耗 1 次效果预算，其后 TS 支线剩余预算 1。

## 3. 工程修复（不改变任何研究语义）

1. 常量更正为 `f36bc46f…`；
2. 父产物 bundle 校验移到语义读取标记**之前**——此后这类绑定失败一律是标记前技术失败，
   不消耗尝试；
3. 新输出根 `ts-v6-3-ranked-subset-effect-v1-r2`；原输出根只读挂载；
4. 候选集（v6-1 冻结 Top-94）、分数、门禁、时间角色、防火墙与 `config/ts_v6_3_ranked_subset_effect_v1.yaml`
   逐字节不变；复用原 scope 已封存的键级预检（SHA `af2541c3…`），不重算。

## 4. 裁决与边界

与父协议完全一致：`REJECT_TS_V6_3_RANKED_SUBSET_DISCOVERY`（任一门失败，剩 1 次预算只准
退出机制单变量研究或支线关闭）/ `GO_TS_V6_3_DRAFT_SEPARATE_HOLDOUT_PROTOCOL_ONLY`（只授权
起草留出期协议）/ `BLOCKED_PRE_EFFECT`。断网、write-once、确定性复算、独立审计、scheduler
不重启——全部不变。
