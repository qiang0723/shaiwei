# M5-0 多股票池策略工厂合同与只读工程协议

> 协议 ID：`m5-strategy-factory-contract-v1`
>
> 冻结时间：2026-08-05T10:25:18+08:00
>
> 权威范围：M5-0 合同、证据投影、只读查询与本机 Web 展示

## 1. 裁决

M5-0 只建设“多股票池研究如何被登记、比较、追踪和展示”的可信底座。本批允许把既有 M1—M4、
P1/P2、F1/F2 的权威证据投影为一个内容寻址、只读的策略工厂快照，并在 Web 中提供研究地图、
研究家族矩阵、历史任务/裁决和浏览器内临时研究草案。

本协议不授权真实候选生成、DeepSeek 或其他外部调用、数据采集、标签/收益读取、模型训练、回测、
模拟仓新增、前瞻、生产发布或 scheduler 改动。Web 继续只允许 `GET/HEAD`；临时草案不持久化、
不冻结、不排队、不执行。

M5-0 通过后的唯一终态为：

`GO_STRATEGY_FACTORY_CONTRACT_AND_READ_ONLY_PROJECTION_ONLY`

该终态不表示任何因子或策略有效，也不推出 M5-1 写控制面、Worker 或真实研究授权。

## 2. 设计依据

本协议吸收并冻结三份专项设计：

- `docs/M5_MULTI_POOL_RESEARCH_GOVERNANCE_20260805.md`：四维身份、尝试数、状态机、授权分离；
- `docs/M5_MULTI_POOL_BACKEND_ARCHITECTURE_20260805.md`：只读证据面与未来独立控制面的隔离；
- `docs/M5_MULTI_POOL_WEB_PRODUCT_20260805.md`：研究地图、坏消息、草案与执行语义。

三份专项文档是设计输入，不单独授权施工范围。发生冲突时以本协议为准。

## 3. 当前事实与展示口径

### 3.1 股票池

M1 冻结注册表仍是八个股票池的身份底座，禁止原地改写。M5 通过追加式权威状态覆盖表达后续进展：

| 股票池 | 当前数据/PIT状态 | 当前研究边界 |
| --- | --- | --- |
| 中证800 | `READY` | 唯一既有生产主策略；可另立新研究协议 |
| 科创50 | `READY` | P2基线与M4残差候选权威REJECT；可另立独立机制新批 |
| 科创100 | `BLOCKED_OFFICIAL_LINEAGE` | 策略`NOT_EVALUATED`，不可发起因子研究 |
| 科创200 | `BLOCKED_OFFICIAL_LINEAGE` | 二级源门PASS但官方PIT谱系NO-GO，策略未评价 |
| 科创综指 | `DATA_GATE_REQUIRED` | 尚未完成数据门，策略未评价 |
| 科创板全市场PIT研究池 | `READY` | `CUSTOM_RULE_BASED`；M3发现Top2后审查合同STOP |
| 科创板中盘PIT研究池 | `READY` | `CUSTOM_RULE_BASED`；M3发现Top2后审查合同STOP |
| 科创板小盘PIT研究池 | `READY` | `CUSTOM_RULE_BASED`；M3发现Top2后审查合同STOP |

因此首版固定显示：登记 8、研究草案可选 5、数据/PIT阻断 3、既有生产 1。任何 `.BJ` 证券、
身份冲突、证据哈希失配或未知枚举均使整份投影失败关闭。

### 3.2 研究事实

首版只登记已有权威研究工作包，不扫描目录推断“最新”：

- 中证800 Alpha158/LightGBM 既有生产基线；
- P1 中证800资金流六候选：REJECT；
- F1 中证800静态基本面六候选：REJECT；
- F2 中证800动态基本面六候选，其中五项进入效果门：REJECT；
- P2 科创50基线：权威纠错后REJECT；
- M1 科创50价量发现：40响应、Top2锁定，审查合同STOP，效果未评价；
- M3 三自建池价量发现：24响应、Top2锁定，审查合同STOP，效果未评价；
- M4 科创50残差三候选：方向2/3、适配效果门0/3，REJECT。

正式因子准入数从 `ledger/factor_admissions.csv` 独立核验，当前必须为 0；实验记录数、候选数、
生成响应数和跨池评价单元不得称为“有效因子/有效模型”。当前活跃授权执行任务必须为 0。

## 4. 身份与状态合同

### 4.1 四维正交身份

完整策略由 `UniverseVersion × FactorDefinitionVersion × ModelDefinitionVersion ×
PortfolioPolicyVersion` 组成。任一维的规则、参数、时间、成本或执行变化都产生新版本，不能在旧身份
下覆盖。因子在一个股票池通过，不自动推出模型、组合、前瞻或生产资格。

### 4.2 四个状态轴

Web 和 API 必须分开表达：

1. `lifecycle_state`：流程阶段；
2. `evidence_tier`：证据支持到哪一层；
3. `authoritative_outcome`：当前权威结论；
4. `production_authorization`：生产权限，M5-0 恒为 `none`，中证800只保留既有生产事实。

`BLOCKED_*`、`STOPPED_CONTRACT`、`REJECT`、`INVALIDATED_METHOD` 和 `NOT_EVALUATED` 不能互换。
数据 GO 不等于策略 GO，研究 REJECT 也不推翻数据/PIT可用性。

