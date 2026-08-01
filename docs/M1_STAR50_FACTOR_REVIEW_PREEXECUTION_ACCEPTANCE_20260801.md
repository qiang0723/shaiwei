# M1-2 科创50机械 Top2 独立审查：执行前验收

日期：2026-08-01（UTC+8）  
裁决：`GO_LIVE_RESULT_BLIND_REVIEW_ONLY`  
策略状态：`NOT_EVALUATED`  
生产授权：`none`

## 放行范围

- 只允许对 M1-1 已冻结的两条表达式各执行四个固定角色复核，共恰好 8 个完成响应。
- 请求只含表达式、原始经济假设、非权威研究背景与角色问题；发现期 RankIC、覆盖率、排序分、
  2023—2025 封存验证、压力期、G1、模型、组合与前瞻结果全部禁止进入请求。
- 任一响应结构或正文语义合同无效即计数并整批停止，不补发；任一候选出现 major/critical 阻断，
  该原式拒绝且不修式、不递补。
- 本批费用硬上限 0.25 USD；8 次全按 cache miss 与最大输出估算为 0.07656 USD。未用额度不自动授权
  后续批次。

执行放行单为 `config/m1_star50_factor_review_execution_v1.yaml`。本文件与放行单必须在首次请求前
提交并推送，live 入口会再次验证 Git、协议、候选、镜像与预算身份。

## 不可变身份

| 对象 | 身份 |
|---|---|
| 结果前审查协议 | `e37ace1d3b8a6c50724f89ebe426ff20ca2a4993f9c8e61eafe3196dc930a29f` |
| Prompt bundle | `5d49c40c9e61e5fc83015fdd965ee4897d5dc2e931cf31bc74d53a52050f1a5e` |
| 自由文本语义门 | `8faf36d33744aec06ec4331266dccf4d96dee904bac0a3d0fb603940e6aef15a` |
| M1-1 发现 manifest | `835d6cf6d5630423f12154ab367ddf46f6712c8f67f105a67802c48bcf29fa59` |
| M1-1 发现报告 | `5cdf09ca316eeb58a9613cf2c4596c0a1fdc2e0c6fd5af49d8974a10f68c45cb` |
| 请求束 | `4fda6297e9acb97b0040a9f2c77ff155087895b9645f99e07f9627f2a69f0557` |
| 实现 Git HEAD | `79e2096463e43674c88fcd46242f68ed9ffcea3f` |
| 最终镜像 | `sha256:15704c6a52ff8c62216498409bec2f9d4cabf6379cd2e89dfab80a8dd9604553` |
| 镜像代码快照 | `5d38f231b01462c438916c9e86b17a9a98ffdb320dfc0a743fea6df83ee40da5` |

## 盲态、隔离与工程门

- 主窗口在协议冻结前误见两候选的发现期 RankIC 与覆盖率，未见封存验证、压力或 G1 结果。污染值
  不进入请求、报告或 Git；主窗口不充当经济裁判，固定的结果盲委员会是本批唯一审查权。
- 最终 Docker 预检：候选 2、请求 8、`provider_calls=0`、`discovery_metrics_read=false`、
  `sealed_validation_read=false`，协议/语义门/请求束哈希均与冻结值一致。
- 容器非 root、只读根、无端口、无 Docker socket；只接收 `DEEPSEEK_API_KEY`，仅 M1-2 专属输出目录
  和两份追加式账本可写。TLS 主机探针及出站正文盲态扫描先于 secret 读取和首次请求。
- 宿主全仓 433 PASS；最终镜像在完整只读夹具挂载下 M1-2/语义专项 20 PASS。Ruff、compileall、
  Compose、diff-check、账本追加约束和凭据卫生均 PASS。
- 两次更窄的测试容器分别因未挂载 `data/ledger/.git`，以及未挂载 `docs/vendor` 出现夹具缺失；均为
  无效调用而非产品失败，未扩大 live 权限。补齐协议需要的只读夹具后 20/20 PASS。
- 第一份构建产物因外部传入的完整 Git 值与实际 HEAD 不同而在放行前作废；零 provider 调用。最终
  镜像按真实完整 HEAD 重建并通过内嵌身份核验。
- 首次 live 还暴露表达式解析器只读挂载遗漏；账本和输出均为零。恢复附录先行推送后只增加该挂载
  与回归测试，并按恢复提交重建上表终版镜像；协议、请求、候选、预算及数据边界未改变。
- 恢复后首次执行又在首请求前发现 execution release 覆盖了镜像受控 `config/`；第二份零调用附录
  先行推送后，只把同一只读 release 移到 `/opt/shaiwei/` 并锁定不得覆盖受控树。上表身份为此次
  恢复后的终版；账本、输出、provider 调用和费用仍均为 0。
- 生产 scheduler 始终为容器 `fd8e96152b53`、镜像 `sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`、
  创建于 `2026-07-24T12:25:27.362813588Z`，状态 running/healthy，未重启。

## 放行后的唯一动作

在放行提交已推送且工作树干净后，只运行一次 M1-2 live 入口。完成后必须用无密钥重放证明零新增
调用和产物/账本哈希不变，再形成脱敏 manifest 与终版验收。即使通过，也只允许另立 M1-3 验证协议；
本目标不得读取封存验证或运行 G1。
