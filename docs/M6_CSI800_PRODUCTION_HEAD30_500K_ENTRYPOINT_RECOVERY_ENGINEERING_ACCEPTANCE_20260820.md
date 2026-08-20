# M6-5B-R1 50万元历史回放入口恢复工程验收

## 裁决

`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`。

本节点只修复 runner 与独立 auditor 的 CLI 参数映射，并完成新镜像、新输出根与精确 release scope。
没有运行真实50万元回放，没有读取封存目标、价格、收益或效果，也不授权生产。

## 失败继承

- 原 scope：`62f88802a8812a8ce87facd4a149c99b26fc0329497983d62cfc27d215c7570d`。
- 原入口在进入 `run()` 前因 `release` / `release_path` 参数名不一致失败；独立 auditor 同类缺陷在
  调用前被发现。
- 原 effect/audit 均为0文件，新增语义尝试0；家族累计仍为1，但原 scope 永久关闭不得重跑。
- 机器失败证据：`config/m6_csi800_production_head30_500k_entrypoint_failure_v1.json`，SHA-256
  `289f21b04e6501d26126d2aee84d2a4fce086479c61899927a278e43fdbb6f6a`。

## 唯一修复与复用边界

- runner/auditor CLI 均逐项把公开参数显式映射到领域函数参数，禁止继续使用无检查的
  `**vars(parse_args())`。
- 原 `run()`、`audit()` 的领域流程抽成共享已授权执行函数，新R1适配器只负责版本化协议、scope和
  approval校验；paper-v1引擎、Head30目标、500,000元、费用/整手/现金/容量、评价门均未改变。
- 新增生产模块均低于400行；未复制账户计算或独立审计统计口径。

## 镜像与合成验收

- 实现提交：`3f13e150361c577b2c01258047c7ee7e80e283b7`，构建前已与`origin/main`同步。
- 镜像：`shaiwei:m6-head30-500k-entrypoint-recovery-v1`。
- 镜像ID：`sha256:afe3d03361692565a02889d8e2a60522a2e04bc07e3f24a7e70904e9c32b6b7a`，
  `linux/arm64`。
- 镜像代码快照：`edd471d46c7facf7cd06f07b7bb8a34c4ca300ca5aef47390d428586f0590c9f`；镜像内
  定向核验Git提交与快照均一致。
- release manifest：1,200文件，SHA-256
  `ee0803c2a9d6e34c3ed53cf2c98210551e8560ae1815c83380f046084a79461f`。
- daemon断网、只读根、非root合成fixture真实穿过runner CLI和auditor CLI，并完成paper-v1、内部
  first/replay与独立重算；状态PASS，SHA-256
  `6ad522f26c7ff608254a745a1386ad30651f03900d488540f8d44d6bbd4d557d`。
- fixture明确记录`real_target_read=false`、`real_price_or_effect_read=false`、`network_used=false`、
  `model_fit_count=0`。

## 精确 scope 与停止点

- 新 scope：`c73b4afb452c55dce0149ef1fd8770c28538be03ec16de6c6de00881f3c74757`。
- scope文档SHA-256：`5c73298a5b6730a55961a699eeabb32097f16789e977c1821e41ffaa97735e40`。
- 仍绑定原21,815个不可变原始批次manifest、R2五文件树和R7独立审计身份；只读取元数据与哈希。
- 新 effect 根`effect-r1`与audit根`effect-r1-audit`均为0文件；approval-r1尚不存在。
- scheduler保持原容器healthy且未重启；模拟仓、Web、账本、生产均未修改。

只有用户绑定上述scope SHA并批准动作
`M6_HEAD30_500K_FEASIBILITY_ENTRYPOINT_RECOVERY_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT`后，才可
唯一执行一次真实first/replay和一次独立audit，届时新增尝试1、家族累计2。同scope不得重跑；外网、
模型拟合、新预测、实验账本、前瞻、模拟仓写入、Web、scheduler和生产继续禁止。

## 验证

- 入口与release专项：18 PASS。
- 架构门：13 PASS。
- 全仓：1,628 PASS，17条既有第三方/未来兼容warning。
- Ruff、compileall、pip check、Compose config、`git diff --check`与定向敏感凭据扫描：PASS。
