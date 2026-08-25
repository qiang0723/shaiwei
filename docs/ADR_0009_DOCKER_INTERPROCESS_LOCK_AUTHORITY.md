# ADR-0009 · Docker 生产写入使用独立 named-volume 锁权威

- 日期：2026-08-25（UTC+8）
- 状态：`ACCEPTED_FOR_ENGINEERING`
- 关联节点：`R2-1R0L-B-R2A`

## 1. 问题

R2-1R0L-B 与 R1B 的真实 Docker fixture 已连续证明：在当前 macOS Docker Desktop 的宿主目录
bind mount 上，只依赖目标文件的 `fcntl.flock` 不能满足 timeline 跨进程串行合同。R1 增加的进程内
互斥修复了线程竞争，但 4 个独立 Python 进程仍产生两个零前驱首事件。

同一假设还存在于 daily、paper、shadow、canonical ledger 和少量研究写路径。当前没有证据表明这些
账本已经损坏；但已经被真实 fixture 否证的公共锁假设不能继续作为生产权威，也不能只为 timeline
再加一层局部补丁。

## 2. 事实边界

- 当前 scheduler 只有一个运行中容器；审计时主进程为一个长期 Python scheduler，shadow 与两个
  paper 账户由主进程按顺序启动短生命周期子进程。
- scheduler 的 `data/`、`ledger/`、`logs/` 都是 macOS 项目目录 bind mount。容器内 `/proc/mounts`
  将三者显示为同一 `fakeowner` 文件共享挂载；这与失败 fixture 的存储边界一致。
- 正常主循环目前串行，降低了日常冲突概率；但 daily/shadow/paper 锁本来就用于防重复 scheduler、
  手工 `--once` 或恢复任务并发，canonical ledger 也明确承担多入口追加保护。因此“通常只有一个
  writer”不能替代机器锁。
- Docker 官方说明 Docker Desktop 的 daemon 位于 Linux VM，macOS 路径通过文件共享机制提供给
  容器；Docker volume 则由 daemon 管理，并可显式供多个服务共享。官方资料没有承诺任意桌面文件
  共享后端的 `flock` 语义，所以最终权威必须是本机 fixture，而不是文档推断。

官方依据：

