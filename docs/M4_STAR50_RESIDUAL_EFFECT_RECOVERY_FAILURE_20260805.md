# M4-1R 科创50残差因子效果恢复失败留痕（2026-08-05）

## 结论

M4-1R 恢复入口完成了首遍与内部确定性复跑，并写出了内容一致的两组 Parquet 和一个绑定正确
release 的效果报告；随后在发布账本证据时因锁文件所在父目录只读而以 `OSError` 中止。运行账本仍
为 0 行、决策账本仍为 0 行、运行 manifest 未生成，独立审计的账本条件不成立。

因此当前权威状态是：

- 研究计算产物：`SEALED_UNADJUDICATED`；
- M4-1 历史效果门：`BLOCKED_EVIDENCE_PUBLICATION`；
- 正式 G1-v1：`NOT_RUN_UNIVERSE_WINDOW_DOMAIN_MISMATCH`；
- 策略有效性：`NOT_EVALUATED_PENDING_EVIDENCE_CLOSURE`；
- 正式因子库插入：0；
- 生产授权：`none`。

本文件不读取、不摘录也不解释报告中的候选 RankIC、收益、回撤、持仓或裁决字段。不得把内部已
生成但尚未完成账本与独立审计的报告当作正式研究结论。

## 两次入口的分层

### 原入口：工程失败、零产物

原镜像在 `metrics._between` 读取一维无名 RankIC 日期索引时触发 `KeyError`。结果目录仍为空，
两本账本仍仅表头。该次永久记为
`INVALID_ENGINEERING_ATTEMPT_NO_RESEARCH_DECISION`。

### M4-1R：计算完成、证据发布失败

单点索引修复及新 release 均已先行推送。恢复镜像完成首遍和内部复跑后，机器只返回：

```json
{"error_class":"OSError","status":"FAIL"}
```

文件时序和代码路径共同确认故障位于结果报告落盘之后、账本追加之前：

1. 两遍各 5 个 Parquet 均在 `effect_report.json` 之前完成写入；
2. `effect_report.json` 已存在，运行 manifest 不存在；
3. 两本 CSV 仍为表头且哈希与运行前完全一致；
4. `append_ledgers` 的首个动作是为 CSV 同目录创建 `.csv.lock`；
5. Docker 只把两个 CSV 文件本身挂为可写，父目录 `/workspace/ledger` 仍为只读，故不能创建锁文件。

这是一项证据发布挂载合同缺陷，不是候选公式、样本、执行或门槛失败。按 M4-1R 预先冻结的二次
工程失败规则，本批立即停止，不修改挂载、不第三次调用入口、不补写账本。

## 保全证据

- 恢复协议 SHA-256：`631608276ab3ddf3ffe0ff15d27184b750c113e7295a02c80b2e66d5fc793e3f`。
- 恢复执行 release SHA-256：`4891c04516913d77e8a64071a050209f533971c467b5ea3cfd8dad4e2c39b430`。
- 纠错实现提交：`f38ad4ef1cbca9bf06d609e46f7ded5bd813d84e`。
- 代码束 SHA-256：`5109ec5b14c899b8696d02089e0e0a80f190241572f05f485cc6ea4692833c83`。
- 恢复镜像内容 ID：`sha256:28d6c295ad2c5c287cd83c1ad23b99a5b7c714b8adb88bfd6d12a61b2b16dfc5`。
- 镜像受控快照：`77e83e653c41d6fc071bc5acc950713850f7fffc47362c5d250bf008fd4b5fc4`。
- 输入快照：`dd2d058eda1aa914fcbe9f1eda86d621ec6e663f37ea7bd8d2e1e9222f5361c0`。
- 封存效果报告 SHA-256：`627f304a076c5854ab02eb78717a8e6035c3c368dab058ad7212fa7022d0656b`。
- 报告身份字段与协议、恢复 release、实现和代码束逐项一致；报告自述
  `determinism_pass=true`，但尚未完成含账本在内的独立审计。

两遍物理文件逐字节相等：

| 产物 | SHA-256 |
|---|---|
| `core_residuals.parquet` | `6d34749bf7bf8c163d84466d86a5776196e5a2ebd897f344b3f899e9a5710db4` |
| `daily_executions.parquet` | `e3c80e377dbaea7ba7deededa356d7db092f0d625e572fd6d80c04bbce79dac6` |
| `daily_rank_ic.parquet` | `6fbf008bed8961454c32223e7e17354ca416f44b8110d6f03f03b8f6ad242681` |
| `extended_features.parquet` | `a1b0f59cdfa5dcac3b255279bd050fa3ff767f73469cb4ec7524ecd96bae3452` |
| `incremental_residuals.parquet` | `243a5500c949d21bc273c083ee218a80dfbbad35d6fd997c9beb32e3d09413f8` |

运行账本和决策账本仍均为 0 数据行，SHA-256 分别保持
`c2989a612949cbdf131b8ab6a80b53d6954dea448cee990f5f3448d6b832f293` 与
`dce031439ad677b76ba3bf5e4534988cc7433509c3539b8c69da950a9401dd52`。

## 生产隔离

生产 scheduler 未重建、未重启且保持 healthy：容器
`183b8c6c...23dd3b`、镜像 `sha256:722f63de...13b76`、创建时间仍为
`2026-08-03T09:39:34.800579793Z`。M4-1R 全程断网、无密钥、无模型训练、无正式 G1、无模拟仓、
Web 或生产路径改动。

## 后续唯一合规方向

如继续，须把它作为新的 M4-1R2“证据发布闭环”目标单独复核并在操作前冻结；该目标只能：

1. 精确绑定上述已封存报告和 10 个 Parquet 的哈希；
2. 只修两本专属账本锁文件的窄写挂载合同；
3. 只走已有报告的复用分支，禁止重算特征、标签、RankIC、组合或收益；
4. 完成账本、manifest、独立审计和再次复用零新增证明；
5. 在独立审计通过前继续隐藏并不解释候选效果。

本节点不自动启动 M4-1R2，等待主控另行确认后再冻结协议。
