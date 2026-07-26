# P3-4A 模型/回测实验目录后端验收

> 验收日期：2026-07-26（Asia/Shanghai）
>
> 协议：`p3-experiment-catalog-v1`
>
> 结论：`GO_BACKEND_ONLY`

## 1. 裁决

P3-4A 已完成内部只读 `GET/HEAD /api/v1/experiments`、类型化 `experiment_catalog`、不可变投影
双协议绑定和 Docker 验收。目录后端 GO，但模型/回测页面、UI 代理路径、远程访问、导出、模型运行、
回测运行、G1/LLM 调用和任何生产授权仍为 **无**。

结果前协议与机器配置由提交 `4f53cbc50b3daac45e12d3a2fd627fb1f43a73df` 先行推送；实现开始前
`HEAD=origin/main` 均为该提交。施工没有读取数值表现来改变 outcome 映射、门槛或范围。

## 2. 目录真身

终版目录来自同一不可变投影中的 783 条记录，分页遍历得到 783 个唯一 `(experiment_kind,
experiment_id)`，无重复、无遗漏：

| kind | 数量 |
|---|---:|
| `research_experiment` | 778 |
| `p2_engineering_run` | 3 |
| `p2_effect_original` | 1 |
| `p2_effect_correction` | 1 |

适配器级 outcome 实际分布为：`FAILED=509`、`DISCOVERY_ONLY=196`、`RECORDED=49`、
`G1_REJECTED=18`、`DISCOVERY_REJECTED=4`、`ENGINEERING_GO_ONLY=3`、`REVIEW_STOPPED=2`、
`HISTORICAL_EFFECT_REJECTED=1`、`INVALIDATED_METHOD=1`、`G1_ADMITTED=0`。因此当前正式因子库仍是
0 插入，目录没有把 783 条记录包装成 783 个模型，也没有生成表现排行榜。

十类冻结 outcome 均有 fixture；当前实际适配器组合已穷尽。未知新状态返回 `NOT_EVALUATED`，缺少
必需字段返回 `EVIDENCE_MISMATCH`，不会静默降级成 `RECORDED`。目录 ID 与详情 ID 抽样逐项一致。

## 3. 查询与 HTTP

- 只允许冻结的八组精确过滤；未知值、未知参数和重复参数均返回 422 `INVALID_ARGUMENT`；
- offset 从 0 开始，limit 为 1—100；783 条以 8 页完整遍历，无跨页重复；
- 固定按 UTC 规范化后的 `recorded_at` 降序，再按 kind、ID 升序；不开放结果排序、模糊搜索或
  客户端表现筛选；
- `as_of=2026-07-23` 实际保留 719 条，并明确返回
  `CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS`；
- 100 条终版响应最大 50,474 bytes，低于 1 MiB 上限；HEAD=200、POST=405；
- `decision`、`params_json`、`result_json`、绝对宿主/容器路径和 `.BJ` 均未出现在全目录响应。

UI 代理对 `/api/v1/experiments` 仍返回 404；这证明本目标没有越过“后端目录”边界进入 P3-4B 页面。

## 4. 不可变投影与幂等

终版快照：

- snapshot：`c2993c39c7c3aa5b28f975d02e6718ddc5aa8c2edebda294f88e0ba33d31e1fe`
- bundle SHA-256：`cf72e70c9dadeac8782e892e4d132a4eec1b5371e82473a9206d206e15e4d773`
- manifest SHA-256：`ca1e60d9ceed2ca99467562476ede20424cb5e9755290a59ee4b39268761292c`
- 协议文件 source SHA-256：`16cb0bc7114e5b27bddf3402468ce45f28fee0721bc83b29e4f9ce6976d7864c`
- 终版构建器 SHA-256：`308e4f0686b095a4cca214d26ea2a3a92590d61ca83a23c853139ea9a13107ba`

manifest 同时绑定 `p3-factor-experiment-query-v1` 与 `p3-experiment-catalog-v1`。相同入口连续两遍均
返回同一 snapshot，bundle/manifest 字节与哈希不变；旧 P3-3B 快照和施工中 provisional 快照均未
删除或改写。web-query 只读选择终版双协议快照。

## 5. Docker 与生产隔离

终版 Web 镜像内容 ID 为
`sha256:bb0082bbdaffd53626ea31a6f4a02355971685f798ca90d025f6e34287c27d7b`；web-query 与 web-ui 均为
非 root、只读根文件系统并保持 healthy。对 `/workspace/src` 和只读研究投影挂载的实际写探针均以
`OSError` 拒绝；项目不挂 Docker socket，query 无宿主端口。

生产 scheduler 施工前后保持同一容器
`fd8e96152b53f3f0d0efdcd6462c2b039aa68c7fb56461b95826709652a5adbb`、同一镜像
`sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`、同一创建时间
`2026-07-24T12:25:27.362813588Z`，持续 healthy，未重建或重启。

## 6. 验证

- 全仓 pytest：296 PASS；
- 实验目录专项：十类 outcome、未知组合、缺字段、过滤、分页、历史切片、HTTP 和脱敏均 PASS；
- Ruff、compileall、pip check、Compose 解析和 `git diff --check` PASS；
- 前端生产构建 PASS；tracked files 未发现 DeepSeek key、飞书 webhook 或签名；
- 终版快照位于 Git 忽略的 `data/`，未提交原始/派生业务数据、日志、密钥或不可变运行产物。

## 7. 后续边界

若继续模型/回测页面，下一目标是 P3-4B。必须另行结果前冻结页面问题、分组、详情下钻、数值展示、
失效方法表达和 UI 代理精确路径；不得将目录改造成收益榜、最佳模型榜或在线调参入口。
