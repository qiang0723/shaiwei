# M6 生产 Head30 目标投资比例绑定补正验收

## 结论

`PASS_PRE_EFFECT_BINDING_FIX`。外部复核发现的 release 阻断成立：协议冻结
`target_investment_ratio=1.0`，但原适配器仍可能继承 Qlib `BaseSignalStrategy` 的0.95默认值。该缺口
已在任何 runner、Qlib挂载和效果读取前修复，不改变研究问题、G0、窗口、成本或尝试数。

## 补正内容

1. `BiweeklyRankHeadEqualWeightStrategy` 将 `risk_degree` 改为必填关键字；缺失直接构造失败，任何非
   1.0值（包括0.95）失败关闭，只有冻结协议值被显式传给父类。
2. 协议合同逐字段校验完整 `treatment_components`：确定性Head30、1/30目标权重、完整目标再平衡、
   1.0目标投资比例，并校验 `target_weight × topk = target_investment_ratio`。
3. `Protocol.target_investment_ratio` 成为未来runner唯一合法读取入口；runner仍未实现，不能绕过精确
   release scope和用户批准。
4. 删除只修改副本、其结果不被后续读取的模拟卖出成交；正式成交检查仍由Qlib executor执行。
5. 新增生产selector交叉测试：同一含平分和缺失值的分数截面分别经过`write_signal_manifest`与研究
   `ranked_topk`，目标证券和顺序必须完全一致。

## 验证

- Head30专项：8 PASS；
- 架构宪法：13 PASS；
- 全仓：1,506 PASS，17条既有第三方/旧M7 warning；
- Ruff、compileall、`git diff --check`和新增范围敏感模式检查PASS；
- 新模块仍低于400行软上限，没有新增依赖、Dockerfile、compose、服务或公共写接口。

## 权限与状态

- 真实预测、收益、净值、换手和成本读取：0；
- 新组合转换尝试：0；实验账本写入：0；
- scheduler、生产镜像、模拟仓、Web、信号和模型：未修改、未重启；
- 七个自然账本及两份既有未跟踪校准文档未暂存、未改写。

## 下一节点

`M6-4B`只能施工结果盲runner、内部replay、独立auditor、隔离镜像和release scope。若新增
Dockerfile/compose，必须先进入`CONTROLLED_FILES`并由测试锁定；release构建必须使用干净、内容寻址
的Git工作树，不能通过暂存、回写或删除自然账本绕过clean-worktree门。scope生成后再次停止，等待
用户绑定SHA精确批准真实效果。
