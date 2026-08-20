# M6-4B-R2 生产 Head30 空成交价恢复工程验收

## 结论

`GO_PRICE_RECOVERY_RELEASE_READY_NOT_EXECUTION_APPROVAL`。空成交价恢复语义已在实现前独立冻结，最小
修复、对抗测试、隔离 Docker、不可变镜像、daemon 级纯合成 fixture 和精确 release scope 均已完成。
真实 Qlib、封存预测、控制报告内容和策略效果未读取，R2 新尝试消费 0，生产授权为 `none`。

## 单一恢复变量

- 成交价有限且为正时保持原行为。
- 成交价为 `None`、非数值、非有限或非正数时返回“缺失”，使已有持仓进入原先已经存在但此前
  无法到达的 `current.get_stock_price` 回退。
- 持仓回退价仍无效时，以包含证券代码的 `FullTargetStrategyError` 失败关闭。
- 没有新增前收盘、未来收盘、复权收盘或人工价格，没有剔除证券/交易日，没有改变排名、Head30、
  等权、10日调仓、成本、六窗口、模型、预测或 G0。

## 结果与尝试隔离

- R1 scope `ea648bda...83d2c`和三份失败产物永久保留，哈希复核不变；R1 已消费 1 次尝试且不得重跑。
- R2 使用新目录 `effect-r2` / `effect-r2-audit`，终版均为空；`approval-r2.json`不存在。
- 新 scope 的 authority 仍为 `execution_authorized=false`；只有用户精确批准后，首次真实读取才消费
  第 2 次家族组合转换尝试。同一 R2 scope 失败也不得重跑。

## 架构与实现

- `full_target.py` 为 239 行，只增加窄价格规范化和估值回退，未引入数据或 I/O 职责。
- 版本化 runner/auditor 命令从 `real_contract.py` 抽到 74 行 `runtime_profiles.py`；主合同为 368 行，
  低于 400 行软上限。
- R2 协议验证独立在 190 行 `price_recovery_validation.py`，绑定 R1 尝试、三份产物哈希、行为白名单、
  新输出根、批准动作和停止条件；R1 validator 未改写。
- 新 Compose 断网、只读根、非 root、cap-drop、no-new-privileges；无 `.env`、Docker socket、生产
  账本或整仓挂载。

## 不可变身份

- 结果隔离协议冻结提交：`eb1d7c312c02cbeb358db6f61b94e261557465d3`。
- 实现提交：`30c758c0560670b1890866b076ee4cffea8311d2`，构建前与 `origin/main` 一致。
- 镜像：`shaiwei:m6-production-head30-price-recovery-v1`，ID
  `sha256:a6544affee82f4d081442472e2211b78a08646a7fc0517f3aee75d835fe64b29`，平台
  `linux/arm64`，镜像内 Git `30c758c...11d2`，代码快照
  `84e45501e4bdde458949806d1be69fc56452479b9de911f2b5cc866fc9cdb76e`。
- 镜像 manifest SHA-256：`3656a3caf5a4fa2e285eecc870a58b10ab7dbdb03d06ffdfbf2e3feca792e8f4`。
- R2 协议 SHA-256：`6e4fc89c5c02db862681866e96d1e8063e6b6bc2a6bb58c3cfc08819ba327a6e`。
- 精确 scope SHA-256：`9b78ef69ec11c180bbc1adc46b95c3f8023bf729480d4fd647e2eab1085f9b4a`；
  scope 文档 SHA-256：`166bd54bfc768929905795a86429ad4233c4bf96c7ceef0dcc232e542d08a663`。
- daemon fixture：first/replay 均为 `269ce579...ca301`，独立重建 PASS，report
  `e6b097ff...121af`，真实效果读取 0、尝试 0。

## 验证

- M6 Head30 原协议、R1 与 R2 专项：39 PASS。
- 架构宪法：13 PASS。
- 全仓：1537 PASS，17 条既有第三方/兼容性 warning。
- Ruff、compileall、pip check、Compose 展开、`git diff --check`：PASS。
- scheduler 容器 `183b8c6c...dd3b`、镜像 `722f63de...3b76`、创建时间
  `2026-08-03T09:39:34Z`，施工后仍 healthy，未重启或替换。

## 下一合法节点

当前必须停止。若用户继续，唯一授权句为：

> 批准 M6-4B-R2 release scope
> `9b78ef69ec11c180bbc1adc46b95c3f8023bf729480d4fd647e2eab1085f9b4a` 按动作
> `M6_PRODUCTION_HEAD30_G0_EFFECT_PRICE_RECOVERY_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT`
> 运行一次断网真实生产 Head30 空成交价恢复效果；首次处理效果读取消耗恰好 1 个新组合转换尝试，
> 家族累计 2 次；不授权模型拟合、新预测、外网、同 scope 重跑、前瞻、模拟仓、Web 或生产。
