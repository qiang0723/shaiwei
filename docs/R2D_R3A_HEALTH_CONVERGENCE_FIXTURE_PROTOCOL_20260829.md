# R2D-R3A 健康状态收敛真实 Fixture 协议

## 1. 目标

R2D-R2 已证明候选与旧生产的底层发布动作均能成功，但发布层在 Docker health 元数据仍为
`starting` 时提前写入 `START_PASS`，上层二次观察由此误判并回滚。R2D-R3 已补齐
“Docker health + 容器内 healthcheck”双门。

本节点只建设并冻结一次真实 Docker 彩排：证明修复后的同一共享发布合同能在隔离 Compose project
中观察 `starting → healthy`，且守卫成功路径不会调用 rollback。它不评价数据、模型或策略。

## 2. 结果前冻结的真实路径

唯一 fixture 必须：

1. 基于终版 `HEAD=origin/main` 与代码快照恰好构建一个内容寻址 scheduler 候选；
2. 使用 `compose.r2d-r3a-health-fixture.yaml` 的独立 project，不复用生产 service/container；
3. 使用候选镜像、生产相同的健康命令、启动健康节拍、只读根、安全能力和四个挂载目标；
4. data/ledger/logs 只挂 scope 专属空目录；锁只复用既有
   `shaiwei_runtime_locks_v1`，不得创建、删除或清空该卷；
5. 主进程仅延迟写入合成健康文件并等待，不运行 scheduler 业务循环；
6. `--env-file /dev/null`、`network_mode: none`、`--pull never`，不得读取项目 `.env`、
   密钥、行情、真实账本或访问外网；
7. claim 必须先于 Docker 命令落盘，同 scope 成功或失败均不得重跑。

## 3. 六项机器门

- scope 冻结的生产 release state 与 audit 哈希必须与执行前真身精确一致；
- 候选镜像标签与运行时 Git/快照/锁 authority 精确一致；
- 真实 Docker health 至少观察一次 `starting`；
- 共享 `release._wait_scheduler_contract` 在 60 秒内收敛到 `healthy`；
- 共享守卫 `_execute_action(..., RESUME_START)` 成功且 rollback 调用数为 0；
- 生产 `.release/scheduler_state.json` 与 release audit 前后哈希完全不变。

任一项失败只保留 claim/report/tree/receipt 与错误类型，不得放宽门、复用 scope 或转为生产操作。

## 4. 权限与停止点

当前只授权源码、测试、Compose fixture、配置和文档施工。没有授权 Docker build、fixture 实跑、
镜像拉取、promote、start、restart、生产业务、外网、密钥、Web、模型或策略改动。

终版提交推送后，才根据最终 HEAD、代码快照、候选标签、组件哈希和输出根生成独立 release scope。
用户逐字批准前必须停止。fixture 全绿也只允许另立新的自然交易日生产启动 scope，不得直接切换生产。
