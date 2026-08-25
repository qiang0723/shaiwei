# R2-1R0L-B-R2B 统一跨进程锁工程验收

- 验收日期：2026-08-25（UTC+8）
- 合同：`r2-1r0l-b-r2b-unified-lock-engineering-v1`
- 协议先行提交：`d7a3932`
- 终态：`GO_ENGINEERING_COMPLETE / R2C_NOT_AUTHORIZED`
- 生产授权：无

## 1. 裁决

ADR-0009 的统一逻辑锁已完成结果盲工程：timeline、daily、shadow、paper 和 canonical ledger 不再直接
依赖业务 bind mount 目标文件的 `flock`，而是共同调用 storage 层的稳定资源锁。线程层先串行，同一
逻辑资源随后在配置的 lock root 上取得 OS advisory lock；Docker authority 缺失、路径/挂载错误、
未知资源、逆序或递归锁均失败关闭。

本节点只取得工程 GO。本机 synthetic 进程锁通过不等于 Docker Desktop named volume 已经通过；
没有构建候选、没有运行 R2C 双容器/SIGKILL fixture，也没有提升或重启生产。

## 2. 实现边界

新增三个职责分离模块：

- `storage/lock_resources.py`：稳定逻辑资源、动态 timeline/ledger 身份和锁等级；
- `storage/interprocess_lock.py`：进程内 mutex、lock-root authority、锁文件身份、SH/EX/NB 与释放；
- `storage/runtime_mount_contract.py`：release 的版本化 bind/named-volume 挂载合同。

旧 `pipeline/scheduler_timeline_lock.py` 已删除，timeline 的线程职责并入统一后端。迁移后直接调用
`fcntl.flock` 的生产关键模块只有统一后端；自发现 inventory 另保留三个未激活迁移的研究历史入口，
与冻结协议一致。

Compose 增加 `runtime-locks`，稳定 volume name 为 `shaiwei_runtime_locks_v1`，容器路径为
`/run/shaiwei-locks`。scheduler 与常用开发服务共享它；业务 `data/ledger/logs` 仍是本地项目 bind
mount。`.runtime-locks/` 只作为宿主 synthetic/直接开发回退目录且被 Git/Docker build context 忽略。

## 3. 发布兼容

新 scheduler 镜像必须带 `io.shaiwei.lock_authority=docker-named-volume-v1` 标签；带标签镜像的 release
门只接受三个既有 bind mount 加精确 named volume。旧镜像没有该标签，在迁移窗口允许原三挂载，或
重建后带额外 lock volume；这使当前健康生产仍可观测，也使未来 R2B 候选不能绕过锁卷。

只读实机核验当前生产仍为：

- 容器 `183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`；
- 镜像 `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`；
- `lock_authority=legacy-bind-flock-v0`；
- 只读根、原 `data/ledger/logs` 三挂载，运行 healthy，未重启。

## 4. 验证

- 全仓：`1,893 passed`；17 条均为既有第三方/类型转换 warning；
- 架构门：13 PASS；
- 新锁专项覆盖线程 no-op-flock、非阻塞、SH/EX、身份碰撞、生产 mount、顺序/递归、本机 8 独立
  进程 ledger 追加、幂等冲突和 `flock` 自发现；
- release 覆盖旧三挂载兼容、新四挂载强制、错 type/name/RW 拒绝及新镜像 label；
- Ruff、compileall、pip check、diff-check、Compose YAML 结构和敏感信息扫描均通过；
- 工程代码快照：`626cacdf48c96ac7a127353bf98ebe9ef3e335d4a07641d01bdb1e245704d4cb`。

关键代码 SHA-256：

- unified lock：`ef08a436f0563d9775f2a6d4a58324defaeaa9d9b8aa73c46f5be0bc65e7d5c2`
- resource registry：`7fdab35387048ef197733d76d92acd53a0bae3c782f4e6e74eed18e21ca4dffb`
- runtime mount contract：`61787c96f2412800f0bffa7be215ef311cd96d0355114fe90a9913a3dc2f5670`
- 冻结协议：`0758aa9a697c2373d0a60f7f00709ad00adf9d6631988510432662bdb0cc8e70`

新生产模块分别为 205/85/56 行；`release.py` 经职责抽离后为 583 行，未突破 600 行硬门；既有热点
paper cycle 从 670 缩至 664 行，没有新增结构例外。

## 5. 未授权与下一节点

本节点没有读取 `.env`/secret、业务数据或策略结果，没有调用外网、模型、回测、DeepSeek 或 Web，
没有写真实 ledger、补造 timeline、构建 Docker 镜像、创建真实 fixture scope、promote 或 restart。
用户自然账本增量和三份校准文档均未纳入本提交。

下一合法节点是 R2C：先绑定终版已推送 HEAD、代码快照、候选标签与唯一 fixture scope，再申请恰好
一次候选构建及一次断网真实 named-volume fixture。fixture 至少覆盖 4 进程 timeline、两个容器
EX/SH/NB、SIGKILL 释放、8 进程 ledger、错/missing/readonly mount；任一失败均不得 promote 或进入
R2-1R1。
