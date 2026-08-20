# M6-4B-R6 生产 Head30 独立审计哈希权威恢复执行失败留痕

## 结论

R6 scope `349859a6794c3c50e377fdaf016e54fb854e1ab06be86b56aff40522799a90fa`
按用户精确授权唯一调用后，在 Docker 创建容器之前失败关闭。R6 不得重跑。

失败原因是新的宿主审计输出目录不存在，而冻结 Compose 对该 bind mount 使用
`create_host_path=false`。Docker daemon 因此拒绝创建容器：

`bind source path does not exist: .../effect-r2-audit-hash-authority-recovery`

这是输出根准备缺口，不是 R2 effect、独立审计算法或哈希权威门失败。

## 失败边界

- 容器创建：`false`；auditor 调用：0；audit 函数进入：`false`。
- R2 effect 语义读取：`false`；独立重算：未开始。
- R6 audit 输出：0 文件；输出根在失败后仍不存在。
- runner、Qlib、训练、预测、回测调用：0。
- 新增组合转换尝试：0；家族累计仍为 2。
- R2 effect 仍为 5 文件、1,191,570 bytes，树 SHA-256
  `d3d84d104968bf01f88312bd665060f2e57727145e4064697b4753bd6fc545c1`，前后不变。
- scheduler 仍为原容器 `183b8c6c5edd` 且 `healthy`，未重启。
- 生产授权：`none`；策略状态：`NOT_AUTHORIZED_PENDING_AUDIT_OUTPUT_ROOT_RECOVERY`。

## 后续边界

不得创建目录后复用 R6 scope。若继续，只能另立 R7 结果盲输出根恢复协议、新镜像或新 Compose 身份、
新输出根和新 scope。R7 必须在生成 scope 前由 daemon fixture 验证真实 writable bind source 已存在、
容器能够创建且 fixture 仍不挂载 R2 effect；哈希权威语义、主身份、`1e-12` 容差和 decision 门均不得
改变。真实 auditor-only 执行仍须用户对新 scope 精确授权。

机器真身：
`config/m6_csi800_production_head30_audit_hash_authority_recovery_execution_failure_v1.json`。
