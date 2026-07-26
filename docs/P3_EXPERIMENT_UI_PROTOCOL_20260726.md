# P3-4B 模型/回测页面协议（结果前冻结）

> 冻结日期：2026-07-26（Asia/Shanghai）
>
> 协议：`p3-experiment-ui-v1`
>
> 状态：`FROZEN_BEFORE_IMPLEMENTATION`

## 1. 目标与第一原则

P3-4B 把 P3-4A 的实验目录和 P3-3B 的类型化详情接成本机只读“模型/回测”页面。页面首先回答：
**“这是什么证据、当前是否权威、能否用于研究结论？”**，之后才展示后台已经登记的数值。

当前 783 条记录不是 783 个模型，也不是 783 个有效回测。它们包括失败运行、GP/LLM 发现尝试、
G1 判决、影子信号、工程门、失效方法和一项权威历史效果裁决。页面不得把它们压平成成功率、收益
排名、模型榜单或“最佳策略”。

本目标不运行模型、回测、G1 或 LLM，不重算指标、NAV、持仓、基准或策略效果，不修改研究证据、
权威覆盖、G1、策略、信号、生产数据、scheduler 或追加式账本；不提供编辑、调参、重跑、导出、
远程访问、交易或生产控制。

## 2. 结构审计

只读结构审计确认当前投影共有 783 条记录：778 条通用研究实验、3 条 P2 工程运行、原 P2-2 与
P2-2C 各 1 条。`kind × evidence_tier × outcome × authority × lifecycle` 有 19 种实际组合；当前
实验 ID 长度 12—43，全部满足 `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`，不含 `/` 或 `%`。

审计只查看字段集合、类型和计数，没有为页面重新计算或选择策略结果。现有详情覆盖十种证据层级：
基线回测、普通/前瞻影子、G1、两类 GP、D1、P2 工程、P2 权威效果和 P2 失效效果。只有 P2 效果
详情登记了窗口/成本/回撤聚合；没有任何实验详情提供逐日 NAV，因此页面不得伪造净值曲线。

## 3. URL、数据源与窄增补

可复核页面固定为：

- `/experiments`：实验目录；
- `/experiments/{experiment_kind}/{experiment_id}`：实验详情。

页面只消费：

- `GET /api/v1/experiments`；
- `GET /api/v1/experiments/{experiment_kind}/{experiment_id}`。

前端不得扫描投影、账本、Parquet、模型或研究目录。动态 kind 只允许四个冻结值，ID 必须满足上述
安全 slug；前后端代理都做精确路径限制。

当前目录行有 `outcome_status`，详情响应没有。若用户直接打开详情深链，前端只能复制后台映射才能
恢复 outcome，存在漂移风险。P3-4B 只授权一个传输窄增补：`experiment_summary` 复用后台同一个
`_experiment_outcome` 适配器增加 `outcome_status`。它不读取数值作标签、不改变 authority、
lifecycle、decision、投影或哈希输入。

## 4. 目录页

首屏固定说明“实验记录不等于有效模型”。关键事实只使用单次目录响应中的投影总数、历史切片数、
筛选后数量和四类 kind 计数；不得用当前页 25 行外推全局 outcome 比例。

筛选只使用后台 `available_filters` 的真实枚举，支持 kind、研究家族、证据层级、权威状态、生命周期、
outcome 和证据状态；`as_of` 由全局查询截止日期提供。目录固定 limit=25，offset 后台分页；任一筛选
变化重置 offset=0。URL 保留筛选和 offset，便于复核与返回。

目录保持后台 UTC 时间降序、kind、ID 的稳定顺序，不提供搜索、客户端排序、表现筛选或跨页合并。
翻页只显示一个快照的当前页；快照变化时清空旧页后重查。桌面用宽表，移动用证据卡；两者都显示
outcome、authority、tier、family、记录时间、模型/引擎、失败原因数和证据状态，不显示数值业绩。

## 5. 详情页与状态语义

详情只发一个请求，响应 kind/ID 必须与 URL 完全一致。首屏顺序为：

1. outcome、authority、evidence tier 和 lifecycle；
2. 这条证据允许/不允许得出的结论；
3. 实验身份、家族、模型/引擎、训练/验证区间、seed、代码与数据身份；
4. 按 tier 类型化的已登记 decision；
5. 失败原因、方法有效性和证据来源。

页面头部状态仍来自响应 meta 的证据新鲜度；研究 outcome 使用独立徽标，不把 REJECT 当成系统
FAIL，也不把工程 GO、发现记录或影子信号解释成策略有效。`FAILED` 只表示登记的执行失败。

