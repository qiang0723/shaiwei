# M3-3 三自建池机械 Top2 独立审查预执行验收

日期：2026-08-02（UTC+8）

裁决：`GO_M3_3_PREEXECUTION_ONLY`

策略有效性：`NOT_EVALUATED`

真实审查授权：`false`

生产授权：`none`

## 结论

M3-3 已完成固定 Top2 结果盲独立审查的工程预执行门。预执行真身能够从 M3-2 不可变原始响应重放
公式、PIT、shift、复杂度和上游哈希，确定性构造恰好 `2候选 × 4角色 = 8` 份请求，并在不解析发现
指标、不读取封存结果、不读取密钥和不访问网络的前提下验证严格 schema、自由文本语义门、负面筛选
裁决和不可递补规则。

这只是“未来审查可安全执行”的工程结论，不是任何候选通过审查，更不是因子、策略或生产有效性结论。
两份专属账本仍只有表头。真实 DeepSeek 调用必须另获用户明确授权并另立不可变 live release。

## 固定合同与身份

- 协议提交：`7649c2686e2d5932519a485fd380acb66cc39806`；
- 预执行实现提交：`9f2c33ef093893765315389152d67568bbad2771`，已先行推送 `origin/main`；
- 协议 SHA-256：`2828623c47d20756f9ca3f59f71c0c55e7b259e734e7b51938fb70f32d34b7c6`；
- 提示 SHA-256：`00f9a063307a98e1b754382ac1f78818ea2615c0d812575f318dd9692248c35f`；
- 语义门 SHA-256：`8faf36d33744aec06ec4331266dccf4d96dee904bac0a3d0fb603940e6aef15a`；
- 预执行 release SHA-256：`bd21cd34f74d3c1529acd418bcf1d36e252ef828d2e9f64978ed523b57bdcfb2`；
- 八请求 bundle SHA-256：`f35daa7f9f1830e0dc6e680eafdfaccc3dc7c58238369fd5dc155defaf1372fe`；
- 六模块代码 bundle SHA-256：`b478ad8206ebb6e96461b8e65794e34dae644932769ca9f35d5b28744f9f7d8c`；
- Docker 受控代码快照：`fdfa717111c374e9fa9c529439889f6600dfc8347946950eead67549a85448a8`；
- 镜像：`shaiwei:m3-multi-pool-review-preexecution-v1`，镜像 ID
  `sha256:f910b4d88eb613a3249845239f1cf04427c8b5b60aef7b084761dfd36b17aecf`。

候选顺序、公式与方向保持为 M3-2 机械 Top2 原值；代码未解析 discovery report、candidate manifest
中的发现指标字段，只做文件哈希绑定。M3-2 `expression_tokens=7` 继续从 provider 原始表达式重放，
规范渲染不得重新排序或替换候选。

## 失败关闭验证

断网 fixture 覆盖并通过：

1. 严格 response schema 与逐字段自由文本语义门必须同时通过；
2. 正文出现“替换公式/归一化替代”等改式建议，即使结构字段仍为 false，也会语义失败；
3. 至少一条候选四角色均无 blocker，只允许后续冻结 M3-4 验证协议；
4. 两条候选均出现 blocker 时，M3 因子家族在验证前停止；
5. 任一响应 schema/语义无效、角色错位、顺序错误或不足 8 份，整批
   `STOP_M3_3_REVIEW_CONTRACT`，不补发、不递补；
6. major/critical 只按原式拒绝，不提供修复或第三名替换通道。

专属账本终态：

- `ledger/m3_multi_pool_factor_reviews.csv`：0 数据行，SHA-256
  `8dbfdefa5a5a34ce829822aecbf1b502caf2ee944d872f54df0063d716fe00fb`；
- `ledger/m3_multi_pool_factor_review_transports.csv`：0 数据行，SHA-256
  `d9e5055ba440c005d63b614dba15d5372da1dc7799773b933c0d937a9e76ed70`。

## 工程与隔离证据

- 全仓：`482 passed`；1 条既有 Starlette 第三方弃用 warning；
- M3-3 与 append-only 专项：`33 passed`；
- Ruff、`compileall`、`pip check`、Compose config、`git diff --check` 和凭据模式扫描通过；
- 同一不可变镜像连续运行两次，核心字段与全部哈希一致；两次均为 provider 调用 0、密钥读取 false、
  发现指标字段未解析、封存结果未读、账本 0 行；
- 容器为非 root、只读根、`network_mode:none`、无端口、无 Docker socket、无 secret environment；
- 未生成 provider 响应、候选效果、G1、模型、回测、组合或信号。

生产 scheduler 施工前后保持同一身份且健康：容器
`fd8e96152b53f3f0d0efdcd6462c2b039aa68c7fb56461b95826709652a5adbb`，镜像
`sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`，创建时间
`2026-07-24T12:25:27.362813588Z`。本阶段没有修改或重启 scheduler。

## 下一步授权边界

若继续 M3-3 live，只允许向 DeepSeek 发送固定两条公式、非权威假设/摘要、公开知识摘要、三规则池
定义和四个窄角色问题；恰好 8 个完成响应，串行执行，费用硬上限 `$0.25`。不得发送发现指标、行情
原始数据、证券清单、封存结果、收益、持仓、本地路径、日志或任何其他凭据。

在用户明确批准上述载荷、次数和费用前，`execution_authorized=false` 保持关闭，不创建 live 入口，
不运行审查，也不解封 M3-4、G1、模型、回测、信号或生产。
