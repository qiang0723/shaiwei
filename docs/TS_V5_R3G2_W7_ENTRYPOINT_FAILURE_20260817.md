# TS-v5 R3G-2 W7入口失败封存

日期：2026-08-17（UTC+8）

裁决：`ORIGINAL_SCOPE_CONSUMED_NO_REAL_LINEAGE_READ`

原release scope：`5d2389429aa4ba272371d60214fd04866405372f61b7d3933db67e8a7b7838ad`

## 事实

用户逐字批准后，唯一runner于2026-08-17 08:33:35（UTC+8）创建容器并调用冻结命令。模块完成导入后，
`main()`把argparse的`release`和`approval`直接展开给要求`release_path`和`approval_path`的`run()`，立即
触发`TypeError: run() got an unexpected keyword argument 'release'`。

失败发生在`run()`进入之前，因此没有写入`authorization.json`或`lineage_read_started.json`，没有调用
provider校验或Qlib初始化，没有训练模型或生成分数；RankIC、收益、H00906、组合和策略效果均未读取。
原scope的runner invocation已消费为1，auditor invocation为0，策略效果尝试为0。

## 裁决边界

- 原scope不得重跑，也不得把入口失败记成策略失败。
- 无完整lineage产物，原scope不得调用auditor伪造结论。
- 修复必须同时覆盖runner与auditor CLI参数映射，并新增直接调用两个`main()`的回归测试。
- 修复提交、不可变镜像和host/image哈希门通过后，只能另立带前序失败身份的新recovery scope；再次取得
  用户逐字批准前，不得读取真实W7。

Git忽略证据：`data/control/ts-v5-r3g2-w7/attempt-5d238942-failure.json`。原lineage与audit目录保持为空。
