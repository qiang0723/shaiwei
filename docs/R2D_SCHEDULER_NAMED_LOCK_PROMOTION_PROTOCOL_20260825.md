# R2D Scheduler named-lock 结果盲生产提升协议

## 1. 目的与裁决边界

R2C-R1 已证明候选镜像在真实 Docker named volume 上通过 10/10 锁 fixture。本节点只把“fixture
可用”转换成一条可安全发布、可恢复、可在首个自然交易日验收的生产路径，不读取或改善策略结果。

本协议冻结为 `FROZEN_ENGINEERING_NOT_EXECUTION_APPROVAL`。当前只授权源码、测试、配置和文档工程；
不授权 build、fixture 重跑、tag、promote、restart、真实业务、手工跑批或生产账本写入。工程完成后
必须另生成绑定交易日和证据哈希的唯一 release scope，再由用户精确批准。

## 2. 不可变身份

- 候选：`shaiwei:scheduler-88e3f471565ba461`，image ID
  `sha256:b7565001835936e1235d24de3c567f0d13869d48f30596ac7172df7b849baa72`，HEAD
  `55f98e7085bf7f1a573c9105606c842a9655b63c`，snapshot
  `88e3f471565ba461fb660f41a97a2dd4ac633585c4f74efadd9a3b264e2abec0`，lock authority
  `docker-named-volume-v1`。
- 当前生产：`shaiwei:scheduler-4e5244b6b02739dd`，image ID
  `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`，snapshot
  `4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708`。
- 上述候选之后只有 STATE、ROADMAP、验收和观察提案发生变化；当前受控代码快照仍与候选完全一致。
- R2C-R1 report、evidence tree、receipt 和 release scope 四个哈希逐项写入机器合同；任何漂移都失败关闭。

## 3. 为什么采用两阶段切换

当前生产镜像仍使用旧 bind-lock 语义，而候选使用 named-volume 锁。把“改 current 指针”和“启动新
容器”拆开可以同时满足两个边界：

1. **Phase A**：在 16:00—19:30 数据保护窗之外执行一次 `promote --no-start`。只改变发布指针，旧
   容器继续以原身份运行且必须保持 healthy；新状态精确为 current=候选、previous=旧生产。
2. **Phase B**：下一官方交易日 16:00 旧容器只读探测已经以 `WAITING_SOURCE` 闭合、且唯一新交易日
   数据具备资格后，在 16:05—19:00 只执行一次 `start_current`。不手工调用 daily，不与旧业务周期
   并发。

若 16:00 旧容器已经进入正式跑批、timeline 未闭合、出现多个可用交易日或任一身份漂移，Phase B
直接阻断并延期，不抢跑、不补跑。

## 4. 回滚口径

旧 production 只能作为 `LEGACY_EMERGENCY_SEQUENTIAL_ONLY`：候选容器必须完全停止后，才能按原
release state 恢复旧镜像并重新验健康；新旧 writer 绝不允许并行。候选启动失败时自动恢复旧
current，且必须把启动失败和恢复失败分别上报。

一旦候选完成第一笔真实业务写入，自动 legacy rollback 权限关闭。此后若出现业务级问题，先安全
停止和保全证据，再另立恢复协议；不能让旧锁实现静默接管已经迁移的运行期。

## 5. 需要补齐的机器门

复用现有 `daily_early_release_guard`，不再复制一套发布 runner。工程必须补齐：

- 候选 label/runtime/state 中的 lock authority 三方一致；
- 新容器只允许 data/ledger/logs 三个 bind 加 `shaiwei_runtime_locks_v1` 一个可写 volume，根只读、
  无 Docker socket、无开发树；
- 发布 Git 门只要求受控发布输入与已推送 HEAD 一致，允许 scheduler 自然追加的 ledger 和用户未纳入
  发布域的草稿共存；
- Phase A 幂等、半切换恢复、Phase B `WAITING_SOURCE` 闭合、候选/旧生产绝不并行；
- fixture receipt 与 report/tree/scope 哈希强绑定；
- 所有失败发生在 mutation 之前，或进入显式且可复核的顺序恢复路径。

## 6. 首个自然交易日验收

新候选第一次自然运行后，同时检查 scheduler 整周期、timeline 哈希链、daily、真实 raw batch 无
`.BJ`、shadow S1—S9、冻结口径下的 S10、Top30/Top20 两账户 paper、飞书开始/完成、重复运行幂等、
零人工修数和候选代码快照。全部通过后才允许启动 R2-1R1 连续计数。

该 PASS 只说明发布与工程闭环稳定，不说明 50 万元 Head30 可行、Top20 优于 Top30或策略有效；这些
研究裁决保持原样。

## 7. 下一停止点

工程完成、测试和脱敏通过并推送后，等待当日自然跑批闭合，再生成唯一执行 scope。该 scope 必须
绑定最终工程 HEAD、候选/旧生产身份、Phase A/Phase B 日期窗口、两个账户最新 FORWARD 日期与产物
哈希、timeline 身份和动作名。用户未精确批准前，promote/restart 均为 0。

