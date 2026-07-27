# Web 模块化治理第一阶段验收

> 日期：2026-07-27（Asia/Shanghai）
>
> 协议：`p3-web-modularization-v1`
>
> 裁决：`GO_MODULARIZATION_ONLY`

## 结论

第一阶段完成了三个最高风险 Web 单文件的职责拆分，并通过结构、类型、测试、真实 API、编译产物和
运行隔离六层门禁。该裁决只说明模块化施工成功，不代表新增功能、策略有效、远程开放或生产授权。

- 结果前协议提交：`8b55653`；
- 实现提交：`1b0cd45`；
- HTTP 路由、JSON 字段、错误码、页面文案、CSS 类名、规则内容和加载顺序均未改变；
- 未修改 scheduler、模型、信号、因子判决、账本、生产数据或 Docker 安全边界。

## 结构结果

### 后端只读查询

原 `src/shaiwei/web/query.py` 为1,548行。终版为：

| 文件 | 行数 | 职责 |
| --- | ---: | --- |
| `query.py` | 474 | 公共门面、原子编排与兼容导出 |
| `query_evidence.py` | 495 | 证据切片与公共投影 |
| `query_paper.py` | 410 | 模拟组合查询 |
| `query_signal.py` | 244 | 信号与对账查询 |

原有 `shaiwei.web.query` 公共导入路径保持不变。

### 前端运行时校验

原 `web-ui/src/validation.ts` 为1,484行。终版门面为21行，领域文件分别为：

| 文件 | 行数 |
| --- | ---: |
| `validation/core.ts` | 454 |
| `validation/experiments.ts` | 380 |
| `validation/paper.ts` | 255 |
| `validation/operations.ts` | 244 |
| `validation/factors.ts` | 244 |

原有 `./validation` 导出入口与类型收窄行为保持不变。

### 样式

原 `web-ui/src/styles.css` 为3,925行。终版门面为10行，按原顺序加载10个片段；最大片段577行，
没有超过600行的新增样式模块。首次机械切分在本机构建时暴露一处组合选择器边界错误，生产构建正确
拒绝；修正后才提交和部署，没有失败版本进入可用 Web。

## 等价性证据

### 真实 API

在旧、新 Web 上固定同一 `as_of=2026-07-27`，对以下14个真实只读请求的原始响应计算SHA-256，
结果14/14逐项完全一致：

- 总览；
- Top30/Top20 的组合快照、NAV、前瞻验收和重放，共8项；
- 最新信号；
- 数据质量；
- 系统运行；
- 因子目录；
- 实验目录。

这说明本次拆分没有改变响应字段、值、顺序、空态或证据身份。

### CSS 编译产物

重构前后生产构建生成相同文件名并具有相同SHA-256：

| 产物 | SHA-256 |
| --- | --- |
| `index-BCeIoLD3.css` | `8ae3ef0d2c38a60f829b80caf5022e363733612bbd5735c04e2f3944c026867f` |
| `vendor-antd-B5BXDqMa.css` | `6b734531b94fda9950119646124dccee1ee7e70e91b3e5be988c378ca9f9f98d` |

因此规则内容和顺序是字节级等价，不以主观视觉判断代替验证。

## 工程验证

- Python全仓：357 PASS；
- 前端单元：25 PASS；
- Ruff：PASS；
- TypeScript：PASS；
- Vite生产构建：PASS；
- Python compile/import、Compose配置与 `git diff --check`：PASS；
- 新增 `tests/test_web_modularity.py`，强制本批目标模块/门面不超过600行，并禁止后端查询层反向依赖
  `shaiwei.config`、`load_dotenv` 或 `shaiwei.web.api`。

终版 Web 镜像为
`sha256:c0a1dde6b1dd448779cc52f2bd0cdbc96dcda36fd35c5b58c50ec23bba6a1e0d`；
`web-query` 与 `web-ui` 均为 healthy，UI仍只监听 `127.0.0.1:8080`。

scheduler 保持原容器、原镜像
`sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`、原创建时间并持续
healthy；本次没有重建或重启 scheduler。

## 保留边界与下一步

以下热点已登记但未夹带施工：

- `src/shaiwei/web/operations.py`：1,160行；
- `src/shaiwei/web/research_projection.py`：1,312行；
- `web-ui/src/pages/FactorsPage.tsx`：952行；
- `web-ui/src/pages/ExperimentsPage.tsx`：861行。

它们不是当前故障，也不应因第一阶段成功立即连续拆分。只有出现明确的新功能落点、维护摩擦或测试
边界需求时，再以独立协议选择其中一组施工；其间所有新增代码继续遵守 `AGENTS.md` 的增量行数、
职责和依赖方向规则。
