# Web 页面模块化治理第二阶段协议

> 日期：2026-08-01（Asia/Shanghai）
>
> 协议：`p3-web-page-modularization-v2`
>
> 状态：`FROZEN_BEFORE_REFACTOR`

## 目标

在不改变页面内容、交互、HTTP契约、业务口径、CSS类名或运行边界的前提下，将因子工厂和模型/回测
两个页面从单文件拆为可独立维护的路由、目录、详情、比较/历史和展示原语模块。该目标只治理结构，
不交付新功能，不重新设计Web 1.1.1。

施工前规模：

- `web-ui/src/pages/FactorsPage.tsx`：952行；
- `web-ui/src/pages/ExperimentsPage.tsx`：861行。

两文件已经同时承担路由分派、查询编排、URL筛选、表格/图表、证据格式化和领域状态展示；继续在其
中加入职责会违反仓库600行棘轮。现有E2E已覆盖因子目录/比较/tear sheet/准入历史/历史态，以及实验
目录/分页/筛选/失效方法/权威纠错/G1十五门，具备结构拆分的回归基础。

## 冻结拆分

### 因子工厂

- `FactorsPage.tsx`：只保留路径解析与页面分派；
- `pages/factors/presentation.tsx`：标签、路径、证据、数值展示和共享状态组件；
- `pages/factors/CatalogPage.tsx`：目录查询、筛选和严格比较选择；
- `pages/factors/DetailPage.tsx`：单因子tear sheet；
- `pages/factors/AdmissionsPage.tsx`：追加式准入历史；
- `pages/factors/ComparePage.tsx`：最多三因子严格可比分析。

### 模型/回测

- `ExperimentsPage.tsx`：只保留路径解析与页面分派；
- `pages/experiments/presentation.tsx`：标签、路径、证据、数值和共享状态组件；
- `pages/experiments/CatalogPage.tsx`：类型化目录、精确筛选和后端分页；
- `pages/experiments/DetailPage.tsx`：身份、结论、G1门、P2窗口和失败边界。

允许在不产生循环依赖的前提下把同一职责再收窄，但不得创建`utils`、`helpers`或万能组件目录。

## 不变量与禁区

- 不新增、删除或重命名URL、API调用、查询参数、JSON字段、状态枚举、错误码、页面文案、ARIA标签、
  CSS类名或图表口径；
- 不修改既有E2E fixture与断言来迁就重构；
- 不修改`src/shaiwei`、后端查询、研究投影、Compose、Docker挂载、模型、信号、门禁、账本、生产数据、
  scheduler、Top20候选或8月3日发布守护；
- 不升级依赖，不联网安装包，不做视觉优化、性能改造或顺手清理；
- 页面模块只依赖既有API、类型、公共组件和同领域展示原语，不允许跨域页面互相导入。

## 结构门

- 两个原页面入口均不超过100行，只负责路由；
- 本批新增页面模块均不超过600行，目录、详情和展示原语职责分离；
- `FactorsPage.tsx`不得再直接导入React Query、Ant Design Charts或业务API；
- `ExperimentsPage.tsx`不得再直接导入React Query、Ant Design Charts或业务API；
- 新增结构测试把上述行数、入口依赖和跨域依赖作为后续棘轮。

## 验收门

- 既有前端单元、TypeScript、生产构建和五视口fixture E2E全部通过；
- 因子与实验既有E2E请求序列、路由、分页、历史态、坏消息、图表和ARIA断言原样通过；
- Python全仓、Ruff、compileall、`pip check`、Compose、`git diff --check`、账本追加和脱敏检查PASS；
- 只重建/重启隔离Web，真实七页只读回归与无障碍/回流门通过；
- scheduler容器、镜像、创建周期和healthy状态施工前后不变；
- 最终工作树干净且`HEAD=origin/main`，不阻断8月3日Top20单次守护。

全部通过才可裁决`GO_WEB_PAGE_MODULARIZATION_ONLY`。该裁决不增加页面功能，不改变任何策略、研究、
前瞻或生产授权。
