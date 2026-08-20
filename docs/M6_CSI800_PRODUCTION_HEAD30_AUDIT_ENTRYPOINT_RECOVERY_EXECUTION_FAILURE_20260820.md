# M6-4B-R4 生产 Head30 独立审计入口恢复执行失败留痕

## 结论

R4 scope `d07daefb27918286f8efa712e60dd6d21482c75b71f7677bd634b85b61c3bd71`
按用户精确授权唯一调用后失败关闭，R4 不得重跑。

容器已由 Docker daemon 创建；失败发生在 R4 校验 R3 谱系文件时，尚未读取 R2 effect 语义，
尚未进入独立统计审计，也没有写出 audit 文件：

`FileNotFoundError: /workspace/config/m6_csi800_production_head30_audit_identity_recovery_v1.yaml`

## 根因

R4 薄镜像以 R3 镜像为基础。R3 镜像本身继承的是 R2 的 `/workspace`，只把 R3 Python 合同和入口
复制到 `/opt`，没有把 R3 协议 YAML 放入 `/workspace/config`。R4 的合成 daemon fixture 精确覆盖了
旧 R2 协议的合法路径，却没有覆盖真实入口新增的 R3 协议谱系路径，因此工程门漏检了这个挂载/镜像
差异。

这是入口与容器打包缺陷，不是研究、统计、策略或 R2 效果缺陷。

## 失败后证据

- R4 auditor 容器调用：1；同 scope 重跑授权：否。
- runner、Qlib、训练、预测、回测调用：0。
- 新增组合转换尝试：0；家族累计仍为 2。
- R4 audit 输出：0 文件。
- `effect_semantics_read=false`。
- R2 effect：5 文件、1,191,570 bytes，树 SHA-256 仍为
  `d3d84d104968bf01f88312bd665060f2e57727145e4064697b4753bd6fc545c1`。
- 五份关键文件物理哈希与 R4 执行前完全一致。
- scheduler 仍为原容器 `183b8c6c5edd`，healthy，未重启。
- 生产授权：`none`；策略状态：`NOT_AUTHORIZED_PENDING_AUDIT_LINEAGE_ENTRY_RECOVERY`。

## 后续边界

不得修改或重跑 R2、R3、R4。若继续，只能另立 R5 结果盲谱系入口恢复协议、新镜像、新空输出根和
新 scope。R5 必须在最终镜像的 daemon fixture 中执行与真实入口相同的完整 authority/lineage
预检（包括 R3 协议文件），而不是只验证旧 R2 协议；真实 auditor 仍须用户对新 scope 精确授权。

机器真身：
`config/m6_csi800_production_head30_audit_entrypoint_recovery_execution_failure_v1.json`。
