# M5-0 多股票池策略工厂只读工程验收

> 验收时间：2026-08-05T11:22:53+08:00
> 协议：`m5-strategy-factory-contract-v1`
> 终态：`GO_STRATEGY_FACTORY_CONTRACT_AND_READ_ONLY_PROJECTION_ONLY`

## 1. 裁决

M5-0 通过。筛微已把八个登记股票池、六类研究家族、八个既有研究工作包、四类尝试计数、证据层、
权威裁决和下一合法动作，统一为内容寻址的只读策略工厂投影，并在本机 Web 新增“策略工厂”页面。

本裁决只证明合同、证据投影、查询和展示工程可用，不表示任何新因子或策略有效。当前真实事实仍为：

- 登记股票池 8；
- 可建立研究草案 5；
- 数据/PIT 阻断 3；
- 既有生产策略 1，仍只有中证800主策略；
- 正式因子准入 0；
- 活跃授权研究任务 0。

页面内“建立研究草案”只生成浏览器临时预览，固定显示未提交、未冻结、未运行；没有写 API、任务队列、
Worker、DeepSeek 调用、真实候选生成、收益读取、模型、回测、前瞻或生产授权。

## 2. 交付范围

### 2.1 结果前合同与专项设计

- `docs/M5_STRATEGY_FACTORY_PROTOCOL_20260805.md`
- `config/m5_strategy_factory_v1.yaml`
- `docs/M5_MULTI_POOL_RESEARCH_GOVERNANCE_20260805.md`
- `docs/M5_MULTI_POOL_BACKEND_ARCHITECTURE_20260805.md`
- `docs/M5_MULTI_POOL_WEB_PRODUCT_20260805.md`

协议与配置已在实现前由提交 `7639dbd` 推送；最终验收时配置相对该冻结提交零改动。

### 2.2 内容寻址投影与查询

- 严格合同模型拒绝未知枚举、重复身份、状态越权和计数冲突；
- 投影器只读取冻结配置、白名单证据和 `ledger/factor_admissions.csv`，逐文件重算 SHA-256；
- 路径逃逸、symlink、证据漂移、`.BJ`、M1 身份冲突和正式准入计数冲突均失败关闭；
- 投影器断网、非 root、只读根，只对 `data/web/research_snapshots` 窄写；全部输入挂载
  `create_host_path=false`；
- 查询只开放 `GET/HEAD /api/v1/strategy-factory`，未知参数 422，写方法 405；
- 查询重新验证 pointer、snapshot、内容哈希、冻结计数和不变量，不扫描生产目录拼接“最新”。
- 运维入口固定为 `make docker-web-strategy-factory-project`，只运行上述断网一次性投影服务。

最终投影身份：

- `snapshot_id=b24142867cf6e68b30724dd8d38a4864c2898e995de3bbf89bd2ea02594af9b3`
- snapshot SHA-256：`83bb3d46e4fc46d450f3e13496d8ecb10b49ca48f86f3536399ea9503e64bcc3`
- pointer SHA-256：`e752cf477fa0276d42b27a22157a4c8977ed7a46c0599e33a530d37ddfdde629`

投影入口终版断网复跑返回相同 `snapshot_id` 与 snapshot SHA，未新增内容或改写旧快照。

### 2.3 Web 页面

本机入口：`http://127.0.0.1:8080/strategy-factory`。

页面按“当前裁决 → 股票池地图 → 股票池×研究家族 → 既有工作包 → 本地草案 → 当前授权任务”组织，
不按收益排序、不制造综合分、排行榜、明星因子或一键回测/上线。REJECT、合同停止、数据阻断和
`NOT_EVALUATED` 均在主视图保留；机器枚举、路径和完整哈希只进入技术证据。

浏览器草案最多选择三个当前可研究池，候选上限只允许 8/12/24；点击只更新浏览器内存，不产生表单、
POST、任务 ID 或外部请求。1440/1024/768/390/320 五档均无页面级横向溢出。

## 3. 验收证据

### 3.1 自动化与浏览器

- Python 全仓：599 PASS；仅保留 1 条既有 Starlette 第三方弃用 warning；
- 新后端/API 专项：5 PASS；Compose 隔离专项并入全仓；
- 前端单元：28 PASS；
- 五视口 fixture Playwright：69 PASS、11 个按视口条件设计的 skip；
- 真实只读部署 Playwright：14/14 PASS，覆盖桌面/移动、严格 CSP、同源零外联、真实七类页面、
  策略工厂证据、Top20 最新 FORWARD 口径和 FCP；
- axe：桌面与移动 serious/critical 均为 0；
- 交互式浏览器复核：五档零横向溢出，本地草案按钮唯一且点击后仍无提交/冻结/运行语义；
- TypeScript/Vite 生产构建、Ruff、compileall、pip check、两组 Compose config 和 `git diff --check`
  全部 PASS。

### 3.2 代码可维护性

策略工厂生产文件均小于 400 行：后端 193/256/320 行，页面与展示组件 155/261 行，样式按职责拆为
282/241 行；没有继续扩大既有查询和页面热点职责。未来写控制面仍须独立为 `research-control`，不得给
现有 `web-query` 增加 POST。

### 3.3 安全与运行隔离

- 新增文件与差异未发现 DeepSeek、Tushare、飞书 webhook 或签名凭据；
- 原始研究数据、snapshot、日志和凭据均未加入 Git；
- Web 最终镜像：`sha256:899e4be78352949598475abfba66ea80d13aed8c01d1a8e118bd54e6cb7960b8`；
- `web-query=7fbb2171dd4f`、`web-ui=b974da5ca3a3`，均 healthy；query 无宿主端口，UI 仅绑定
  `127.0.0.1:8080`；
- scheduler 始终为容器 `183b8c6c5edd`、镜像
  `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`、创建时间
  `2026-08-03 17:39:34 +0800 CST`、代码快照
  `4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708`，施工前后未重启且 healthy。

## 4. 验收中发现并闭环的问题

1. 旧 Compose 白名单测试未登记新的一次性投影服务。已把它纳入默认关闭、断网、非 root、只读根、
   无 secret/端口/Docker socket、仅输出目录窄写的同级硬约束。
2. 首轮 axe 发现策略工厂 11/12px 辅助文字对比度约 3.7—4.39:1。已统一加深，完整五视口复跑后
   serious/critical 为 0。
3. 真实数据增长后 Top20 已从 BACKFILL 进入 FORWARD，旧 E2E 和页面文案仍假定“只有工程回放”。
   已改为由真实账户证据决定状态；存在 FORWARD 时明确说明“已开始自然前瞻，但样本仍不足”，不把
   正常数据前进误判为故障，也不提前宣称策略优劣。

## 5. 后续边界

M5-0 到此停止。下一阶段若要让 Web 真正提交研究，必须另立 M5-1 协议，建设独立控制面并继续保持：
一个有界批次、四维身份、四类尝试计数、五类独立授权、结果终态不自动派生下一批。M5-1 获批前，
策略工厂只负责看清证据和形成临时草案。
