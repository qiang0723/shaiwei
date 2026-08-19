# TS-C 触发器资格赛 v2 协议（2026-08-19，待用户批准）

- 机器真身：`config/ts_c_trigger_qualification_v2.yaml`，SHA-256
  `f89292253e2819db199df307fee37310a0147bcf2aa1ef309964580cd2e8e2c2`
- 状态：`RESULT_BLIND_QUALIFICATION_PREFLIGHT_FROZEN_PENDING_USER_APPROVAL`
- 上位授权：用户 2026-08-19 批准"许可开启年"口径重述（v1 STOP 裁决保留不动）

## 1. 唯一变化（设计语义论证，非结果推导）

v1 的逐日历年密度门把"熊市整年空仓"这一 v3 设计行为误判为触发器失败。v2 只改门的时间轴：

- **许可开启年**：指数 000906 月级双许可（上月收盘>SMA6 且 SMA6 环比上升）在该年 ≥50% 的
  交易日成立——只从绑定指数数据机械计算，不由事件数反推；
- 每臂在**每个许可开启年**≥10 条（阈值与 v1 逐字相同）；许可关闭年的事件仍计入总量与
  信号日；许可开启年数 <4 即失败关闭（防止重述坍缩成择年）。

其余全部与 v1 逐字节一致：三臂触发器、资格堆栈、事件语义、期间、防火墙、执行边界。

## 2. 裁决

- `GO_TS_C_TOURNAMENT_PROTOCOL_DRAFT_ONLY`：只授权起草锦标赛协议；
- `STOP_TS_C_NO_DENSE_LEGAL_TRIGGER`：TS-C 关闭，移交下一方法家族。

批准即施工，fixture 先行。
