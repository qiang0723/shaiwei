# ADR · A1-1B D1 transport 合同解环

- 日期：2026-08-07（UTC+8）
- 状态：`ACCEPTED_IMPLEMENTED`
- 开工代码：`6b2320f8578c4a7b66a8275636bdd115ad1242c8`
- 决策范围：只重排 D1 控制面与 DeepSeek transport 的依赖，不改变任何研究或外部调用语义

## 问题与结果目标

`deepseek_client.py` 为了获得 `D1Protocol`、`ProviderResponse`、请求规划和敏感输出规则，直接导入
1,254 行的 `llm_factor.py`；后者的离线 fixture 又局部导入 `deepseek_client`，形成静态循环依赖。
这扩大了网络适配层的依赖面，也使 D1 控制文件继续承担合同、规划、账本、候选裁决和 fixture 多种职责。

本次目标是建立一个不含 HTTP、环境变量、账本写入和研究执行的窄 transport 合同/规划 seam，使
`deepseek_client` 只依赖该 seam；`llm_factor` 保持原公共导入兼容。完成后全仓 Python 循环从 2 个降为
1 个，`llm_factor.py` 明显缩小，DeepSeek 的授权、费用、重试和秘密边界逐字段不变。

## 权威事实与不可触碰边界

- D1 v1 protocol、prompt、knowledge manifest、候选 schema、40次历史响应和 STOP/REJECT 证据不修改。
- 不读取 `.env`，不创建真实 transport，不调用 DeepSeek，不发送任何数据或提示。
- 原公共导入 `from shaiwei.research.llm_factor import ...` 在兼容期内继续成立。
- `deepseek_client.py` 已是超过600行的 grandfathered热点，本次只能保持或减少行数，不能加入新职责。
- 请求 JSON 的 canonical SHA-256、attempt identity、Pydantic schema、错误类型名和 mock transport 事件
  顺序必须不变。
- scheduler、Web、模拟仓、研究账本、数据和生产镜像不修改。

## 候选方案

### 方案一：只移动 `run_fixture`

可以消除图上的反向边，但 `deepseek_client` 仍要加载整个 `llm_factor` 生命周期，网络适配层与研究控制
继续高耦合。拒绝。

### 方案二：合并 control 与 transport

能消除循环，但会产生超过2,000行、同时拥有网络、secret、账本和领域裁决的单文件。拒绝。

### 方案三：抽出窄 transport contract/planning seam（采用）

新增 `llm_factor_contract.py`，只包含协议读取、候选 typed schema、attempt/request 规划、provider response
值对象和敏感输出规则。它不导入 `llm_factor`、`deepseek_client`、HTTP 或 `.env`。两个旧模块都只向内
依赖该 seam；`llm_factor` re-export 原符号，旧调用方不迁移。

## 合同、迁移与回滚

- 新模块默认少于400行；不建立 `utils/common`。
- `llm_factor.py` 删除迁出的定义，保留同名 import/re-export；ledger lifecycle、候选执行和 fixture 留在原
  模块，本批不拆第二项职责。
- `deepseek_client.py` 仅替换 import 来源，其 HTTP、费用、事件账本和 live factory 字节逻辑不改。
- characterization 先锁定 ordinal 1 请求 SHA
  `8ddb033eac5a8b2d0595868ed38f8fb424afb9404c56353e1cfa08d0fb14e21c`，再实施迁移。
- 单一回滚点为 A1-1B 提交的父提交；失败时完整 revert 本包，不保留半迁移路径。

## 验收

1. AST 导入图不再包含 `deepseek_client <-> llm_factor`，循环总数由2降为1。
2. `llm_factor.py` 不增长且迁出一个稳定职责；`deepseek_client.py` 不增长。
3. 旧/新导入的合同符号是同一对象；请求 SHA、mock transport、恢复、敏感输出和未授权先停测试通过。
4. `make architecture-check`、全仓测试、Ruff、compileall、依赖、diff与脱敏门通过。
5. scheduler 容器、镜像、创建时间和 healthy 状态不变；七个自然账本保持未暂存。

## 实施结果

- 新增357行纯合同模块；不导入HTTP、环境、账本、控制面或transport。
- `llm_factor.py`从1,254行降至944行，机器上限由版本化A1-1B增补收紧；`deepseek_client.py`保持808行。
- 旧architecture v1被历史release按物理SHA冻结，保持原字节；增补只引用其SHA，不改写旧证据。
- 原模块对合同符号作同一对象re-export，ordinal 1请求SHA保持
  `8ddb033eac5a8b2d0595868ed38f8fb424afb9404c56353e1cfa08d0fb14e21c`。
- AST强连通分量由2个降至1个，D1循环已消除；剩余M3循环不在本包施工范围。
- 全程未读取secret、未创建live transport、未调用DeepSeek、未运行研究或生产任务。
