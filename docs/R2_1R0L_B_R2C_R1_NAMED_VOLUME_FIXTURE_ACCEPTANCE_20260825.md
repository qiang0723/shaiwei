# R2-1R0L-B-R2C-R1 Named-volume 锁真实 Fixture 验收

- 日期：2026-08-25（UTC+8）
- release scope：`8887bbdf31f1f05fe0a7feffca80a5b96605f407182eb4d3275c5346c2369a22`
- 动作：`R2C_R1_RUNTIME_LOCK_FIXTURE_ENTRY_RECOVERY_ONCE`
- 终态：`BUILD_PASS / FIXTURE_PASS / GO_R2D_PROTOCOL_ONLY`
- 生产授权：无

## 1. 裁决

绑定最终 HEAD 和代码快照的新候选已恰好构建一次；同一候选的完整断网真实 Docker fixture 已恰好
调用一次，冻结的 10 项用例全部 PASS。R2C-R1 scope 已关闭且永久不得重跑。

本次 PASS 回答的是 named-volume 锁工程合同：线程、独立进程、双容器、崩溃释放、canonical ledger
并发和错误挂载在唯一候选上均满足冻结门。它允许另立 R2D 生产提升协议，不等于已经 promote、
restart 或启动 R2-1R1，也不构成任何策略、模型或模拟仓有效性结论。

原 R2C scope 的 `BUILD_PASS / FIXTURE_FAIL` 及三份失败证据永久保留；R2C-R1 不改写历史，只以新
候选和新 scope 首次完成锁行为评价。

## 2. 唯一候选构建

- Git HEAD：`55f98e7085bf7f1a573c9105606c842a9655b63c`；
- 代码快照：`88e3f471565ba461fb660f41a97a2dd4ac633585c4f74efadd9a3b264e2abec0`；
- 候选：`shaiwei:scheduler-88e3f471565ba461`；
- image ID：`sha256:b7565001835936e1235d24de3c567f0d13869d48f30596ac7172df7b849baa72`；
- lock authority：`docker-named-volume-v1`；
- release build audit：`279593f93d217bbd09ed1ee045a395d5658efae8578ab9d9b276472c0b203035`；
- approval / build claim / build receipt SHA-256：`72fe1bdb...404e0` /
  `a8d9ff30...8098` / `ccf57a99...2c01`；
- 构建次数：恰好 1，状态 `BUILD_PASS`。

构建来源为已推送的隔离 Git archive；只使用 Dockerfile 冻结的软件包安装网络，没有读取 `.env`、
secret 或业务数据，没有修改 current/previous alias 或生产容器。

## 3. 唯一真实 Fixture

fixture 在新输出根先写 claim，再执行 34 条受控 Docker 命令。以下 10 项全部 PASS：

1. 镜像 label、运行时 HEAD、代码快照和锁权威一致；
2. 候选原生 payload 在 no-op `flock` 下保持 8 线程临界区串行；
3. 4 个独立 Python 进程生成唯一合法 timeline 哈希链；
4. 两个容器的 EX/SH/非阻塞冲突矩阵正确；
5. holder 被 `SIGKILL` 后锁可接管且锁文件身份保留；
6. 8 进程合成 canonical ledger 追加不丢行，重复键异内容失败关闭；
7. missing mount 失败关闭；
8. readonly mount 失败关闭；
9. 真实 wrong-volume metadata 被 release 门拒绝；
10. 未知资源、逆序和递归锁全部失败关闭。

不可变证据：

- claim SHA-256：`f357fb9007d9d62bb65914258c3ba6b24fecabe429e1b53d0aebadb2a769efb6`；
- report SHA-256：`6e5a9ec20f8d81d9b995f74e4882d08cadbaaf858fa742f5e42787fcf21b208b`；
- tree 文件 SHA-256：`8119713085742c0e37b2660669b98cd0ebeabbae61c71b306ecb909672f8e233`；
- tree 内容摘要：`36b9cc9cd59a9e4d8b16b718667bf304f7d099fe73f0e280a4ce5a452b00dee6`；
- fixture receipt SHA-256：`9bd08aecd49de220a51985b0b82e2821f093d02b1ea7d5c6f940c3aac2fa9fe3`；
- 证据树共 9 份文件，仅含 claim、report、合成 CSV 和 fixture gate 文件。

报告、tree 和逐文件哈希已独立复算一致；未包含环境变量、主机绝对路径或完整 Docker metadata。

## 4. 清理与生产隔离

- scope 专属临时容器残留 0；
- `shaiwei_r2c_wrong_*` 临时错误卷残留 0；
- 既有稳定锁卷 `shaiwei_runtime_locks_v1` 保留，driver=`local`，未创建或删除；
- 生产 scheduler 仍为原容器 `183b8c6c5edd...23dd3b`、原镜像
  `sha256:722f63de...13b76`、原创建时间，`running / healthy / RestartCount=0`；
- current alias 仍指向旧生产镜像，候选没有 promote，生产没有 restart。

真实业务、历史回填、真实 ledger、Web、模型、策略、模拟仓、外网数据源和密钥读取均未执行。

## 5. 下一停止点

R2C-R1 到此关闭。下一合法节点仅为 R2D 结果盲生产提升协议：避开数据窗口，结果前冻结 candidate →
current、previous 回滚、四挂载、启动健康、首个自然交易日 timeline/daily/shadow/paper/通知与幂等门。
R2D 的 promote/restart 必须再次绑定精确身份并由用户单独授权；在此之前不得切换生产，也不得启动
R2-1R1 连续计数。
