# M5-2B 动态基本面数据门 release v2 验收（2026-08-05）

## 1. 结论

机器裁决为 `GO_DATA_GATE_RELEASE_V2_READY_NOT_EXECUTION_APPROVAL`。

旧 release scope `f53085d3...cefe70` 因未绑定正式 `/registry:rw`，已在任何真实财务语义值读取前
失败关闭并永久标记 `SUPERSEDED_BEFORE_REAL_DATA_READ`。恢复未改变研究协议、候选、股票池、输入、
数据门阈值、尝试 N 或提案有效期；只修复 release 对正式 registry runtime 的内容寻址约束。

新 release 仍只供用户审批：`data_gate_release_ready=true`，其余真实读取、门执行、标签/效果、外部
调用、模型、回测、Web、scheduler 与生产权限全部为 false/none。

## 2. v2 内容寻址身份

| 对象 | 身份 |
|---|---|
| protocol scope | `ab8c33968c4ced325ec79524b774163f2991edd0c4d5d7eb7c139b27e9b17557` |
| 恢复实现提交（已先推送） | `a98cd1d4f83dba022b199ae267d0bdc802f5bc2b` |
| code bundle | `cf9cd3608388688ea3b3424ecf4631b221fdbd125c35c7bb58c2324ad0e0bd0b` |
| 输入清单逻辑 SHA-256 | `d9de2ece3dda2fe49c9cd9ae24e58c9f129931b9366814bce390f6d5d5ef8d4d` |
| 输入清单物理 SHA-256 | `3277114e007d49c0f7071e0a5c5f2c58e6d72ddcf67f7f216df9464d97075919` |
| v2 镜像 ID / repo digest | `sha256:d04f96f579c21f0624d21f3907354e6a433e3f1dcaed45e14a487dd88639e2f3` |
| 镜像平台 | `linux/arm64` |
| v2 release scope | `a847c4da8541f5fd421747079145e723675cfbe6f5ed2eb15d2b7fa4779a6c96` |
| v2 release 文件物理 SHA-256 | `882ae6b5bff7bcbd9585ce75b4e2a566a6ea148119c402a833172fb7b85499c4` |
| scope 创建时间 | `2026-08-05T22:04:07+08:00` |
| 绑定提案到期时间 | `2026-08-12T18:48:16+08:00` |

机器真身为 `config/m5_dynamic_fundamental_data_gate_release_scope_v2.json`。文件沿用冻结的
`m5-data-gate-release-scope-v1` envelope schema；文件名 v2 表示第二个不可变 release 实例，不是静默
改写旧实例。

## 3. 唯一恢复差异

v2 强制恰好四个项目内挂载：

| target | mode | 用途 |
|---|---|---|
| `/inputs` | `ro` | 已批准的内容寻址输入包 |
| `/outputs` | `rw` | runner write-once staging |
| `/audit` | `rw` | 独立 auditor write-once staging |
| `/registry` | `rw` | 正式四表 registry、outbox 与脱敏 gate ledger |

任何 mount 缺失、额外 mount、绝对/越界路径或 mode 漂移均失败关闭。断网、非 root 65532、只读根、
drop ALL capabilities、no-new-privileges、128 PID 以及 runner/auditor/registrar 资源上限不变。

## 4. 输入与未授权边界

输入仍为同一 metadata-only manifest：7 类 API、16,843 个不可变批次和三份成员证据（科创50官方
PIT 72,800 行；科创板中盘/小盘规则 PIT 各 779,271 行）。metadata 复核仍为
`semantic_rows_read=false`；没有行情、标签、效果、模型、预测、持仓、凭据或外部网络输入。

当前正式 registry、approval envelope、input bundle、真实 runner/auditor 产物均不存在；
`real_financial_rows_read=false`、`real_candidate_values_computed=false`、
`data_gate_execution_count=0`、`effect_test_count=0`、`production_authorization=none`。

## 5. 验证

- 修复后 M5 专项：71 PASS；全仓：726 PASS，1 条既有 Starlette 第三方弃用 warning；
- 架构门：6 PASS；Ruff、compileall、`pip check`、Compose config、diff 与 secret hygiene：PASS；
- v2 镜像完全合成断网全链：8 候选、3 池、24 单元、独立审计 PASS，正式 registry 未初始化，真实
  财务读取与效果测试均为 0；
- scheduler 保持原容器 `183b8c6c5edd...`、原镜像 `sha256:722f63de...13b76`、原创建时间，状态
  `running/healthy`，未重启或重建。

## 6. 下一授权边界

只有用户针对完整新 SHA
`a847c4da8541f5fd421747079145e723675cfbe6f5ed2eb15d2b7fa4779a6c96` 再次明确批准，且提案仍未到期，
才允许初始化正式 registry、生成绑定 event 4 的 approval envelope 与硬链接输入包，并运行一次断网
真实 DATA_GATE 和独立 auditor。

该批准仍不包含标签、效果、G1、DeepSeek、模型、回测、模拟仓、前瞻、Web、scheduler 或生产。
