# M6-2R 独立审计入口恢复终版验收

- 验收日期：2026-08-07（UTC+8）
- 原真实效果 scope：`9b609f0764240ff3930a4aeaaf16cef9deb82579d2a5875f1be9e8c4ffb0b139`
- 恢复 scope：`30ab35ed29b8e0135fcc81d4d274b764870154aa07bbc0469903f30e260e1ec1`
- 批准动作：`M6_INDEPENDENT_AUDIT_ENTRYPOINT_RECOVERY_ONCE`
- 终态：`independent_audit=PASS`
- 权威归因裁决：`PORTFOLIO_CONVERSION_BOTTLENECK_INDICATED`
- 生产授权：`none`

## 1. 恢复原因与边界

M6-2 唯一真实 runner 已在原授权下完成 `first_pass/replay`，并消费恰好两个替代研究尝试。原 auditor
进程在进入 `audit()` 前因 CLI 参数名与函数关键字不一致而停止，未读取效果语义、未产生 audit 文件。
原 runner、scope、approval、report、两遍产物和失败事实均永久保留，不以恢复覆盖。

M6-2R 只允许在原不可变镜像外增加薄控制入口，用显式关键字调用字节未变的原审计函数。恢复容器断网、
非 root、只读根，无 Qlib、`.env`、Docker socket、整仓、实验账本或生产挂载；effect 只读，空 audit
目录是唯一可写目标。本恢复不训练、不预测、不回测、不增加第三臂，也不修改模型、特征、窗口、组合、
成本、指标、统计、门槛或终态逻辑。

## 2. 执行前身份

- 实现提交：`010e6f4dba6ed094c8a181d3a809e6c53c10a71d`，scope 提交：
  `157f0f5d255578bb83b74ac525c74668d85f8392`，执行前均已推送 `origin/main`；
- 原基础镜像：`sha256:3c40c9c74bbbda926433f2d49cd78128c665cbb84e071ab3d44d187ecc2cd40e`；
- 薄恢复镜像：`sha256:658d64584a7d4c954f1320cecb2b7d6d88cc1acb99392190166ea92c638a24b0`，
  `linux/arm64`；
- 原镜像和薄镜像中的 `effect_audit.py` 物理 SHA 均为
  `e2bf3ec57ca6025d5388785a548eadb9b20768c329c47ba89ac738efbd6987c8`；
- 恢复合同/入口 SHA：`2ccab6b8...ed1cd` / `f26b00e2...723a`；
- recovery approval SHA：`103cdb00fcc9d17efa458367fc159d3af3016f7f3fb484c58152329d03f4c24f`；
- 执行前 effect：199 文件、84,957,571 字节，整树 SHA
  `dfbc0b52f40250b7151d74d9a45f3fdc17a69ca1f7b9c853267c1071b4b0d5cb`；audit 目录为空。

薄镜像的零挂载、断网 synthetic 自检通过：原审计签名 PASS、树篡改检测 PASS、真实效果读取 false、
审计调用 false。只挂载协议、scope 和 Compose 的 release-only 验证也通过，未挂载 effect 或 approval。

## 3. 唯一恢复调用

2026-08-07 08:34（UTC+8）只调用一次 `make docker-m6-audit-recovery-run`，进程退出码为 0。输出明确：

- `independent_audit=PASS`；
- `additional_alternative_attempt_count=0`；
- `runner_invocation_count=0`；
- `effect_tree_unchanged=true`；
- `reused=false`；
- `production_authorization=none`。

恢复容器结束后已自动删除，不存在活动 M6 恢复容器；本 scope 不得再次运行。

## 4. 权威结果

两个预冻结替代臂都通过分数改善门，但均未通过组合转换门：

| 替代臂 | pooled RankIC 增量 | RankIC 正窗 | 1.0x/1.5x/2.0x pooled 净超额增量 | 净超额正窗 | 最大回撤 | NW(10) t / Holm p |
|---|---:|---:|---:|---:|---:|---:|
| Ridge `alpha=1.0` | +0.008649 | 4/6 | -33.96% / -33.39% / -32.83% | 3/6 | 27.78% | -0.961 / 1.000 |
| LGBM/Ridge 排名 50/50 融合 | +0.008776 | 5/6 | -37.17% / -36.57% / -35.98% | 3/6 | 26.60% | -1.225 / 1.000 |

两臂换手比分别为控制组的 100.28% 和 101.27%，单独满足不超过 110% 的上限，但不能抵消以下失败：
主要检验未通过、pooled 增量为负、只有 3/6 净超额窗口为正、三档成本增量均为负，且最大回撤超过
20%。独立 auditor 已从成员日、预测、标签、组合日报和压力期产物重新计算 RankIC、成本、主动收益、
换手、回撤、NW(10)、Holm、Top30 及最终类别，并确认首遍/replay 完全一致。

因此权威裁决是 `PORTFOLIO_CONVERSION_BOTTLENECK_INDICATED`：替代模型的横截面分数包含增量信息，
但冻结的 Top30/`n_drop=3`/10 日调仓组合没有把信息转化为更好的扣费后结果。这是资源排序证据，不是
因果证明，也不是策略准入或生产授权。按结果前协议，下一研究批最多改变一个事先冻结的组合转换变量，
不得继续增加模型、seed、网格或第三臂；任何后续批次仍须另立协议和授权。

## 5. 不可变证据

- 原 report SHA：`65e7b7ae2a8c4844f11d855f978d13c58eb082547f76a92ce92c8d6dc94b29f3`；
- 首遍/replay bundle SHA 均为
  `424e3ff9751522bb11736b4a80ef5dc8225a25ef14475611e6335e6ff0dea27e`；
- 独立重算 SHA：`ade8c64f79cb4ed3f5e1763c2f1b82b6c1f8ae503032d85091eada3e671106e1`；
- `audit.json` SHA：`8788bddc6df2bdd74de489b7efaaf8eb1818c9787424a59a9e59b8ab2c5d0fd6`；
- `recovery-receipt.json` SHA：
  `178f7bd21eac10c2a0d3743e1b38bd84c774b18bf6e2d93ac659f6b497ff3785`；
- effect 前/后/终验整树身份均为 199 文件、84,957,571 字节、SHA
  `dfbc0b52f40250b7151d74d9a45f3fdc17a69ca1f7b9c853267c1071b4b0d5cb`。

approval、真实 effect、audit 与 receipt 均在项目 `data/` 忽略区，不提交 Git。实验账本未写入；自然
scheduler 账本改动不纳入本次提交。scheduler 施工前后均为容器 `183b8c6c5edd`、镜像
`sha256:722f63de...13b76`、创建时间 2026-08-03 17:39:34（UTC+8），状态 healthy，未重启。

## 6. 工程验证

- 恢复实现提交前：全仓 871 PASS，架构门 6 PASS，Ruff、compileall、pip check、Compose 展开和
  `git diff --check` PASS；
- 正式恢复后：M6 release/recovery 专项 27 PASS，架构门 6 PASS；
- 新模块均不超过 400 行；薄镜像仅复制恢复合同和入口两个文件，原 `/workspace` 未改变；
- 受控文档与提交范围未发现凭据；未读取 `.env`，未访问筛微目录以外的任何项目。
