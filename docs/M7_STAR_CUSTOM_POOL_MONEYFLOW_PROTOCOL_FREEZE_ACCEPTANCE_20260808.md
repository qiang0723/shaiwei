# M7-0 三自建科创池资金流兼容协议冻结验收（2026-08-08）

## 裁决

`GO_M7_0_PROTOCOL_FREEZE_ONLY`

本裁决只证明 M7-0 键级数据兼容协议已经结果前冻结、先行推送，并形成内容寻址 protocol scope。
它不是资金流数据门 GO，不授权读取真实证券键或资金流数值，也不授权候选生成、标签/收益、效果、
模型、回测、外网、前瞻、模拟仓、Web、scheduler 或生产变更。

## 冻结身份

- protocol commit：`0ec4725d830346a74d0edcef17d00bc11cda0398`
- parent：`c1cb3b169641a129378870454f11b2077e607dfa`
- tree：`995b5b9995aa86e5e490171e75fd2b5bf1da1251`
- 推送证明：scope 创建时本地 `origin/main` 与 protocol commit 相等
- protocol scope canonical SHA-256：
  `3b137d0b84e557c4fa38ea5072fe22241802f7a714f5890fc365705f2b71d59b`
- scope envelope physical SHA-256：
  `157231297ee10eacfab1d056f3204d6fc759fafcc32c508e25c851424db73f78`

scope 绑定 proposal ID、request/canonical proposal SHA、seq=2 事件链头、到期时间、协议提交、协议
文档、机器配置、proposal export、合同测试、架构宪法和 M5 研究治理。冻结文件均逐物理 SHA-256 核验。

## 冻结的数据合同

- 研究池固定为科创板全市场自建 PIT 池及其中盘/小盘迁移池；三者都不是官方科创指数。
- 兼容门只投影 P1 `tushare.moneyflow` 的 `ts_code, trade_date`，与 M3 日成员精确键连接；资金流数值
  字段禁止读取。
- feature 日期域固定为 2021-01-04—2026-06-30；D 日源只可供下一 SSE 开市日使用，P1 的 46 个
  `moneyflow-quality-v2` 隔离日保持整日隔离，不填0、不前后填。
- 三池总体、11个完整半年、逐日最低覆盖、连续隔离、重复/非法/PIT/.BJ/修订/饱和硬门均在真实键
  读取前冻结；不得 partial-pool GO 或结果后放宽。
- 本批候选定义、评价单元、效果测试和生成尝试增量均为0；资金流历史背景仍为 `N=18`，提案最多8次
  只是未执行计划。

## 数据质量复核发现

首次专项测试发现导出草稿中的 canonical proposal SHA 是手工转录错误值。提交前已按控制面既有
`canonical_json` 规范从只读 proposal 真身独立复算为
`67e1674835f2077a0d59e8ec6968ded2729f48bde7c296e11ea8519bb42faeb8`，并同步修正 export、config、协议和
测试；proposal request SHA 仍为 `05caa719...ba88c`。错误草稿从未提交、推送或进入 release scope。

## 验证与隔离

- M7 协议与 scope 专项：6 PASS；
- 全仓：947 PASS；
- 架构门：13 PASS；
- Ruff、compileall、Git diff-check：PASS；
- 唯一 warning 为既有 Starlette TestClient 第三方弃用提示；
- 未访问 `.env`，未调用 DeepSeek、Tushare、飞书或其他外网，未读取真实证券键、资金流数值、标签或
  效果，未创建研究尝试或改动自然账本。

生产 scheduler 仍是原容器 `183b8c6c5edd`、原镜像
`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`、创建时间
`2026-08-03 17:39:34 +0800`，状态 healthy；本目标未重启或修改它。

## 下一合法动作

只允许按 scope 施工并推送：metadata-only 输入 inventory、只读键级 runner、独立 auditor、合成
fixture、一次性断网镜像和新的精确 real-data release scope。施工阶段仍不得读取真实证券键。

未来只有在提案仍为 `REVIEW_REQUIRED`、seq/链头/到期均未漂移，且用户逐字绑定新 release scope SHA
批准后，才能唯一运行一次断网真实键级数据门。即使数据门 GO，策略仍 `NOT_EVALUATED`、生产授权
`none`；候选公式必须另立后续结果前协议。
