# M6-2 中证800模型归因真实 release 准备验收

日期：2026-08-06（UTC+8）

## 1. 裁决

`m6-csi800-model-attribution-real-release-v1` 已达到
**`REAL_EFFECT_RELEASE_READY_NOT_EXECUTION_APPROVAL`**，并停在真实效果读取之前。

| 状态 | 结论 |
|---|---|
| 结果前协议、真实 runner、内部 replay 与独立 auditor | PASS |
| 不可变镜像、代码快照与精确 scope | PASS |
| 断网合成 runner / 独立 auditor | PASS / PASS |
| 真实 Qlib 特征或价格读取 | 0 |
| 真实标签或效果读取 | 0 |
| 真实模型拟合 / 预测 / 回测 | 0 / 0 / 0 |
| 正式效果产物 / 实验账本写入 | 0 / 0 |
| 策略有效性 | `NOT_EVALUATED` |
| 生产授权 | `none` |

本节点只证明冻结的 M6-0 比较可以由一个内容寻址、断网、一次性的 runner 完成内部两遍，并由无
Qlib 挂载的第二进程独立复核。合成夹具的 `MODEL_STRUCTURE_SUPPORTED` 只是预演分支，不是中证800
真实效果结论，也不授权替换当前生产基线。

## 2. 结果前冻结与提交顺序

- M6-0 研究协议提交：`262d941baa97c4aae4ddf57ed2950529d307dca3`；
- M6-1 工程协议提交：`64fe39d8c1ab183bd367f5e6866f8ea3735ae10f`；
- M6-2 真实 release 协议提交：`c8667eb`，先于本轮实现推送；
- M6-2 主实现提交：`27922c0f071453d636d3744aa33b741fef5f3e6d`；
- release manifest CLI 最小修复提交：`35fd1d58c7db00a3d97d98ca79699b6f8911789c`，先于终版镜像推送。

冻结身份：

| 证据 | SHA-256 |
|---|---|
| M6-0 结果协议 | `6c170d991df1ef75f18208837301b545fe50518c028a65c814d425fc36d7a22a` |
| M6-1 工程 manifest | `546216de432336e96dd1ea62428c19f57c909469885a6665eb8f657df246809a` |
| M6-2 release config | `3d0f76fe0ede71cb3c4b8a7a280767e82b989dd3d1c9e56de7983ef87f0a1b7c` |
| M6-2 release 协议文档 | `7790aa36b1b0e761185e8988cbdf61768fed29985f0a04d5898aeba0adabc483` |

协议冻结的唯一批准动作是
`M6_REAL_EFFECT_ONCE_WITH_INTERNAL_REPLAY_AND_INDEPENDENT_AUDIT`。仅说“继续”、旧节点授权或批准某个
缩写 SHA 均不能启动真实运行。

## 3. 首个临时镜像及失败关闭

首个实现镜像 `sha256:4e45df7fd5502e8a21d29dff4238ffa9ee38051f3724a81f9d45990737992a65`
已完成断网合成 runner/auditor，但生成 scope 的 CLI 参数名与 `build()` 绑定名不一致，程序在任何
scope 写入前抛出 `TypeError`。因此该镜像永久标记为 provisional：

- 正式 scope、approval、效果产物和账本写入均为 0；
- 真实 Qlib/标签/效果读取、拟合、预测和回测均为 0；
- 替代尝试未消费；
- 不允许以该镜像生成或执行正式 release。

修复只统一 CLI 参数绑定并增加回归覆盖，不修改三臂、窗口、模型、标签、组合、成本、统计、门槛或
权限。修复先提交推送，再构建下述终版镜像。

## 4. 终版镜像与精确 scope

终版镜像：

| 字段 | 值 |
|---|---|
| reference | `shaiwei:m6-model-attribution-release-v1` |
| image ID | `sha256:3c40c9c74bbbda926433f2d49cd78128c665cbb84e071ab3d44d187ecc2cd40e` |
| platform | `linux/arm64` |
| embedded Git commit | `35fd1d58c7db00a3d97d98ca79699b6f8911789c` |
| embedded code snapshot | `71a0cc5f704a0ebbc887d76a10382280e4a5945f387292ac976c4fd27ec1a239` |
| release manifest SHA | `e75e5d556d3828cc63531a98f0901741a5792f6afd3c153776c96ce632b967d5` |
| release manifest files | 501 |

精确 scope 真身为 `config/m6_csi800_model_attribution_release_scope_v1.json`：

