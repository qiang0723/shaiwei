# P3-2B 数据质量与系统运行页面验收

> 验收日期：2026-07-25（Asia/Shanghai）
>
> 协议：`p3-web-operations-ui-v1`
>
> 结论：`GO`
>
> 边界：两个本机只读运维证据页面 GO；不授权远程开放、日志/文件浏览、导出、重跑、写接口、
> scheduler 控制、交易、在线改参或生产策略变更。

## 1. 结果前冻结与范围

页面源码、UI 代理变更和真实构建之前，协议与机器配置已由提交 `fa63883` 推送至 `origin/main`。
本阶段严格复用 P3-2A 已验收的三个只读入口：

- `/data-quality` 只消费一次 `GET /api/v1/data-quality`；
- `/system-runs` 只消费一次 `GET /api/v1/system/runs`；
- 稳定消息 ID 的通知详情按用户点击读取
  `GET /api/v1/notifications/{message_id}`，保持独立 `snapshot_id/as_of/generated_at`，不合并进
  系统页主结论。

未修改 P3-2A schema、查询公式、scheduler、生产镜像、策略、模型、信号、门禁、原始数据或
追加式账本。

## 2. 已交付页面

### 2.1 数据质量

- 第一视觉焦点把“数据门 PASS”和“证据 WARN”并列，PASS 不覆盖证据缺口；
- 展示最新完整交易日、当日行数/批次、登记总批次/总行数和数据快照；
- 完整呈现 S1—S10，S10 `NOT_APPLICABLE` 不误报为失败；
- 当日批次、来源、采集时刻、内容哈希和登记身份链均可核对；
- 常驻展示 `SENTINEL_REPORT_NOT_HASH_BOUND`、`IDENTITY_MATCH_UNHASHED`、
  `raw_parquet_rehash_status=NOT_EVALUATED` 和未挂载 `data/raw`；
- `.BJ` 三层计数必须全部为 0，且不把返回计数 0 冒充原始 Parquet 逐字重哈希；
- 后端没有历史序列，因此页面没有制造趋势图、成功率或伪时间线。
- PASS、WARN、FAIL 与未就绪状态使用独立结论文案；未来真实失败不会只变徽标却继续显示“数据门通过”。

### 2.2 系统运行

- 核心任务状态与通知状态分列，固定呈现日增量、哨兵、次日开盘对账、影子信号、模拟仓和独立重放；
- 步骤表保留尝试数、失败数、恢复、首错类型、终态时间与运行身份；
- 终态 PASS 不删除先前 `ForwardQlibError`，系统 WARN 被解释为“存在失败恢复或核心故障记录”，
  不是当前任务仍失败；
- 通知摘要分列可寻址消息、attempt、失败、恢复和 legacy 不可寻址计数，legacy 不合成 ID；
- 稳定消息 ID 打开独立通知证据抽屉，展示脱敏尝试、恢复与重复投递风险；
- release 只显示最后一个已登记 `START_PASS`，实时 Docker 身份保持 `NOT_EVALUATED`；
- scheduler 心跳只标“已登记记录”，不根据浏览器时钟猜测实时健康。
- 核心与通知卡片均按各自状态生成文案；FAIL 不会显示“最终完成”，通知 PASS 也不会沿用失败恢复措辞。

两页均沿用 URL `as_of`、5 秒超时、零自动重试、刷新/错误/旧值处理、证据抽屉和页面级
fail closed。未知状态、无效日期/数字/哈希、缺字段、超限响应或任一 `.BJ` 都不会降级成可用页面。

## 3. 真实证据对账

终验直接读取 P3-2A 的真实只读快照，截至 `2026-07-24`：

- 数据结论 `PASS`，证据强度 `WARN`；登记身份链为 69,020 批、45,160,002 行；
- 当日日增量 5 批、15,613 行；S1—S9 `PASS`，S10 `NOT_APPLICABLE`；
- 原始 Parquet 重哈希 `NOT_EVALUATED`，三层北交所计数均为 0；
- 系统结论 `WARN`，保留一次影子 `ForwardQlibError` 和随后恢复 `PASS`；
- 可寻址通知 9 条、11 次投递、1 次失败、1 次恢复；另有 40 条 legacy 不可寻址 attempt；
- 失败消息 `ce3bfbf96e9ec474` 的独立详情可读取，且不改变系统页快照；
- release 为已登记身份，实时容器身份保持 `NOT_EVALUATED`，heartbeat 保持 recorded-only。

