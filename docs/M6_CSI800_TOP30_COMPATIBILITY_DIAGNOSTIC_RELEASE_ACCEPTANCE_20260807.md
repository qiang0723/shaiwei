# M6-3C-R1 Top30 兼容诊断 release 准备验收

- 验收时间：2026-08-07 12:59:10（UTC+8）
- 裁决：`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`
- 策略有效性：`NOT_EVALUATED_FOR_PRODUCTION`
- 生产授权：`none`

## 1. 交付结论

M6-3C-R1 已把“首个 W1 控制臂 Top30 日报为何不能精确复现”做成结果盲、可一次性授权的诊断
release。最终 scope 已生成并通过主机及两套镜像内的自哈希、代码、部署文件和运行身份校验：

- scope SHA-256：`cad1928cfc882f259fe9cfc5aeb753d69a03fcfe769b6a860eed4eec71a1fc23`；
- scope 文件 SHA-256：`2a80241ff0f8f11c23826a49cc30362b13f7fd02a2c925c21d65bbe93089de75`；
- scope 真身：`config/m6_csi800_top30_compatibility_diagnostic_scope_v1.json`；
- 协议 SHA-256：`02b4893208af3afa74ff8f4ce414d8143322e760080761199023666cd452b09c`。

当前 approval 不存在，正式输出根也不存在；真实 Qlib、封存预测/日报和 Top30 回测读取为 0，Top20
仍为硬禁止。

## 2. 冻结诊断矩阵

未来只有在完整 scope 获精确批准后，才允许串行运行：

1. 原 M6 镜像 + 原执行器，内部双跑；
2. 失败 M6-3C 镜像 + 原执行器，内部双跑；
3. 失败 M6-3C 镜像 + 新执行器，内部双跑；
4. 两个 runner 都成功后，再由无 Qlib 的独立 auditor 精确分类。

合计恰好 6 次同一 W1/Top30 控制臂诊断回测；模型拟合、新预测、Top20、其他窗口/臂/TopK、研究
尝试增量和实验账本写入全部为 0。每个浮点值用 IEEE-754 位模式比较，禁止舍入、容差或 inner join。

## 3. 正式镜像与代码身份

- original wrapper：`sha256:4d04632d853afd742626d1f3242e7ad3da6bcb21de39db22d7fbb07ec7c5b7b5`；
- current wrapper：`sha256:83e48a0e52ec1ddbb78060cb79096dae0c4865d632e7205486eff7736196c413`；
- 平台：`linux/arm64`；嵌入 Git：`67d53fa3d262a45314f8a98f6a7794d81f29b73d`；
- 8 文件代码 bundle：`2298040ce59c81b5fbdb4ee3ec8ef4164ecc4b03b4ce76bbed968a05d7ef1084`；
- original/current 镜像清单 SHA：`5fb233af...ff9a` / `49211c51...e7db`；
- base 镜像严格保留为原 M6 `3c40c9c...cd40e`和失败 M6-3C `69c1a497...afa17`。

两个 runner 上限均为 2 CPU/4GB/128 pids，auditor 为 1 CPU/2GB/64 pids；全部断网、非 root、只读
根、drop ALL、no-new-privileges，不挂 `.env`、Docker socket、整仓或生产账本。auditor 不挂 Qlib。

## 4. provisional 留痕

在任何 scope 批准或真实读取前，工程门连续发现并修正三类发布问题：

- 首批镜像手工扩展短 Git 为错误 40 位值：original/current ID 为`2fb1fde0...3515`/`ff45acb7...bc66`；
- 第二批对目录使用只读 `0444`，非 root 无法遍历新包：`0e6b5c54...666e`/`0083f3c0...23e6`；
- 第三批未嵌入 Dockerfile/Compose，scope 运行时无法复算部署 SHA：`ebbd2d02...b7b5`/
  `8c4401a5...28f1`，其 provisional scope SHA 为`331408b2...e5ea`。

三批均已加明确 provisional 标签或在文档中留存身份，未生成 approval、未挂 Qlib、未读封存日报、
未运行真实回测，不能用于正式执行。最终镜像分别通过非 root fixture 和无真实数据 scope/runtime 门。

## 5. 验证

- 两套最终镜像断网合成 fixture：6 类冻结分类逐项 PASS；真实 Qlib/日报/回测读取 0；
- 主机 scope 与 original/current 镜像内 runtime identity：PASS；
- 全仓测试：926 PASS，只有 1 条既有 Starlette 第三方弃用提示；
- M6-3C-R1 专项：8 PASS；架构门：10 PASS；
- Ruff、compileall、pip check、Compose 展开、JSON/YAML、自哈希、`git diff --check`和脱敏：PASS；
- scheduler 保持原 `shaiwei:scheduler-current`、Up 3 days、healthy，未修改或重启；7 个自然账本改动
  未暂存。

## 6. 精确授权门

后续若继续，用户必须逐字批准动作：

`M6_TOP30_COMPATIBILITY_DIAGNOSTIC_MATRIX_ONCE`

并绑定完整 scope SHA：

`cad1928cfc882f259fe9cfc5aeb753d69a03fcfe769b6a860eed4eec71a1fc23`

获批后也只能各运行一次 original runner、current runner 和独立 auditor，同 scope 任何失败不得重跑。
诊断成功只形成工程根因分类，不授权 Top20、模型、前瞻、模拟仓或生产；Top20 如需继续仍须新 release。
