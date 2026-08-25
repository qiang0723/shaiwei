# R2-1R0L-B-R2C Docker lock fixture 编排工程验收

- 日期：2026-08-25（UTC+8）
- 合同：`r2-1r0l-b-r2c-named-volume-fixture-v1`
- 终态：`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`
- 生产授权：无

## 1. 结果

R2C 一次性真实 Docker fixture 已完成结果盲编排工程，尚未运行。最终编排器只接受内容寻址候选标签、
精确 Git HEAD、精确代码快照、64 位 scope SHA-256 和唯一输出根；任何字段漂移或输出根已存在都会在
首个 Docker 命令前失败关闭。

执行入口会先写 scope claim，再按冻结顺序运行 10 项真实用例，落盘候选身份、逐项状态、Docker 命令
计数、失败类型、报告 SHA-256 和证据树清单。同一 scope 无论成功或失败均不能重跑。

## 2. 真实执行合同

编排器只构造以下运行边界：

- `network=none`、只读根、`cap-drop=ALL`、`no-new-privileges`、受限 CPU/内存/PID、tmpfs `/tmp`；
- 只挂载稳定锁卷到 `/run/shaiwei-locks`，以及当前 scope 的合成输出根；
- ledger 用例只把同一合成根挂到 `/workspace/ledger`，不挂生产 ledger；
- 不挂 `.env`、secret、Docker socket、工作树、业务 data、生产 logs 或其他项目目录；
- wrong-volume 用例只创建 scope 专属临时空卷，读取真实 daemon mount metadata 后交给同一 release
  mount contract 判定，并在用例结束清理临时容器和空卷。

10 项门逐项对应冻结清单：镜像/运行时身份、8 线程 no-op `flock`、4 独立 timeline 进程、双容器
EX/SH/NB、SIGKILL 释放、8 进程合成 ledger、missing、readonly、真实 wrong-volume metadata，以及未知
资源/逆序/递归失败关闭。

## 3. 架构与代码规模

- `runtime_lock_fixture.py` 只负责宿主 Docker 编排、scope claim 和证据汇总，共 400 行；
- `runtime_lock_fixture_payloads.py` 只保存候选容器内的固定 Python payload，共 75 行；
- 两个模块均不超过 400 行常态门，没有把 fixture 职责堆进 `release.py` 或锁内核；
- fixture 复用冻结的 `runtime_mount_contract`、candidate label 和真实锁 API，不复制业务口径；
- 业务锁实现、Compose、release、scheduler、模型、策略、Web 和账本 schema 均未修改。

关键 SHA-256：

- 最终工程代码快照：`8009eeb50c7d35f5c9a1762dc92ee36c112db75e4ff67b94f6096bee381d7b70`
- 编排器：`30027583f072dcd7c2572da0c8c1865c5ad7660ff216a6e4aebf8fde9aad9e61`
- 固定 payload：`522b214f9649daf283a2a98b6c87b0202cc8f89c8caa0de24b7f9811b939c1c3`
- 冻结 config：`768f17cfdaa1a7210d54cab02e0466733bf718b8a07346ced456520bbdb28d42`
- 协议文档：`834286887ebc265322416e3642b3e1b4dd587b9d5b3456fb22beb25ad641cd88`

## 4. 验证

- R2C 编排专项：11 PASS；
- 锁、timeline、release、隔离构建与构建身份联合专项：92 PASS；
- 架构门：13 PASS；
- 全仓：1,904 PASS，17 条均为既有第三方/兼容性 warning；
- Ruff、compileall、pip check、diff-check、敏感信息和受控账本门均通过。

离线测试覆盖：协议非执行状态、10 项清单自一致、身份字段对抗、scope 已存在拒绝、claim 先于首个
容器、失败证据保留、只允许冻结安全参数和合成挂载、readonly 语法，以及新增模块行数预算。

## 5. 生产与停止点

本节点 Docker build、fixture suite、volume 创建/删除、promote、restart、真实业务读取/运行、真实
ledger 写入、网络和密钥读取均为 0。生产 scheduler 保持原镜像和容器健康运行。

下一步只能在本提交推送后复算最终 `HEAD`，并生成绑定最终 HEAD、上述代码快照、候选标签和唯一
scope SHA-256 的授权句。用户精确批准前不得调用 build 或 fixture；即使 R2C 将来全绿，R2D 生产提升
仍须另行授权。
