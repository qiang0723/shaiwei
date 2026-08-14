# TS-v5 R3G-2 H00906 显式字段映射恢复 R3

日期：2026-08-14（UTC+8）

状态：`RESULT_UNKNOWN_EXPLICIT_FIELD_MAPPING_RECOVERY_FROZEN`

机器真身：`config/ts_v5_r3g2_benchmark_evaluation_recovery_r3.yaml`

R2 三份官方原始证据已成功固化，两份历史 JSON 物理 SHA 完全相同。第一次断网评价在任何 Parquet、
report或manifest写入前，于指数身份门失败。只读身份诊断确认原始响应共有1846行，`indexCode` 全部为
`H00906`，名称为中证800全收益指数；错误来自实现先将 JSON 字典 key 规范排序，再按原接口位置重命名，
导致字段值错位。

R3 不再联网，也不改原始文件。唯一实现变化是按16个中证指数官方字段名显式映射到内部列；缺字段、
多字段或重复字段全部 fail closed，字典 key 顺序不得影响结果。新增一项 key 顺序扰动对抗测试。
日期解析、双响应一致性、事实表身份、SSE日历、唯一键、close和可选OHLC门均保持不变。

R3只允许一次断网评价恢复和一次断网独立审计；不读取secret、候选收益或Alpha158数值，不做参数比较、
模型、回测、模拟仓、Web、scheduler或生产变更。GO仍只代表H00906基准数据门通过。
