# RF-0B 缺口谱系诊断协议（2026-08-19，待用户批准）

- 机器真身：`config/rf_0b_gap_lineage_diagnostic_v1.yaml`，SHA-256
  `0a04c12edf5bad56c1571227c48b0e081cad0c10f60b69e9e5035702e1453bb3`
- 状态：`RESULT_BLIND_DATA_LINEAGE_DIAGNOSTIC_FROZEN_PENDING_USER_APPROVAL`
- 上位授权：用户 2026-08-19 按建议立项

## 1. 目标（只做谱系解释）

从绑定的不可变原始快照重算同一个 RF-0B 成员日面板，精确取出被分类为 `NO_BAR_UNEXPLAINED`
的 5 个键（`ts_code, trade_date`），并只用绑定证据层逐键解释来源：

| 证据层 | 解释类别 |
|---|---|
| Baostock 独立交易状态='0' | `SUSPENDED_BY_INDEPENDENT_BAOSTOCK_STATUS` |
| Tushare suspend_d 有记录（含时段标注，即 RF-0B 主停牌定义未覆盖的盘中/半日停牌） | `SUSPENDED_BY_SUSPEND_D_WITH_TIMING_ANNOTATION` |
| 临近上市/退市边界 | `LIFECYCLE_LIST_OR_DELIST_EDGE` |
| 指数成员形成日边界 | `MEMBERSHIP_FORMATION_EDGE` |
| 以上全无 | `UNEXPLAINED_REMAINS` |

键计数必须等于 5 且与封存画像一致；任一键无证据层即按 `UNEXPLAINED_REMAINS` 留痕。

## 2. 铁边界

- 不计算任何候选值/收益；不改任何门槛；不重新评价 RF 机制（`BLOCKED_DATA` 裁决不动）；
  诊断只产生证据，不产生裁决翻转。
- RF 若要继续，必须另立全新预检协议并再次获得你批准。
- 断网、write-once、一次诊断、一次独立审计、同 scope 不重跑、不碰生产。

## 3. 裁决

- `DIAGNOSIS_COMPLETE_ALL_EXPLAINED`：5 键全部权威解释——为将来可能的 RF 新预检备齐证据；
- `DIAGNOSIS_COMPLETE_UNEXPLAINED_REMAINS`：存在无法解释的键——RF 遗留数据问题坐实；
- `BLOCKED_DIAGNOSTIC`：键重推或输入失败。

批准即施工；fixture 与真实诊断之间不停顿（本协议零效果零结果，仅为数据证据）。
