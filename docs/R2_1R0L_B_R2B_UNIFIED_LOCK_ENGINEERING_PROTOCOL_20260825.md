# R2-1R0L-B-R2B 统一跨进程锁工程协议

- 冻结时间：2026-08-25 10:23:37（UTC+8）
- 合同：`r2-1r0l-b-r2b-unified-lock-engineering-v1`
- 状态：`FROZEN_ENGINEERING_ONLY`
- 前序架构提交：`849aa0a1395e82dec45c3f7b3b81509552e63d0b`

## 1. 结果目标

将已被 R1B 否证的“项目 bind mount 目标文件自身 `flock`”替换为统一逻辑锁后端，使 timeline、daily、
shadow、paper 和 canonical ledger 在进入下一次 Docker 候选验收前，共用同一个可测试的线程、进程与
容器锁合同。

本节点只证明工程结构和 synthetic 行为，不证明 Docker Desktop named volume 的真实锁语义，也不
改变任何模型、策略、模拟仓结果或自然前瞻状态。

## 2. 冻结实现边界

- 新增单一职责 storage 锁模块与资源注册表；每个新生产模块不超过 400 行。
- Docker authority 固定为 `docker-named-volume-v1`，Compose key 为 `runtime-locks`，稳定 volume name
  为 `shaiwei_runtime_locks_v1`，容器路径为 `/run/shaiwei-locks`。
- `data/ledger/logs` 继续是项目 bind mount，锁 volume 不保存业务证据、运行结果或密钥。
- production 与常用 development Compose 服务挂同一个 lock volume；缺 mount、错路径、未知 authority
  或不可写必须失败关闭，不能退回 bind 锁。
- 资源身份、锁等级和既有冲突语义以机器合同为准。paper 首版保持现有 blocking 行为，不在本节点
  顺带引入超时参数。
- timeline R1 的进程内互斥职责并入统一后端；迁移完成后不保留第二套活跃生产锁实现。
- 三个已识别研究 `flock` 路径只登记，不改源码、不重开研究；未来重新写共享 canonical ledger 前再
  迁移。

## 3. 测试与失败关闭

本节点允许本机临时目录上的 synthetic 线程和独立进程测试，但禁止构建 Docker 镜像或运行 R2C 的
named-volume fixture。必须覆盖资源身份、线程层、真实本机进程层、SH/EX、非阻塞、锁顺序、递归、
生产 mount 校验、ledger 并发追加和重复键异内容。

测试还须自发现生产源码的 `fcntl.flock`：迁移的六个模块不得残留直接调用；后端之外只允许机器合同
明确列出的三个研究历史入口。Compose/release 必须精确核对三个 bind mount 与一个 named volume 的
类型、来源、目标和读写属性。

任何测试失败只允许在本工程 scope 内修复源码；不得构建候选碰运气，也不得通过删除旧失败 fixture、
降低并发数或回到局部锁绕过。

## 4. 迁移、回滚与权限

R2B 完成后只提交和推送源码、测试、配置、Compose 与文档。当前生产 scheduler 继续运行旧不可变
镜像，不重启、不读取新工作树。若 R2B 工程失败，回滚是撤回未发布代码；生产无需数据迁移。

工程通过后另立 R2C，绑定精确 HEAD、代码快照、候选镜像与一次真实 fixture。R2C 必须包含多进程、
双容器、SIGKILL 释放和 ledger 并发；未全绿不得 promote。生产提升和 R2-1R1 仍须更晚的独立授权。

本节点不授权 `.env`/secret 读取、外网、业务数据或结果读取、真实 ledger 写入、历史回填、模型、
回测、DeepSeek、Web、模拟仓变更、Docker build/fixture、promote 或 restart。
