# M7-0R3 真实恢复 release 前置工程合同

## 目标

把已经通过的 synthetic 领域内核扩展为可发布但尚不可执行的恢复链：精确目标投影、依赖注入的 provider
适配器、隔离追加批次、断网 evaluator、独立 auditor 和内容寻址 release 合同。当前不读取 R2 真键、
不联网、不读取凭据或真实资金流数值。

## 为什么改为四个角色

真实 provider 调用需要网络，而数据裁决和独立审计不应拥有网络。冻结角色如下：

1. `status_collector`：只消费轨 A 请求计划，联网调用 Baostock，写独立状态批次；
2. `moneyflow_collector`：只消费轨 B 双形态计划，联网调用主 Tushare `moneyflow`，写两类独立批次；
3. `evaluator`：断网读取目标计划和回收批次，内部双跑后写聚合报告；
4. `auditor`：断网、只读 evaluator 产物，以 DuckDB 独立复算后写审计报告。

collector 之间不得共享可写目录；evaluator 不写生产数据或生产 ingest ledger；auditor 对 evaluator 输出只读。
恢复数据即使 GO，也只能由后续 successor 数据门决定是否进入 M7 分母，不能在本链直接提升。

## 两级批准

生成真正的网络 release scope 前必须知道 908/541 的精确去重键与请求身份，但当前协议明确禁止读取这些
真实键。因此施工完成后分两步：

1. 用户先批准一次**离线 key-only 目标投影**：只读已封存 R2 输入，不读资金流数值、不联网，输出留在
   Git 忽略区，只提交计数和哈希；
2. 根据投影 manifest、已推送实现和不可变镜像生成精确网络 scope；用户再逐字绑定 scope 批准一次
   provider collection。

旧 M7、R2 或之前的任何批准都不能复用。

## 实现约束

- provider client 必须依赖注入，新模块禁止导入项目 `.env`/Settings 或创建 live client；
- 当前只允许 mock provider，实际调用计数必须为 0；
- 批次写入 `data/control/m7-recovery` 隔离域，Parquet 与规范 receipt JSON 都 write-once；
- 不写 `data/raw` 或生产 ingest ledger，不生成证券代码跟踪文件；
- 新模块各自单一职责、常态不超过 400 行；既有 S1、Baostock、P1、R2 和 synthetic 主审代码不改；
- 不新增常驻服务、外部依赖、账本或公共 schema，本节点无需 ADR。

## 停止点

全部工程门通过只裁 `GO_M7_RECOVERY_RELEASE_ENGINEERING_ONLY`。提交推送后停止在离线真实键投影前，
不生成真实 scope 或批准 envelope，不启动 provider、evaluator 或 auditor 的真实执行。
