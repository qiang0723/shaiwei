# TP-F-0B 预检工程说明（2026-10-29，序列第②步：工程 + 合成测试）

- 依据：`docs/TP_F_0B_DATA_IDENTITY_PREFLIGHT_PROTOCOL_20261027.md`（`b5bc05f5…`）+ 补遗 A1
  `docs/TP_F_0B_DATA_IDENTITY_PREFLIGHT_ADDENDUM_A1_20261029.md`（配置 `00457fd9…`，在门实现前提交为 244c5f3）
- 包：`src/shaiwei/research/tp_f_0b/`；容器：`compose.tp-f-0b.yaml`；make：`docker-tp-f-0b-build / -fixture`、`tp-f-0b-scope-prepare`、
  `tp-f-0b-record-approval`、`docker-tp-f-0b-profile / -audit`
- 截至本文：真实画像 0 次；身份普查未在任何真实来源上运行；TP-F 公式 0 个

## 1. 模块

| 模块 | 职责 |
|---|---|
| `contract` | 钉住协议、补遗及两份文档的 sha；权限字段失败关闭；14 个绑定输入；R3 manifest 内 11 层全部原始 artifact 逐文件重哈希；qlib 产物哈希与日历 |
| `panel` | 复用 `recovery_store.prepare_core_tables`（PIT 中证800 成员日、两层停牌、申万 L1、ST）；加 SSE 日历时钟（t+1、t+11）、全量原始日线开盘、上市序号、原始行业命中数；直读 qlib bin |
| `fields` | RF-0C 分类器逐行原样调用；TP-F 新增 22 类；只输出计数与比例；门与裁决 |
| `signature` | 两种语法（AlphaGen 前缀、qlib 中缀）统一成规范 AST；冻结的趋势/回踩/联合状态规则 |
| `registry` | 用 RF-0B 原协议与原规则重建注册表并逐字节比对 `d3777d7a…`；扩展层（R3/R4/R5、TS v5 语义层、g1-v2）；联合状态普查 |
| `profile` | 排他认领目录 → 标记 → 两次完整计算比对（确定性重放）→ write-once 输出 |
| `scope` / `release` | 精确 scope（绑定镜像、代码快照、全部输入哈希、镜像内 fixture 报告）、逐字批准转录、漂移拒绝、CLI |
| `audit` | 独立容器只读重算一次，比对注册表、字段画像、画像、manifest 哈希与载荷哈希 |
| `fixture` | 18 例全合成对抗 fixture：建一个微型不可变库与 qlib 缓存，走真实的库→面板→分类路径 |

## 2. 实现中的口径选择（均在任何真实普查/画像之前确定）

1. **补遗 A1**：raw open/前收的分母 = 成员日 − `NO_BAR_SUSPENDED`；分子同 RF-0C；未解释无 bar 日留在分母；全成员日比例只报告。
2. **RF-0C 分类器原样复用**：只把 SQL 空值从 NaN 转成 None 再传入（该分类器按 `is None` 判断）。只影响"有 bar 但缺复权因子"的日子是否被误判为除权日；RF-0C 区间内复权覆盖为 100%，不受影响。
3. **申万 L1 唯一**沿用 `recovery_store` 的 PIT 规则（`in_date ≤ 日 ≤ out_date`，同日多条取最新 in_date），与 TS v3 数据门的 99.2539% 同一机器；原始命中多于一个 L1 的日子另记 `SW_L1_RAW_MULTIPLE_HIT`（只报告）。
4. **时钟**：t+1、t+11 按 SSE 交易日历（trade_cal 至 2026-10-31）推算；开盘价取该股全部原始日线，不限成员日。
5. **涨跌停开盘**（只报告）：把 t+1 开盘相对前收的涨幅交给生产函数 `attach_trade_limit_flags`，沿用板块/日期/PIT ST/上市首日/退市首日规则。
6. **qlib 门**：有 bar 成员日上六个特征全部非缺失（字面口径）；零成交量日 vwap 未定义，同时计 `ZERO_VOLUME_DAY`。
   只报告的完整性检查：
   - `QLIB_VALUE_ON_NO_BAR_DAY`：无 bar 日却有值，即被前值或零填充；
   - `QLIB_ADJUSTMENT_INCONSISTENT`：qlib 收盘 × factor ≠ 原始收盘，或 factor × 原始复权因子在除权日跳变（相对容差 1e-5）。
7. **预热**：qlib 日历序号 + 1 < 100 计 `WARMUP_BEFORE_QLIB_CALENDAR_START`；上市以来交易日数（含上市日）< 100 计 `LISTING_SHORTER_THAN_WARMUP`。上市早于 2016-01-04 的只由前一类覆盖。
8. **联合状态签名按冻结原文字面实现**：
   - 价格一侧必须是裸价格特征；
   - 锚一侧是"窗口内价格特征的 Mean/EMA/WMA/Med/Max/Min"，或"价格特征的 Ref"；
   - Div/Sub 不分操作数顺序；|c| ≤ 1e-6 的加法常数一律去掉；
   - 缩量 = 两个成交量项（裸量记窗口 1）的 Div/Sub，且窗口不同，原文未给窗口界；
   - 收盘位置只认 (close−low)/(high−low)。

   **已知局限**：均线交叉类（如 EMA10−EMA50）和收盘位置的仿射变体不算分量。它们在正式批中仍受规范 AST/语义去重约束。
9. Alpha158 任一式无法解析即失败关闭；LLM 账本表达式解析失败只计数。
10. **裁决优先级**：`REJECT_DUPLICATE`（机制终局）> `BLOCKED_DATA`（可恢复）> `GO_FORMAL_PROTOCOL`。
11. **两套列口径**：
    - 封存注册表按 RF-0B 原规则重建，会读 v1 准入的 `evidence_sha256`，这是原规则本身；
    - TP-F 扩展层只读协议允许的身份列，效果列在读入时即丢弃。
12. **scope 不绑定 ingest 账本快照**：原始输入已由不可变 R3 manifest 逐文件钉住，而 ingest 账本每天随生产追加，绑定它只会造成假漂移。

## 3. 验证

- `tests/test_tp_f_0b.py`（17）：
  - 钉扎与篡改（4 份冻结文件任一改动即失败关闭）；
  - 14 个绑定输入、封存注册表逐字节复现、账本只读允许列；
  - 签名的两种语法、拒绝非白名单语法；
  - 18 例 fixture 全过，削弱机器（复权容差放大）时 fixture 失败关闭；
  - 门与裁决优先级、逐字批准与漂移；
  - 在合成库上单次执行、拒绝重跑，独立审计 PASS，篡改证据后审计 FAIL。
- `tests/test_tp_f_0b_docker_contract.py`（2）：
  - 三个服务断网、只读根、宿主 UID、无 env_file 与锁；
  - 每个服务只有一个写入点，fixture 不挂真实数据；入口为 release 子命令。
- 构建资产注册表新增组件 `tp-f-0b`（102 项）；架构检查通过（拆出 `scope.py` 消除 audit↔release 循环）。
- 规模压测（纯合成 210 万行）：分类约 5 秒，进程峰值约 2.1 GB。

## 4. 后续（每步单独授权）

③ 推送后构建镜像 `shaiwei:tp-f-0b-<快照12位>`，镜像内跑 fixture 并写报告；
④ `tp-f-0b-scope-prepare` 生成精确 scope 与逐字批准文本 → 用户逐字批准 → 唯一画像 + 独立审计 → 验收与 STATE。
