# R2-1R0L-B-R2C Named-volume 锁 fixture 失败验收

- 日期：2026-08-25（UTC+8）
- release scope：`2da6de12e3c4ab2d7b301a9e279ffc5091b458672672f4b9ca81a3adf8ed5afa`
- 动作：`R2C_RUNTIME_LOCK_NAMED_VOLUME_FIXTURE_ONCE`
- 终态：`BUILD_PASS / FIXTURE_FAIL / NO_GO_PROMOTION`
- 生产授权：无

## 1. 裁决

绑定最终 HEAD 与代码快照的候选已恰好构建一次并通过身份门；同 scope 的断网真实 Docker fixture
也已恰好调用一次，但在第 2 项 `eight_threads_with_noop_flock` 失败关闭。因此本 scope 永久不得重跑，
候选不得 promote，R2D 和 R2-1R1 均不得启动。

这不是 named-volume 锁行为失败。第 1 项已经证明候选 image ID、label、运行时 manifest、Git HEAD、
代码快照和 `docker-named-volume-v1` 权威一致；第 2 项在进入并发临界区前因 fixture 入口合同不匹配
退出，后续 8 项均未运行。权威状态只能是 `LOCK_BEHAVIOR_NOT_EVALUATED`。

## 2. 唯一候选构建

- Git HEAD：`a909cdd1c79bc4a27e121647e9e272c8b91d02e7`
- 代码快照：`8009eeb50c7d35f5c9a1762dc92ee36c112db75e4ff67b94f6096bee381d7b70`
- 候选：`shaiwei:scheduler-8009eeb50c7d35f5`
- image ID：`sha256:da26760247c55e9d2c5189aa28dcf7dc3d6fb07a74b8e5d2dca7bf5895cea4d7`
- lock authority：`docker-named-volume-v1`
- release build audit：`59a0aa9b9325883b63e1fd5bb273d6758d89e947bdaee3ea5c389a6f51903ca1`
- 构建次数：恰好 1，状态 `BUILD_PASS`

构建来源为已推送 Git archive；没有读取 `.env` 或 secret，没有挂载业务数据，也没有修改 current/
previous alias 或生产容器。

## 3. 唯一 fixture 与根因

fixture 在新输出根写入 claim 后才执行 Docker 命令，命令计数为 3：候选 label inspect、运行时身份、
第 2 项测试容器。第 1 项 PASS，第 2 项 FAIL，suite 立即停止。

根因可由冻结源码直接复核：

1. R2C 编排器为候选容器设置 `SHAIWEI_LOCK_AUTHORITY=docker-named-volume-v1`，要求锁根只能是
   `/run/shaiwei-locks` 的真实 mount；
2. 被选中的宿主测试 `test_thread_layer_serializes_even_when_flock_is_ineffective` 调用
   `logical_lock(..., lock_root=tmp_path)`；
3. 生产锁后端在 Docker authority 下明确禁止任何显式 `lock_root`，因此在并发临界区前正确抛出
   `LockConfigurationError("Docker lock authority has an invalid root")`；
4. fixture 编排器把该容器非零退出包装为 `FixtureError` 并按协议停止。

因此错误属于 `FIXTURE_ENTRY_TEST_CONTRACT_MISMATCH`：宿主隔离测试被错误复用为生产 authority 测试。
不得通过放宽生产锁根校验修复；正确恢复是新增候选原生 payload，在不传显式锁根的情况下把候选内
`flock`替换为 no-op，再验证 8 线程进程内串行。

## 4. 不可变证据

- claim SHA-256：`52d956eac57bd738ab25615d6c9338bcda6052359f59facf365d72a1d1f7647f`
- report SHA-256：`7bb5e6c124361ea27653a7459d2ec62e115bab4cec7a77bd88a5880adf6654e7`
- tree 文件 SHA-256：`b5fcf8a1953507725d9718d6abe0ecb8503764e2b614b79bd0133d0fcfa9fe5e`
- tree 内容摘要：`03f564da57b441c79acc2f43839b09bcce924401dccc6a32672eeb9c375fc4e4`
- 证据文件：claim/report/tree 共 3 份；同 scope 输出根已存在，编排器会拒绝再次进入。

稳定锁卷 `shaiwei_runtime_locks_v1` 已由唯一 suite 创建并保留；失败发生在 wrong-volume 用例前，
scope 专属容器和临时错误卷残留均为 0。未读取锁卷内文件。

## 5. 生产隔离与下一合法节点

失败后生产 scheduler 仍为原 `shaiwei:scheduler-current`、运行 3 周且 healthy；未 restart、promote、
运行真实业务、写真实 ledger、访问 Web/模型或读取密钥。

下一合法节点只能是 `R2C-R1` 结果盲 fixture 入口恢复：

1. 永久保留 R2C scope、候选和三份失败证据；
2. 只替换第 2 项为不传显式锁根的候选原生 8 线程 payload；
3. 增加 daemon 命令形状门，证明真实 authority、真实 volume 和 no-op `flock` 同时成立；
4. 其余 9 项、安全边界、门槛和顺序不变；
5. 工程推送后绑定新 HEAD/快照/候选和新 scope，再申请一次新构建与一次新 suite。

R2C-R1 未全绿前，不得进入 R2D 或启动 R2-1R1。
