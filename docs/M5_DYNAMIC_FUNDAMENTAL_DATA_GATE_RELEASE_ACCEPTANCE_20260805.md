# M5-2B 动态基本面数据门发布范围验收（2026-08-05）

## 1. 结论

机器裁决为 `GO_DATA_GATE_RELEASE_READY_NOT_EXECUTION_APPROVAL`。

本节点完成了 M5-2B 数据门的施工、纯合成验证、实现提交推送、最终离线镜像重建、真实输入的
metadata-only 清单和精确发布范围。发布范围只供用户审批，明确保持：

- `data_gate_release_ready=true`；
- `data_gate_approval_recorded=false`；
- `data_gate_execution_authorized=false`；
- `real_data_read_authorized=false`；
- `label_read_authorized=false`、`effect_read_authorized=false`；
- `external_call_authorized=false`、`model_training_authorized=false`、`backtest_authorized=false`；
- `scheduler_mutation_authorized=false`、`web_change_authorized=false`；
- `production_authorization=none`。

因此，本文不是数据门 GO、因子有效或生产授权。正式 registry 尚未初始化，真实财务语义行、真实候选
值和 24 个真实评价单元均未读取或计算。

## 2. 内容寻址真身

| 对象 | 身份 |
|---|---|
| protocol scope | `ab8c33968c4ced325ec79524b774163f2991edd0c4d5d7eb7c139b27e9b17557` |
| 实现提交（已先推送） | `4369d7f9fa08fca023c07beecb47bc898c56ba72` |
| code bundle | `f2b9b377a30cfca203b5041c85a65233ce412581a89fb28ac02e2b8da7195675` |
| 输入清单逻辑 SHA-256 | `d9de2ece3dda2fe49c9cd9ae24e58c9f129931b9366814bce390f6d5d5ef8d4d` |
| 输入清单物理 SHA-256 | `3277114e007d49c0f7071e0a5c5f2c58e6d72ddcf67f7f216df9464d97075919` |
| 最终镜像 ID / repo digest | `sha256:64928c6273666cc767ef7bd038c0b4919811fc8c738de8131512f429d8cf555c` |
| 镜像平台 | `linux/arm64` |
| data release scope | `f53085d3cc428e17f014a3d1b0ab7f2f2f0f4ddf6eb64b2db7042fd26ccefe70` |
| release 文件物理 SHA-256 | `b1ce2cbeb7899c412fe05cc883e71de668ef76fcb9e8e14fed30af003fc860d5` |
| scope 创建时间 | `2026-08-05T21:25:21+08:00` |
| 绑定提案到期时间 | `2026-08-12T18:48:16+08:00` |

发布真身为 `config/m5_dynamic_fundamental_data_gate_release_scope_v1.json`。它绑定固定 runner、独立
auditor 和 registrar 命令，断网、非 root、只读根、drop all capabilities、no-new-privileges、
`pids_limit=128`，且只允许三个项目内内容寻址挂载：`/inputs:ro`、`/outputs:rw`、`/audit:rw`。
runner 为 1 CPU/2 GiB，auditor 与 registrar 各为 0.5 CPU/512 MiB。

## 3. 将来获批后可读取的精确输入

清单生成过程只读取 ingest ledger、文件大小、Parquet footer/schema、行数和文件哈希，
`semantic_rows_read=false`。清单包含恰好七类 API、16,843 个最新不可变批次：

| 来源 | 批次数 |
|---|---:|
| `tushare.trade_cal` | 2 |
| `tushare.income` | 5,445 |
| `tushare.income_vip` | 169 |
| `tushare.balancesheet` | 5,445 |
| `tushare.balancesheet_vip` | 169 |
| `tushare.cashflow` | 5,445 |
| `tushare.cashflow_vip` | 168 |

另绑定三份冻结成员证据：科创50官方 PIT 72,800 行，以及科创板中盘/小盘规则 PIT 各 779,271 行。
这些数字均来自 Parquet metadata，不是成员值或财务值。清单不包含行情、估值、复权、指数行情、标签、
效果、模型、预测、持仓、`.env`、日志或 Docker socket。

## 4. 施工发现与修复

1. 首次最小镜像运行发现 Pandas Spearman 间接依赖未锁定的 SciPy，按合同失败关闭。实现改为确定性
   average-rank + Pearson，没有扩大冻结依赖。
2. metadata-only 清单校验发现上游官方科创50成员文件使用稳定字段 `code`，M3 规则池使用
   `ts_code`。新增严格 source adapter：仅 `star50-official-pit-v2` 将 `code` 规范化为内部
   `ts_code`，另两池继续强制 `ts_code`；未知池或 schema 漂移仍失败关闭。修复提交已在生成 release
   前推送。
3. 输入清单同时绑定 canonical JSON 的逻辑哈希与落盘字节的物理哈希，避免相同逻辑对象被非规范
   序列化替换。

## 5. 验证结果

- 最终离线 Docker 纯合成全链：PASS；8 个候选、3 个池、24 个单元，独立重算审计 PASS，临时
  registry 恰好四表；`real_financial_rows_read=false`、`effect_test_count=0`。
- M5 动态数据门与 registry 专项：70 PASS。
- 全仓：725 PASS，1 条既有 Starlette 第三方弃用 warning。
- 架构门：6 PASS；新增生产模块最大 365 行，低于 400 行施工上限。
- Ruff、compileall、`pip check`、Compose config、`git diff --check` 和全仓 secret hygiene：PASS。
- 生产 scheduler 施工前后保持同一容器 `183b8c6c5edd...`、同一镜像
  `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`，状态
  `running/healthy`，创建时间仍为 `2026-08-03T17:39:34+08:00`，未重启、未重建。

compileall 另报告一处既有测试正则字符串 SyntaxWarning，不影响编译与测试结果，本节点不为无关提示
扩大修改范围。

## 6. 用户批准边界

下一步只能由用户针对精确 release scope
`f53085d3cc428e17f014a3d1b0ab7f2f2f0f4ddf6eb64b2db7042fd26ccefe70` 明确批准一次真实
`DATA_GATE`。若批准且提案未到期，授权仅包括：

1. 在项目目录内生成与该 scope 绑定的审批 envelope 和内容寻址输入包；
2. 在一次性断网 Docker 中读取上述清单允许的财务列与三份成员真身；
3. 运行固定 8 候选 × 3 池的数据门和独立 auditor；
4. 仅在 auditor PASS 后登记正式 gate 事件及脱敏投影。

批准仍不包括标签、效果、G1、DeepSeek、模型、回测、模拟仓、前瞻、Web、scheduler 或生产。数据门
即使得到 GO，也只表示候选数据可用；后续 synthetic engineering gate 和效果门继续分别立项、冻结与
授权。