特殊边界必须常驻：

- `INVALIDATED_METHOD`：先显示方法失效阻断，数值只能标“可复算、非权威”，并在合法 successor
  身份存在时提供 P2-2C 链接；
- `PROVISIONAL_HISTORICAL`：只证明历史工程记录，不是当前工程裁决，更不是效果结论；
- `ENGINEERING_GO_ONLY`：只证明工程通路；
- `DISCOVERY_ONLY/DISCOVERY_REJECTED/REVIEW_STOPPED`：发现或复核层，不是 G1；
- `RECORDED`：只说明基线/信号已经登记，不推断策略有效；
- `G1_REJECTED/HISTORICAL_EFFECT_REJECTED`：明确显示已有拒绝结论及失败项，但不以红色系统故障
  语义呈现。

## 6. 已登记数值和图表

decision 顶层键按 evidence tier 使用冻结 allowlist；出现未知键、未知 outcome 或未知组合时前端
`EVIDENCE_MISMATCH`，不做通用 JSON dump。布尔、字符串、有限数值、数组和嵌套对象均须类型校验；
禁止 `params_json/result_json/daily_series/predictions/holdings`。

- G1：显示记录判决、尝试 N 和完整十五门；
- GP：显示已登记的 RankIC 聚合，常驻“发现层、非 G1”；
- D1：显示发现/复核/生产授权状态，不显示不存在的业绩；
- 基线/影子：显示状态、行数、调仓标记和信号身份，不将其当效果；
- P2 工程：显示工程、fixture、幂等和是否看过策略结果；
- P2 效果：窗口 × 基础/1.5×/2×/额外滑点使用分组柱图并紧邻精确表，回撤保留精确表；
  失效方法的全部数值区常驻“可复算、非权威”。

没有逐日 NAV、逐日持仓或基准序列，因此不画策略/基准净值、日回撤或交易时序。图表不得以 0
补缺，必须提供等价表格和明确单位。

## 7. 历史视图、导航与响应式

历史 `as_of` 常驻 `CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS`：事件按查询截止裁剪，但
authority 使用当前已知纠错。它不是当时权威状态的重演。详情若在 `as_of` 前不存在则 404，不回退
最新。

桌面导航把“模型/回测”加入“研究”组，位于因子工厂之后；移动底栏继续保持“总览 / 因子 / 组合 /
更多”，模型/回测进入“更多”，避免挤压 390 px。全局日期在 `/experiments` 路径显示“查询截止”。

1440/1024/768/390、320 CSS px 与 400% 缩放必须无页面级横向溢出；宽表只在自身容器滚动。键盘
可完成筛选、翻页、进入/返回详情和证据抽屉；图表有文本说明和等价表；axe serious/critical 为 0。

## 8. 安全、性能与验收

UI 只新增固定 `/experiments` 和严格 kind/ID 动态详情路径；API 代理同样精确限制。GET/HEAD、1 MiB
响应上限、同源 CSP、零外部资源、无 `.env`/Docker socket/宿主 query 端口、非 root、只读根和
`127.0.0.1:8080` 保持不变。

通过条件：

1. 本协议与机器配置先提交并推送，再改详情、代理和前端；
2. 目录筛选/分页全部由后台执行，ID 与详情一致，不跨快照拼页；
3. 十层证据与所有当前结构组合至少 fixture 覆盖，未知键/状态 fail closed；
4. 失效方法、provisional、工程、发现、G1 和权威效果语义不混淆；
5. 不展示未登记 NAV、参数 JSON、结果 JSON、排行榜、最佳模型或跨实验比较；
6. fixture 覆盖筛选、分页、历史、空态、详情、失效 successor、错误、刷新、键盘和 axe；
7. 真实投影完成目录与 G1、P2 工程、P2 失效、P2 权威效果等代表详情闭环；
8. TypeScript/Vite、前端单元/浏览器、全仓 Python、Ruff、compileall、依赖、Compose、脱敏与
   `git diff --check` 全部通过；
9. Web 容器资源和隔离不放宽，scheduler 容器、镜像、创建时间和 healthy 状态施工前后不变。

## 9. 停止条件

若页面需要逐日序列、新指标、模型参数、跨实验比较、表现排名、浏览器补算、原始文件扫描、任意
代理或 Docker 隔离放宽，立即停止并回主控裁决。不得用“页面更完整”填充不存在的证据。
