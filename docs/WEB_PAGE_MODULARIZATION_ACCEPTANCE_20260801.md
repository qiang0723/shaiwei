# Web 页面模块化治理第二阶段验收

> 日期：2026-08-01（Asia/Shanghai）
>
> 协议：`p3-web-page-modularization-v2`
>
> 结果前冻结提交：`2873bdf`
>
> 裁决：`GO_WEB_PAGE_MODULARIZATION_ONLY`

## 裁决边界

因子工厂与模型/回测页面已从两个超大单文件拆为薄路由入口、目录、详情、比较或准入历史以及领域展示
原语。验收只证明结构治理完成且行为未回归，不增加页面功能，不改变研究、策略、前瞻或生产授权。

本次未修改后端`src/shaiwei`、API契约、研究投影、Compose、依赖、模型、信号、门禁、账本、生产
数据、scheduler、Top20候选或2026-08-03单次发布守护。

## 结构结果

### 因子工厂

| 文件 | 终版行数 | 职责 |
| --- | ---: | --- |
| `pages/FactorsPage.tsx` | 23 | 路径解析与页面分派 |
| `pages/factors/presentation.tsx` | 237 | 共享标签、证据和展示原语 |
| `pages/factors/CatalogPage.tsx` | 298 | 目录、筛选和严格比较选择 |
| `pages/factors/DetailPage.tsx` | 241 | 单因子研究证据 |
| `pages/factors/AdmissionsPage.tsx` | 93 | 追加式准入历史 |
| `pages/factors/ComparePage.tsx` | 141 | 最多三因子可比分析 |

原入口由952行降至23行。入口不再直接导入React Query、Ant Design Charts或业务API。

### 模型/回测

| 文件 | 终版行数 | 职责 |
| --- | ---: | --- |
| `pages/ExperimentsPage.tsx` | 21 | 路径解析与页面分派 |
| `pages/experiments/presentation.tsx` | 332 | 共享标签、路径、证据和展示原语 |
| `pages/experiments/CatalogPage.tsx` | 269 | 类型化目录、筛选和后端分页 |
| `pages/experiments/DetailPage.tsx` | 292 | 身份、结论、G1/P2和失败边界 |

原入口由861行降至21行。入口不再直接导入React Query、Ant Design Charts或业务API。

`tests/test_web_modularity.py`已把两个入口不超过100行、所有相关模块不超过600行、入口依赖边界和
因子/实验领域禁止交叉导入固化为结构棘轮。新增模块最大332行；未创建万能`utils`或`helpers`目录。

## 行为不变量

- 既有`web-ui/e2e`与`web-ui/src/test`未修改；
- URL、API调用、请求参数、JSON字段、状态枚举和错误码未改变；
- 页面文案、ARIA标签、CSS类名、图表口径和查询语义未改变；
- Vite产物继续使用原CSS资产名`index-BCeIoLD3.css`与`vendor-antd-B5BXDqMa.css`；
- 因子目录/详情/比较/准入历史，以及实验目录/分页/详情/失效与权威状态均由原断言通过。

## 机器验收

| 验收项 | 结果 |
| --- | --- |
| TypeScript与生产Vite构建 | PASS |
| 前端单元测试 | 25 PASS |
| 五视口fixture Playwright | 64 PASS / 11预期skip |
| Python全仓 | 385 PASS / 1条既有第三方弃用warning |
| Ruff | PASS |
| compileall | PASS |
| pip check | PASS |
| `git diff --check` | PASS |
| 账本追加约束 | 17 PASS |
| 凭据与账本专项 | 18 PASS |

前端构建阶段镜像内容标识为`sha256:a05f2edd671c...360a`；完整只读Web部署镜像内容标识为
`sha256:523c85c70705e05fa4db8a97c825f13e717a9ae2fe67fce5dca60610adc8bbe8`。

## 真实部署与浏览器复核

- `web-query`和`web-ui`只读容器均为healthy；查询服务不暴露宿主端口，UI仅监听
  `127.0.0.1:8080`；
- 真实数据下核验总览、因子工厂、模型/回测、模拟组合、股票池/信号、数据质量和系统运行七页；
- 390px视口下七个主页面、单因子研究证据和实验结论详情的页面宽度均为390px，无横向溢出；
- 因子目录、单因子G1证据、实验目录和类型化实验详情均正常加载，坏消息与权威边界仍保留；
- 浏览器控制台warning/error为0。

生产scheduler施工前后均为原容器、原镜像
`sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`，连续运行7天且healthy，
未被重建或重启。

## 结论

全部冻结门通过，裁定`GO_WEB_PAGE_MODULARIZATION_ONLY`。后续新增因子或实验展示必须进入对应领域
模块并继续受100/600行与依赖边界约束；不得把已拆出的查询、展示或状态逻辑重新堆回路由入口。
