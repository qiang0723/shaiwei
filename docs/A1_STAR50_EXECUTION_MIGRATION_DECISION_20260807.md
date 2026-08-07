# A1-1A 科创50纠错执行内核迁移前置裁决

- 裁决日期：2026-08-07（UTC+8）
- 开工代码：`fb5d9c67d4b8e934f6404ff2ea55ed8ffae513b4`
- 原计划：把 P2-2C corrected execution 从 `tools` 提升到稳定 `src` 内核
- 终态：`DEFERRED_FROZEN_IDENTITY_CONFLICT`
- 生产授权：`none`

## 1. 结论

A1-1A 不进行代码迁移。完整施工前置检查证明，现有 `src -> tools` 不是可用普通兼容 wrapper 消除的
一般技术债，而是同时被 P2-2C 与 M4 历史证据绑定的冻结实现身份。原地替换、复制后切换或修改冻结
协议，都会让至少一条合法历史复算链失真。

本裁决不是放弃架构治理，而是把这条债务从“待迁移”改为“历史复算隔离项”：机器门继续保证它是
唯一一处 `src -> tools`，禁止出现第二处；P2/M4 未通过显式版本化退出或归档 ADR 前，旧路径和字节
保持不变。未来建立新的科创50策略或执行版本时，新版本必须直接使用 `src` 领域内核，不能再继承这条
反向依赖。

## 2. 冻结冲突证据

### 2.1 路径与文件哈希被协议写死

`config/m4_star50_residual_effect_v1.yaml` 明确绑定：

- `corrected_executor_path = tools/p2_star50_effect_correction/executor.py`
- `corrected_executor_sha256 = d8dbdb8bf0706af86757a853602c70dc4e7b5f73a901de1ea8f4045165bc9679`

开工前实际文件 SHA-256 与上述值完全一致。M4 的 `EffectProtocol.verify_upstream()` 会逐路径复算哈希，
把旧文件改成 re-export wrapper 会立即使合法复算失败。

### 2.2 M4 release 同时绑定整套代码 bundle

`src/shaiwei/research/star50_residual_effect/evidence.py` 的 `CODE_BUNDLE_PATHS` 同时包含：

- M4 `metrics.py`；
- P2 原 metrics；
- P2-2C corrected executor。

当前 bundle 为 `22c76e4788a20172305a6e8ad95515b7d4977d29a155e500503a785dfff43e59`，并由
`config/m4_star50_residual_effect_audit_order_recovery_execution_v1.yaml` 的 recovery release 绑定。
即使保持旧 tool 文件不变，只把 M4 import 切到新 `src` 内核，也会改变 bundle，且协议仍声称旧 tool
executor 是权威输入，形成“声明与实际执行不一致”。

### 2.3 P2-2C 也绑定旧工具代码身份

P2-2C 的 `correction_code_sha256()` 会哈希整个 `tools/p2_star50_effect_correction/*.py`、P2 metrics、
协议与输入审计；权威 manifest 保存的纠错代码身份为
`66666772f2a7a46c51a7eda2c9bbc90e018f4a2de6ae1374d1d0d4d4428559f7`。修改 executor 或 contract
都会让新的代码身份不同。该聚合身份还包含后来持续演进的`ledger.py`，所以当前HEAD不应冒充原提交的
完整聚合身份；旧结果由原Git提交复算。这个事实不构成当前代码门，但同样禁止把新实现静默包装成旧实现。

## 3. 方案比较

| 方案 | 结果 | 裁决 |
|---|---|---|
| 旧 executor 改成新 `src` re-export wrapper | 破坏 M4 固定 executor SHA 与 P2-2C code identity | 拒绝 |
| 复制到 `src` 并让 M4 切换，旧 tool 原样保留 | 形成两套实现；M4 当前 release bundle 失效，协议声明与执行不一致 | 拒绝 |
| 修改 M4 v1 协议或现有 release 接受新路径 | 结果后改写冻结协议/执行身份 | 拒绝 |
| 保留唯一 grandfathered 反向依赖并机器隔离 | 历史复算完整，新债务仍被禁止 | 采用 |

## 4. 保护与退出条件

1. `tools/p2_star50_effect_correction/executor.py`、M4 v1 protocol/release 和 P2-2C manifest 不修改。
2. 现有机器测试继续要求 `src -> tools` 实际集合与登记集合精确相等，任何第二处反向依赖失败。
3. M4/P2 历史包转为 no-growth；不得把旧 executor 用于新的股票池、策略或生产能力。
4. 只有以下任一条件满足后才重新评审迁移：
   - 通过单独 ADR 和版本化 M4-v2/P2 replay successor 建立新内核，旧 v1 只保留归档复算；或
   - 旧复算入口已由可执行 Git tag、镜像、命令、输入 manifest 和预期输出哈希完整归档，并经用户批准
     退出当前工作树。
5. 即使退出，也不得删除冻结协议、验收、失败/REJECT 证据和不可变产物。

## 5. 本节点实际影响

- 生产代码修改：0
- 冻结文件修改：0
- 文件删除：0
- 数据、研究、回测、外网和生产运行：0
- scheduler 修改或重启：0
- 自然账本写入：0（已有 scheduler 变动保持未暂存）

下一项安全可执行的架构包是 A1-1B：拆解 `deepseek_client <-> llm_factor` 循环依赖。它与本次
历史执行身份无关，但仍须按 A1 清单获得新的继续指令，不能由本裁决自动授权。
