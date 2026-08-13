# TS-v5-R3B 机制专属合同投影与确定性编译器工程验收

日期：2026-08-13（UTC+8）

权威裁决：`GO_NEW_LIVE_CANARY_SCOPE_PROPOSAL_ONLY`

## 结论先行

R3A识别的合同投影缺口已在不放宽冻结候选validator的前提下闭合。未来LLM不再自由填写机制身份、
参考框架、回调量纲、两个强制取消规则或必需features；它只填写研究假设、经济解释、恢复确认方式、
机制允许范围内的参数槽、可选取消规则、证伪条件和lineage。确定性编译器从冻结`v5_models`常量补齐
其余字段，并强制让终产物再次通过原`MechanismCandidate`。

这次只完成工程资格门：可以另行提出一个新的小批真实合同金丝雀scope。没有调用DeepSeek，没有读取
secret、行情、证券、收益或R2正文，没有修补R2旧候选，没有参数搜索、回测、模拟仓、Web或生产；
策略效果仍为`NOT_EVALUATED`，生产授权仍为`none`。

## R3A问题如何闭合

- 六种机制各有独立proposal Schema和`mechanism_projection`，不再向模型暴露一个带隐含条件分支的
  宽合同。
- 必需/可选parameter id、类型、精确闭区间、整数约束、数值格式、唯一性、每槽搜索点和最大笛卡尔积
  196均显式投影；编译器按同源`PARAMETER_BOUNDS`再次fail closed。
- reference frame、pullback measure、强制取消规则和产品/机制features从`ARCHETYPE_CONTRACT`、
  `COMMON_FEATURES`与`MECHANISM_FEATURES`确定性生成，不再要求LLM复述本地隐式规则。
- 文本长度、安全字符、禁止类别、falsification唯一性、lineage父候选数量/指纹和optional cancellation
  枚举均进入模型可见合同并在本地复核。
- 原`v5_models.py`与`v5_prompt.py`字节哈希保持不变；旧R2四响应继续无效，不回溯修复或录取。

## 机器证据

- scope SHA-256：`9e7c317f798f313db098e3cb195fc7341c89c99b817641573c58c3330a9ab26b`。
- proposal合同 SHA-256：`538326777bdeb3c0793e729b1c4dc086b804e07743aca8adba7e9f251e9b09a0`。
- proposal投影/编译器 SHA-256：`7a6c8f728c756084df5bc5c68e18332f62fc1666813943df5e331c749c71bd31`。
- 六机制projection bundle：`e0d06b1cefeb198d16566506abcd48deabe45d91785516cb2b061060df679129`；
  Schema bundle：`dc294672b7c1554a79cc2a3486d993dadbeca2da1a9944f6b0327eb21d4399e1`；
  六请求bundle：`8183eb24156a5285835ace5244028d8d70345102d5779bc15bbe8d54c408b415`。
- 六个最小proposal全部编译并通过冻结validator；每个机制21条规则均被标注为“显式投影”或“确定性
  补齐”。
- 42/42个对抗样例fail closed，覆盖跨机制参数、缺必需参数、重复、越界、LLM注入确定性字段、把强制
  取消规则冒充可选规则和搜索空间爆炸。
- 工程payload SHA-256：`ed48c171609245c1203b712ad5c98db8d7cc3ae89655a5ba917047bab600d9e7`；
  工程报告文件 SHA-256：`0c45e34123f8240023fd608ba36a0d6a7552f33375ca7188d2c30aaca365f034`。
- 独立audit完整重算一致，10项检查全部PASS；文件 SHA-256：
  `8b85bc88e18e57f6a2227d9a9b875eb2c32dc8183cb3a72f6463e6105189900f`。
- 相同入口二次运行只复用相同write-once内容，两份文件哈希均不变。

## 不可变证据补遗

首轮工程报告写入后，终验前逐规则检查补上了proposal文本对冻结`SAFE_TEXT`控制字符规则的显式复用。
旧报告已采用write-once，故不覆盖、不删除，永久保留在原忽略目录作为provisional；终版改用独立
`ts-v5-r3b-contract-projection-final`输出根。该操作不改变scope、机制、候选、研究结果或权限边界，
详见`docs/TS_V5_R3B_CONTRACT_PROJECTION_ENGINEERING_ADDENDUM_20260813.md`。

## 架构与下一步边界

实现分为proposal合同/确定性编译、工程验收和独立audit三个职责模块；主模块350行，低于400行架构
上限，没有复制provider、live runner或回测逻辑。定向合同测试31项、TS-v5兼容链57项、架构宪法
13项、全仓1214项全部PASS；Ruff、compileall、pip check和diff check均PASS。生产scheduler保持原
`shaiwei:scheduler-current`且healthy，未重启。

下一步如继续，只能先冻结新的小批真实金丝雀scope、响应数、费用上限、唯一release和发送内容，再由
用户明确批准。该工程GO不得表述为候选有效、TS策略有效、可进入参数搜索或可接入模拟仓/生产。
