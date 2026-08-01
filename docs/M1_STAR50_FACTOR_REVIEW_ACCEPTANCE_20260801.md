# M1-2 科创50机械 Top2 独立审查终版验收

日期：2026-08-01（UTC+8）  
裁决：`STOP_M1_2_REVIEW_CONTRACT`  
策略有效性：`NOT_EVALUATED`  
M1-3 验证/G1 协议授权：`false`  
生产授权：`none`

## 结论

M1-2 没有通过，不能进入 M1-3，也不能解封 2023—2025 验证窗或运行 G1。固定批次在第 1/8 个
`deepseek-v4-pro` 响应后按结果前规则立即停止：JSON schema 为 PASS，但确定性自由文本语义门检出
`AMBIGUOUS_CHANGE_LANGUAGE` 与 `DIFFERENT_DSL_EXPRESSION`，终态为
`FAIL_SEMANTIC_CONTRACT / semantic_contract_violation`。

该响应携带的结构化角色结论为 `BLOCKER_FOUND`，并记录 1 个 critical、1 个 major finding；但响应
本身违反审查合同，因此这些内容没有候选裁决权。机器报告的 `candidate_decisions` 为空，不能据此说
第一条因子在经济上已被权威拒绝，也没有评价第二条因子。权威结论只到“本批审查合同失败、停止”。

按冻结规则，这一完成响应计入批次 N，不补发、不换角色、不改提示、不递补第 3 名。两条原公式、
方向和 M1-1 机械排序均未改变。

## 调用与费用

- 用户在主窗口明确批准向 DeepSeek 发送两条候选公式、经济假设、公开研究背景与固定审查问题。
- 实际完成响应 1/8；HTTP 200，传输严格为 1 个 STARTED + 1 个 COMPLETED，无重试、无重复请求、
  无计费不确定性。
- 实际估算费用 `0.002073210000 USD`，低于 `0.25 USD` 本批硬上限；停止后没有继续消耗额度。
- 发现期 RankIC、覆盖、排序分、封存验证、压力、G1、模型、组合、前瞻和生产结果均未进入请求。

## 零调用恢复留痕

首次实际请求前出现过两项基础设施阻断，均在账本、结果文件、provider 调用和费用为 0 时处理：

1. live profile 漏挂 AlphaGen 表达式解析器；恢复附录先行推送，只增加只读挂载和测试。
2. execution release 曾覆盖镜像受控 `config/`，导致代码快照必然不一致；第二份附录先行推送，只把
   同一 release 移到只读 `/opt/shaiwei/`，未改研究载荷或边界。

另有一次空密钥、零研究载荷 TLS 探针用于定位瞬时连接问题；它不创建 provider、不发送候选、不计费。
恢复真身分别为 `config/m1_star50_factor_review_recovery_v1.yaml` 和
`config/m1_star50_factor_review_recovery_v2.yaml`。

## 证据与幂等

- 终态报告 SHA-256：`5f2887a788144fda650232b259d1985e841f1224b51b124723c981020d318d26`。
- 专属 review/transport 账本 SHA-256：`ff5371be...e4baf` / `e5b79eeb...1dd1b`。
- 5 个不可变证据文件的规范树 SHA-256：
  `bb54891addceea302d27ed7f9bd79ef11091f86554031c2cc7ba15d8340982d2`。
- M1-1 manifest、报告和尝试账本哈希仍为 `835d6cf6...f29fa59`、`5cdf09ca...8c45cb`、
  `262fcbb8...794092`，机械 Top2 与发现证据未被改写。
- 无密钥复跑返回 `idempotent_reuse=true / external_api_calls_this_run=0`；证据树与两账本哈希前后
  完全不变。

## 范围、秘密与生产

- `sealed_validation_read=false`、`stress_or_g1_run=false`、`model_or_portfolio_run=false`、
  `new_candidates_generated=false`，生产授权仍为 `none`。
- DeepSeek key 只由项目内 Git 忽略且权限 0600 的 `.env` 注入获批的临时 live 容器；没有进入镜像、
  Git、请求正文、响应证据、账本、报告或日志。幂等重放为空密钥。
- scheduler 始终保持容器 `fd8e96152b53`、镜像 `sha256:de87ec74...0261`、原创建时间和
  running/healthy，未重启。

## 验证与下一步

执行前与恢复后均通过宿主全仓 433 PASS、Ruff、compileall、pip check、Compose、diff-check、账本
追加约束、凭据卫生、断网预检和镜像内身份复核。终态追加后全仓 434 PASS、终态专项 30 PASS；
结果以终版 manifest 与 Git 提交为准。

本批没有通过，因此**不允许另立 M1-3 验证/G1 协议**。若未来重新研究，只能由用户另行决定并建立
新的结果前研究批次；不得补发本批第 1 份、从第 2 份续跑、修正文案后回救、替换候选或使用剩余额度
静默重启。科创50数据可行性、P2 工程 GO 与 P2-2C 历史策略 REJECT 均保持原结论，不受本批改写。
