# P2-1 账本时间字段审计附录（2026-07-25，UTC+8）

本附录在任何 P2-2 真实科创50模型、预测、回测或效果计算前冻结。它只更正 P2-1 三条 run ledger
和三条 admission ledger 的字段语义说明，不删除、覆盖或重写旧行，也不重算 P2-1 manifest、代码、
质量报告或工程报告。

## 发现与正确解释

`tools/p2_star50_engineering/run.py` 第 102–127 行把协议的
`frozen_at=2026-07-25T00:00:00+08:00` 同时写入旧账本的 `finished_at` 与 `evaluated_at`。因此旧字段名
不能按“真实运行完成时点/真实裁决时点”解释；其正确语义均为 **P2-1 协议冻结时点**。这不改变三条
追加记录的顺序、报告哈希、工程 GO 或“没有查看真实策略结果”的边界。

可核验的实际先后证据为：

- P2-1 冻结提交 `00bc0301dac6c050c347dd956381cf9d704511ba`，Git author/commit time 均为
  `2026-07-25T00:02:09+08:00`；
- P2-1 终版提交 `ea225cdaf06b951932ca5155ede7b61676fe0847`，Git author/commit time 均为
  `2026-07-25T00:32:01+08:00`；
- 终版工程报告 SHA-256 为
  `a4cfad049e36914fcec76f05c9dc6f5c24b55d85fe4213a37a3e8f7ae9909401`；
- 终版 tracked manifest SHA-256 为
  `4e946aa7d3e3c3da31ca8ad700bee2587a189dddfcf62b83054bc6804c163986`；
- 冻结提交先于终版提交，终版 manifest 又绑定三次 append-only 尝试和终版报告哈希。这些证据能证明
  先冻结后施工，但不能事后虚构旧三次运行的精确完成时间。

## P2-2 防回归

P2-2 新账本永久分列：

- `protocol_frozen_at`：配置中预注册的协议冻结时间；
- `run_started_at` / `run_finished_at`：真实执行时以 UTC 记录的开始/完成时间；
- `evaluated_at`：真实历史裁决形成时以 UTC 记录的时间。

P2-2 统一追加入口不以 `protocol_frozen_at` 为运行时间默认值，专项测试证明冻结时间和运行时间是不同
字段且相同终版键幂等。任何未来代码不得借本附录修改旧 P2-1 行。
