# M7-0R3-P1 断网真实 key-only 目标投影验收

## 权威裁决

`GO_M7_RECOVERY_TARGET_PROJECTION_ONLY`。

该 GO 只证明 R2 两条冻结类别已被精确投影并完成独立审计。它不改写原 M7-0 数据兼容 NO-GO 或
M7-0R2 缺口谱系 NO-GO，不计算调整覆盖率，不授权 Baostock/Tushare、外网、资金流数值、候选、效果、
模型、回测、前瞻、模拟仓或生产。

## 批准与唯一执行

- 用户逐字批准 scope：`9aca04576362455af66c5426bd0b4b6211d7edecc8b141de5ecee96ae5781614`；
- approval canonical SHA：`708fbf2b695b15896a2be3092f5560a801bb9ec84eabc92b18a60b08841a8130`；
- approval physical SHA：`bbfbc108bdef0b097fff61a5556754b3f949c77284a26c60bb9da36b87f3a215`；
- run ID：`9a7cba4ec6d3a2da809d8a2475a426857131ba2bcfc5f633d86f91f7d870ffab`；
- projector 和 auditor 各形成且只形成一个 claim，均写明 `same_role_retry_authorized=false`。

projector 使用 2 CPU/4 GiB，auditor 使用 1 CPU/2 GiB；两者均为 arm64 固定镜像、非 root、只读根、
drop all capabilities、no-new-privileges、`network=none`。R2 输入束只读；输出、claim、audit 为互相隔离
的窄挂载；生产 data/raw、ledger、logs、scheduler、Web、Docker socket 和 `.env` 均未挂载。

## 输入与 core

- R2 input manifest：`5f3e28088038e423d2f21a1c8b712457b620045749c9052c730cdc777871f9a7`；
- input bundle manifest：`3f4a6cc371186c3864d8ec857c4641e49b66fa38d9e8083c6b2e0a38d9a005eb`，
  10,927 个文件；
- Pandas 主算与 DuckDB 独立复算的 lineage core 均为
  `df5de3990428e630eb2f56380601f3bee12fee2d2220a99c48c286e3701beeca`。

## 精确目标

轨 A（主源全天停牌但缺独立确认）：

- 908 个成员粒度目标，527 个去重 `source_date × ts_code` 请求键；
- feature date `20210107`—`20260630`，source date `20210106`—`20260629`；
- intended-grain 重复、全行重复、PIT 逆序、`.BJ` 均为 0；
- Parquet SHA `71aded70452d4837b6beb0979b03b750db17aaec1208edb6e08cc4497f0a1237`；
- logical SHA `f9aa12c8b21ac45a9f52542911432ca3e40703a5244d4d81fde0087954e09bf8`。

轨 B（daily 存在但 moneyflow 缺键）：

- 541 个成员粒度目标，541 个去重请求键；
- feature date `20211101`—`20240119`，source date `20211029`—`20240118`；
- intended-grain 重复、全行重复、PIT 逆序、`.BJ` 均为 0；
- Parquet SHA `fbf2f704c9f5c6d5958f7356953ac34675fd39895eae4dd77b435097376f5dc8`；
- logical SHA `1e579885863c8e4d522672430d0fc50d9ad2cec7adbdbd8da3ce2b95153e2331`。

两轨 intended grain 交集为 0。projector 内部 replay 哈希一致；auditor 从冻结 DuckDB classified 关系
独立重建，两轨逻辑哈希与主算逐项相同。

## 不可变与幂等

- projection manifest SHA：`d8dba2e92cec6f062721ab5847efefdbbc26f96492c7d82013dc6704311e6fa6`；
- report SHA：`a029072b893eefa3da7e5148ff74ca9b16f917db96615503ca1418c4eebaeac4`；
- independent audit SHA：`8356c5b3d9ab779ab269353019a097b43c75a7361ba7a5db62ef2ae125f7d6f2`；
- projection/claim/audit 整树 SHA 分别为 `b745d9c9...5e8eb`、`a34b64dd...9131e`、
  `49d9a5c2...c3bf5`；执行后目录已收紧为 owner-only。

用户批准明确禁止同 scope 重跑，因此没有启动第二个真实容器。不可重入证据由三部分组成：真实
projector/auditor 双 claim 已存在；精确运行代码在 semantic loader 前原子 claim；同一最终镜像的
真实规模合成验收已证明第二次调用在 loader 前停止。一次重入探针请求被权限审查在容器创建前拒绝，
没有形成容器、语义读取或文件变更。

## 脱敏、隔离与状态

- tracked execution manifest 仅含计数、日期范围、状态和哈希；证券代码正则、`sk-`、Webhook 与绝对
  用户路径扫描均为 0；
- moneyflow/daily 数值列读取 0，provider 调用 0，网络 0，调整覆盖率 0，研究尝试增量 0；
- scheduler 仍为容器 `183b8c6c5edd`、镜像 `sha256:722f63de...13b76`、创建时间
  `2026-08-03 17:39:34 +0800`，healthy 且未重启；
- 七个自然生产账本仍只保留原有未暂存变化，本执行没有挂载或写入它们。
- 终版投影专项23、架构13、全仓1,043 PASS；Ruff、compileall、pip check、Compose、diff-check和仓库
  凭据门均PASS，仅保留既存第三方弃用提示与冻结lineage Pandas future warning。

tracked execution manifest：
`config/m7_moneyflow_recovery_target_projection_execution_manifest_v1.json`，物理 SHA
`7abf0889a9dd94364f68df08bb99d9e090e0f5b982000e604fbca50fc686ed5d`。

## 下一停止点

本 scope 永久关闭，不得重跑。若继续证据恢复，须先基于 527/541 去重请求键生成新的精确网络 release，
分别限定 Baostock 状态与 Tushare `moneyflow` 的调用计划，并再次获得用户批准；本 GO 不自动授权该步骤。