### 4.3 尝试数

`generation_attempt_count`、`evaluation_unit_count`、`effect_test_count`、
`engineering_attempt_count` 必须分列。同一候选预注册多个股票池只增加评价单元，不增加生成尝试；
相同身份的幂等复跑不增加研究N。

## 5. M5-0 数据合同

新增 `config/m5_strategy_factory_v1.yaml`，它是首版策略工厂目录与 authority overlay 的冻结输入。
配置必须：

- 绑定本协议和全部白名单证据的项目相对路径与物理 SHA-256；
- 复用 M1 八个稳定 `universe_id`，不得新增或改名；
- 对后续状态使用显式 overlay，不改写 M1；
- 登记已有研究工作包、股票池、机制家族、尝试计数、证据层和权威结论；
- 固定 `external_calls_authorized=false`、`real_research_authorized=false`、
  `write_api_authorized=false`、`production_authorization=none`；
- 固定浏览器草案为 `DRAFT_NOT_SUBMITTED`，刷新可丢失。

一次性投影器只读取该配置、白名单证据和 `factor_admissions.csv`，逐项重算哈希后生成：

```text
data/web/research_snapshots/strategy_factory/
  snapshots/<snapshot_id>.json
  latest.json
```

`snapshot_id` 是规范内容哈希；相同输入二次运行必须字节不变并复用。正式快照和指针均不得覆盖成
不同内容；路径逃逸、symlink、文件缺失、哈希漂移、重复ID、状态越权和计数冲突全部失败关闭。

## 6. 只读查询与 Web

M5-0 只新增：

- `GET/HEAD /api/v1/strategy-factory`：原子返回总览、股票池、研究工作包、研究家族矩阵、准入事实、
  当前任务和草案模板；
- `/strategy-factory`：本机只读策略工厂页面。

查询不接受表现排序、不拼生产SQL、不扫描Parquet/账本/文档，不返回原始行情、证券清单、绝对路径、
provider原文或凭据。未知或重复参数返回422；POST/PUT/PATCH/DELETE继续405。

页面首屏固定回答：哪些股票池可研究、哪些被阻断、当前最重要的坏消息、正式准入数、生产策略数和
活跃授权任务数。页面顺序为：

`结论与需关注 → 股票池研究地图 → 股票池×研究家族 → 历史工作包 → 临时研究草案 → 技术证据`

草案只允许选择后端返回的 eligible 股票池和冻结研究家族；生成浏览器内预览，明确显示
`未提交 / 未冻结 / 未运行 / 零外部调用 / 生产授权none`。不得伪造任务ID、排队状态或执行按钮。

## 7. 未来真实执行的独立门

M5-1及以后若开放写能力，必须新增独立 `research-control`，不得给现有 `web-query` 增加POST。
真实研究至少拆成五项不能互相推导的批准：

1. `protocol_freeze_approval`；
2. `external_call_approval`；
3. `sealed_effect_open_approval`；
4. `forward_account_approval`；
5. `production_release_approval`。

每个真实协议必须冻结研究域、股票池矩阵、候选/响应上限、尝试背景、多重检验、数据与封存窗口、
费用/资源/时限和停止条件。终态不得自动生成下一批，剩余预算不结转；定时任务只允许维护数据和证据，
不得自产新假设；LLM无追加候选、开封效果、准入或上线权。

## 8. 验收条件

### 8.1 后端与证据

- 八个股票池身份与M1一致，当前overlay与白名单证据一致；
- 研究草案可选5、阻断3、生产1、正式准入0、活跃授权任务0；
- 投影双跑字节与哈希一致，篡改、路径逃逸、symlink、`.BJ`和状态冲突失败关闭；
- API包络、ETag、1MiB上限、GET/HEAD和错误语义延续P3合同；
- 无SQLite、无真实研究账本、无Worker、无网络、无secret读取。

### 8.2 Web与产品

- 正式库0、P1/F1/F2/P2/M4 REJECT、M1/M3 STOP和阻断池无需筛选即可看到；
- 不出现综合分、成功率、排行榜、最佳因子、一键回测或一键上线；
- 草案与提交/冻结/执行语义明确分开，网络记录保持零写请求；
- 1440/1024/768/390/320无页面级横向溢出，键盘可达，axe serious/critical为0；
- 主视图用中文业务语义，机器枚举、路径和完整哈希只放技术证据。

### 8.3 工程与隔离

- 新生产文件职责单一，常态不超过400行，不扩大既有热点职责；
- 全仓测试、专项测试、Ruff、compileall、pip check、Compose与脱敏检查通过；
- Web投影器断网、非root、只读根，只对白名单输出目录窄写；
- scheduler容器、镜像、创建时间和健康状态施工前后不变；
- 所有改动提交并推送，工作树干净。

## 9. 停止条件

发生任一项立即停止，不以旧快照或部分数据降级展示：证据哈希不符、M1身份不一致、`.BJ`非零、
正式准入计数冲突、策略工厂快照不同内容同ID、Web发出写请求、scheduler身份变化、凭据或原始研究
数据进入Git。

