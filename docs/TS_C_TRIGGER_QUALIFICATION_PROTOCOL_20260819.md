# TS-C 触发器资格赛结果盲预检协议（2026-08-19，待用户批准）

- 机器真身：`config/ts_c_trigger_qualification_v1.yaml`，SHA-256
  `44dcaf42e1446f07ead27e74d5dfcfc536077bd66def3c0a1780f1f4553a95fa`
- 状态：`RESULT_BLIND_QUALIFICATION_PREFLIGHT_FROZEN_PENDING_USER_APPROVAL`
- 上位授权：用户 2026-08-19 批准前瞻锦标赛方案与三候选清单

## 1. 三臂触发器（机制互异、结果盲定义、零参数调优）

| 臂 | 触发（收盘后判定，只用 ≤t 数据） |
|---|---|
| `VWAP_ANCHOR_PULLBACK` | 当日最低价 ≤ 上一完整周 VWAP − 1×ATR20（v3 原生锚） |
| `HIGH20_DRAWDOWN` | 当日最低价 ≤ 20 日最高复权收盘 − 1×ATR20（极值回撤） |
| `MA20_PULLBACK` | 当日最低价 ≤ MA20 ≤ 当日收盘（触均线而不破） |

共享事件语义：武装后 ≤10 个交易日内"收复前日高点 + 收阳 + 指数>SMA20"确认成事件；
失效线 = 武装参考 −1×ATR20；同 episode 不重复武装；事件键 `[ts_code, signal_date]`。

## 2. 资格堆栈（v3 冻结值 + R3G-1 市场板块门）

中证800 PIT、非 ST、`.BJ`=0、月 SMA6 双许可（指数与个股）、市值≥200亿、上周成交额≥50亿、
三根完整周 K 低点不下移、7 个完整月末 + 20 个有效日线。板块门本次复用 R3G-1 冻结门（锦标
赛协议将单独冻结板块口径）。

## 3. 门（前瞻证据产能门槛，非结果推导）

每臂：确认事件 ≥120 条（2019—2025）、每年 ≥10 条、不同信号日 ≥40、`.BJ`=0。门在画像前
冻结，不达标即出局，不调参、不降门。

## 4. 防火墙与出口

只输出事件计数/信号日/年度分布/状态转换计数；不读收益、不读 Alpha158、不训练不回测。
- `GO_TS_C_TOURNAMENT_PROTOCOL_DRAFT_ONLY`：只授权起草锦标赛协议；
- `STOP_TS_C_NO_DENSE_LEGAL_TRIGGER`：三臂全灭，TS-C 方向关闭，回下一方法家族。

批准后施工；fixture 与真实画像之间不停顿（零效果）。
