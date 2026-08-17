# TS-v5 R3G-3 独立审计序列化恢复协议（2026-08-17）

## 阻断事实

auditor 入口恢复 scope 已唯一调用。审计函数读取既有 R2 诊断及相同封存输入并完成全部独立检查，
但在写 `audit.json` 时，四项 `numpy.bool_` 检查值不能被标准 JSON 序列化，触发 `TypeError`。
audit-r3 输出根仍为空；R2 runner 与原 auditor 恢复均不得重跑。

## 唯一修复

本 scope 只把 `numpy.isclose` 返回值显式规范为 Python 原生 `bool`，不改变比较公式、容差、诊断输入、
指标或裁决。恢复继续绑定同一 R2 authorization/report/manifest 哈希，并写入独立 audit-r4 根；新增
测试强制所有 point check 为原生 `bool` 且可通过 canonical JSON 序列化。

仅允许一次 auditor 序列化恢复；不运行 runner，不增加策略效果尝试，不访问外网、留出期或2026，
不运行模型、回测、搜索、DeepSeek，不修改模拟仓、Web、scheduler或生产。同 scope 不得重跑。

机器 scope：`config/ts_v5_r3g3_discovery_diagnostic_auditor_serialization_recovery_v1.yaml`。
