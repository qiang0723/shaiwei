# M5-2B 输入包身份与预语义失败恢复单（2026-08-05）

## 1. 触发事实

release v2 scope `a847c4da...a6c96` 获用户批准后，正式 registry 已依次形成 IMPORT、
PROTOCOL_FROZEN、DATA_GATE_RELEASE_READY、DATA_GATE_APPROVED 和 DATA_GATE_STARTED 五个事件。真实 runner
随后以 exit code 2 失败：`/inputs/config/m5_dynamic_fundamental_data_gate_build_v1.yaml` 不存在。

失败发生在 `M5DataProtocol.load`，早于 `load_allowed_inputs`，因此：

- `real_financial_rows_read=false`；
- `real_candidate_values_computed=false`；
- 没有 feature panel、data gate report、run manifest 或 audit report；
- 标签、效果、DeepSeek、模型、回测、Web、scheduler 与生产均未触碰。

v2 输入包永久保留，不补文件、不改 manifest、不删除；v2 不产生 DATA verdict，也不是策略 REJECT。

## 2. 根因

旧 `materialize_bundle` 有两个相连的合同错误：

1. runner 明确要求 build contract，但输入包控制文件只含 input manifest、release scope 和 approval
   envelope，遗漏 build contract；
2. 输入包目录只以 input manifest SHA 命名，但目录内部同时包含会随 release/approval 变化的控制文件。
   相同数据输入下，不同 release 会碰撞同一路径；旧复用检查只验证包内自洽，不能证明其控制文件等于
   当前 release/approval。

因此不能把 build contract 追加到已批准的 v2 包，也不能在原路径删除重建。

## 3. 唯一允许恢复

### 3.1 正式事件

状态机只新增 `DATA_GATE_PREEXECUTION_FAILED`，且仅允许从 `DATA_GATE_RUNNING` 返回
`PROTOCOL_FROZEN`。payload 必须逐字段等于：

```json
{
  "release_scope_sha256": "<当前活动scope>",
  "failure_code": "INPUT_BUNDLE_CONTROL_MISSING",
  "runner_exit_code": 2,
  "semantic_rows_read": false
}
```

该事件不产生数据判决、不改变尝试 N、不会授权下一次执行；它只把已发生的预语义失败纳入哈希事件链，
使新的 release 可以从协议冻结态重新开始。

### 3.2 输入包 v2

- 控制文件必须包含 input manifest、build contract、release scope、approval envelope；
- bundle manifest 同时绑定四个控制对象的逻辑/物理 SHA、全文件清单和
  `semantic_rows_read=false`；
- release 中 `/inputs` 路径必须严格为
  `data/control/m5_2/input-bundles/<input_manifest_sha256>-<implementation_commit前7位>`；
- 已存在目录必须逐项匹配当前 input/release/approval/build identity；任何复用漂移失败关闭；
- 新实现不得修改 protocol scope、候选、票池、公式、PIT/覆盖门、输入 manifest、尝试 N、提案到期、
  Docker 网络/资源或未授权项。

## 4. v3 边界

恢复实现须先测试、提交和推送，再重建镜像、使用新目录生成 release v3。v2 approval 不迁移；必须先
登记 `DATA_GATE_PREEXECUTION_FAILED`，再形成 v3 RELEASE_READY，并向用户报告完整新 SHA 后重新取得
批准。v3 批准前不得再次登记 STARTED 或读取真实财务值。
