# M6-5A：生产 Head30 的 50 万元账户可行性工程验收

日期：2026-08-20（UTC+8）

裁决：`GO_ENGINEERING_ONLY`

策略效果：`NOT_EVALUATED`

生产授权：`none`

## 1. 本节点回答的问题

本节点只回答：在不读取真实目标、价格或收益的前提下，冻结的 Head30 目标能否被一套确定、可复算、
失败关闭的 50 万元账户执行语义承接。它不回答 50 万元真仓是否可行，也不改变已经完成独立审计的
`VALIDATED_RESEARCH_SCALE` 历史结论。

协议提交 `5c7c58c` 先于工程实现提交 `53a198e`，两者均已推送至 `origin/main`。

## 2. 已冻结口径

- 六窗口分别以 500,000 RMB 重置现金，目标仍是生产 Head30、等权、10 个交易日调仓、次日开盘执行。
- 费用与整手规则继承 `paper-v1`：佣金万三且最低 5 元、卖出印花税万五、过户费十万分之一；
  主板/创业板买入 100 股整数手，科创板首次买入至少 200 股、之后以 1 股递增。
- 容量只使用信号日前 20 个有效成交金额的中位数，至少 15 个观察；单笔上限 5%，禁止读取执行日成交额。
- 资金可执行性硬门同时约束持仓数、现金比例、目标权重 L1 偏差、最低手数拒绝、容量、负现金、
  会计恒等和非法成交。
- 历史效果保持门固定为：至少 4/6 窗口净超额为正、合并 1.5 倍成本净超额大于 0、
  50 万可执行组合与理想组合 pooled NAV 比不低于 0.95。
- 所有结果都不授权生产；自然 FORWARD 只作独立描述性证据，不可反向调门槛。

## 3. 工程真身

- `src/shaiwei/research/capital_feasibility/contract.py`：冻结协议与权限机械校验。
- `execution.py`：确定性卖后买、费用、整手、现金和容量纯函数。
- `verdict.py`：`BLOCKED / CAPITAL_FEASIBLE_RESEARCH_ONLY / CAPITAL_INFEASIBLE` 裁决。
- `fixture.py`：完全合成的可行路径、高价最低手数失败路径和双跑确定性。
- `compose.m6-head30-500k-feasibility.yaml`：断网、只读根、非特权、无真实数据挂载的 fixture。

新增生产模块最大 153 行，低于 400 行软上限；执行、合同、裁决和 fixture 分层，没有把逻辑继续堆入
既有 M6 大文件。

## 4. 验证证据

- 专项测试：7 PASS。
- 架构宪法：13 PASS。
- 全仓回归：1,610 PASS；17 条均为既有第三方弃用或 pandas FutureWarning。
- Ruff、compileall、pip check、Compose config、`git diff --check`：PASS。
- 最终镜像：`sha256:9b116f46b9ee535d46188a08491462b8023b581cacc93e3256ad063380f427b5`。
- 镜像 Git 身份：`53a198e3a739df80ec7d982b6ad0405a6050a7a2`。
- fixture 证据 SHA-256：`20eb5b2827e654dd6031d7fe6080685433216a28c82f49b65237bb619d7799a9`。
- daemon 断网双跑内容一致；第二遍 `reused=true`。
- fixture 明示：真实行情读取 0、真实效果读取 0、Qlib 读取 0、模型拟合 0、预测生成 0。
- scheduler 保持原容器 `shaiwei_init-scheduler-1`，连续运行且 `healthy`，未重启。

## 5. 裁决边界与下一节点

`GO_ENGINEERING_ONLY` 仅说明 50 万元机械口径已被可测试代码承接。真实六窗口仍未加载，因而当前不能
声称 50 万元可行或不可行，也没有消费本家族的新尝试。

下一合法节点是 M6-5B 结果盲 release 工程：绑定 R2 五件封存效果、目标/日期/价格/容量输入身份，补齐
真实 runner、内部 replay、无 Qlib 的独立 auditor、不可变输出根和精确 scope。工程完成后必须再次停止，
由用户绑定 scope SHA 与冻结动作明确授权；授权前不得读取真实目标、价格、收益或运行 50 万元回放。