- [Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)
- [Docker storage](https://docs.docker.com/engine/storage/)
- [Docker Compose volumes](https://docs.docker.com/reference/compose-file/volumes/)

## 3. 候选方案

### A. bind mount 上继续叠加进程内互斥（拒绝）

改动最小，也已经证明能覆盖线程；但不能覆盖独立 Python 进程、重复容器或未来 worker。R1B 已直接
否决其作为跨进程权威，继续叠加只会形成更多局部锁实现。

### B. bind mount 上使用原子目录锁（不选为主方案）

`mkdir` 的原子命名操作可避开 advisory file-lock 的具体语义，但进程异常退出会留下锁目录，必须再
引入 owner、lease、时钟、过期接管与误删防护。它可作为 named volume 不可用时的显式恢复候选，
不能在本轮成为默认权威。

### C. 专用 Docker named volume + 统一逻辑资源锁（选择）

新增只保存锁 inode 的 Docker named volume，并挂到所有获准写生产持久化状态的容器同一路径。统一
锁后端先取得进程内逻辑资源互斥，再在 named volume 的对应文件上取得 `flock`；业务数据、ledger、
logs 仍写原 bind mount，完全不迁移到 volume。

优点是：锁域位于 Docker daemon 管理的存储中、可被多个容器共享、进程退出会由内核释放 advisory
lock，而且不会把业务证据藏进 Docker volume。代价是新增一个生产挂载、统一注册表和发布验收面；
它是否在本机提供所需语义仍须一次真实 fixture 证明。

## 4. 统一锁合同

### 4.1 资源身份

锁必须使用稳定的逻辑资源 ID，而不是宿主绝对路径或容器路径。首批受控资源为：

- `runtime:daily-cycle`
- `runtime:shadow-cycle`
- `runtime:paper-cycle`（首版保持当前所有账户共用一个周期锁）
- `runtime:scheduler-timeline:<YYYYMMDD>`
- `ledger:<project-relative-csv-path>`

文件名由 schema 版本与完整 resource ID 的 SHA-256 确定，可带短的人类可读前缀；冲突校验必须比较
完整 resource ID。生产不得依赖 host/container 路径恰好一致。

### 4.2 锁后端

- 同一 API 同时承担进程内互斥与跨进程/跨容器 `flock`，禁止各模块继续自建新锁。
- writer 使用 exclusive；timeline verifier 使用 shared。为避免同进程线程绕过 shared/exclusive，
  进程内层对同一资源至少实行保守串行化。
- 生产 lock root 缺失、不是预期挂载、不可写、权限异常或资源未登记时 fail closed；不得退回业务
  bind mount，也不得静默降级成只用线程锁。
- 锁文件只是协调设施，不是业务证据，不进入 Git、备份或研究裁决；进程退出后文件可保留，权威是
  内核持锁状态而不是文件存在。
- 初版保持既有锁的业务结果语义。daily/shadow 的非阻塞冲突继续映射现有异常；paper 的等待上限与
  错误类型须在 R2B 协议中结果盲冻结，不能在实现时临时决定。

### 4.3 写入权威与混合运行禁令

只有挂载同一个 production lock volume 的容器可以写生产 `data/ledger/logs`。宿主 Python、未挂锁
volume 的开发容器和一次性研究容器，在 scheduler 运行时不得写这些生产路径。发布门必须检查所有
获准 writer 的 mount 与 lock schema；仅靠操作约定不算验收。

研究专用、已关闭或只写隔离输出根的锁暂不强制迁移，但须进入 inventory 并标明 authority。任何
研究入口若要重新写共享 canonical ledger，必须先接入统一后端，不能援引历史例外。

## 5. 锁顺序与失败恢复

首批调用关系保持：`cycle lock -> canonical ledger lock`。timeline 事件写入在进入/退出业务阶段时形成
短临界区，不在持有 timeline lock 时等待 daily/paper/shadow；单次 ledger append 不再嵌套第二个
ledger lock。统一 API 应拒绝未登记的逆序嵌套，测试须覆盖死锁风险。

进程崩溃、SIGKILL 或容器停止后，文件描述符关闭即释放锁；不得用删除锁文件释放。Compose recreate
当前应先停止旧容器再启动新容器，但发布验收仍须以两个容器同时竞争同一资源证明共享锁域，防止未来
发布方式变化或人工重复启动。

若 named volume 丢失或 mount 身份不符，scheduler 启动失败关闭；因为 volume 不含业务状态，可以在
scheduler 完全停止后重建，再通过完整 fixture 和发布门恢复。回滚镜像若不认识新锁合同，不得与已
迁移 writer 同时运行；首次生产提升必须把 current/previous 兼容性写进 release 状态。

## 6. 分阶段施工与验收

### R2B：工程，不构建生产候选

1. 建统一锁模块、resource registry 与自发现门；模块保持单一职责且不超过 400 行。
2. 迁移 timeline writer/verifier、daily、paper、shadow 和 `ledger.py`；删除或封存重复锁实现。
3. Compose 增加唯一 lock volume；release mount allowlist、镜像身份和回滚合同同步更新。
4. 只运行 synthetic/单元/架构测试，不读取真实业务结果、不写生产 ledger、不重启 scheduler。

### R2C：单独授权的真实 Docker fixture

绑定已推送 HEAD、代码快照和唯一候选镜像后，只运行一次断网 fixture，至少证明：

- 8 线程在 `flock` 被替换为 no-op 时仍串行；
- 4 个独立 Python 进程形成一条完整 timeline 链；
- 两个容器共享同一 named volume 时 exclusive/shared 与非阻塞冲突正确；
- writer 被 SIGKILL 后新进程可取得锁，且不能靠删除文件接管；
- ledger 并发追加无丢行、重复键异内容 fail closed；
- 缺 mount、错 volume、只读 volume、未知资源和锁顺序错误全部 fail closed。

任一项失败即 `NO_GO_PROMOTION`，不删除测试、不改门槛、不在同 scope 重跑。

### R2D：生产提升

只有 R2C 全通过，才另行申请 promote/restart。提升避开数据窗口，先证明 previous 回滚兼容，再完成
首个自然交易日的 scheduler、timeline、daily、shadow、paper、通知与幂等验收。稳定前不启动
R2-1R1 计数。

## 7. 不授权事项

本 ADR 不授权源码、Compose 或配置修改，不授权新镜像、fixture、promote、restart、真实业务运行、
历史补写、密钥读取、Web、模型、回测、DeepSeek、模拟仓变更或生产账本写入。它只冻结 R2B 的工程
方向；实际施工仍须下一节点单独执行。
