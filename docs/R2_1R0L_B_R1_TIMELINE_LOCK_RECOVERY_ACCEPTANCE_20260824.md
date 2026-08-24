# R2-1R0L-B-R1 Timeline 并发锁恢复工程验收

- 验收日期：2026-08-24（UTC+8）
- 合同：`r2-1r0l-b-r1-timeline-lock-recovery-v1`
- 协议提交：`8e0898fd9f9598df8e5a812d64e3de380f7ff74f`
- 实现提交：`ed8e4ec8b08bd7ef1e08daea40c399c59e6b5701`
- 代码快照：`6be617e41ab6f88c12e27c920c4b6af66c481f6f2e7964f8978c3149693c1e2c`
- 终态：`GO_ENGINEERING_COMPLETE / NEW_CANDIDATE_NOT_BUILT`
- 生产授权：无

## 1. 裁决

R2-1R0L-B 暴露的同进程并发分叉已在源码层闭合：timeline writer 现在先按规范路径取得进程内互斥，
再打开文件并取得既有 `flock`，随后才读取和验证旧链、计算前驱、追加、flush 与 fsync。线程层不再把
Docker bind mount 的 `flock` 语义当作唯一保护；跨进程保护仍由文件锁承担。

专项、架构与全仓测试全部通过，旧事件 Schema、哈希、phase、预算、跨午夜、通知和业务账本语义均未
改变。本裁决只证明工程修复完成；尚未构建新镜像，也没有在真实 Docker bind mount 上复验，因此不
授权 L-C 或生产提升。

## 2. 实现边界

新增 `scheduler_timeline_lock.py`，职责仅为同一 Python 进程内按规范路径串行化临界区：

- 注册表键为 `Path.resolve(strict=False)` 的规范路径；
- 使用者计数包含正在持有和等待的线程；
- 最后一个使用者退出即删除条目，避免按日期无限增长；
- 等待或临界区异常也通过 `finally` 释放计数与已取得的 mutex。

原 writer 只增加薄调用。锁顺序固定为：

1. 进程内路径互斥；
2. 打开 append handle；
3. `flock(LOCK_EX)`；
4. 校验旧链并计算前驱；
5. append、flush、fsync；
6. 关闭 handle 后释放进程内互斥。

生产 writer 从 354 行增至 360 行；新锁模块 54 行，均低于 400 行软上限，没有把锁注册、业务阶段或
测试进程编排继续堆入 writer。

## 3. 独立工程门

`tests/test_scheduler_timeline.py` 现为 15 项，新增三层证据：

1. **互斥本体**：8 个线程同时进入同一路径，临界区最大并发数恰好为 1；全部退出后注册表为 0。
2. **线程集成**：测试中把 `flock` 替换成无效果函数，并在旧链读取后主动让出调度；8 个线程、8 个
   cycle、32 个事件仍形成单一合法链。这直接覆盖 L-B 的失败形状。
3. **独立进程**：4 个独立 Python 进程经 ready/start gate 同时写入同一文件，只依赖真实 `flock`；
   16 个事件形成单一合法链，每个 cycle 序列均为 `[1,2,3,4]`。

既有跨午夜文件绑定、篡改/截断 fail closed、未知 phase/account、写失败不进入 body、慢阶段 WARN 与
通知失败隔离均继续通过。

## 4. 验证结果

- timeline 专项：15 PASS；
- architecture-check：13 PASS；
- 全仓：1,879 PASS；
- warning：17 条，均为既有 Starlette 弃用提示和 M7 pandas future warning；
- Ruff：PASS；
- compileall：PASS；
- pip check：PASS；
- git diff-check：PASS；
- 新凭据、网络、`.env`、data 与真实业务读取：0。

关键文件 SHA-256：

- 协议机器真身：`3caf7504d28695c823fa18dc43c35c5bbbe1faf5a31c81a5377f395ef15258de`
- timeline writer：`8fae5c92b82ee76e50cca2e20ae6dc5f0b96246c441b01aa48213b5af38961c6`
- 进程内锁模块：`f37e070c6e988ee672c19f452fddc7fb6aaa4a631048947167ab91f3bf9c7cd7`
- timeline 测试：`1ebc31a6f20d3067dcf9b327299201af313a1a926188e6d5a7d346a2450f2809`

## 5. 生产与失败证据

本节点 Docker build、Docker fixture、promote、restart 和真实业务运行均为 0。生产 scheduler 保持：

- 容器：`183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`
- 镜像：`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`
- 状态：`running/healthy`
- restart policy：`unless-stopped`

失败候选 `sha256:56a97f02...0064f` 仍保留且没有运行中容器；L-B 的 JUnit、分叉 timeline 和输出树
原样保存在 Git 忽略区，同 scope 未重跑、未覆盖。

## 6. 下一合法节点

后继必须绑定包含本实现的已推送最终 HEAD、代码快照
`6be617e41ab6f88c12e27c920c4b6af66c481f6f2e7964f8978c3149693c1e2c`，再由用户明确批准：

1. 恰好构建一个新的内容寻址 scheduler 候选；
2. 使用同一新候选恰好运行一次断网、只读、只挂载专用日志根的 bind mount fixture；
3. 新 fixture 必须 15/15，并核验生产 scheduler 与业务账本不变；
4. 通过后仍须另行精确授权 L-C promote/restart。

不得重用或改标失败候选，不得用本机 1,879 PASS 代替 Docker bind mount 验收。
