# TS-v5-R3F 本地绑定 proposal 真实合同金丝雀验收

日期：2026-08-13（UTC+8）

权威裁决：`GO_BOUND_PROPOSAL_CANARY_ONLY`

策略效果：`NOT_EVALUATED`

生产授权：`none`

## 结论

R3E 的本地权威绑定修复已经通过真实 DeepSeek 金丝雀：六种机制按冻结顺序各取得一份完成响应，
6/6 均可解析、通过严格 proposal v3 Schema、由本地编译器注入批准的独立 lineage，并通过原冻结
`MechanismCandidate` validator；六个语义签名互不重复。

本次只证明“LLM 可以稳定产出符合筛微结构化合同的六类研究 proposal”。没有读取行情、证券、收益、
持仓或封存结果，没有执行参数搜索、回测、模拟仓、Web 或生产，因此不能表述为六个策略有效、因子
有效或可以交易。

## 结果前冻结顺序

- scope SHA-256：
  `1a45898caa3c4fac0c7a1b8a301271d48c3b0a666e947d7b988bd50d7e7aee61`
- scope/协议提交：`baa43ad`，先于实现推送。
- 请求束 SHA-256：
  `74eca6f39f088f837c7137d6861f5b61b6c1cac3c89da90d053e1821ca7c3a45`
- 无重试 transport 协议 SHA-256：
  `2510e8ccc5590fc8de37f48e0b3bfc85ee95e5bce5f353cb377d129d1e8b195c`
- proposal v3 合同/编译器 SHA-256：
  `c46ee09cf6d1039e85f797e8510284533e0b8980cda255bfb827c30e69942dc8` /
  `6b790b50664cf7304ffecc52ad0f6b0878ac2517cbdceeb075260949eebc15dc`
- 实现提交：`2031df86bd81e613c118b19a5af31deaa2be11d9`，全量验证后先行推送。
- 独立镜像：
  `sha256:f3ccf7dfde00da698f2eae2172dcabad33fbe65346c31b45611402959c056efd`
- 镜像内代码快照：
  `e1bdaa8b9d2ae1aff93139bf8d6419393911a325c05734642e9fb8b24ba79659`
- execution release SHA-256：
  `da758d6de3f09f71c03497b306938a9ecf66ef5170d0f6eddc606e4d11347ab6`
- release 提交：`e1e8f31813d5385a4d87ea7a05cc237cb68fc609`，先于 secret 读取与 API
  调用推送。

release 推送后，终版镜像再次在 `network=none`、无 secret、专用空账本下预检：请求束、Git、镜像、
代码快照、输出路径和单槽一次 transport 上限全部一致，`provider_calls=0`。

## 唯一真实批次

- 固定顺序：波动自适应回调、周结构分位、突破回踩、均线恢复、收缩扩张、相对强度回调。
- 独立席位 6、反方席位 0；完成响应 6、外部请求 6、第 7 次调用 0。
- 每个席位只有 sequence 1；`STARTED=6`、`COMPLETED=6`、HTTP 200=6、重试/递补/计费不确定=0。
- prompt tokens 18,825，其中 cache hit 1,024、cache miss 17,801；completion tokens 3,486。
- 实际费用 `$0.010779967`，低于本批 `$0.15` 硬上限，也低于结果前全未命中最坏估算
  `$0.051156`。
- `parse_status=PASS`、`schema_status=PASS`、`duplicate_status=UNIQUE` 均为 6/6；failure class 全空。
- 六个候选的参数槽数依次为 4/3/4/4/5/4；本地机械搜索预算依次为
  81/125/81/81/32/81，均不超过冻结上限 196。这里只形成预算，没有运行搜索。

DeepSeek key 仅由项目 `.env` 提供给一次性容器的 `DEEPSEEK_API_KEY` 环境变量；`.env` 未挂载到容器，
其他 Tushare/飞书变量没有进入服务声明、日志、账本或 Git。执行时直接使用 Compose 的项目级
`--env-file` 完成单变量注入，没有另建 secret 副本；这与协议正文建议的“专用临时 secret 文件”实现
形式不同，但满足 machine scope/release 冻结的“`.env` 不挂载、容器只注入 DeepSeek key”边界，特此
留痕而不静默改写协议。

## 断网独立审计与幂等

- 主报告 SHA-256：
  `a742ddc550f3a48af699ee74ef35f5a82ec918e4e04ca4d86d83233da98554f5`
- 独立审计 SHA-256：
  `9cd374470ff5b473da3fe4f2dc2d4b78912210d82c6a1f4dffe5131c61e03aa9`
- 脱敏 attempt ledger SHA-256：
  `ccf7155cbd769100b1d04b624f1605cfbe15d5961ec76f495cd7f33541817d98`
- 脱敏 transport ledger SHA-256：
  `3839d57fb02e8e7f03b317fb5b8d26333a36b6661dbdfb634764e6e4a9730121`
- Git 忽略区 28 份请求/响应/manifest/report 证据树汇总 SHA-256：
  `2f61c511ca4632064b698b6e06007eba5cf8cb9a0a5322dde8ebf2a9ec54645b`
- 独立审计在 `network=none` 且无 secret 下逐请求重建、逐响应重分类、复算费用/候选/证据束；13 项
  检查全部 PASS。
- 随后的 `network=none` 全只读调用入口只复用终端报告，`external_api_calls_this_run=0`；未改变两个
  专用账本或不可变产物。

原始 request、provider response、raw envelope 和 candidate manifest 全部位于项目内 Git 忽略目录；
Git 只提交不含 prompt/response 正文的脱敏账本。R3C/R3D/R3E 的文件、账本和裁决均未改写。

## 工程与生产隔离

- 全仓测试：1,284 PASS；17 条 warning 均为既有第三方弃用或 pandas 类型提示。
- 架构门：13 PASS；R3F 五个生产模块分别 298/67/221/287/275 行，均不超过 300 行专项上限。
- Ruff、compileall、pip check、Compose config、`git diff --check` 和凭据形态扫描 PASS。
- live 容器非 root、只读根、`cap_drop=ALL`，只挂 R3F 输出和两个专用账本；不挂原始行情、生产数据、
  Docker socket 或 `.env`。preflight/audit/replay 全部断网；audit/replay 不接 secret，账本只读。
- scheduler 仍是原容器 `183b8c6c5edd`、原镜像 `shaiwei:scheduler-current`、创建时间
  2026-08-03 17:39:34 +0800，连续运行且 `healthy`；本节点未重启或替换。

## 下一合法节点

R3F scope 已完整消费并关闭，不得递补、改写回答或发起第 7 次调用。下一步不是直接寻找最高收益，
而是另立结果前的 `R3G` 小规模发现期评价协议：先把六个候选登记进永久尝试谱系，做确定性语义/行为
去重，冻结发现期、事件密度门、参数预算、成本与多重检验背景，再允许本地断网参数搜索和发现期评价。
该阶段会首次读取行情/效果，必须由主控单独冻结 scope；历史发现 GO 仍不授权模拟仓或生产。
