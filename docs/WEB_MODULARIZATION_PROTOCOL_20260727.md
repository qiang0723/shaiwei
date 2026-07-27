# Web 模块化治理第一阶段协议

> 日期：2026-07-27（Asia/Shanghai）
>
> 协议：`p3-web-modularization-v1`
>
> 状态：`FROZEN_BEFORE_REFACTOR`

## 目标

在不改变任何业务口径、HTTP 契约、页面信息、视觉顺序或运行边界的前提下，拆分当前 Web 三个最高
风险热点文件，使后续功能不再向单文件堆积。该目标只治理结构，不交付新功能。

施工前规模：

- `src/shaiwei/web/query.py`：1,548 行；
- `web-ui/src/validation.ts`：1,484 行；
- `web-ui/src/styles.css`：3,925 行。

## 冻结范围

1. 后端查询按“公共类型与基础校验 / 证据切片 / 模拟组合 / 信号与对账 / 原子编排”拆分；
   `shaiwei.web.query` 原有公共导入路径和 API 调用不变。
2. 前端校验按“公共原语 / 模拟组合与信号 / 运维 / 因子 / 实验”拆分；`./validation` 原导出名不变。
3. CSS 按基础与壳层、公共组件、组合与信号、研究页面、运维页面、响应式分文件；加载顺序必须与原
   文件逐段顺序一致，`main.tsx` 入口不变。
4. 第一阶段不拆 `operations.py`、`research_projection.py`、`FactorsPage.tsx` 或
   `ExperimentsPage.tsx`；它们列入后续热点，但不得夹带在本阶段扩大改动面。

## 非目标与禁区

- 不新增、删除或重命名 HTTP 路由、JSON 字段、状态枚举、错误码、CSS 类名或页面文案；
- 不改变因子、实验、模型、模拟仓、信号、门禁、数据、账本、Docker 网络或只读挂载；
- 不修改 scheduler、生产镜像、Top20 冻结候选或发布门；
- 不做顺手功能优化、视觉调整、依赖升级、格式全改或历史代码清理；
- 不为满足行数制造循环依赖、万能公共模块或只有一层转发价值的碎片文件。

## 结构门

- 三个原热点入口文件应变为薄门面或被职责文件替代；新增职责文件常态不超过 600 行；
- 依赖只能从编排层流向领域投影和基础原语，领域模块不得反向导入 API、Docker、`.env` 或前端；
- 公共导入路径、TypeScript 类型收窄、异常传播和 fail-closed 语义保持不变；
- 相同 fixture 的 API payload、错误码和 snapshot 身份必须一致；CSS 生产构建的规则内容与顺序必须
  等价，不以肉眼“看起来差不多”代替验证。

## 验收门

- Python 全仓测试、Ruff、compile/import、Compose 与 `git diff --check` 全部通过；
- 前端单元、TypeScript 与生产构建通过；既有 E2E 契约不得修改为迁就重构；
- 重构前后真实只读 API 的账户、信号、数据质量、系统运行和研究端点语义哈希一致，除非期间出现新
  不可变生产证据，此时改用同一 `as_of` 复核；
- 编译后 CSS 规则序列与重构前一致；桌面、移动和 400% 回流无新增横向溢出；
- 只重建并发布隔离 Web，scheduler 容器 ID、镜像和创建时间保持不变。

只有全部门通过才可结论 `GO_MODULARIZATION_ONLY`。该结论不改变策略、研究或生产授权。
