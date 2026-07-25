# P3-1 Web 1.0 首批正式界面验收

> 验收日期：2026-07-25（Asia/Shanghai）
>
> 协议：`p3-web-ui-v1`
>
> 结论：`GO`
>
> 边界：只读本机 Web 首版 GO；不授权远程开放、交易、在线改参、导出、研究口径变更、
> scheduler 变更或生产策略变更。

## 1. 结果前冻结与实现身份

任何 P3-1 源码和真实页面构建前已提交并推送：

- 协议冻结：`b75b4b3`；
- 首轮路由依赖安全补遗：`84aa4f8`；
- 最终移除存在已知高危告警的第三方路由器：`3d19fab`；
- 终版实现提交：`133c6737a6b65dd1535d04532bab4525deb7e0d9`。

路由补遗没有改变页面、数据、状态、性能或 Docker 门槛。项目最终只保留同源固定路径
`/overview`、`/paper`、`/signals` 和根路径重定向；完整依赖与生产依赖 `npm audit` 均为
0 个已知漏洞。

## 2. 已交付页面

### 2.1 总览

- 只请求一次 P3-0 原子 `/api/v1/overview`，不在浏览器拼接多个“最新”；
- 顺序为综合结论 → 今日行动 → FORWARD 观察 → 组合/运行诊断 → 恢复历史 → 证据；
- 核心任务和飞书通知状态分列，先失败后恢复不会被最终 PASS 覆盖；
- 当前只有 2 个自然 FORWARD 账户日，成熟度保持 `OBSERVING`，不展示年化、Sharpe 或
  信息比率。

### 2.2 模拟组合

- 四个组合响应必须具有相同 schema、`snapshot_id` 和 `as_of`，否则页面级 `CONFLICT`；
- FORWARD 锚定结果与全账户 BACKFILL/FORWARD 审计分开；
- 目标、订单、成交、实际持仓和现金不混用；当前 API 未开放订单/成交明细时如实标注未开放；
- 持仓、账户日、费用、分红、重放与产物哈希均可下钻，图表提供同口径数据表。

### 2.3 股票池/信号

- 目标权重、最近实际权重和计划权重差并列；计划差不冒充订单或成交；
- `NOT_DUE` 时不预测停牌、涨跌停、真实开盘、成交、换手或成本；
- 没有后端因子贡献契约时明确显示“暂无可审计分解”，不生成前端解释；
- 未知状态、无效数字/哈希、跨快照或任一 `.BJ` 证券均 fail closed。

三页均支持 URL `as_of`、证据抽屉、键盘关闭后焦点返回、加载/刷新/错误/重试/空筛选状态。
刷新时保留上一份已核验证据并明确标出旧 `as_of/generated_at`；若刷新失败，旧数字从结论区
移除并显示稳定错误码和请求 ID。

## 3. 真实证据对账

终验使用 P3-0 同一真实原子快照：

- `as_of=2026-07-24`；
- `snapshot_id=1675b728a9a8134ea076f5adc94f2be54053a5aac3df13a7dd4c976d20473347`；
- 必需证据 `PASS`，账本重放 `PASS`，`.BJ=0`；
- 信号日和模拟账户日均为 `2026-07-24`，目标 30 只、实际持仓 22 只；
- 当期不调仓，执行证据 `NOT_DUE`；
- 综合状态为 `WARN`，原因是核心运行已从一次 `ForwardQlibError` 恢复、飞书有一次失败后恢复
  且保留重复投递风险；这不是 Web 查询失败，也没有被页面粉饰成全绿。

## 4. 浏览器、响应式与视觉

- fixture 浏览器回归：18 PASS、7 个有意 SKIP、0 FAIL。SKIP 仅来自刷新闭环只在桌面重复一次，
  axe 全页扫描只在 1440 和 390 两个代表视口执行；
- 视口覆盖：1440×900、1024×768、768×1024、390×844，以及 320 CSS px 的 400% 重排等价检查；
- 真实部署回归：桌面/移动共 6 PASS，覆盖三个真实页面、根路由、严格 CSP、外部请求、
  console/page error、axe 和首次内容绘制预算；
