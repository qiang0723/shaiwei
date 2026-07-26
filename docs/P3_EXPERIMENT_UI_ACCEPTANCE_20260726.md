# P3-4B 模型/回测页面 1.0 验收

> 验收日期：2026-07-26（Asia/Shanghai）
>
> 协议：`p3-experiment-ui-v1`
>
> 结果前冻结提交：`fcf7f38`
>
> 机器裁决：`GO`

## 1. 结论

P3-4B 已完成本机只读“模型/回测”目录与详情页，Web 1.0 的七类页面现已全部具备真实数据入口。
页面使用 P3-4A 的类型化实验目录与 P3-3B 的类型化详情，不扫描账本、研究目录、Parquet、模型或
原始 JSON，不运行模型、回测、G1 或 LLM，不重算策略结果，也没有获得交易、生产或远程访问授权。

验收裁决只说明页面工程、证据语义、只读边界、响应式和真实投影闭环通过，不说明任何策略有效。
当前中证800仍是唯一生产主策略；科创50 P2-2C 的权威历史结论仍为 `NO_GO / REJECT`。

## 2. 交付范围

新增页面：

- `/experiments`：后台精确筛选、固定排序、每页 25 条的实验目录；
- `/experiments/{experiment_kind}/{experiment_id}`：单请求、类型化实验详情。

桌面导航在“因子工厂”之后增加“模型 / 回测”。移动底栏仍为“总览 / 因子 / 组合 / 更多”，新页面
只进入“更多”，没有挤压 390 px 主导航。页面不提供搜索、客户端排序、表现筛选、成功率、排行榜、
最佳模型、跨实验比较、导出、调参或重跑。

目录首屏明确显示“实验记录不等于有效模型”，四类计数直接来自同一次后台目录响应。详情先显示
`outcome_status / authority_status / evidence_tier / lifecycle_status`，之后才显示冻结 decision、失败项
和证据。详情新增的 `outcome_status` 只复用目录同一个后台 `_experiment_outcome` 适配器；数值、权威、
生命周期、研究投影及其哈希输入均未改变。

## 3. 研究语义与 fail-closed

页面对十种证据层级分别渲染，不把它们压成同一种“回测”：

- 基线/影子只表示记录存在，不推断策略效果；
- GP/D1 是发现或复核层，不冒充 G1；
- G1 展示完整十五门，`REJECT` 是研究结果而非系统故障；
- P2 工程 GO 只证明工程通路；
- P2-2 原方法常驻“可复算、非权威”，并链接 P2-2C；
- P2-2C 显示当前权威历史 `REJECT`、三个冻结窗口、成本场景、回撤与精确表。

前端按 evidence tier 冻结 decision 顶层键，并进一步验证必需键、tier/outcome 组合、P2 权威/失效身份、
`STAR-W1/W2/W3` 顺序、pooled 交易日合计和 G1 十五门。未知字段、未知枚举、请求/响应 ID 不一致、
筛选或分页回显漂移、原始 `params_json/result_json`、逐日序列、持仓、预测或 `.BJ` 均 fail closed。
筛选或历史切片变化时立即清空旧页，再等待单一新响应；延迟响应 fixture 已锁定不得短暂复用旧证据。

实验详情没有逐日 NAV，因此页面明确说明不绘制净值、日回撤或交易时序。P2 窗口成本使用分组柱图，
并紧邻完整精确表；移动和 400% 回流下隐藏非必要图形但保留同一张数据表。

## 4. 真实证据身份

P3-4B 没有重建或改写研究投影，继续使用 P3-4A 的不可变真身：

- snapshot：`c2993c39c7c3aa5b28f975d02e6718ddc5aa8c2edebda294f88e0ba33d31e1fe`；
- bundle SHA-256：`cf72e70c9dadeac8782e892e4d132a4eec1b5371e82473a9206d206e15e4d773`；
- manifest SHA-256：`ca1e60d9ceed2ca99467562476ede20424cb5e9755290a59ee4b39268761292c`；
- 记录：783 条，其中通用研究 778、P2 工程 3、原 P2-2 与 P2-2C 各 1；
- 正式准入因子仍为 0。

真实浏览器从目录找到原 P2-2，核对 `INVALIDATED_METHOD`、三个窗口精确表和无 NAV 边界，再沿受控
successor 到 P2-2C，确认 `HISTORICAL_EFFECT_REJECTED`。真实 G1/因子页面也继续通过，证明新导航和
详情合同没有破坏既有研究入口。

## 5. 验证结果

- 宿主全仓 Python：299 passed；
- Docker 全仓标准入口 `python -m pytest`：299 passed；
- 前端 TypeScript/Vite 生产构建：PASS；
- 前端单元：22 passed；
- fixture 浏览器：63 passed、7 个按项目配置 intentional skip，覆盖
  1440/1024/768/390/320 CSS px、键盘、400% 回流、无页面级横向溢出与 axe；
- 真实部署浏览器：10 passed，覆盖桌面/移动、真实研究投影、严格 CSP、零外部 origin、页面入口、
  P2 失效/纠错和首屏性能；
- Ruff、compileall、宿主/最终 Web 镜像 pip check、Compose config、`git diff --check`：PASS；
- npm 生产依赖与完整依赖审计：均为 0 vulnerabilities；
- 跟踪文件未发现真实 token、Webhook 或签名；`.env`、数据、日志、构建和浏览器测试产物均保持忽略。

首次容器全仓命令直接调用 `pytest` 时，Python 控制台入口没有把 `/workspace` 放入 `sys.path`，导致
`tools` 在收集期不可见；改用仓库标准 `python -m pytest` 后 299 项全绿。这是验收命令入口差异，
没有修改依赖或测试。浏览器首轮还实际捕获并修正了空 `as_of` 回显、320 CSS px 长身份溢出和 warning
Tag 对比度三项问题，终版全绿。

## 6. Docker 隔离与主线不变证据

终版 Web 镜像内容 ID：
`sha256:2da4299a2a5fb9db832d82b74780eb2705a1bf9a27663823d91d9be073bcfad5`。

`web-query` 与 `web-ui` 均为 `10001:10001`、只读根、`cap_drop=ALL`、384 MiB 上限且 healthy。
query 没有宿主端口，只读挂载既有证据目录；UI 没有证据挂载，只绑定 `127.0.0.1:8080`。验收时两者
约 45.7 MiB，未放宽网络、端口、卷、Docker socket、密钥或写权限。

scheduler 施工前后保持：

- container：`fd8e96152b53f3f0d0efdcd6462c2b039aa68c7fb56461b95826709652a5adbb`；
- image：`sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`；
- created：`2026-07-24T12:25:27.362813588Z`；
- status：`healthy`。

本目标没有构建、重启或修改 scheduler，也没有修改 CSI800 配置、模型、G1、信号、生产数据、调度器
或追加式账本。

## 7. 保留边界

P3-4B 仍是本机只读研究证据页，不是模型管理平台或在线回测器。若未来需要逐日 NAV、参数详情、
跨实验严格比较、导出、研究重跑或新的指标，必须先由后台形成类型化、可追溯、结果前冻结的查询，
再另立协议；前端不得自行扫描、拼接或补算。