## 4. 导航、浏览器与响应式

- 桌面侧栏新增“运行与证据”，移动底栏为总览、组合、信号、数据、运行五项；
- fixture 浏览器回归：28 PASS、7 个有意 SKIP、0 FAIL。SKIP 仅来自刷新闭环只在桌面重复一次，
  axe 全页扫描只在 1440 和 390 两个代表视口执行；
- 视口覆盖 1440×900、1024×768、768×1024、390×844 和 320 CSS px 的 400% 重排等价检查；
- 真实部署桌面/移动共 6 PASS，连续访问五个正式页面；外部 origin、console/page error、
  CSP violation 均为 0；axe critical/serious 为 0；
- 本机首次内容绘制通过 `≤2 秒` 硬断言；
- 10 张新页面终版截图保存在 Git 忽略的项目测试目录，人工复核桌面/移动信息层级、宽表滚动、
  关键状态可读性和证据下钻无阻断问题。

真实浏览器使用本机已安装 Chrome 的临时无头会话，只访问 `127.0.0.1`，未使用用户配置、登录、
历史记录或扩展。项目内 Playwright 浏览器下载在发现不必要后有界中止，未形成可执行浏览器缓存。

## 5. 代理、安全与容器隔离

- UI 静态 allowlist 只增加 `/data-quality`、`/system-runs`；
- API 只增加两个固定路径及严格小写十六进制
  `/api/v1/notifications/[0-9a-f]{16}`；非法大小写 ID 为 404，POST 为 405；
- 连续真实页面保持同源 CSP，不含 `unsafe-inline` 或 `unsafe-eval`，不加载外部资源；
- `web-query` 与 `web-ui` 均以 `10001:10001`、只读根和 `cap_drop=ALL` 运行；
- query 无宿主端口，只挂载 P3 白名单证据目录且全部只读；UI 只绑定
  `127.0.0.1:8080` 且没有任何挂载；两者均无 Docker socket；
- 终版 `shaiwei:web-v1` 内容身份为
  `sha256:cd922d89061dde8a0af0bc0118a801f3fd17ec6fa03ebcd63520288164c7bada`；
- 验收时 scheduler 仍是原容器 `fd8e96152b53...a5adbb`、原镜像
  `sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`、原创建时间
  `2026-07-24T12:25:27.362813588Z`，状态 `healthy`；本阶段未启动、停止、重建或换镜像 scheduler；
- 瞬时内存约为 scheduler 305.7 MiB、query 40.32 MiB、UI 45.92 MiB，Web 各自低于 384 MiB 限额。

## 6. 构建与验证

- 全仓 Python：278 PASS；
- P3 Web Python 专项：14 PASS；
- 前端单元：13 PASS，其中状态文案门禁覆盖 PASS、WARN、FAIL 与未就绪；
- fixture Playwright：28 PASS / 7 intentional SKIP / 0 FAIL；
- 真实部署 Playwright：6 PASS；
- TypeScript、Vite production build、Ruff、compileall、`pip check`、Compose、
  `git diff --check`：PASS；
- 前端构建中数据质量页约 3.24 KiB gzip、系统运行页约 4.27 KiB gzip；现有最大图表分包
  414.28 KiB gzip，仍满足冻结首屏和全路由预算；
- Git 脱敏与忽略边界：PASS，未跟踪 `.env`、data、logs、Node 模块、构建物、截图或浏览器产物。

测试工具恢复说明：一次尝试使用工作区 bundled pnpm 时发现它会迁移现有 npm `node_modules`，已在
安装阶段立即中止；随后仅从同一冻结 `web-ui-build` Docker 目标恢复项目内忽略的依赖树。该过程未
修改跟踪依赖、生产容器、生产数据或项目外文件，也未改变终版构建与测试来源。

唯一 Python 提示仍是 FastAPI TestClient 对当前 httpx 的上游弃用警告，不影响运行；没有为消除
提示擅自升级冻结依赖。

## 7. 结论与后续边界

P3-2B 完成后，Web 1.0 已有五个可真实使用的本机只读页面：总览、模拟组合、股票池/信号、数据质量、
系统运行。结果不是“全绿”：数据 PASS 与证据 WARN、当前恢复与历史失败、核心状态与通知状态都被
同时保留。

因子工厂和模型/回测仍没有正式只读查询契约，继续保持禁用；任何新页面、远程开放、导出、认证、
写能力或生产控制均须另立目标，不得由前端反向推导或改写后台口径。
