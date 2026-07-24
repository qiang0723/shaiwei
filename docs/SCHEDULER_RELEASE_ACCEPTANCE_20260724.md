# Scheduler 发布快照隔离验收（2026-07-24，UTC+8）

## 1. 当前裁决

状态：**PASS**。

不可变镜像、开发隔离、挂载白名单、双身份验证、跨快照启动门、回滚状态机和 2026-07-24 真实
交易日周期全部通过。首次真实运行发现“镜像无 `.git`、哨兵仍调用 Git”的兼容故障；失败证据完整
保留，按最小修复恢复后，current/previous 均为已修复镜像，完整闭环和幂等复跑 PASS。

## 2. 迁移前根因证据

迁移前容器：

- image ID：`cb7686862919745c4ef1e09499cae884503aa182dcf1f9d9bd185c2c9c1c2577`；
- 唯一挂载为宿主项目根 → `/workspace`；
- `RW=true`；
- 迁移前健康状态为 healthy。

该证据确认生产 scheduler 的运行代码直接来自开发工作树，符合
`docs/INCIDENT_20260723_CODE_SNAPSHOT_MISMATCH.md` 的结构性根因。

## 3. 最终不可变发布快照

| 角色 | Git 提交 | 代码快照 | image ID |
|---|---|---|---|
| previous D | `2ea5343` | `2b6816c459310e83e9c9b9de412a7d507d10d8b69e402ce400d1561e6ded7577` | `a36452873110facef465369cc9b42d90bbafbff8a5ad584124a4685bb5646b31` |
| current E | `ecda815` | `eb8e752132ac1fbe6a9557d26b4c7a65df36f6169d617b6e1e10db88d46b7fbd` | `de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261` |

两个镜像均通过：干净 Git 工作树、镜像 OCI 标签、镜像内发布清单逐文件重算和镜像内嵌 Git 提交
身份四者一致。D/E 均不包含或挂载 `.git`；实现和回归测试提交均已推送 `origin/main`。

## 4. 开发工作树隔离探针

在宿主 `src/shaiwei/` 临时加入受控探针后：

- 宿主动态代码快照由 `817ebb...` 变为
  `05d26023824b47eaa53a0968d1fa4b1c77d291115070e3201bb2e431aa8fdd7a`；
- 已构建镜像内不存在该探针；
- 镜像内重算快照继续为 `817ebb...`。

探针随后删除，宿主快照精确恢复。这直接证明开发文件变化不能进入既有生产镜像，而非仅凭 Compose
文本作推断。

## 5. 发布与回滚证据

未启动生产服务时，先以 A/B、B/C 完成机制演练；发现 C 的运行身份兼容故障并修复后，又以最终
D/E 完成：

1. promote D；
2. promote E；
3. rollback D；
4. re-promote E。

`.release/scheduler_state.json` 最终 current/previous 与上表一致；
`logs/releases/scheduler_releases.jsonl` 当前 18 条记录，哈希链 tip 为
`a17053888070010ec009cfea94acbb1199cda51952cd5255b4d2e9dab5400db2`，完整校验 PASS。
发布工具没有删除失败候选或覆盖运行 ledger。

## 6. 最终容器静态契约

最终 current E 容器已启动并完成真实周期，Docker 实际状态为 healthy：

- image ID 精确为 current E 的 `de87ec74...a0261`；
- 运行时 Git 提交精确为 `ecda815409fae323eee8254d13e9d19f9fdeaf24`；
- root filesystem `readonly=true`；
- capability drop：`ALL`；
- security option：`no-new-privileges:true`；
- 挂载只有 `/workspace/data`、`/workspace/ledger`、`/workspace/logs`；
- 没有 `/workspace` 整仓挂载，没有 Docker socket；
- 无 Docker socket、整仓或 `.git` 挂载。

最终镜像在同一挂载白名单下的只读预检：

- 发布快照重算：`eb8e7521...b7fbd`；
- 对 `/workspace/src` 的写入被只读根文件系统拒绝；
- 窗口前本地日计划：watermark/eligible target 均为 `20260723`，缺口 0；
- 窗口前模拟仓独立重放：5 个账户日、174 个事件、30 个订单、22 个成交，PASS；
- 窗口后启动门识别 `20260724` 为新可用交易日才允许跨快照启动。

