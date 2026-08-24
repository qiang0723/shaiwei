# ADR-003：封存组件身份与当前构建注册表解耦

- 日期：2026-08-24（UTC+8）
- 状态：`ACCEPTED / IMPLEMENTED`
- 节点：`A1-6B`
- 范围：组件 release 的历史只读复核与生命周期关闭；不授予任何执行或生产权限

## 问题与结果目标

`config/build_asset_registry_v1.yaml` 同时承担“当前构建资产所有权”和“组件当前生命周期状态”。它必须
随新组件登记和旧组件关闭而演进。已经封存的 release scope 则必须永久使用发布当时的注册表 SHA、
逐资产 SHA 和组件快照。若历史 scope 校验继续读取当前注册表，关闭一个已经执行完毕的组件反而会
使其历史证据失效。

A1-6B 的结果目标是：当前注册表可以如实关闭 R4 组件，R2/R4 两份历史 scope 仍可离线复核；任何
历史注册表 SHA、资产路径、资产内容 SHA 或组件快照篡改都必须失败关闭。完成后不再依靠“把已结束
组件继续标为 active”维持旧证据。

## 现状证据

1. ADR-002 已使 R2 使用冻结的历史注册表 SHA 和三资产路径，但校验逻辑仍为该研究入口私有实现，
   且未把逐资产 SHA 固定为通用身份权威。
2. R4 scope `117e69a8c29f48d2434c84363d4766d48af4f2010aeddae1610128fb9614c51d`
   已唯一执行并永久关闭；其组件仍为 `ACTIVE_LOCAL_READ_ONLY`。
3. R4 校验器动态调用 `load_build_registry()` 并要求 scope 的历史 SHA 等于当前注册表 SHA。将组件改为
   `CLOSED_FROZEN` 会改变当前注册表身份并错误破坏 R4 复核。

## 候选方案

1. **继续把 R4 标为 active。** 历史测试暂时不坏，但生命周期状态失真，也允许关闭组件继续形成新
   release；拒绝。
2. **封存校验只信 scope 自带记录。** 能与当前注册表解耦，但攻击者可同时改资产 SHA 和 scope 自哈希，
   独立校验强度不足；拒绝。
3. **通用封存身份校验器 + release 合同中的精确历史权威。** 固定历史注册表 SHA、按序资产路径与
   逐资产 SHA、组件快照；当前 builder 仍只接受 active 当前组件；采用。

## 冻结设计

新增单一职责的 `verify_sealed_component_identity`，只处理以下稳定合同，不读取文件系统或当前注册表：

- 输入：scope 的 `implementation` 映射；调用方冻结的历史注册表 SHA；有序的 `path + sha256` 资产
  记录；冻结的组件快照 SHA。
- 输出：通过严格验证的规范化资产记录，供容器路径和镜像标签边界继续复核。
- 失败关闭：字段类型或 SHA 格式错误、资产记录键不精确、顺序/唯一性不规范、任一历史值不同、
  冻结资产本身不能重算到冻结快照，均抛出构建身份错误；研究合同只做错误类型适配，不复制算法。
- 权威边界：调用方必须把精确历史身份作为版本化 release 合同常量传入；不得把 scope 当前值反过来
  当作 expected，也不得读取当前注册表替代历史权威。

本节点同时完成：

1. R2 迁移到通用校验器，历史 scope 和裁决不变；
2. R4 迁移到相同校验器，并固定其发布时的三条资产及 SHA；
3. R2/R4 合成 fixture 使用各自冻结身份，不再依赖当前注册表；
4. 当前注册表把 `m6-head30-delisting-entitlement-release` 改为 `CLOSED_FROZEN`；
5. 关闭组件不得再通过当前 active release builder 形成新 release。

## 影响边界与兼容

- 不修改 R2/R4 scope、协议、approval、claim、effect、audit、账本、镜像或研究裁决。
- 不读取任何效果、行情、持仓、原始数据或 secret；不运行 runner、回测、模型、模拟仓、Web 或外网。
- 当前/未来新 release 仍必须使用当前注册表、当前文件 SHA，且组件状态必须是
  `ACTIVE_LOCAL_READ_ONLY`。封存校验器不能用于签发新 release。
- 当前注册表 SHA 预期改变，这是生命周期元数据的正常演进；历史 release 不应因此改变身份。
- scheduler 镜像和服务不变。

## 迁移、回滚与验收

迁移以 R2、R4 两个已封存合同为首批消费者，不批量改写其他历史入口。回滚点为本 ADR 的冻结提交；
若实现未同时通过历史 scope 正向、四类身份篡改、当前 active release、关闭组件拒绝签发、资产100%
覆盖、架构与全仓测试，则不提交实现。

验收至少证明：

1. 当前注册表 SHA 已不同于 R2/R4 历史 SHA，但两份真实 scope 均通过；
2. 篡改历史 registry、资产路径、资产 SHA 或组件快照分别失败；
3. R4 状态为 `CLOSED_FROZEN`，且不能形成新的 active release；
4. Web 等 active 组件现有 release 身份门保持通过；
5. `make architecture-check`、`make test`、Ruff、diff-check、脱敏检查通过。

## 复审触发器

若出现第三个需要历史 registry 兼容的已封存组件，直接复用本合同；若不同 release 需要改变字段集合、
签名方式或外部可信根，再另立 v2/ADR，不在本函数中增加分支。异机归档就绪后再决定是否清理历史
builder/fixture；本节点删除文件数固定为 0。
