# TS-v5-R3B 机制专属合同投影与确定性编译器工程协议

日期：2026-08-13（UTC+8）

状态：`ENGINEERING_ONLY_FROZEN`

## 目标与边界

把R3A发现的全部“模型看不到、本地才知道”的候选规则改造成两类：一类显式进入机制专属proposal
Schema；另一类由同源确定性编译器补齐。冻结的`MechanismCandidate`仍是唯一最终validator，不改字节、
不降门槛；旧v1/v2请求构建器保持字节不变，避免改变历史复算。

该工程只决定未来是否具备提出新小批金丝雀scope的资格，不调用DeepSeek，不读取或修补R2响应，不看
行情、收益或效果，不运行参数搜索、回测、模拟仓、Web或生产。

## 设计冻结

- 新公共合同版本为`ts-v5-mechanism-proposal-v2`，按六种机制分别生成；不做一个包含大量条件分支的
  宽Schema。
- LLM只填写研究假设、经济解释、变更摘要、恢复确认方式、投影范围内参数、证伪条件和lineage。
- 机制身份、reference frame、pullback measure、两个强制取消规则及全套产品/机制必需features由编译器
  从`v5_models`同一组常量确定性补齐。
- 可选取消规则、必需/可选parameter ID、每个参数的精确类型和安全范围、最大搜索笛卡尔积196全部在
  projection正文中显式可见；编译前再独立失败关闭。
- compiler输出必须通过原冻结`MechanismCandidate`，不得以compiler替代validator。

## 工程门

六机制最小合法proposal、全部边界、确定性/内容寻址、重复与跨机制参数、越界、非法枚举、搜索爆炸、
文本与lineage均须有合成/对抗测试。还要验证每条compiler拒绝均有对应投影规则、每条本地语义规则均
属于“已投影”或“确定性补齐”，并由独立离线audit复算。

全部通过最多裁决`GO_NEW_LIVE_CANARY_SCOPE_PROPOSAL_ONLY`。新DeepSeek调用仍须另立scope、费用/次数
边界、release及用户明确批准；R2旧响应保持无效，策略效果仍`NOT_EVALUATED`。
