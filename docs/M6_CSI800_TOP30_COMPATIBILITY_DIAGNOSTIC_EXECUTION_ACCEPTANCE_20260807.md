# M6-3C-R1 Top30 兼容诊断运行验收

- 调用时间：2026-08-07 15:15:16（UTC+8）
- 机器阶段：`BLOCKED_PRE_CONTAINER`
- 诊断分类：`NOT_EVALUATED`
- 策略有效性：`NOT_EVALUATED_FOR_PRODUCTION`
- 生产授权：`none`

## 1. 结果

用户逐字批准动作 `M6_TOP30_COMPATIBILITY_DIAGNOSTIC_MATRIX_ONCE`并绑定 scope
`cad1928cfc882f259fe9cfc5aeb753d69a03fcfe769b6a860eed4eec71a1fc23`后，主控调用了一次冻结的
original 入口 `make docker-m6-top30-diagnostic-original`。Docker 在创建一次性容器时返回：

`invalid mount path: 'mode=1777' mount path must be absolute`

入口退出码为 2。容器没有进入 runner，原执行器双回放没有开始；按冻结停止线，同 scope 不重跑，
current runner 和独立 auditor 均未启动。

## 2. 已证实根因

`compose.m6-top30-diagnostic.yaml`用未加引号的 flow-style YAML 列表声明 tmpfs，例如：

`tmpfs: [/tmp:rw,noexec,nosuid,size=1g,mode=1777]`

本机 Docker Compose v5.3.0 的 `config --format json` 将它确定性展开为五个列表项：
`/tmp:rw`、`noexec`、`nosuid`、`size=1g`、`mode=1777`。Docker daemon 因而把`mode=1777`当作挂载
路径并在容器创建前拒绝。original/current 的 1GB 声明和 auditor 的 512MB 声明具有同一结构问题。

这是一项 release 编排合同错误，不是 Qlib、原/新执行器、Top30 日报或运行内确定性的诊断结果。
六类冻结分类均未被评价。

## 3. 尝试、数据与停止线

- original 编排入口调用：1 次；容器创建失败；同 scope 永久不得重跑；
- current 编排入口、独立 audit：0 次；
- original/current/audit 三个专属目录：合计 0 文件；
- Top30 诊断回测：0/6；Top20 读取与回测：0；
- Qlib、封存预测/日报、原 M6-3C 失败效果语义读取：0；
- 模型拟合、新预测、研究尝试、实验账本写入、外网、前瞻、模拟仓和生产写入：均为 0；
- approval SHA-256：`62b794739ce3cf9336b46da85c1f97d2586b2fbedc8ce51243c5bfc4da5df570`，
  runner 未启动，因此文件内 `consumed=false`，但主控编排调用已发生，不能把它当成可重试许可。

## 4. 隔离与生产

失败后没有 M6 Top30 一次性容器残留。scheduler 仍为原容器
`183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`、原镜像
`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`，状态`healthy`、重启次数 0；
未被修改或重启。7 个 scheduler 自然账本改动继续保留且不纳入本次提交。

## 5. 下一合法节点

如继续，只能另立 `M6-3C-R2` 结果盲编排恢复：将三项 tmpfs 声明改为不会被 YAML 拆分的单一挂载
字符串，先用无真实数据 fixture 证明 Compose 展开和非 root/断网运行门，再重新构建正式镜像、生成
绑定新 Git/Compose/镜像身份的完整 scope，并获得用户新的精确批准。

恢复不得改变原三路矩阵、IEEE-754 比较、分类、参数、数据或尝试口径；不得复用本 scope、直接手工
运行容器、删除失败历史或借机读取 Top20。新 scope 获批前，M6-3C 继续保持`BLOCKED_PRE_EFFECT`。