- axe critical/serious 为 0，外部 origin 请求为 0，CSP violation 为 0；
- 6 张终版桌面/移动视觉截图只保存在 Git 忽略的项目测试目录，人工复核信息层级、表格、图表、
  下钻和移动重排无阻断问题。

页面采用克制的浅色金融研究风格。原 Ant Table 会在运行时插入不带 nonce 的滚动条测量样式，
终版改为项目内原生语义表格，没有通过 `unsafe-inline` 放宽 CSP。

## 5. CSP、静态边界与依赖安全

- 脚本、连接和静态资源均为同源；无 CDN、远程字体、分析脚本或外部图像；
- `script-src` 不含 inline，`style-src` 使用每次响应随机生成、写入页面 meta 且与响应头一致的
  24 字符 nonce；连续两次真实请求 nonce 不同，构建占位符不会泄漏到客户端；
- CSP 不含 `unsafe-inline/unsafe-eval`，并固定 `object-src/base-uri/form-action/frame-ancestors`；
- UI 仅服务固定页面、哈希资源、健康检查与既有 API allowlist；其他路径 404，写方法 405；
- 静态单文件上限 3 MiB，代理响应上限 1 MiB；错误不返回栈、绝对路径或秘密；
- `package-lock.json` 完整固定传递依赖；全量与 production-only 审计均为 0 漏洞。

## 6. 性能与 Docker 隔离

Vite 按页面拆分，Charts 只在模拟组合页加载。终版构建：

- 首个页面所需资源保守合计约 270 KiB gzip，低于 600 KiB 门槛；
- 全部页面资源合计约 706 KiB gzip，低于 2.5 MiB 门槛；
- 最大图表分包 414.28 KiB gzip；构建无未解释大包告警；
- 本机真实桌面与移动首次内容绘制均通过 `≤2 秒` 浏览器硬断言。

终版镜像与运行边界：

- `shaiwei:web-v1` 内容身份
  `sha256:e9232bfd357f1b6c481525bcd09601a99bde4b92c6427ab3fb7bcd8df7b25a9d`；
- query 与 UI 使用同一镜像、`uid=10001:10001`、只读根、`cap_drop=ALL`、
  `no-new-privileges`、384 MiB/0.75 CPU/128 PID；
- query 无宿主端口，证据目录全部只读挂载；UI 无任何挂载，只绑定
  `127.0.0.1:8080`；
- 最终运行镜像不含 Node/npm、`.git`、`.env` 或 Docker socket；
- scheduler 始终为原内容镜像
  `sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`，
  原启动时间未变且 `healthy`，P3-1 未启动、停止、重建或换镜像 scheduler。

## 7. 验证清单

- 全仓 Python：214 PASS；
- P3 Web 查询/UI 专项包含在全仓测试中：8 PASS；
- 前端单元：7 PASS；
- fixture Playwright：18 PASS / 7 intentional SKIP / 0 FAIL；
- 真实部署 Playwright：6 PASS；
- TypeScript、Vite production build、Ruff、compileall、`pip check`、`git diff --check`：PASS；
- npm 完整依赖/生产依赖审计：0 / 0 漏洞；
- Git 脱敏与忽略边界：PASS，未跟踪 `.env`、data、logs、Node 模块、构建物、截图或浏览器产物。

唯一提示仍是 FastAPI TestClient 对当前 httpx 的上游弃用警告，不影响生产运行；没有为消除提示
擅自升级冻结依赖。

## 8. 当前边界与后续

P3-1 完成的是可真实使用的本机只读首版，不是完整七页平台。因子工厂、模型/回测、数据质量、
系统运行等页面仍须先有各自只读查询契约；认证、脱敏导出、局域网/公网、远程部署、交易与在线
改参均未授权。建议先用首版观察真实误读点和决策效率，再决定 P3 后续页面优先级，避免为“页面
齐全”反向污染后台主线。
