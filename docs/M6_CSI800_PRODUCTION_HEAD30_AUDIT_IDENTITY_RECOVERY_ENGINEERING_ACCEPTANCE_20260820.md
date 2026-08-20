# M6-4B-R3 生产 Head30 独立审计身份恢复工程验收

## 结论

`GO_AUDIT_IDENTITY_RECOVERY_RELEASE_READY_NOT_EXECUTION_APPROVAL`。R3 已完成版本化 auditor-only
合同、隔离 Docker、不可变薄镜像、纯合成对抗 fixture 和精确 release scope；真实 R2 effect
未由恢复入口读取，恢复 audit 未运行，新增组合尝试为 0，生产授权为 `none`。

## 单一恢复变量

- 主结果身份仍严格校验：report 必须精确绑定 first/replay 文件哈希，且 report 的 result SHA 必须
  等于主 bundle result 的 canonical SHA。
- 独立重建仍复用既有 `audit_statistics.independently_evaluate`，逐字段使用冻结的
  `rel_tol=abs_tol=1e-12`；独立 SHA 被记录，但不再错误要求与主结果 SHA 相等。
- report、主 bundle 和独立重建 decision 必须逐字一致；G0、窗口、成本、组合、收益和阈值均未改变。
- 任一主身份漂移、裁决漂移、超容差差异、文件集合漂移或 effect 树改写均失败关闭。

## 架构与边界

- 原冻结 `real_audit.py` 零修改；新增 contract 307 行、entrypoint 384 行、release builder 214 行，
  职责分别为合同、一次性审计编排和发布元数据，没有新增万能模块或超 400 行生产文件。
- 薄镜像从原 R2 镜像精确派生，只复制 recovery contract/entrypoint；运行时断网、只读根、非 root、
  cap-drop、no-new-privileges，无 Qlib、`.env`、Docker socket、项目整仓或生产账本挂载。
- effect 只读；未来恢复输出使用新目录 `effect-r2-audit-recovery`。原 R2 五文件、失败的空 audit 根、
  R1 证据及 scheduler 均未修改。

## 不可变身份

- 协议冻结提交：`3dbaec5344954b041c1966043e9066d6fb8b08c9`。
- 实现提交：`4ccab1baf78f60ecbc0239ce4fab1e3cbe6325af`，构建前与 `origin/main` 一致。
- 恢复协议 SHA-256：`60e36c6ebedcf9051561f6fc823866787a982dac79651e24c40bfb39c2f8d2e2`。
- 镜像：`shaiwei:m6-production-head30-audit-recovery-v1`，ID
  `sha256:91cca66537e0ba058116f79c20897728d9913aa850af6e9f4efb8f50f61c9d3c`，平台
  `linux/arm64`；基础镜像 ID `sha256:a6544aff...64b29`。
- 镜像内 Git：`4ccab1b...25af`；contract/entrypoint SHA-256 分别为
  `1586afcf...6cba` / `3c88b973...e563`。
- 精确 recovery scope SHA-256：
  `b38628defcfee83087f0c0d982d0c1145b3f6d642c28508055cba2bddb9614d3`；scope 文档 SHA-256：
  `b6f385911832e104b04ca3354e3ec385af92645f24a2fc81a0c5f7fb6d9a40bd`。
- scope 绑定 R2 五文件、1,191,570 bytes、tree SHA-256 `d3d84d10...45c1`，以及原 scope、approval
  和审计失败证据；authority 仍为 `execution_authorized=false`。

## 验证

- R3 专项：13 PASS；架构宪法：13 PASS；全仓：1550 PASS，17 条既有 warning。
- 最终薄镜像断网 fixture：浮点尾差等价、主/独立哈希分离、裁决漂移失败关闭、树篡改检测均 PASS；
  `real_effect_read=false`、`audit_invoked=false`。
- Ruff、compileall、pip check、Compose 展开、`git diff --check` 与脱敏扫描均 PASS。
- scheduler 容器 `183b8c6c...5edd`、镜像 `722f63de...3b76` 保持 healthy，未重启或替换。

## 下一合法节点

当前必须停止。若用户继续，唯一授权句为：

> 批准 M6-4B-R3 release scope
> `b38628defcfee83087f0c0d982d0c1145b3f6d642c28508055cba2bddb9614d3` 按动作
> `M6_PRODUCTION_HEAD30_AUDIT_IDENTITY_RECOVERY_ONCE` 运行一次断网 auditor-only 身份恢复审计；
> 只读 R2 五份封存 effect，新增组合尝试 0，不授权 Qlib、runner、训练、预测、回测、实验账本、
> 外网、前瞻、模拟仓、Web 或生产，同 scope 不得重跑。
