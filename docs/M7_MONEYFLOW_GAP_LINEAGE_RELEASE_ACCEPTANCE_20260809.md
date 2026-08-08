# M7-0R2 资金流缺口谱系 release 验收（2026-08-09）

## 1. 裁决

`GO_LINEAGE_RELEASE_READY_ONLY`。

本裁决只说明全域缺口谱系的结果无关协议、元数据清单、Pandas 主算、DuckDB 独立审计、一次性读取门和
隔离 Docker release 已完成。它不改变 M7-0 权威 `NO_GO_M7_0_DATA_COMPATIBILITY`，不表示缺口已被
解释或资金流数据已恢复为 GO，也不授权候选、效果或生产。

截至本验收，真实证券键、真实缺失行类别和资金流数值读取仍为 0；`strategy_effective=NOT_EVALUATED`、
研究尝试增量 0、生产授权 `none`。

## 2. 结果前冻结与上游身份

- 协议：`m7-moneyflow-gap-lineage-v1`；机器 SHA-256
  `bf5ebac79cb1b81699e5a8f4d1fae13b78dedb35e7ed19672e0c69ea8254ad9e`；
- 协议冻结提交：`5d83f3e`，先于任何谱系语义读取推送；
- 实现提交：`6178ba4cc8e528c1e61f7fabb843e145831282fa`，先于 release scope 推送；
- 原 M7 run `54529f2c...032d`、scope `f4710068...b24e1` 和四个失败半年单元永久保留且未重跑；
- R1 全 A 源域和 pre-read consumption 原语身份保持不变。

诊断域没有按已知四个失败单元裁剪，而是固定原 M7 的三个池、2021-01-04—2026-06-30 全 feature
域和 11 个完整半年。旧 99.5%/99%/95% 门槛、PIT 时钟、分母和隔离语义均未修改；本节点禁止输出
“剔除停牌后覆盖率”等反事实口径。

## 3. 元数据清单

完整明细清单位于 Git 忽略的 `data/control/m7-lineage/input-manifest-v1.json`，只记录内容身份，不含
证券代码：

- canonical SHA-256：`5f3e28088038e423d2f21a1c8b712457b620045749c9052c730cdc777871f9a7`；
- physical SHA-256：`01430f44e2233439763dbefbeb90d060d87f46c9859f1cfceac6e9ab64a151a7`；
- predecessor 输入束：1,342 文件，manifest `3e49ce01...5157`；
- `tushare.daily`：8,225 批、10,563,948 行、474,522,846 bytes，只允许投影代码与日期；
- `tushare.suspend_d`：1,328 批、51,997 行、4,027,031 bytes，只允许投影代码、日期、停牌时段与类型；
- `baostock.history_k_data_plus`：16 批、3,755 行、47,139 bytes，只允许投影代码、日期和交易状态。

清单用冻结 cutoff `2026-08-08T16:07:32+00:00` 从追加式 ledger 选择每个规范请求的最新批次，逐文件
核对普通文件、非软链、footer 行数、schema 和 SHA。当前 Baostock 目录明确只是部分独立证据；协议
不会前后填充，也不会把主源停牌单独升级为独立确认。

## 4. 分类与实现

每条原 M7 未匹配成员行必须恰落入十类之一：整日隔离、daily 确认资金流缺键、独立源确认未交易、
两类 daily/独立源冲突、独立源内部状态冲突、主源整日/日内停牌冲突、主源单边未决、日内停牌不足以
解释和完全无证据未决。

只有分区完整、冲突为 0、未决为 0、全部身份/PIT/代码域门通过且 Pandas 与 DuckDB 完全一致，未来
真实运行才可裁 `GO_M7_GAP_LINEAGE_COMPLETE_ONLY`；否则裁
`NO_GO_M7_GAP_LINEAGE_INCOMPLETE`。两者都不改原 M7 NO-GO，也不自动授权数据补齐或候选生成。

新实现独立位于 `m7_moneyflow_lineage` 包，15 个模块、最大 278 行，均低于 400 行软上限；旧 M7 包
与默认入口未改。合成 fixture 同时触发十类，每类 3 行，30 条缺失行完整分区，Pandas/DuckDB 规范
SHA 完全一致；合法资金流匹配行不进入缺口类别。

runner 与 auditor 在任何 Parquet loader 前分别原子消费五字段身份；同角色第二次调用以及首次读取后
失败的重试都在 loader 前停止。runner 只复用同一内存输入做内部确定性回放，auditor 重新读取并以
独立 DuckDB 算法复算。

## 5. 验证与生产隔离

- M7-0R2 专项：14 PASS；
- 全仓：988 PASS，只有既有 `StarletteDeprecationWarning`；
- 架构宪法：13 PASS；
- Ruff、compileall、pip check、Compose、diff-check、脱敏扫描：PASS；
- 最终断网、非 root、只读根、无数据挂载 Docker fixture：PASS；fixture SHA
  `07b61e11ef026491dbe752cb300a0a17df45e07482e40d9471fddf60f6d7b2ab`；
- scheduler 保持原 `shaiwei:scheduler-current` 容器 healthy，未重启。

最终镜像：`sha256:3f827cc897ae3f13e89a85cb406d81f8a48b6a46f1daa740f823a7e04824cda6`
（linux/arm64）。runner/auditor 均断网、UID/GID 65532、只读根、drop all capabilities、禁止项目根、
`.env`、`.git` 与 Docker socket；auditor 对 runner 输出只读。

## 6. 精确 release 与停止线

- action：`M7_MONEYFLOW_GAP_LINEAGE_ONCE`；
- release scope SHA-256：`9b5e40ec772df4a179fd3b57449304f32bf45f673a0627b1b2e1787e595c0cae`；
- release 物理 SHA-256：`c03969d63f85fc381f478a3609599bce4a811eeb6c6f42d4681a09d1b9e09f71`；
- code bundle SHA-256：`fdde13e3a8f0d42528853c2354e61b5e252504dd5bea651213f154869bee1ab6`；
- 当前 `release_ready=true`，但 `release_approval_recorded=false`、`execution_authorized=false`。

下一步只能等待用户逐字绑定完整 scope 批准。建议批准句：

> 批准 M7-0R2 release scope 9b5e40ec772df4a179fd3b57449304f32bf45f673a0627b1b2e1787e595c0cae 按动作 M7_MONEYFLOW_GAP_LINEAGE_ONCE 运行一次断网真实缺口谱系；只读资金流/成员键、daily键、suspend_d停牌状态与Baostock trade_status，不授权资金流数值、调整覆盖率、候选、标签、收益、模型、回测、外网、前瞻、模拟仓或生产，同scope不得重跑。

批准后仍会先复算 live proposal 的状态、事件序号、head 和有效期，再物化内容寻址输入束。批准未到前
不创建 approval、不物化真实输入束、不启动 runner/auditor。
