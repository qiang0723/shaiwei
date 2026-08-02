# M3-2 三自建池真实价量因子发现批终版验收

日期：2026-08-02（UTC+8）

裁决：`GO_M3_2_DISCOVERY_TOP2_LOCKED`

策略有效性：`NOT_EVALUATED`

生产授权：`none`

## 结论

本批按结果前冻结 release 完成恰好 24 个 `deepseek-v4-pro` 响应，并只在 2021-01-04 至
2022-12-15 的发现期，使用同一个规范 AST 对科创板全市场、中盘和小盘三个规则型 PIT 池评价。
15 条候选完成发现评价，3 条重复 AST、1 条受限沙箱拒绝、5 条自由文本语义合同拒绝；9 条失败全部
计入尝试且没有补位、重发、调门槛或人工挑选。

共有 8 条候选满足三池覆盖/有效日和“三池定向 RankIC 均为正”的发现期资格。因子方向只由全市场
发现期锚定，子池没有单独翻向；24 次全部完成后才按预注册顺序机械锁定 Top2：

1. `f6fd83e97bad3114`，全局序号 3，`trend_momentum`；
2. `ca552f379c62504d`，全局序号 4，`trend_momentum`。

Git 中的机器摘要只保存 attempt、序号、主题、公式身份哈希和发现证据哈希；追加式研究审计 ledger
仍按已冻结公共 schema 保留规范表达式与发现期摘要，便于重放和重复门核验。原始响应、逐证券数据、
证券清单和发现产物不提交 Git。Top2 只是下一阶段的固定审查对象，不表示因子有效、模型有效或获得
生产授权。

## 响应、费用与多重检验

- 四个冻结主题各 6 次，共 24/24 个连续完成响应；传输事件严格为 24 个 `STARTED` 和 24 个
  `COMPLETED`，没有计费不确定性。
- 实际估算费用为 `0.053605862 USD`，通过 `0.50 USD` 单批硬熔断；未用余额不授权新响应或新批次。
- 旧 GP 166、D1 40、M1 40 与本批 24 次共同构成相关价量研究域 `N=270`。三个池产生 72 个评价
  单元，但仍只增加 24 次研究尝试，不能机械记为 72 次独立试验。

## 数据与评价合同

- 断网预检重新绑定六类源批次、复权链和 PIT 行业/市值：321 个历史证券、474 个发现交易日、
  73,839 条 PIT 暴露，输入快照为 `90a8d377…f1193`，`.BJ=0`。
- 价格、成交量、VWAP 与 T+11 开盘标签复用同一冻结复权链；行业和同日市值只用于中性化，不进入
  候选 DSL。
- 同一规范 AST 在三池保持完全相同定义；全市场只负责方向锚定，不允许以子池结果翻向。
- `sealed_validation_read=false`、`stress_periods_read=false`、`g1_run=false`、
  `model_or_portfolio_run=false`；没有训练、回测、组合、信号或前瞻运行。

## 静态证据与幂等

- attempt 24 行与共享 experiments 中本 release 的 24 行严格一一对应；transport 48 行，完成事件
  24/24；静态证据含 24 份原始响应、24 份 provider 响应、24 份 manifest、15 份发现产物及终态
  report/context。
- 项目忽略区证据树共 89 个文件、527,791 bytes，规范树哈希为
  `d9b843261d01af635f3546b15dc8400cb1e2f5c765ff99cb83af63fa7624dfbc`；终态报告哈希为
  `428772649728a1ff6db7d537cb1a531e3a133f5f0d1c8c30e17c1e1fac9ca7ce`。
- 完成后在 `network_mode:none`、无密钥且 `data/ledger` 只读的同一镜像复跑，返回
  `idempotent_reuse=true / external_api_calls_this_run=0`；attempt、transport、experiments、报告和
  live context 五项哈希前后完全相同。

机器可读摘要为 `config/m3_multi_pool_factor_discovery_manifest_v1.json`。完整响应和发现期证据只留在
项目 `data/` 的 Git 忽略区。

## 秘密、外发与生产隔离

- DeepSeek 密钥只从项目内权限 `0600`、被 Git 忽略的 `.env` 注入首次临时容器；镜像内无 `.env`，
  密钥没有写入账本、报告、产物、源代码、文档或 Git。
- 对外仅发送冻结的受限研究提示、固定知识摘要和同批允许的脱敏反馈字段；没有发送行情原始数据、
  证券清单、其他凭据或项目外内容。
- live 容器非 root、只读根、无端口和 Docker socket；只开放 M3 专属结果及三份追加账本写入。
- 生产 scheduler 前后均为容器 `fd8e96152b53`、镜像 `sha256:de87ec74…0261`、创建时间
  2026-07-24 20:25:27 +0800，最终仍为 `running/healthy`，没有重启或重建。

## 最终验证

- 宿主全仓 `472 passed`；同一 M3 镜像在断网、工作树只读、真实 `.env` 被 `.env.example` 覆盖的
  环境中再次 `472 passed`，两次都只有 1 条既有 Starlette 弃用提示；其中新增 2 项专门把 M3
  attempt/transport ledger 纳入通用追加前缀棘轮。
- Docker 首轮把 `/workspace/logs` 也设为只读，影子周期 fixture 因无法创建临时锁得到
  `469 passed / 1 failed`；只把容器内日志目录改为不落盘的 tmpfs 后全绿。该失败是测试容器挂载过严，
  没有修改代码、宿主日志、生产容器或研究结果。
- Ruff、compileall、pip check、生产/研究 Compose 静态校验、JSON/报告逐字段一致性和
  `git diff --check` 均 PASS；追加账本无删除，旧 GP/D1/M1 专属账本未改。

## 下一阶段边界

本批在 Top2 锁定后停止。若继续，必须另立结果前 M3-3，只能对这两条固定候选做独立的经济解释、
数据泄漏、单位/符号与表达式稳定性审查；不通过即停止，不递补第 3 名、不改式、不追加 DeepSeek
响应。只有审查通过并再次冻结协议后，才可解封 2023—2025 验证期并运行既有 G1；当前不得接模型、
模拟仓、Web 结果页、前瞻或生产。
