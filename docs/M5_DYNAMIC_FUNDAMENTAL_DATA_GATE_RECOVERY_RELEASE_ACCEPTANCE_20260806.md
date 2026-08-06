# M5-2B-R1 恢复实现与 release v4 验收

- 验收时间：2026-08-06（UTC+8）
- 阶段裁决：`GO_RECOVERY_RELEASE_READY_NOT_APPROVED`
- 精确 release scope：`8858912f14577a8911e47f0ec338cde82208fe818b4c7a921578e42aeeed6f65`
- 新 case：`a2539149d588a0c19f9cb73331f19a66df63e301df03f56fbb2c8e5c74672068`
- 生产授权：`none`

## 1. 本次完成了什么

恢复实现已把 release v3 暴露的财报来源身份冲突转成可封存、可独立审计的正式数据失败路径。普通源、
VIP 源内部及两源之间的完全重复只做确定性无损折叠；任一业务字段精确不一致即停止 PIT、候选公式和
feature panel，write-once 生成脱敏冲突报告、data gate report 与 run manifest。

全局失败固定投影原协议顺序的 8 候选×3 股票池共 24 单元，全部为
`FAIL / GLOBAL_SOURCE_IDENTITY_CONFLICT / NOT_COMPUTED_GLOBAL_FAILURE`；eligible 为空、八候选全部
rejected，verdict 为 `NO_GO_M5_2_DATA_PREEXECUTION`。该裁决只表示输入完整性不满足，不评价因子或
策略效果。

## 2. 架构与安全边界

- 主分类、失败投影、write-once 封存、独立分类、独立失败投影和审计编排已拆分；runner 149 行、
  auditor 260 行，新增模块均小于 400 行。
- 独立 auditor 不导入 runner、主冲突分类器、主失败投影、候选公式、特征或质量矩阵实现；它重读同一
  输入并重算六类计数、冲突字段计数、每表/全局 commitment、24 单元矩阵和裁决。
- 冲突报告只保留表级聚合与 canonical conflict-set SHA；证券代码、公告日、报告期、report type、
  update flag、原值、规范化值、候选值和绝对路径均受递归禁字段门保护。
- registry 仍为 v1 四表，零 schema 迁移。只有 audit PASS 的简化 24 单元结果才能记录为
  `DATA_GATE_RECORDED`；全局 NO-GO 进入 `BLOCKED_DATA`。runner exit 3 本身没有登记权。
- 旧 case `223414f...b0a78`、旧 release v3 和 event 1—10 未改、未重跑；纯合成夹具证明旧
  `STOPPED` case 与新 case 可同时保持各自终态。

## 3. 合成与回归证据

- 全仓：761 PASS；架构宪法：6 PASS；Ruff、compileall、pip check、git diff-check 通过。
- 完全合成夹具覆盖六种互斥类别、NULL 与整数/等值小数规范化、三种冲突的全局封存、禁字段注入、
  commitment 篡改、24 单元篡改、partial directory、正常模式和失败模式。
- 两次独立的 `network_mode:none`、非 root、只读根 Docker 运行逐字段一致：正常模式
  `GO_FULL_M5_2_DATA_PREEXECUTION_ONLY`；三种冲突均封存 NO-GO；独立 audit PASS；临时 registry
  `BLOCKED_DATA`；runner/auditor/registry 重放均幂等。
- 构建期间先后发现 `.dockerignore` 未放行恢复协议、镜像未带齐旧失败验收真身；两次均在协议加载时
  fail closed。最终只通过显式白名单补齐冻结文件，没有绕过哈希门。

## 4. 发布身份

- 实现提交：`18e7502b74919641e02689720dd31b1e36b276a7`，生成 scope 前已推送
  `origin/main`。
- code bundle：`afdc4f2b402fedba8a91969d5a03c86a50f124c74fe2ff2c1d82803fc182093f`。
- 最终镜像 ID/repo digest：
  `sha256:acb7c6c2828dd3b8a40f599f934f3059904ec27835c19e3847bbb416897d1ea7`，平台
  `linux/arm64`。
- metadata-only input manifest：逻辑 SHA
  `f4aeb411af00ea2f5ad096983859f50a587ed9ad6cee1f384268e14d1ef9399b`，物理 SHA
  `683bed3adda638ab890a30cbadca77a07b1d39fd58b8347dcdb65c5b6053f020`；绑定 7 类 API、
  16,843 个不可变批次和 3 份成员证据，`semantic_rows_read=false`。
- release 真身：`config/m5_dynamic_fundamental_data_gate_release_scope_v4.json`；物理 SHA
  `08d8180ce4fbbef97985f9b5610afe6b10ac9240ad34018482f919c54aecbef2`。

## 5. 当前停止线

本次没有读取真实财务字段值，没有诊断冲突证券/日期/数值，没有创建 approval envelope 或 input bundle，
没有初始化新正式 case、写正式 gate event、运行真实 runner/auditor，也没有读取标签/效果、训练、回测、
调用 provider、修改 Web/scheduler/生产。

若继续，用户必须明确批准完整 scope
`8858912f14577a8911e47f0ec338cde82208fe818b4c7a921578e42aeeed6f65`。该批准只允许一次断网真实
DATA_GATE；若封存 DATA NO-GO，必须经独立 audit 后才登记 `BLOCKED_DATA`；若 DATA GO，也只允许另立
M5-2C synthetic engineering release，不自动授权效果研究或生产。
