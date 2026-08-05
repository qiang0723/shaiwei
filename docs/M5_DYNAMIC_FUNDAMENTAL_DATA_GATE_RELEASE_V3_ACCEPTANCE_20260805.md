# M5-2B 动态基本面数据门 release v3 验收（2026-08-05）

## 1. 结论

机器裁决为 `GO_DATA_GATE_RELEASE_V3_READY_NOT_EXECUTION_APPROVAL`。

release v2 获批后，runner 在加载 protocol/build contract 阶段以 exit code 2 失败，早于任何真实财务
列读取。该事实已作为正式 event 6 `DATA_GATE_PREEXECUTION_FAILED` 写入原事件链，payload 明确
`semantic_rows_read=false / INPUT_BUNDLE_CONTROL_MISSING`；registry 随后恢复到
`PROTOCOL_FROZEN / NOT_READY / PROTOCOL_ONLY`。

v3 修复输入包控制文件与跨 release 身份，但仍只是待审批 release。没有数据门判决、因子效果、模型或
生产授权。

## 2. v3 内容寻址身份

| 对象 | 身份 |
|---|---|
| protocol scope | `ab8c33968c4ced325ec79524b774163f2991edd0c4d5d7eb7c139b27e9b17557` |
| 恢复实现提交（已先推送） | `a7960666b884cc1d5d7add5c1ff2bc69482ab0da` |
| code bundle | `24f93a5f489ead95bc2d11b6479d21f5d11e7a93832db445b46f0dbed7c6fbb6` |
| 输入清单逻辑 SHA-256 | `d9de2ece3dda2fe49c9cd9ae24e58c9f129931b9366814bce390f6d5d5ef8d4d` |
| 输入清单物理 SHA-256 | `3277114e007d49c0f7071e0a5c5f2c58e6d72ddcf67f7f216df9464d97075919` |
| v3 镜像 ID / repo digest | `sha256:738b9d7facf428dcf5564b432c1ced257b78c5d8febdb5075e1a60fedba80d0f` |
| 镜像平台 | `linux/arm64` |
| v3 release scope | `49fdc6e79ee7591fb03732fc4fa08430f4049b720d0552cca49ff9e153e05830` |
| v3 release 文件物理 SHA-256 | `d4bb5ff242863280ec9a28fc6b598b4d19a96744f5fdd5d6834d6243365f51f4` |
| scope 创建时间 | `2026-08-05T22:30:10+08:00` |
| 绑定提案到期时间 | `2026-08-12T18:48:16+08:00` |

机器真身为 `config/m5_dynamic_fundamental_data_gate_release_scope_v3.json`。v1/v2 文件和各自物理哈希
永久保留，v3 不改写历史 release。

## 3. v2 失败证据

正式 case 为 `223414f...b0a78`。event 5 `DATA_GATE_STARTED` 后没有 runner 产物；event 6 为：

- event SHA-256：`d258e076d66efd8f5fd3c8cf014fca89f34f6005be23bacdde4f87a69094559c`；
- failure code：`INPUT_BUNDLE_CONTROL_MISSING`；
- runner exit code：2；
- `semantic_rows_read=false`；
- 终态回到 `PROTOCOL_FROZEN`，不存在 DATA GO/NO-GO。

v2 输入包保持原样，不补 build contract、不改 bundle manifest、不删除重建。

## 4. v3 输入包合同

v3 `/inputs` 精确路径为：

`data/control/m5_2/input-bundles/d9de2ece3dda2fe49c9cd9ae24e58c9f129931b9366814bce390f6d5d5ef8d4d-a796066`

目录身份同时绑定 input manifest 与 implementation。批准后生成的 bundle manifest 还必须绑定：

- input manifest 逻辑/物理 SHA；
- build contract 物理 SHA；
- release scope 逻辑/物理 SHA；
- approval envelope 逻辑/物理 SHA；
- 逐文件 bytes/SHA 清单和 `semantic_rows_read=false`。

控制文件固定包含 input manifest、build contract、release scope、approval envelope。相同数据输入下，
不同 release/approval 不能复用已有包；任何碰撞或身份漂移失败关闭。

其他挂载仍为独立 `/outputs:rw`、`/audit:rw` 和延续同一正式事件链的 `/registry:rw`。断网、非 root、
只读根、drop ALL capabilities、no-new-privileges、128 PID 与资源限制不变。

## 5. 输入与授权边界

metadata-only 授权前复核再次得到与冻结清单逐字节相同的物理 SHA，仍为 7 类 API、16,843 个不可变
批次和三份成员证据。当前 v3 approval envelope/input bundle/STARTED 均不存在；真实财务行、候选值、
数据判决和效果仍为 0。

所有 authority 除 `data_gate_release_ready=true` 外仍为 false；
`strategy_effective=NOT_EVALUATED / production_authorization=none`。

## 6. 验证

- M5 专项：74 PASS；全仓：729 PASS，1 条既有 Starlette 第三方弃用 warning；
- 架构门：6 PASS；Ruff、compileall、`pip check`、Compose、diff、secret hygiene：PASS；
- 新镜像纯合成断网全链：8 候选、3 池、24 单元、独立审计 PASS；真实财务读取与效果测试为 0；
- 既有正式 registry 在新实现下全库重放 PASS；生产 scheduler 身份未变且 `running/healthy`。

## 7. 下一授权边界

v2 的用户批准不能迁移。只有用户针对完整 v3 scope
`49fdc6e79ee7591fb03732fc4fa08430f4049b720d0552cca49ff9e153e05830` 再次明确批准，且提案仍未到期，
才允许追加新的 RELEASE_READY/APPROVED、生成 v3 approval envelope 与输入包、再次登记 STARTED，并
运行一次断网真实 DATA_GATE 和独立 auditor。

该批准仍不包含标签、效果、G1、DeepSeek、模型、回测、模拟仓、前瞻、Web、scheduler 或生产。
