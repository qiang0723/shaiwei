# R2-1R0L-B-R2C Named-volume 锁真实 fixture 协议

- 日期：2026-08-25（UTC+8）
- 合同：`r2-1r0l-b-r2c-named-volume-fixture-v1`
- 当前状态：`FROZEN_RELEASE_ENGINEERING_NOT_EXECUTION_APPROVAL`
- 生产授权：无

## 1. 结果目标

R2B 已把五类生产关键写路径迁移到统一逻辑锁，但宿主单元测试不能证明 Docker Desktop 的真实
named volume 在独立进程、双容器、崩溃和错误挂载下满足合同。R2C 只回答这一项工程问题：最终候选
镜像能否在不读取任何业务数据的前提下，通过一次断网、合成、可审计的真实 Docker 锁 fixture。

通过只允许进入后续 R2D 生产提升评审，不等于生产已发布，不构成策略、模型、模拟仓或研究有效性
证据。任一用例失败都必须 `NO_GO_PROMOTION`，同一 scope 不得重跑。

## 2. 冻结身份与两段授权

R2C release 工程以前驱实现提交
`669174e2354ac2f5148e6c79a2b7a975664c612b`、前驱快照
`626cacdf48c96ac7a127353bf98ebe9ef3e335d4a07641d01bdb1e245704d4cb` 为起点。fixture 编排器、合同和
测试本身属于受控构建输入，因此必须先完成并推送，再从最终 `HEAD == origin/main` 复算最终代码快照、
候选标签和唯一 scope SHA-256。

本提交只授权 release/fixture 编排工程。真实 Docker 操作必须等待用户另行批准一条同时绑定最终
HEAD、最终快照、候选标签、scope SHA-256 和动作名的精确授权。授权后只允许：

1. 从隔离 Git archive 恰好构建一个候选；
2. 使用该候选恰好调用一次完整 fixture suite；
3. 写入唯一、Git 忽略的 R2C 合成证据根。

build 失败或 fixture 失败均消费该 scope；禁止原 scope 重试、删失败证据或放宽门槛。

## 3. 唯一真实 fixture

fixture 必须同时满足：`network=none`、只读根、`cap-drop=ALL`、`no-new-privileges`，不挂载 `.env`、
secret、Docker socket、项目工作树、业务 data、生产 ledger 或生产 logs。只允许：

- 把稳定锁卷 `shaiwei_runtime_locks_v1` 挂到 `/run/shaiwei-locks`；
- 把本 scope 新建的合成输出根挂到 `/fixture`，ledger 用例可把同一合成根挂到
  `/workspace/ledger`；
- 使用 tmpfs `/tmp`。

一次 suite 内必须全部证明：

1. 镜像 label、运行时 manifest、Git HEAD、代码快照和锁权威逐项一致；
2. `flock` 被替换成 no-op 时，8 线程仍由进程内层串行；
3. 4 个独立 Python 进程写出唯一合法 timeline 哈希链；
4. 两个容器共享同一锁卷时，EX/SH 与非阻塞冲突矩阵正确；
5. holder 被 `SIGKILL` 后新进程可接管，锁文件仍保留且不能靠删除接管；
6. 8 个进程追加合成 canonical ledger 不丢行，重复键异内容继续失败关闭；
7. missing mount、readonly mount、真实 wrong-volume metadata、未知资源、逆序和递归全部失败关闭。

fixture 开始前必须先在新输出根写 scope claim；每项用例、精确容器命令计数、候选身份、失败类型、
报告哈希和证据树清单都要落盘。报告不得包含环境变量、主机绝对路径或 Docker 完整 metadata。

## 4. 迁移、回滚与停止点

R2C 不修改当前 scheduler，不标记 current/previous，不运行真实业务。稳定锁卷只保存逻辑锁身份，
不保存业务证据；fixture 后可保留供 R2D 使用。候选失败时保留镜像和合成证据，当前生产仍运行旧
`legacy-bind-flock-v0` 镜像。

只有 R2C 全绿后，才可另立 R2D：避开数据窗口，精确批准 promote/restart，验证 previous 回滚兼容、
首个自然交易日 timeline/daily/shadow/paper/通知/幂等，再决定是否启动 R2-1R1 连续计数。

## 5. 当前不授权

当前不授权 Docker build、真实 fixture、volume 创建/删除、promote、restart、业务读取、历史回填、
真实 ledger 写入、网络、密钥、模型、Web、DeepSeek、模拟仓或生产。fixture 工程推送后必须停在精确
授权前。
