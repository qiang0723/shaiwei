# M1-1 科创50价量因子发现批：执行前验收

日期：2026-08-01（UTC+8）  
裁决：`GO_LIVE_DISCOVERY_ONLY`  
结果状态：`NOT_EVALUATED`  
生产授权：`none`

## 本批唯一授权

- 研究家族：`m1-star50-price-volume-v1`。
- 股票池：官方 PIT 科创50，`star50-official-pit-v2`。
- 模型：`deepseek-v4-pro`，thinking enabled，reasoning effort high。
- 完成响应：恰好 40；每个完成响应均计研究家族 N，失败、重复和语义拒绝不递补。
- 预算：D1 总授权 10 USD，本批硬熔断 1 USD；未使用余额不构成后续批次授权。
- 允许：受限价量 DSL 的假设生成、语法/沙箱/语义门、冻结发现期 RankIC 与覆盖率评价、机械 Top2 锁定。
- 禁止：读取 2023-01-03 至 2025-12-31 封存验证窗、压力期、G1、模型训练、组合回测、前瞻、生产、Web、观象和新增市场采集。

执行授权由 `config/m1_star50_factor_execution_v1.yaml` 固化，提交
`f811961b1532c0474d0a23eb8fb674b497f0d164` 已先于任何本批 API 请求推送到 `origin/main`。

## 不可变身份

| 对象 | SHA-256 / Git 身份 |
|---|---|
| 结果前研究协议 | `a6bcf102480505e53b4bcb087a8f82ceee55fd4494004f6805f559e5d3dbf534` |
| Prompt bundle | `6e0df7fd61b5c309cdcbbc72c02417de92a110f7799b816044971e8dc52fcd06` |
| 冻结知识 manifest | `0f1e8ab2461352ce020dcf1873a5d79bfc010b08eea205b6b308e27bc3c23fad` |
| 发现输入快照 | `f6ad4566a522281102dd84a993bf9e774228bc0271ee9adb1ea3e1d3103cf4c5` |
| STAR50 qlib 树 | `b8f736ef9bc9e31cc236a81ca281a23e904789fb5ec87caa9195b572c6b78729` |
| 成员日数据 | `a6fb10532bba9de9504fc4be0bfe6e45e50621a761ae29fbaa1cf9ba39356061` |
| 最终研究镜像 | `sha256:7729c89e56865db4b2369f2f076db9bf9068017d34b830bb4dffab9ca3bb411c` |
| 镜像内代码快照 | `180ad8fc02d2dba9f2f8eca30d5684c2b3a1e366a221f071279effb83dfc4473` |
| 镜像 release Git HEAD | `f811961b1532c0474d0a23eb8fb674b497f0d164` |

## 数据与隔离门

- 最终断网只读预检：577 个发现信号日、28,850 个官方成员日、每日严格 50 只、28,838 个可用行情成员日；`.BJ` 为 0。
- 最后一个发现标签在 2022-12-30 成熟；封存验证窗从下一官方交易日 2023-01-03 开始，预检与执行 release 均拒绝跨界。
- 首次容器预检因注册表引用的已脱敏证据文档不在镜像内而 fail closed，`provider_calls=0`。修复仅给 M1 预检/执行容器增加 `docs` 只读挂载；没有跳过注册表证据校验。
- M1 执行容器非 root、只读根、无端口、无 Docker socket、不加载 `.env`，只接收单一 `DEEPSEEK_API_KEY` 环境项；数据与证据只读，仅专属结果目录和三份追加式账本可写。
- 生产 scheduler 保持容器 `fd8e96152b53`、镜像
  `sha256:de87ec740981166b032b394fb256a978acdc8d35e999a369f1debc3466aa0261`、
  创建时间 `2026-07-24 20:25:27 +0800`，状态 healthy，未重启。

## 工程验证

- 宿主全仓：422 PASS；Ruff、compileall、pip check、Compose 校验、diff-check 和凭据模式扫描 PASS。
- 最终只读镜像：release manifest 重算 PASS；M1-1 专项 18 PASS；pip check PASS；最终零调用输入预检 PASS。
- 另一次把旧 D1 全套测试放入最窄 M1 预检容器时为 49 PASS、2 FAIL；两项失败都只因该容器按设计没有挂载旧 D1 账本。没有为通过测试扩大权限，旧 D1 全套已包含在宿主 422 PASS 中。

## 操作化说明

冻结协议把后续变异反馈概括为 `semantic_gate_status`；现有追加式尝试账本没有新增一列，而是以
`failure_class=semantic_contract_violation` 表示语义门失败。两者语义一一对应，所有语义失败照样计 N、
不运行 DSL 沙箱或发现评价。该说明不更改协议、候选、预算、排序或结果边界。

## 下一步

只允许运行一次本批 live 入口，网络中断时从已核验的连续账本前缀恢复；完成 40 份后机械锁定最多
Top2，并做无密钥、零网络调用的幂等复跑。任何验证窗、G1 或生产动作都必须另立目标与结果前协议。