## 7. 跨快照启动安全门

current 镜像在启动生产容器前比较最新 PASS 模拟仓的交易日/代码快照与当前发布快照：

- 同快照重启允许直接恢复；
- 跨快照启动必须已有或计划处理一个晚于最新模拟仓日的新交易日；
- 无更新交易日时 fail closed，不创建“旧 FORWARD 产物 + 新代码身份”的必然失配。

16:14 的真实项目状态为最新模拟仓 `20260723`、日增量缺口 0；以 current C 试算启动门禁得到预期
`REJECT`。这证明数据窗口前不会为追求“容器在线”而提前制造新一轮快照失配。测试同时覆盖
初始发布、同快照重启、跨快照无新日拒绝、计划新交易日放行和新日 daily PASS 后故障恢复。

20:05 日计划出现 `missing_trade_dates=[20260724]` 后，门禁以
`CROSS_SNAPSHOT_WITH_NEW_DATA/PASS` 放行；修复后的 E 再启动时使用已完成的 `20260724` daily PASS
作为恢复凭据，同样 PASS。两次均未绕过门禁。

## 8. 真实故障与恢复

首次 current C 真实运行中，daily 和次日对账 PASS，影子在哨兵末端以 `ForwardQlibError` 失败。
同镜像独立复跑证明根因为不可变镜像没有 `.git`，旧 `git_head()` 仍执行
`git rev-parse HEAD` 并退出 128。容器没有 OOM，数据哨兵未得出规则 FAIL。

修复把干净提交号同时绑定进 OCI revision 标签和只读运行元数据，发布工具在构建镜像、候选镜像与
运行容器三处复核；没有恢复 `.git` 挂载。失败运行、飞书告警、修复和恢复均保留。完整 RCA 见
`docs/INCIDENT_20260724_RELEASE_GIT_IDENTITY.md`。

## 9. 质量门

- 核心实现后全仓 189 项测试 PASS；
- 最终双镜像回滚契约加入后全仓 190 项测试 PASS；
- 跨快照启动门禁加入后全仓 193 项测试 PASS；
- 发布 Git 身份修复后全仓 195 项测试 PASS；
- 镜像标签/运行时双身份回归加入后全仓 196 项测试 PASS；
- Ruff、compileall、`pip check`、Compose 解析和 `git diff --check` PASS；
- 受控提交不含 `.env`、Token、Webhook、签名、绝对本机路径、数据或运行日志。

## 10. 真实运行证据

2026-07-24 最终恢复周期取得：

1. `20260724` daily PASS：5 个市场批次、15,613 行；当日共 8 个新原始批次、21,148 行，逐文件
   行数与 SHA-256 重算一致，`.BJ=0`；
2. `20260723 → 20260724` 对账 PASS：30 个目标、0 交易腿、平均绝对开盘偏差 1.8210%；
3. current E 哨兵：S1-S9 PASS、S10 NOT_APPLICABLE，数据/代码/Git 身份匹配；
4. `20260724` 信号 PASS：`on_time=true`、`rebalance_due=false`，信号绑定 current E；
5. 模拟仓新增第 2 个自然 FORWARD：账户事件 198、订单 30、成交 22，净资产 471,824.90 元；
6. 独立重放 PASS，机器 acceptance PASS，`.BJ` 事件 0；
7. 飞书日增量、对账、信号、模拟仓开始/完成最终均 PASS；模拟仓完成首次网络超时，第 2 次自动
   恢复；
8. 受控完整重复周期返回 shadow/paper NOOP，7 类 ledger、通知、哨兵、信号、对账、模拟仓产物和
   qlib 指针的行数/哈希不变。可覆盖汇总 `forward_report.json` 仅刷新生成时间，业务统计不变；
9. 运行 operator 均为 `docker-scheduler`，零人工修数；scheduler 最终 healthy。

据此生产/开发发布快照隔离门禁 PASS，可按 ROADMAP 另立 P2；本裁决不自动授权 P2、Web 后端或
模型变更。
