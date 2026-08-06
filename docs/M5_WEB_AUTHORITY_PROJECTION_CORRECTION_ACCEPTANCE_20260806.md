# M5 最新权威状态 Web 投影补正验收

- 验收日期：2026-08-06（UTC+8）
- 协议提交：`6b6bef38ecb0355d584da99f1f1b62192b1d1eaa`
- 工程裁决：`GO_LOCAL_READ_ONLY_TRUTH_PROJECTION`
- 研究、效果、生产授权：`none`

## 1. 结论

策略工厂 Web 已从 2026-08-05 的旧 v2 真身升级为新的不可变 v3 投影。页面现在明确显示 M5 动态
基本面跨池批次因历史来源谱系不足进入 `BLOCKED_DATA / LINEAGE_NO_GO_ONLY`，23 个冲突组全部只能
证明当前观察版本，历史 PIT 版本链可恢复 0 组；策略仍为 `NOT_EVALUATED`，没有效果读取、活跃任务
或生产授权。

该裁决作为独立的终态数据门展示，没有被伪装成第九个效果工作包，也没有改变 8 个既有工作包、
5 个可建立草案的股票池、3 个池级数据/PIT阻断、正式因子库 0 或当前生产策略 1 的既有事实。

## 2. 来源与内容身份

v3 生成只读取并逐文件核验以下权威真身：

- release scope：`config/m5_dynamic_fundamental_source_lineage_release_scope_v2.json`，物理 SHA-256
  `9343fa9cfaa8855739b700fbf244d6597f1f10f070c780f8d973ce11cfdd2933`；
- 真实运行验收：
  `docs/M5_DYNAMIC_FUNDAMENTAL_SOURCE_LINEAGE_SCOPE_RECOVERY_REAL_RUN_ACCEPTANCE_20260806.md`，
  SHA-256 `f41fad01c2527cbba1dde0083a490b69424d0863aec655f63d0ee0f1be891309`；
- 路线复盘：`docs/PLATFORM_ROUTE_REVIEW_20260806.md`，SHA-256
  `5a06ab43d484dae32780b1a6cda8d1ce9d57524cc47126174cd5cc7e15b7c703`；
- 既有策略工厂目录、计数修正 addendum 及其原有证据。

新快照：

- snapshot id：`80498300f2b2c0933eed163fe214115c59babae0f3a609b12191d11d54340840`；
- snapshot SHA-256：`8cf59d2a7326fd85cf9927a50305336f03d307fa36e4fa8341dae2775e16c640`；
- pointer SHA-256：`063f987f649a5345e7ddd5294cd18a4c4da4a66b1d1cff1a86a57849534dcf02`；
- `generated_at=2026-08-06T17:30:40+08:00`，API `as_of=2026-08-06`。

旧 v2 pointer / snapshot SHA-256 仍为
`eb196680e972c02afe8815587047efdeb792c36cc294ec43ae5ab6035b8b4a41` /
`36f750639f5643a67ac0c2f9eb7505949542a9404edad9ff3d7fb970f7bd6f2b`，逐字未变，可作为回滚真身。

## 3. 查询与页面

- `/api/v1/strategy-factory` 继续只接受 GET/HEAD；无 v3 时 `NOT_READY`，身份或固定事实漂移时
  `EVIDENCE_MISMATCH`，禁止自动回退过时 v2。
- 新字段版本为 `m5-strategy-factory-authority-projection-v1`，`recent_gate_decisions` 本版恰好一条。
- 首屏显示阻断结论、三池范围、23/23/0 聚合计数、效果未评价与下一合法动作。
- release、run、audit、registry event 和 commit 等技术身份默认隐藏，仅在“查看技术证据”展开后显示。
- 页面没有新增执行、重跑、补数、调参、队列或生产按钮；浏览器提案能力和 `active_tasks=[]` 保持原样。

## 4. 验证

- 后端专项、协议和模块测试：13 PASS；来源篡改、终态改成 `REJECT`、pointer/快照漂移均失败关闭。
- 全仓：815 PASS；仅 1 条既有 Starlette 第三方弃用 warning。
- 架构宪法：6 PASS；新增生产模块 203 行，未增长既有热点。
- 前端单元：33 PASS；TypeScript 与生产构建 PASS。
- 断网 fixture：1440/1024/768/390/320 五视口 5 PASS，无页面级横向溢出。
- 真实部署：桌面/移动 2 PASS；CSP、同源零外联、axe serious/critical=0、响应式与真实 API 均通过。
- 首次真实验收发现“下一合法动作”标签对比度 4.46:1，已加深文字颜色；修复后同一真实门通过。
- Ruff、compileall、pip check、Compose 合同、`git diff --check` 和敏感凭据模式扫描 PASS。

## 5. 隔离与剩余边界

最终 Web 镜像为
`sha256:cb955cccc26636cb42e2d3d154d3daf5213aac37ce81dc6c3be5e1349b413eac`，web-query 与 web-ui 均
healthy，仍只在 `127.0.0.1:8080` 暴露 UI。生产 scheduler 仍是原容器
`183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`、原镜像
`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`，healthy 且未重启。

本任务不解除 M5-2C 阻断，不授权联网补证、模型、回测或生产。按路线复盘，下一独立目标是只冻结
中证800模型/组合归因小批协议；不得与本次 Web 实现混成同一提交。
