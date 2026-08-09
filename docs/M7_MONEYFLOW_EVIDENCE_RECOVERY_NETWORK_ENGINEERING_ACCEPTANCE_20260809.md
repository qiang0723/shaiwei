# M7-0R3-P2 精确网络恢复 release 工程验收

## 裁决

`GO_M7_RECOVERY_NETWORK_RELEASE_ENGINEERING_ONLY`。

该 GO 只证明离线请求计划、四角色隔离执行壳、写一次批次、精确 release/approval 契约和断网合成
fixture 已具备。真实 527/541 键请求计划尚未运行，Baostock/Tushare、外网、`.env`/token 与资金流
数值读取均为 0；本裁决不是数据恢复 GO，不授权调整覆盖率、候选、效果、模型、回测、前瞻、模拟仓
或生产。

## 架构边界

P2 新能力位于独立包 `m7_moneyflow_network_recovery`，只复用冻结的
`m7_moneyflow_recovery` 规划、provider adapter、claim、batch、evaluator 与 auditor 能力。没有向旧包
继续堆叠文件；旧 P1 target-projection code bundle 回归哈希仍为
`17997e655421b0f9192a506cb9c4bc471290887e357e591c5a4dc97facbc26d0`。

新包拆为 protocol、request plan、store、collector、live client、runtime、release、evaluator、auditor 与
CLI；最大模块 377 行，低于 400 行软上限。状态 collector、资金流 collector、evaluator、auditor 四角色
窄挂载，collector 无共享可写目录；只有未来获批的资金流 collector 能读取单独 token 文件，禁止挂载
`.env`。evaluator 与 auditor 永久 `network=none`。

## 失败关闭与安全

- 每个 provider 请求在调用前原子 claim；最多 3 次传输尝试，语义失败不重试；
- 批次为 write-once Parquet + canonical receipt，重复调用在 provider 前停止；
- 请求计划只从 `source_date × ts_code` 精确投影，证券代码只允许出现在 Git 忽略控制目录；
- tracked manifest/release 只允许计数、日期范围与哈希；`.BJ`、额外键、缺键、重复、饱和、字段异常、
  非有限值与双请求形态不一致均失败关闭；
- 开发工作树、Docker socket、生产 raw/ledger/logs、scheduler 与 Web 均不挂载、不修改。

## 验证证据

- 本地网络协议、请求计划、四角色工程与旧恢复回归共 36 PASS；
- 全仓 1,059 PASS，保留 1 条既有 Starlette 弃用提示和 16 条冻结 lineage Pandas future warning；
- 架构宪法 13 PASS，Ruff、compileall、pip check、Compose config、diff-check、凭据扫描 PASS；
- `network=none` Docker fixture PASS：3 次均为 mock provider 调用，重复请求在 provider 前停止；
- 工程镜像：`sha256:21fe0c42a0111005806438274d50c3e0b2205beadacf24baf75a672f12b71e1b`，
  `linux/arm64`；
- scheduler 保持 `shaiwei:scheduler-current`、Up 5 days、healthy，未重启；7 个自然生产账本未暂存。

## 下一停止点

本实现必须先提交并推送。随后只允许使用该推送代码的不可变镜像，以 `network=none` 读取 P1 封存目标
与 R2 封存日历元数据，生成一次真实请求计划及脱敏 manifest。最终代码、镜像、请求身份、命令、挂载、
资源、网络角色与调用上限绑定为新 scope 后必须停止，等待用户逐字批准；当前仍不得调用 provider 或
读取 secret。

