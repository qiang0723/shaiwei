# M6-4B-R3 生产 Head30 独立审计身份恢复协议

## 结果目标

对 R2 已封存、已内部重放一致的五份效果产物执行一次 auditor-only 恢复审计，修复“独立浮点重建
必须与主结果生成相同 canonical SHA”的错误身份合同。恢复通过后才能把既有研究裁决升级为权威
历史研究结论；本节点不产生新策略结果，也不授权前瞻、模拟仓或生产。

## 权威事实与不可触碰边界

- R2 effect 树固定为 5 文件、1,191,570 bytes、tree SHA-256 `d3d84d10...45c1`。
- first/replay bundle 物理 SHA 均为 `389c1770...92ec2`；报告 SHA 为 `79c67444...1d3a`。
- 报告 `result_sha256` 与主 bundle 的 canonical result SHA 均为 `42a60f59...de7a1`。
- 原 R2 runner、auditor 和 scope 均永久不得重跑；R2 1 次、家族累计 2 次组合转换尝试不得改写。
- 恢复过程只读 effect，不挂载 Qlib，不运行 runner、训练、预测或回测，新增尝试为 0。

## 单一恢复变量

旧 auditor 同时要求：独立重建在 `1e-12` 容差内等价，以及独立重建 canonical SHA 与主结果完全
相同。第一条已经通过；第二条把不同求和顺序产生的机器级浮点尾差错误解释为身份漂移。

R3 将身份拆为三层：

1. **主产物精确身份**：report 必须精确绑定 first/replay bundle 文件哈希，且
   `report.result_sha256 == canonical_sha256(first.result)`。
2. **独立数值重建**：继续调用现有、未导入主计算实现的 `independently_evaluate`，逐字段使用冻结的
   `rel_tol=abs_tol=1e-12`；独立 SHA 只记录，不要求等于主 SHA。
3. **裁决精确一致**：report、主 bundle 与独立重建的 decision 必须逐字相同，生产授权必须为 none。

这不改变 G0、窗口、成本、组合、收益或任何阈值，也不对封存数值做舍入、归一化或重写。

## 架构与失败关闭

- 新能力属于一次性研究审计编排层；复用既有独立统计内核和内容寻址函数，不修改冻结的
  `real_audit.py`。
- 使用从 R2 不可变镜像派生的薄恢复镜像；仅复制版本化 recovery contract/entrypoint，运行时断网、
  只读根、非 root、无 `.env`、无 Docker socket、无项目整仓或生产账本挂载。
- 任一文件、scope、approval、镜像、运行时、树身份、主哈希、容差等价或 decision 不一致均失败关闭；
  恢复输出写入全新的 Git 忽略目录 `effect-r2-audit-recovery`，不污染旧空 audit 根。
- 成功时写 `audit.json` 与 `recovery-receipt.json`；receipt 必须证明 effect 树前后完全一致。

## 施工与授权顺序

1. 本协议先独立提交并推送。
2. 实现与对抗测试提交推送后，构建不可变薄镜像并仅运行纯合成 fixture。
3. 生成绑定镜像、协议、R2 scope/approval 和 effect 树的新 release scope，再提交推送。
4. 停在用户精确授权前；真实恢复审计只允许执行一次，同 scope 不得重跑。

协议机器真身：`config/m6_csi800_production_head30_audit_identity_recovery_v1.yaml`。
