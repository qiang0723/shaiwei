# M5-2B release v3 断网真实 DATA_GATE 验收（失败关闭）

- 执行日期：2026-08-05（UTC+8）
- 用户批准的唯一 release scope：`49fdc6e79ee7591fb03732fc4fa08430f4049b720d0552cca49ff9e153e05830`
- 协议：`m5-dynamic-fundamental-cross-pool-data-preexecution-v1`
- case ID：`223414f4341a3edca15e5a626a3d0da642c4aa671db6d9cf67c9c870b8eb0a78`
- 终态：`STOPPED / NOT_EVALUATED / production_authorization=none`

## 1. 裁决

本次获批的唯一真实 DATA runner 已执行一次，并在真实语义读取后以 exit code 2 失败关闭：

```text
balancesheet contains conflicting duplicate source identities
```

这不是因子效果 REJECT，也不是一个经过独立审计的 DATA NO-GO。runner 没有形成
`feature_panel.parquet`、`data_gate_report.json` 或 `run_manifest.json`，因此 auditor 没有合法输入，
registry 也没有追加 `DATA_GATE_RECORDED`。权威结果保持 `NOT_EVALUATED`，工程门、效果门与生产均未获
授权。

本 release 已消费且不得重跑。正式 registry 已追加 event 10 `STOPPED`，原因明确绑定 release scope、
exit code、语义读取阶段、源身份冲突、零输出和零重试授权。

## 2. 执行前身份与隔离

- release v3 冻结实现：`a7960666b884cc1d5d7add5c1ff2bc69482ab0da`；release 提交：
  `daff831bd82445d4dc01040313547ce5d66e88c4`，均已在执行前推送。
- runner 镜像：`sha256:738b9d7facf428dcf5564b432c1ced257b78c5d8febdb5075e1a60fedba80d0f`；
  `linux/arm64`。
- 输入 manifest 逻辑 SHA：`d9de2ece3dda2fe49c9cd9ae24e58c9f129931b9366814bce390f6d5d5ef8d4d`；
  冻结输入束共 16,854 个文件，bundle manifest 物理 SHA：
  `a0d01080477dceaf4e854dcb8a3964adab02cdb5390d162c6a4ada4b1a669c15`。
- 批准 envelope 逻辑 SHA：`c31878e554eefe5db3afdf4c4567f4db5772c91a029e98f5d6bfb9b67712d9aa`；
  批准 event 8 SHA：`3a4995c0df09997ff33f648ab277c7d6cc7d773d85bf8ad6d5fe09058c1db40a`。
- runner 保持 `network_mode:none`、non-root、只读根、drop ALL caps、no-new-privileges、1 CPU/2 GiB；
  输入只读，只允许项目内内容寻址 staging 写入。不挂载 `.env`、`.git`、Docker socket、标签、效果、
  模型、生产 compose 或 scheduler 路径。

## 3. 真实失败证据

event 9 `DATA_GATE_STARTED` SHA 为
`800c3be036764417d7655411958a49b79d4433b8983dcb7e0bbeb5ec9ae3fbfa`。runner 随后读取冻结 allowlist
中的真实财报、交易日历和成员证据，在 `canonical_statement("balancesheet", ...)` 合并普通/VIP
资产负债表来源时检测到冲突。

冻结身份为 `(ts_code, f_ann_date, end_date, report_type, update_flag)`。错误意味着至少一个相同身份组的
冻结资产负债表业务字段不一致；本次没有额外展开或输出证券、日期、财务值及候选值，也未判断冲突
来自单一 API 内部还是普通/VIP 交叉来源。该事实必须由未来另行获批的窄诊断读取确认，不能在本批
外读数据猜测。

输出 staging 和 audit staging 均为 0 个条目；候选矩阵、eligible/rejected 集合、相关性诊断、真实
候选值和审计报告均不存在。运行期间只出现 pandas 未来版本兼容提示；它不是本次退出原因。

## 4. 状态机、发布与幂等

- event 10 `STOPPED` SHA：
  `e0ca4594e03639212ba6ed5ebe75f651a0d3664da7cad86e232e3cefc0b9b3bd`。
- registry 全链 verify：PASS；最终 seq=10，`lifecycle_state=STOPPED`、
  `authoritative_outcome=NOT_EVALUATED`、`evidence_tier=PROTOCOL_ONLY`、
  `engineering_gate_status=NOT_READY`、`production_authorization=none`。
- `data_gate_status=RUNNING` 是冻结状态机对终止事件保留上一个正交轴的机械投影；不能解释为仍有进程
  或仍获执行权。没有 M5 容器继续运行。
- 10/10 outbox 已发布到项目内脱敏 append-only ledger；ledger 共 1 行表头 + 10 行事件，SHA-256 为
  `2f316d8dcb76c5dd10884cc9a586595609b12b88fd1e2fd83a7bec82e6066488`。
- 同一 STOPPED command 重放返回原 event 10；outbox 重放 `published_count=0`。正式 registry 数据库
  SHA-256 为 `b11ac47786bbdb797e70ffa28561382c0898a90e620fce4cfd4c8ea294654f35`。

runner 失败前未封存 run identity，继续调用会再次读取真实数据，既不构成合法产物幂等验证，也超出
“运行一次”的用户授权，因此没有重跑 runner。

## 5. 生产与未授权边界

生产 scheduler 施工前后均为：

- container：`183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`；
- image：`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`；
- created：`2026-08-03T09:39:34.800579793Z`；
- state：`running / healthy`。

本批标签、收益、RankIC、候选排名、模型、训练、回测、信号、持仓、DeepSeek、Tushare/飞书凭据、
外部网络、Web、生产配置与生产授权均为 0/未触碰/none。

## 6. 双重阻断与下一合法动作

本次同时暴露两层问题，必须分开处理：

1. **真实数据阻断：**资产负债表冻结来源身份存在内容冲突，数据可用性尚未裁决；
2. **执行合同阻断：**协议把“全局源身份冲突”定义为 DATA NO-GO，但 v3 runner 在封存规范化失败报告
   前抛错，导致 auditor 无法独立复核，也不能合法追加 `DATA_GATE_RECORDED`。

旧 case 已终止，禁止改库、删事件、补造矩阵、把 STOPPED 改写为 NO-GO，或在同一 release 下重跑。
若继续，须先结果前冻结 superseding protocol/build contract，形成新的 `protocol_scope_sha256` 和新
case；新协议应同时冻结：

- 只读诊断怎样区分“完全重复”“普通/VIP 冲突”和同 API 内冲突，并保存不含财务值的计数/哈希证据；
- 全局完整性失败怎样生成 canonical failure report、由独立 auditor 重算后落为
  `NO_GO_M5_2_DATA_PREEXECUTION`；
- 不允许根据冲突内容改公式、门槛、池、方向或尝试数，八次研究尝试 N 继续保留；
- 新实现、镜像、输入束和 release scope 必须先推送并由用户针对新 SHA 重新批准。

在上述恢复协议、实现、release 和新授权完成前，M5-2C synthetic 工程门、效果/G1、前瞻和生产均不
得启动。
