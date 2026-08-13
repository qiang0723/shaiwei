# TS-v5-R3B 终版输出根补遗

日期：2026-08-13（UTC+8）

原工程报告在首轮实现完成后写入忽略区`ts-v5-r3b-contract-projection/`。随后终验前的validator逐规则
复核发现proposal文本校验只复用了禁止词规则，尚未显式复用冻结候选的控制字符`SAFE_TEXT`规则；该
缺口在无外网、无secret、无行情/效果、无候选录取时修复，并新增对抗测试。

因为旧产物采用write-once，代码身份变化后不得覆盖。旧目录永久保留为provisional；终版输出迁移至
`data/research/trend_swing/ts-v5-r3b-contract-projection-final/`。scope、六机制、validator、projection
语义、工程门和所有权限边界不变；本补遗只解决不可变证据路径，不把首轮报告冒充终版或删除失败留痕。
