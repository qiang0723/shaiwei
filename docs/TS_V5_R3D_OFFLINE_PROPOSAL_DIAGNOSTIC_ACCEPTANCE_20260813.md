# TS-v5-R3D 六响应离线 proposal 失败诊断验收

日期：2026-08-13（UTC+8）

权威裁决：`STOP_LOCAL_IMPLEMENTATION_DEFECT`

## 结论先行

R3C六份响应的首要问题不是“DeepSeek不会输出JSON”，而是本地授权合同没有把用户批准的六个
`INDEPENDENT`席位绑定进每份请求：模型看到的lineage Schema同时允许`INDEPENDENT`和
`ADVERSARIAL_REVISION`，请求中没有`assigned_attempt_mode`；六份回答最终都选择了
`ADVERSARIAL_REVISION`，但runner又把六行证据统一硬编码为`INDEPENDENT`。

这形成了可复算的本地授权绑定缺陷：请求允许模型改变尝试类型，证据账本却不反映已验证的响应类型。
按结果前判据，必须先停止并修复本地合同，不能用更多DeepSeek调用绕过。R3C原
`STOP_NO_VALID_CANDIDATES`保持不变，六份响应不修补、不录取；策略效果仍`NOT_EVALUATED`。

## 六份匿名诊断

- 六份都存在至少一项可见合同违反；六份都存在“批准独立席位，但响应为反方改版”的授权绑定缺口。
- `SEARCH_PRODUCT_LIMIT`：5/6。五份把参数搜索点数相乘后超过冻结上限196。
- `TEXT_SAFETY`：2/6。两份自由文本触发已发送的禁止文本规则；报告不保存原词句。
- `LINEAGE_PARENT_HASH`：2/6。两份父指纹不满足可见SHA-256格式。
- `REQUIRED_FIELD_MISSING`：1/6。一份缺少必填`schema_version`。
- 所有原始content仍只存在Git忽略的R3C不可变产物中；诊断报告只保存匿名序号、机制、字段路径、
  错误类型、规则ID和计数，不保存原文、提交值或reasoning。

字段错误说明当前proposal接口仍需要收敛，但按冻结的首要规则优先级，本轮不得在授权绑定缺陷未修前
继续计算“是否值得新live批”的次级门。

## 建议恢复

下一合法目标是`R3E`零API合同恢复工程，不是新的DeepSeek批次：

1. 从批准scope/AttemptPlan确定性注入`assigned_attempt_mode=INDEPENDENT`。
2. 机制专属proposal Schema只允许该席位对应的lineage模式；独立席位父指纹恒为空，不让LLM自由选择。
3. compiler显式核对响应lineage与批准席位，runner账本的`mode`只来自已验证合同，禁止硬编码掩盖差异。
4. 将搜索积预算改为确定性分配，或在请求中提供不超过196的合法点数组合；不提高196、不放宽参数域。
5. 用合成对抗样例和六份封存document做只读回放，证明授权模式错配、搜索积、文本安全、父哈希和缺字段
   都能逐项失败关闭；旧响应仍不得转为候选。

R3E完成后也只能重新判断新小批是否值得，不能自动调用。任何未来调用仍须新scope、release和用户
明确批准。

## 证据、幂等与隔离

- 结果前scope提交`d40603e`先行推送；scope SHA-256：
  `cbfba18e67ea50469548d46f0d43ccd25d7ba11f3980063022fd809665fb6090`。
- 实现提交`555ccdf`先行推送；专用镜像
  `sha256:d143fa2d232b1b43f39335707f27f10e282c9b26f51a3a3ca08a84e69add109b`，镜像内Git
  HEAD为`555ccdfc4e8df516231c72efb455b636bdbb45e4`，代码快照
  `3440c50b6983a8a3c484dd91662eba6cadb30e9b269085f105dd5c7f70392cb2`。
- 诊断报告SHA-256：`4ba99d3b119ec08a095abf9b29b0593cfcd44b47c78544070a49046cd137717c`；
  独立audit SHA-256：`5007b045364256060a88a27fd7d4bcb7eb08390198b41e639373075ee1645ddc`。
- 独立audit完整重算相等，12项检查全部PASS。断网二次运行报告/audit及R3C两账本四项哈希前后不变。
- R3D全程`network=none`、无secret、只读R3C产物和账本；外部调用、费用、行情/收益读取、候选修补、
  参数搜索、回测、模拟仓、Web和生产均为0。
- 诊断/输入核验/audit模块分别334/83/88行；专项39项和架构13项PASS。scheduler保持原容器
  `183b8c6c5edd`健康运行，未修改或重启。
