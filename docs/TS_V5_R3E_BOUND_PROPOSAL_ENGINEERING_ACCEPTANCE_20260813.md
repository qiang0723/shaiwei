# TS-v5-R3E 本地绑定 proposal 合同工程验收

日期：2026-08-13（UTC+8）

权威裁决：`GO_R3F_LIVE_CANARY_SCOPE_PROPOSAL_ONLY`

策略效果：`NOT_EVALUATED`

生产授权：`none`

## 结论

R3D发现的本地实现缺陷已经关闭。未来独立proposal席位的模式、父候选和搜索预算不再由LLM回答决定：
结果前批准的本地authority贯穿request、compiler与evidence；proposal v3响应只填写研究语义和参数上下界。
六种机制均可编译为原冻结`MechanismCandidate`，所有对抗用例失败关闭，R3C六份旧失败回答保持0录取。

这个GO只表示可以另行设计R3F小批金丝雀，不授权DeepSeek调用、费用、secret读取、行情/收益、参数搜索、
回测、模拟仓、Web或生产。

## 结果前顺序与身份

- scope：`config/ts_v5_r3e_bound_proposal_engineering_v1.yaml`
- scope SHA-256：`30185aa4f34d2d186472594af43b0faadabce1215190cdd047031278087ec691`
- proposal v3合同 SHA-256：
  `c46ee09cf6d1039e85f797e8510284533e0b8980cda255bfb827c30e69942dc8`
- 协议冻结提交：`863f7d2`，已先于实现推送。
- 实现提交：`aee51dce00c07ad5a507c4407da36bbfc8a2dc28`；随后结果未变时复核发现v3投影遗漏
  required features、取消规则和文本安全的完整可见表达，以`e1ebfa43794bd625d30ee6ec29b88ad660902277`
  补齐并推送后，才构建终版权威镜像。`aee51dc`镜像产出的报告/audit保留在忽略区provisional子目录，
  未作为权威验收。
- 正式镜像ID：
  `sha256:1ae8f03b57e25f93c1551b595ad31d485e2ca305fad81123479c01c2b033d584`
- 镜像内release Git身份：`e1ebfa43794bd625d30ee6ec29b88ad660902277`
- 镜像内代码快照：
  `b41c5560ffef088cd4e424fcaf4eee7d0883ba81cf22ff8b28b8abe8d4d810d4`

公共合同变化另由`docs/ADR_0007_TS_BOUND_PROPOSAL_AUTHORITY.md`记录兼容、回滚和未来反方席位边界。
v2合同、R3C/R3D旧证据和最终候选validator未改写。

## 本地权威与搜索预算

每个请求显式包含只读的：

```text
mode = INDEPENDENT
parent_candidate_fingerprints = []
source = RESULT_BLIND_SCOPE_ATTEMPT_PLAN
```

proposal response Schema不包含`lineage`，编译器从验证后的authority注入候选lineage。证据mode只能由编译
产物派生；构造候选mode与批准authority不一致时失败关闭。

搜索点不再是response字段。按参数槽数机械分配：

| 参数槽数 | 每槽点数 | 最大笛卡尔积 |
|---:|---:|---:|
| 1 | 7 | 7 |
| 2 | 7 | 49 |
| 3 | 5 | 125 |
| 4 | 3 | 81 |
| 5 | 2 | 32 |

全部低于冻结上限196，编译产物仍由原validator重算上限。这只是预算合同，没有运行任何搜索。

## 合成、对抗与旧回答重放

- 六种机制各一份proposal v3全部编译，6/6通过原冻结候选validator；request哈希各不相同。
- 共48个对抗fixture（每机制8个）全部fail closed：响应注入lineage、响应注入搜索点、注入确定性机制、
  缺必填字段、重复参数、越界参数、禁止文本、重复证伪条件。
- R3C六份封存content在`network=none`下只读重放；未读reasoning、未修改正文、未去除字段、未重写
  schema_version，6/6仍未被v3录取，候选录取数0、修补/规范化数0。
- 原字段缺陷中的模式和搜索积已通过职责迁移消除；文本安全与缺必填等语义错误继续严格失败，不因恢复
  被放宽。

## 正式证据与幂等

- engineering report SHA-256：
  `095ebb49084010030e152bd85ee211f27c8e6e91c81036ccd20a190709a27f73`
- report payload SHA-256：
  `f1adfebb1f5a40cab8b252358a6e4e1e8e3155df84c6d0ed51ecb9252d0e8198`
- independent audit SHA-256：
  `e7c6c47d2ca06423cab43dc2a3cc07fe42a6d1396cbbb6940ba3b0274ded5a9e`
- 独立audit 11项全部PASS；完整重算与报告逐字段一致。
- 工程入口与audit入口各二次运行，两个文件哈希前后完全一致，write-once未产生替代版本。

旧输入复核仍为：proposal v2合同`53832677...09a0`、v2编译器`7a6c8f72...bd31`、候选validator
`dc3a19b7...b37b`、R3C两个账本`18d206fe...e14e`/`0da6ea6c...9446`、R3D report/audit
`4ba99d3b...717c`/`5007b045...5ddc`，与scope冻结值一致。

## 验证与隔离

- 专项测试：63 PASS（R3E、R3D和proposal回归）。
- 架构门：13 PASS；新生产模块分别338/263/91/71行，均低于400行常态上限。
- 全仓测试：1278 PASS，17条均为既有第三方弃用/数据类型warning。
- Ruff、Compose config、YAML解析、`git diff --check`均PASS。
- 正式工程与audit容器均`network=none`、只读根、`cap_drop=ALL`、无DeepSeek变量；只挂载R3C/R3D证据、
  两个旧账本和R3E输出，不挂`data/raw`、`.env`、行情或生产写路径。
- 外部调用0、secret读取0、行情/证券/收益读取0、参数搜索/回测0。
- 生产scheduler仍为原容器`183b8c6c5edd`、原镜像`shaiwei:scheduler-current`、创建时间
  2026-08-03 17:39:34 +0800，`healthy`，本目标未重启或替换。

## 下一合法节点

如继续，只能另立R3F小批live canary scope，结果前冻结确切席位、调用数、费用、发送内容、v3 request
bundle、镜像和release，并再次取得用户明确批准。建议先维持六个独立机制各1席、无递补和较低费用，
验证本地合同恢复是否真正提升有效proposal比例；不得把R3E GO直接解释为候选有效或启动参数搜索。
