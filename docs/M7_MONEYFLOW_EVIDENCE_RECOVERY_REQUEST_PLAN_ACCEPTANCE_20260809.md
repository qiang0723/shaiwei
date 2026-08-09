# M7-0R3-P2 精确请求计划与独立审计验收

## 结论

精确请求计划与独立审计闭环为 `GO_M7_RECOVERY_EXACT_REQUEST_PLAN_ONLY`。该 GO 只证明封存的 527/541
恢复键已被确定性投影为完整、无额外项、可审计的 provider 请求计划；不代表网络恢复成功、调整后
覆盖率通过、候选有效或生产授权。

## 唯一计划

- plan ID：`406f083f09cc8e41517ff9b38a4e109606a44b3da923710e4f745e34932b0470`。
- 聚合 manifest SHA-256：`dcc2a78d8d399321bbd042acba009e9e39b428beb6640756c605e2498859bf43`；
  Git 跟踪副本与忽略区真身逐字节一致，不含证券代码。
- 状态轨：75 个最大连续窗口，精确覆盖 527 个状态键，最大窗口 17 个官方交易日。
- 资金流轨：541 个按日全市场请求和 541 个单票单日请求；两种形态均精确覆盖同一 541 个键。
- 官方日期：1,328 日，范围 2020-12-31 至 2026-06-29。
- 若未来获得最终网络 scope 批准，精确 provider 请求总数为 1,157；本节点实际调用仍为 0。

## 首次审计失败与恢复

首次 auditor 把内容寻址计划目录挂成 `/plans`，触发 plan root basename 身份门，返回
`RecoveryError` 且没有生成审计产物。该 FAIL 已永久保留，未被改写为 PASS。

用户随后绑定 scope
`3a5d201bf3972198cd98d74e6c40cb1fb15a63180fe0e660054ca37286b9592f`，批准动作
`M7_REQUEST_PLAN_INDEPENDENT_AUDIT_MOUNT_RECOVERY_ONCE`。恢复只把挂载目标改为
`/plans/<plan_id>`；同一镜像、输入、算法和阈值不变。唯一恢复审计 PASS，审计 SHA-256 为
`4f63bfe8ccaee68195f37f82c57db038cf948311695ad9c74a2c973364bb7dd5`，恢复 scope 现已关闭。

## 同类阻断修复

审计失败暴露出未来四个真实角色的 release 也曾把 plan 目录挂成 `/plans`。在最终网络 scope 生成前，
已把 status collector、moneyflow collector、evaluator 和 auditor 的挂载与 `--plan-root` 统一改为
`/plans/<plan_id>`，并新增四角色逐项机器断言。该修复尚未授权或触发任何 provider 调用。

## 权限和隔离

- 计划生成、首次审计、恢复审计均未读取 `.env`、token 或资金流数值。
- 恢复审计使用 `network=none`、非 root、只读根、`cap_drop=ALL`、`no-new-privileges`，未挂载项目根、
  Docker socket、生产 `data/raw`、ledger 或 logs。
- `provider_call_count=0`，`research_attempt_increment=0`，生产授权为 `none`。
- 下一步只允许提交本次归档与四角色挂载修复，从已推送代码重建镜像、生成最终聚合网络 release
  scope，然后再次停下等用户绑定完整 scope。不得直接联网。
