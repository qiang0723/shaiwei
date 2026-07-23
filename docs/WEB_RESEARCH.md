# Web 1.0 竞品与规范调研（持续更新；最近核查 2026-07-23）

> 调研只借鉴信息架构和交互，不复制品牌视觉、指标结论或产品代码。来源优先采用产品官方文档与 W3C 规范。

| 来源 | 借鉴什么 | 不照搬什么 | 对筛微的裁决 |
|---|---|---|---|
| [Grafana dashboard best practices](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/) | 仪表盘先回答问题、从总到分、减少认知负荷、面板说明、定向下钻、刷新频率匹配数据频率 | 监控大屏密度、自由编辑、把通用可观测性指标直接套到量化结果 | 首页只放决策指标和异常；Web 只读；按日数据不高频轮询 |
| [MLflow Tracking](https://mlflow.org/docs/latest/tracking) | 实验→run→参数/指标/代码版本/产物的可追溯层级；支持失败运行和比较 | 直接嵌入 MLflow UI；以“最佳 run”替代预注册门禁 | 模型页先判决和身份，再显示窗口结果；保留 REJECT/失败实验 |
| [QuantConnect backtest results](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results) | 结果页组合 equity、fees、orders、trades、logs 与项目文件；从曲线下钻到执行 | 将回测与真实/模拟前瞻混在一个视觉层；复制其指标集合 | 模型/回测与 PAPER/FORWARD 强制标签隔离；结果必须连接费用和订单 |
| [QuantConnect performance report](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/report) | 收益、回撤、滚动统计、暴露和危机区间分区；最大回撤定义清晰 | 前瞻样本不足时展示年化、Sharpe 或复杂统计 | Web 1.0 暂不显示前瞻年化/Sharpe；回撤独立副图，六窗口展示稳定性 |
| [Ant Design visualization principles](https://ant.design/docs/spec/visual/) | 准确、有效、清晰、克制；先总览、再筛选、按需详情；响应式图表布局 | 装饰性动效、为了统一而压缩量化语义 | 采用 Ant Design 组件与信息层级；准确性优先于视觉统一 |
| [Ant Design visualization page](https://ant.design/docs/spec/visualization-page/) | 关键 scorecard 和图表置顶，内容按优先级组织 | 固定模板或固定卡片数量 | 卡片数量由决策需要决定，总览优先结论/行动/结果 |
| [Ant Design Charts line chart](https://ant-design-charts.antgroup.com/components/plots/line) | 折线适合连续趋势，brush/filter 用于时段探索，双击复位 | 平滑曲线、面积填充或堆叠用于美化金融净值 | 净值用直线、默认不平滑不堆叠；交互后仍显示范围与口径 |
| [Lightweight Charts docs](https://tradingview.github.io/lightweight-charts/docs) | K线、时间轴、事件标记；公开使用必须满足 TradingView 归属 | 把 K 线作为总览主视觉；首版为了“像交易终端”而引入 | 仅在单股价格事件定位确有需求时引入；许可证归属作为实现门禁 |
| [Lightweight Charts accessibility](https://tradingview.github.io/lightweight-charts/tutorials/a11y/intro) | 官方明确其无内建无障碍语义，需要自行实现 ARIA 和替代内容 | 假设 canvas 图表天然可访问 | 首版通用量化图优先 Ant Charts；所有图表仍提供摘要/表格替代 |
| [WCAG 2.2 Use of Color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color) | 颜色不能是唯一信息通道 | 只用红/绿表达涨跌或 PASS/FAIL | 状态使用文字+图标+颜色；曲线兼用线型和直接标签 |
| [WCAG 2.2 Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) | 320 CSS px 宽度下非必要二维内容不丢信息、不双向滚动 | 把桌面大表整体缩小到手机 | 卡片单列重排；宽表仅在自身容器横向滚动并保留关键列摘要 |
| [WCAG 2.2 Status Messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages) | 动态结果、等待、错误应能被辅助技术识别，避免过度播报 | 每个行情或数值变化都触发 live region | 刷新完成用 `role=status`；阻断错误按需 `alert`；日频页面不连续播报 |
| [WCAG 2.2 Target Size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) | AA 最小目标 24×24 CSS px 或满足间距例外 | 以最低合规尺寸作为所有按钮目标 | 高频按钮目标至少 36×36，24×24 只作硬下限 |
| [WorldQuant BRAIN](https://www.worldquant.com/brain/) | 将数据、算子、alpha 构建、模拟、绩效面板和质量度量放在同一研究工作流 | 竞赛排行榜、数量激励、单一平台评分、看结果反复试表达式 | 因子工厂必须覆盖“假设→实现→模拟→判决”，但由预注册 G1 和实验总账裁决 |
| [WorldQuant alpha example](https://worldquantbrain.com/alpha-examples) | 在结果旁常驻数据类别、delay、neutralization、decay、持仓约束、覆盖和换手 | 继承其示例 Sharpe/收益、做多做空或阈值 | 因子身份区常驻数据时点、中性化、方向和约束；筛微仍用 A 股冻结口径 |
| [Qlib workflow](https://qlib.readthedocs.io/en/latest/component/workflow.html) | 数据处理、训练/推理、信号分析和回测构成可追踪 execution | 直接暴露 qrun 配置为在线改参入口 | 因子详情连接数据、模型、评估和产物，但 Web 保持只读 |
| [Qlib Recorder](https://qlib.readthedocs.io/en/stable/component/recorder.html) | ExperimentManager → Experiment → Recorder 的层级，以及参数、指标和产物版本 | 直接嵌入 MLflow UI 或只保留成功 run | 因子目录下钻实验和 run，失败尝试也进入 N 和历史 |
| [Alphalens](https://quantopian.github.io/alphalens/) | tear sheet 将收益、IC、换手和分组分析组织为一致页面 | 默认美股/多空/分位口径及过时视觉样式 | 借鉴 tear sheet 信息结构；计算完全服从筛微 horizon、中性化和 G1 |
| [Alphalens API](https://quantopian.github.io/alphalens/alphalens.html) | IC 时序/分布/月度热力、分位收益 spread、分位换手和自相关互相解释 | 只看 IC 均值或累计收益；无条件使用重叠组合算法 | 每个 factor tear sheet 必须同时显示预测力、单调性、稳定性和可交易性 |
| [QuantRocket factor analysis](https://www.quantrocket.com/docs/api/) | 因子信息、收益和换手 tear sheet；支持 group neutral 和相对收益参数显式化 | 参数扫描直接进入生产研究流程 | 对比页必须锁定 universe、horizon、中性化和成本，不可比即拒绝 |
| [MSCI Barra equity factor models](https://www.msci.com/data-and-analytics/factor-investing/equity-factor-models) | 将因子暴露、风险、收益归因和非预期押注联系起来 | 复制商业模型、因子定义或黑箱风险分数 | 正式入库后展示暴露与组合增量归因；无正式因子时显示 N/A |
| [BlackRock Aladdin Risk](https://www.blackrock.com/aladdin/platforms/products/aladdin-risk) | 整体组合视角下统一展示持仓、暴露、风险、绩效归因和压力情景 | 复制黑箱模型、机构级多资产复杂度或允许页面修改假设 | 保持“一个账户、一套身份、一致数据语言”；先解释暴露和结果来源，情景模拟不进入 Web 1.0 |
| [BlackRock Aladdin Accounting](https://www.blackrock.com/aladdin/platforms/products/aladdin-accounting) | IBOR/ABOR/PBOR 的统一视图、锁定期间结果、质量控制和对账 | 引入本项目不需要的会计体系或合规营销报告 | 模拟仓继续以追加账本、独立重放和账户恒等作为唯一结果真身 |
| [OpenBB widget anatomy](https://docs.openbb.co/workspace/analysts/widgets/overview) | 每个 widget 包含数据源、元数据、视觉和参数；共享参数可同步分析上下文 | 自由添加数据源、任意 widget、AI 自动调用敏感数据 | 筛微每张卡只回答一个问题并携带来源/时点；仅同步受控 `as_of/account_id` |
| [OpenBB dashboards](https://docs.openbb.co/workspace/analysts/dashboards) | 通过布局面积和位置建立视觉优先级，组合表格与图表形成工作流 | 用户自由拖拽导致冻结布局漂移，自动刷新所有组件 | v1.0 使用固定、经过验证的布局；刷新频率服从日频数据时钟 |
| [OpenBB sandbox guidance](https://docs.openbb.co/workspace/analysts/widgets/sandbox-widgets) | 示例组件明确说明只是演示，不应直接作为生产分析工具 | 把示例数据或 sandbox 画板冒充生产能力 | 可点击原型始终标“示例”，只有冻结查询接入后才称真实页面 |
| [Andrew Lo, The Statistics of Sharpe Ratios](https://alo.mit.edu/publications/page/18/) | Sharpe 估计受抽样误差和序列相关影响，常见年化换算只在特殊条件下成立 | 对短样本或有自相关的日收益直接乘 `sqrt(252)` | 1 年前不展示年化；风险调整指标至少 2 年/40 调仓周期，并要求后台冻结序列相关修正；这是项目保守推断，不是论文给出的固定天数 |
| [FastAPI in Containers](https://fastapi.tiangolo.com/deployment/docker/) | 从官方 Python 镜像构建独立容器；前后端可拆成不同服务 | 复用已弃用的通用 FastAPI 基础镜像或把生产目录整体挂进容器 | 查询适配层独立构建，只包含代码/config 和 allowlist 只读数据挂载 |
| [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/) / [Trusted Host](https://fastapi.tiangolo.com/advanced/middleware/) | CORS 应明确列出 origin，Host 应受控 | `allow_origins=["*"]` 或把查询端口直接暴露给宿主/局域网 | 首版由 web-ui 同源反向代理 API，查询服务不映射宿主端口；未来跨源时显式 allowlist |
| [Docker Compose profiles](https://docs.docker.com/compose/how-tos/profiles/) / [services reference](https://docs.docker.com/reference/compose-file/services/) | profile 使可选服务默认关闭；`read_only` 和只读 bind mount 提供隔离能力 | 误以为启用 profile 只会启动 profile 服务；继承带 `.env` 和整仓写挂载的生产公共配置 | Web 命令显式点名两个服务；单独 Web 公共配置，根文件系统/数据挂载只读，无 Docker socket |

## 结论

主流范式一致指向“摘要优先、范围明确、可下钻、证据可追溯”。专业因子工厂还必须把数据/算子、经济假设、IC、分位收益、稳定性、换手、相关性、成本、组合增量和准入历史串成研究生命周期。筛微需要比常规金融面板更严格地区分 BACKTEST/BACKFILL/FORWARD、目标/计划交易腿/订单/成交/持仓，以及任务/通知状态。视觉上采用中性、克制、桌面优先风格；产品差异化来自预注册门禁、失败留痕、独立增量和真实前瞻证据，而不是高饱和行情大屏或 alpha 排行榜。技术上，当前账户的 BACKFILL 初始化意味着 FORWARD 主结果必须另设锚点，不能把全账户累计净值差改名后直接展示。

## 冻结后调研规则

- 本文可以持续追加官方来源，但不能凭竞品截图直接改动 v1.0 基线。
- 新范式先判断是否提高决策速度、统计诚实性、证据追溯、可访问性或工程隔离；不能改善其中至少一项则不进入提案。
- 第一版实现前优先发现阻断性缺口；实现后优先使用真实操作证据和浏览器 QA，而不是继续堆叠竞品功能。
- 任何建议必须标记为 `OBSERVE / PROPOSE / ACCEPT / REJECT`，只有 `ACCEPT` 且完成主控复核后才改变下一设计版本。
