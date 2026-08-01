# M1-0 多股票池因子研究底座验收

> 日期：2026-08-01（Asia/Shanghai）
>
> 协议：`m1-multi-universe-foundation-v1`
>
> 结果前协议提交：`57302597ad712ce02a70cae26f1961ab7a148ac0`
>
> 裁决：`GO_MULTI_UNIVERSE_FOUNDATION_ONLY`

## 1. 裁决边界

M1-0已建立机器可校验的多股票池身份、PIT状态、当前用途和跨池因子评价合同。该GO只允许后续按
注册状态另立数据、规则或因子协议，不表示任何新增股票池数据GO、因子有效、策略有效、前瞻授权或
生产授权。

本目标没有调用DeepSeek，没有读取或计算新因子、IC、收益、回撤、排名或信号，没有运行qlib、G1、
训练或回测，也没有写数据、账本或运行日志。

## 2. 注册终态

| 股票池 | PIT状态 | 当前最高权限 |
| --- | --- | --- |
| `csi800-pit-v1` | READY | 保持既有生产；可另立新因子协议 |
| `star50-official-pit-v2` | READY | 可另立新因子协议；旧P2基线仍REJECT |
| `star100-official-pit-v1` | BLOCKED_OFFICIAL_LINEAGE | 只可冻结数据恢复协议 |
| `star200-official-pit-v1` | DATA_GATE_REQUIRED | 只可冻结数据可行性协议 |
| `star-composite-official-v1` | DATA_GATE_REQUIRED | 只可冻结数据可行性协议 |
| `star-board-all-pit-v1` | RULES_NOT_FROZEN | 只可冻结自建规则协议 |
| `star-board-midcap-pit-v1` | RULES_NOT_FROZEN | 只可冻结自建规则协议 |
| `star-board-smallcap-pit-v1` | RULES_NOT_FROZEN | 只可冻结自建规则协议 |

注册表不含执行因子、模型、前瞻或新增生产的权限枚举。只有中证800保留
`CONTINUE_EXISTING_PRODUCTION`，只有中证800和科创50具备`FREEZE_NEW_FACTOR_PROTOCOL`。

## 3. 机器合同

新增：

- `config/m1_multi_universe_v1.yaml`：严格的8股票池冻结注册表；
- `src/shaiwei/research/universe_registry.py`：独立只读加载、Pydantic严格校验、项目内证据检查、
  稳定哈希、确定性摘要和未来评价身份校验；
- `tests/test_multi_universe_registry.py`：17个通过/失败fixture。

校验器不导入`shaiwei.config`、`.env`、HTTP客户端、Docker、Web或生产服务。生产文件323行，测试文件
223行，均低于仓库结构上限。

因子评价身份按以下有序字段完整登记：

`factor_id / factor_version / universe_id / benchmark_id / label_id / horizon_id /
neutralization_id / window_set_id / cost_policy_id / decision_rule_version`

删除、增加或重排字段均失败。因子定义身份全局稳定，但准入必须绑定股票池；同一生成响应计一次全局
尝试，多个预登记股票池产生多个评价单元，不把评价单元冒充独立生成尝试。

## 4. 失败关闭覆盖

专项fixture确认以下情况全部拒绝：

- 官方池与自建池身份混淆，自建池声明官方代码或使用“指数”标签；
- 科创100/200、科创综指或未施工自建池提前进入因子评价；
- 除中证800以外的股票池取得既有生产权限；
- 重复`universe_id`、重复官方代码、未登记股票池或修改冻结股票池集合；
- `.BJ`放行、PIT状态与权限不一致；
- 缺失/新增评价字段，重排身份字段或删除必需门；
- 证据文件缺失、路径逃逸、协议哈希不一致或未知配置字段。

## 5. 确定性纠错

首次Docker复核发现：权限字段在模型中使用`frozenset`，直接依赖运行时集合迭代顺序会使宿主与容器
对同一配置生成不同canonical SHA-256。该版本未提交、未写业务数据，也未形成任何研究结果。

终版在序列化前对集合递归规范排序，同时保留评价字段和门数组的冻结顺序。修正后宿主双跑和断网
只读Docker双跑均得到：

`acece635101ca08303d303a2229b49f2405f5919aa65745b5590aa03f7da927f`

这证明跨Python运行环境的注册身份一致，不把单进程内偶然稳定冒充确定性。

## 6. 验收结果

| 验收项 | 结果 |
| --- | --- |
| M1-0宿主专项 | 17 PASS |
| M1-0断网只读Docker专项 | 17 PASS |
| 宿主全仓 | 402 PASS / 1条既有第三方弃用warning |
| Ruff | PASS |
| compileall | PASS |
| pip check | PASS |
| 主Compose与研究Compose解析 | PASS |
| `git diff --check` | PASS |
| 账本追加与凭据专项 | PASS |

关键身份：

| 产物 | SHA-256 |
| --- | --- |
| 冻结协议 | `03b69841a7c813dec2b90dfa33ea282fb9e7a35a7ed8234181aedd11fefdbed9` |
| 注册配置 | `964631891a69b4ed2a6c697066a89300910b620d3c71acdf65803248900c4274` |
| 校验器代码 | `61b37f0ccaf64f06e022e7a29b544d02ef9037840c266d2f39ea653b08613d7d` |
| 专项测试 | `f2c9ee6c0103ccee3f94984611366e8e8ae195c03378a57f04210d38fdfc2d7b` |
| canonical注册身份 | `acece635101ca08303d303a2229b49f2405f5919aa65745b5590aa03f7da927f` |

代码在验收文档完成前的上述哈希用于绑定终版实现；文档和STATE不参与注册表canonical身份。

## 7. 生产隔离

施工后scheduler仍为：

- 容器：`fd8e96152b53f3f0d0efdcd6462c2b039aa68c7fb56461b95826709652a5adbb`；
- 镜像：`sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`；
- 创建时间：`2026-07-24T12:25:27.362813588Z`；
- 状态：`running / healthy`。

M1-0未修改或重启scheduler，未修改Compose、`settings.yaml`、中证800、科创50/100既有证据、
Top20候选或2026-08-03单次发布守护。

## 8. 下一目标

下一候选为M1-1科创50新因子研究。它必须另立结果前协议，明确新因子家族、数据与代码身份、发现期、
尝试预算、跨池计划、多重检验、语义门、成本和停止条件；不得调优旧P2基线，也不得把M1-0的底座GO
解释为DeepSeek、G1、模型、前瞻或生产授权。
