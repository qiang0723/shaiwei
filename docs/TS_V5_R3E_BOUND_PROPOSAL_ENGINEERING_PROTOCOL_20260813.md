# TS-v5-R3E 本地绑定 proposal 合同恢复协议

日期：2026-08-13（UTC+8）

状态：`RESULT_BLIND_ENGINEERING_FROZEN`

唯一 scope SHA-256：
`30185aa4f34d2d186472594af43b0faadabce1215190cdd047031278087ec691`

## 目标与边界

R3D已确认R3C的首要失败不是模型能力，而是本地授权没有贯穿请求、Schema、编译器和账本：批准的六个
席位是`INDEPENDENT`，响应却可自行选择`ADVERSARIAL_REVISION`，runner仍把它们登记成独立尝试。
同时，模型还被要求自行填写搜索点数，导致5/6响应的参数搜索积超过196。

R3E只修复这两个本地合同职责：尝试模式及父候选由结果前批准的本地`AttemptPlan`唯一提供；每个参数
的搜索点数由本地编译器按槽位数量机械分配。LLM响应只提供研究语义和参数上下界，不再拥有lineage或
搜索预算的决定权。R3E不调用DeepSeek、不读取行情、证券、收益或secret，不运行参数搜索、回测、
模拟仓、Web或生产。

## 版本化兼容与不可变边界

- R3B/R3C使用的proposal v2合同与编译器保持字节不变；最终`MechanismCandidate` validator也保持字节
  不变。新能力单独版本化为proposal v3，不静默改变旧请求的复算口径。
- R3C六份原始响应、请求、manifest、两个账本和R3D诊断/audit只读重放，不修补、不规范化、不生成
  候选，也不改变旧`STOP_NO_VALID_CANDIDATES`与`STOP_LOCAL_IMPLEMENTATION_DEFECT`。
- v3编译产物仍必须通过原冻结`MechanismCandidate`，因此这是输入职责收窄，不是放宽候选门槛。

## 本地权威绑定

本scope固定未来独立金丝雀的权威为：

```text
mode = INDEPENDENT
parent_candidate_fingerprints = []
```

请求必须显式包含`assigned_attempt_authority`，但proposal response Schema不得出现`lineage`。编译器只从
经过验证的本地权威生成候选lineage；证据层的attempt mode只准从已编译候选lineage派生。任何调用方
另传冲突模式、父候选或证据模式必须失败关闭。

未来若要研究`ADVERSARIAL_REVISION`，必须另立带唯一父候选哈希的结果前scope和对应版本，不能复用
本独立席位合同。

## 机械搜索预算

proposal response只允许每个参数槽提供`parameter_id/value_type/minimum/maximum`。本地按最终槽位数给
每槽分配同一点数：1槽7点、2槽7点、3槽5点、4槽3点、5槽2点，对应最大搜索积分别为7、49、125、
81和32，全部不超过冻结上限196。模型不得填写或覆盖`search_points_maximum`；编译器仍须在生成最终
候选前重新计算并证明乘积不超过196。

这只确定未来允许的搜索预算，不运行任何参数搜索，也不增加研究尝试。

## 验收方法

1. 六种机制各构造一份最小proposal v3，验证request/Schema/编译器/原候选validator贯通。
2. 对1—5个参数槽逐项验证机械点数与搜索积；对模式覆盖、lineage注入、搜索点注入、额外字段、跨机制
   参数、缺必需参数、文本安全、范围和证伪条件构造对抗fixture并失败关闭。
3. 只读重放R3C六份封存content。旧回答因为包含已移出响应职责的lineage/搜索点数或仍有文本/缺字段
   问题，必须全部保持未录取；报告只保存错误类别和计数，不复制回答正文。
4. 独立audit从scope、合同、请求、合成fixture与旧只读证据重新计算全部关键门；write-once二次运行
   哈希必须一致。
5. 验证R3C/R3D账本、报告、audit以及v2合同/编译器/validator哈希未改变，生产scheduler身份和健康
   状态未改变。

## 结果前裁决

只有全部门同时通过，才裁`GO_R3F_LIVE_CANARY_SCOPE_PROPOSAL_ONLY`：六机制合成编译通过、原validator
通过、模式绑定不可绕过、搜索积机械合法、对抗fixture全部失败关闭、六份旧回答0录取、旧证据字节
不变、独立audit与幂等通过。

任何一项失败裁`STOP_R3E_ENGINEERING_GAP`。即使R3E GO，也只表示可以另提R3F小批金丝雀scope；不
授权外部调用、费用、secret读取、参数搜索、效果读取、回测、模拟仓、Web或生产。R3F仍须冻结确切
次数、费用、发送内容、release并获得用户明确批准。
