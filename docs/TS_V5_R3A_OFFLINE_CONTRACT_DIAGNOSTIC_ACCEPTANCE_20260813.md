# TS-v5-R3A 四响应失败的离线合同诊断验收

日期：2026-08-13（UTC+8）

权威裁决：`GO_R3B_CONTRACT_PROJECTION_RECOVERY_ONLY`

## 结论先行

R2四份JSON全部失败的共同主因是`INCOMPLETE_LLM_FACING_CONTRACT_PROJECTION`，不是本地validator错误，
也不能简单归为模型整体不服从。四份都违反了至少一条仅存在于本地Pydantic自定义validator、没有完整
投影到模型所见JSON Schema和candidate limits的语义规则；其中仅第2份还违反了已明确可见的800字符
上限和Feature枚举。

因此R2的`STOP_NO_VALID_CANDIDATES`保持不变，四份响应仍不得修补、录取或进入效果评价；但后续恢复
应先修合同投影，而不是增加响应数、放宽validator或把相同请求再次交给模型。

## 逐席位诊断

- 波动自适应回调：缺强制市场/板块取消规则；ATR范围越界；混入其他机制参数；搜索笛卡尔积960大于
  196；缺产品级必需特征。
- 周结构分位：经济解释807字符，超过模型可见的800上限；两个Feature值不在可见枚举；分位参数下界
  低于本地安全范围；缺产品级和机制级必需特征。
- 突破回踩：缺强制市场/板块取消规则；三个参数安全范围越界；缺产品级必需特征。
- 均线恢复：混入ATR lookback这个跨机制参数；搜索笛卡尔积240大于196；缺产品级必需特征。

根因按响应计数：JSON Schema表达缺口4/4、提示/candidate limits缺口4/4、已可见规则的模型不服从1/4、
本地validator缺陷0/4。部分后层错误在原Pydantic首轮因前层失败没有显露，诊断器只做确定性结构检查，
没有修改或保存修补后的候选。

## 建议的R3B恢复设计

1. 保持冻结validator和全部安全边界不变。
2. 按primary mechanism生成专属合同投影，明确该机制必需/可选parameter id及每个精确范围。
3. 明确最大搜索笛卡尔积196，并在请求构建时先验证投影与validator同源。
4. 强制取消规则、产品级与机制级required features不再交给LLM自由填写，由确定性编译器从冻结机制
   合同补齐；LLM只负责假设、经济解释、确认方式和边界内参数选择。
5. 新请求前必须先通过合成与对抗fixture，证明投影能表达全部本地规则且不会静默改旧候选合同。

该建议是恢复工程方向，不是新调用authority。R3B若完成也只能到工程GO；真实DeepSeek调用仍须新scope、
新release和用户明确批准。

## 证据与隔离

- scope SHA-256：`9f82d89ff21c3415182a7fa910dbd972b95e8f4b01a30c52be318b46ea48e4d1`，
  在详细展开四份content前提交并推送。
- 脱敏diagnostic SHA-256：
  `251dd338d57315e5abb2e0ec0431ca6879f401cd9478c7e3f62b6220a5093c29`；独立audit SHA-256：
  `04826005037c325d5275af3fe2ea2f97e385df1f7a224dbac2dcd2c4dfea8924`。
- 独立audit完整重算一致，9项检查全部PASS；报告未保存原响应正文或reasoning。
- 外部调用0、secret读取0、行情/收益读取0、候选修补/录取0、参数搜索/回测0、模拟仓/Web/生产0。
