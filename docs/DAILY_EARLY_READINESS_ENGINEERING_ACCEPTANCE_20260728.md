# 日增量16:00早探测工程验收

> 日期：2026-07-28（Asia/Shanghai）
>
> 协议：`p0-daily-early-readiness-v1`
>
> 裁决：`GO_EARLY_READINESS_ENGINEERING_ONLY`
>
> 生产状态：`NOT_PROMOTED_NOT_ACTIVE`

## 结论

系统已从“19:30后才把当日纳入计划”改造为“16:00起每15分钟在内存中探测五类正式输入，数据完整
即进入原正式跑批；19:30仍恢复原硬失败与飞书告警路径”。工程门全部通过，但候选未提升、未启动，
尚无真实交易日16:00稳定性结论。

- 结果前协议提交：`d8b72d5`；
- 实现提交：`7b48291`；
- 未改变数据源、请求字段、最低行数、唯一键、跨接口覆盖、基准唯一行、`.BJ=0`或S1—S10；
- 未改变模型、信号截止、Top30/Top20账户、模拟成交、飞书完成事件或生产挂载。

## 实现语义

1. `ready_hour/minute` 固定为16:00，`source_deadline_hour/minute` 固定为19:30，且配置schema强制
   deadline晚于ready。
2. 16:00—19:29只对当日执行 `daily`、`adj_factor`、`daily_basic`、`suspend_d`、中证800
   `index_daily` 五项查询。
3. 内存响应经过与正式采集相同的Tushare字段规范化、重试、`.BJ`过滤和 `validate_trade_date` 门。
4. 未齐或临时请求错误返回 `WAITING_SOURCE`；不调用RawBatchWriter，不写Parquet/业务账本，不发开始、
   完成或失败通知，不使scheduler降级。
5. 探测通过后重新请求并执行原正式写入路径，不能把内存frame直接升级成生产真身。
6. 19:30起跳过静默探测，恢复原正式写入、FAIL账本、飞书告警和scheduler降级语义。
7. 若同时存在历史缺口和当日缺口，先正式补历史；下一轮再探测当日，不用当日未齐阻塞历史恢复。

## 验证

- 相关Python测试：40 PASS；
- 全仓：361 PASS，只有既有Starlette弃用warning；
- Ruff：PASS；
- `compileall`：PASS；
- `git diff --check`：PASS；
- fixture明确断言未齐时：`WAITING_SOURCE`、完成日期0、batch 0、row 0、通知0、Parquet 0；
- 16:00带历史缺口只补历史、16:00仅当日进入探测、19:30仅当日进入正式路径均有纯函数断言；
- 候选镜像在 `--network none`、只读根、drop all capabilities、no-new-privileges 下专项40 PASS。

## 不可变候选

| 字段 | 值 |
| --- | --- |
| 镜像 | `shaiwei:scheduler-0963ed74efef91f9` |
| image ID | `sha256:0a5a64d494e05dfb80b6bdb6ef0b4f198a79e417a2532494d4e48fdc4339f273` |
| 代码快照 | `0963ed74efef91f98b3d6230d6734da217bd1867b17c4d730a3d2cd1b1fdc99f` |
| Git | `7b482916c974fe77200d60ffe2d8c31cd1aabdf3` |

候选只构建，未promote、未tag为current、未启动。

## 重复构建留痕

第一次受控构建是长时异步session；在其仍运行时，操作层误把外层等待完成当成构建完成，随后再次
启动同一构建。两次最终都成功，追加链保留两条 `BUILD_PASS`：

- 第一条record：`7b52c97841973615c337ba09f3445ecf18af0663456ada139f10c20892bf6175`；
- 第二条record：`48b40297b7dd06b5d03c6d48f18717119de82921c310ba1a61be3dd56f794d9c`。

两条的镜像、image ID、代码快照和Git身份完全一致；release审计链22条、tip为第二条record，终验
PASS。没有删除、合并或改写记录，没有promote或重启生产。后续长构建必须持续poll同一session，禁止
因暂时无stdout重复发起。

## 生产隔离与启用顺序

验收时发布指针仍指向已授权但未启动的Top20候选
`shaiwei:scheduler-4e5244b6b02739dd`；实际运行scheduler仍为原镜像
`sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`，持续healthy。

为保持一次一个生产变量：

1. 先在原19:30口径下完成Top20候选首次生产切换与自然FORWARD验收；
2. 早探测候选不参与该次切换；
3. Top20稳定后，在下一个新交易日窗口单独promote并启动本候选；
4. 至少记录首次探测时点、首次就绪时点、正式完成时点、整日PASS、`.BJ=0`、信号、两账户、飞书、
   重放和幂等；
5. 多日真实观测后才评价16:00—17:00完成率，单日早完成不得外推为稳定SLA。