- scope SHA：`9b609f0764240ff3930a4aeaaf16cef9deb82579d2a5875f1be9e8c4ffb0b139`；
- scope 文档 SHA：`3550046f8cb34a6b4ee33ae0655fbec377928d93a043b4c5e424caa98447779d`；
- Qlib manifest/tree：`62cae2f4...05a9` / `0532f6cd...1778`，54,464 个文件；
- 交易日历：2,557 行，SHA `80ddefd8...8bdb`；
- `release_ready=true`，其余执行、真实读取、效果写入、实验账本、外网、前瞻、模拟仓和生产权限均
  为 `false` 或 `none`。

宿主 loader 先验证 scope 自哈希与冻结合同；终版镜像随后以断网、只读根、非 root 且仅挂载 scope
的方式复核，返回完全相同的 Git commit 和代码快照。重新哈希的 scope 也不能改变镜像、命令、挂载、
资源或授权字段；任何漂移均失败关闭。

## 5. runner、两遍与独立 auditor

获批后的唯一 runner 调用内部串行执行 `first_pass` 与 `replay`。每遍独立重建 handler、拟合固定
LightGBM 与 Ridge、形成固定融合、六窗回测和 2026H1 stale-model 压力诊断；模型、预测、标签、日表、
Top30、持仓/交易和 summary 全部 write-once，两遍全量内容必须一致。

独立 auditor 是第二个进程，不挂载 Qlib，也不导入主指标、主推断、执行器或产物写入器；它只从
write-once Parquet/JSON/模型产物重算成员日、RankIC、相关性、成本、主动收益、换手、净策略回撤、
NW(10)、Holm、Top30 和唯一终态，并核对 release/approval/两遍哈希。

最终镜像的纯合成闭环结果：

| 证据 | 值 |
|---|---|
| runner report SHA | `7f4890719a555df7c9c1c81602d6054706232d9ba2db4a04a5c94dffc6e73f92` |
| auditor report SHA | `becf2c5ab24948df6eb8df9567301b1c977e91f07e5efcd1b06dbe3bba4ac319` |
| independent audit | `PASS` |
| real_data_read | `false` |

另有一字节篡改对抗 fixture，独立 auditor 会失败关闭。合成夹具没有宿主挂载、网络或真实证券代码，
其分支结论不得进入实验账本或 Web 权威结果。

## 6. Docker 与生产隔离

`compose.m6-attribution.yaml` 只定义两个短命服务：

- runner：6 CPU、12 GiB、256 pids；Qlib/scope/approval 只读，effect 目录唯一可写；
- auditor：2 CPU、4 GiB、256 pids；无 Qlib，仅 effect 只读、audit 目录可写。

二者均 `network_mode=none`、非 root、只读根、`cap_drop=ALL`、no-new-privileges，无 `.env`、Docker
socket、整仓、生产账本和端口。M6 不修改或重启 scheduler，也不能在 scheduler 保护窗口内启动。

施工前后 scheduler 均为容器
`183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`、镜像
`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`、创建时间
`2026-08-03T09:39:34.800579793Z`，状态 `healthy`；身份未变。

## 7. 验证与仓库边界

在生成最终 scope 前，交付已通过：

- 全仓 `857 passed`；另有既有测试正则转义 `SyntaxWarning` 和 Starlette 弃用 warning 各 1 条；
- M6 effect 专项与 CLI 回归 PASS；架构门 `6 passed`；
- Ruff、compileall、`pip check`、Compose config 和 `git diff --check` PASS；
- 最终镜像断网合成 runner/auditor PASS，镜像内 scope/发布身份复核 PASS。

scope 生成后仍须复跑合同测试、全仓测试、架构门和静态门；终版提交只包含 scope、本文、STATE 和
ROADMAP，不包含项目忽略目录内的镜像清单、合成输出、真实/派生业务数据、日志、`.env`、模型、预测、
交易、持仓或其他凭据。每日 scheduler 自然追加的七个 ledger 文件不属于本提交。

## 8. 停止线

M6-2 release 准备到此完成。用户对完整 scope SHA 明确批准前，不创建 approval 文件，不启动 runner
或 auditor，不读取真实 Qlib 特征、价格、标签或效果，不拟合、预测、回测、写正式效果产物或实验
账本。真实运行一旦开始即消费恰好两个替代尝试；失败不得递补、换 seed、调门槛或以同一 release
重跑。真实审计完成后才形成 M6 权威效果终态；它仍不自动授权前瞻、模拟仓或生产替换。
