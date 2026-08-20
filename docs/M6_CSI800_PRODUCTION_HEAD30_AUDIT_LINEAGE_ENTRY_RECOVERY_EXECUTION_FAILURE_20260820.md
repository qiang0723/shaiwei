# M6-4B-R5 生产 Head30 独立审计谱系入口恢复执行失败留痕

## 结论

R5 scope `baa43d73ab0310c039d1c4794e74ebd3eda4a51578204224778ddaca0d724789`
按用户精确授权唯一调用后失败关闭，R5 不得重跑。

本次完整谱系预检成功，R2 effect 已只读加载并完成独立统计重算。所有主产物身份、首遍/重放身份、
冻结 `1e-12` 容差等价和主判/独立判决一致性检查均通过；唯一失败项为：

`independent_result_lineage`

审计在写出 artifact 前失败，因此 R5 audit 输出仍为 0 文件。

## 根因

R5 沿用了 R3 入口中的额外检查：要求本次独立重算结果的 canonical SHA 与 R3 失败时记录的历史独立
重算 SHA 完全一致。该要求把浮点独立重算再次当成了跨运行逐字节身份。

冻结 R3 协议实际要求的是：

- 独立重算不得导入主计算代码；
- 与主结果按相对/绝对 `1e-12` 容差等价；
- 主判和独立判决完全一致；
- 独立 SHA 被记录；
- 不要求独立结果 SHA 等于主结果 SHA。

R3 协议没有要求后续独立重算 SHA 必须等于某次历史独立重算 SHA。因此本次失败是实现比冻结协议多加
了一项不稳定的字节级权威门，不是 R2 策略、结果、主身份或统计等价失败。

## 失败后证据

- R5 auditor 容器调用：1；R5 同 scope 不得重跑。
- `effect_semantics_read=true`，独立重算已完成。
- 失败列表只有 `independent_result_lineage`，其余 audit checks 全部 PASS。
- runner、Qlib、训练、预测、回测调用：0。
- 新增组合转换尝试：0；家族累计仍为 2。
- R5 audit 输出：0 文件。
- R2 effect 仍为 5 文件、1,191,570 bytes，树 SHA-256
  `d3d84d104968bf01f88312bd665060f2e57727145e4064697b4753bd6fc545c1`，五份物理哈希不变。
- scheduler 为原容器 `183b8c6c5edd`，healthy，未重启。
- 生产授权：`none`；策略状态：`NOT_AUTHORIZED_PENDING_INDEPENDENT_HASH_AUTHORITY_RECOVERY`。

## 后续边界

不得重跑 R2、R3、R4 或 R5。若继续，只能另立 R6 结果盲独立哈希权威恢复协议、新镜像、新输出根和
新 scope。R6 只允许删除“当前独立 SHA 必须等于历史独立 SHA”的额外实现约束；仍须记录当前独立
SHA，并保持主身份精确、独立 `1e-12` 容差等价、decision 精确一致和生产 `none`。

R6 发布 fixture 必须显式覆盖：历史独立 SHA 不同但数值容差等价且 decision 一致时通过；数值超容差
或 decision 不同时失败关闭。真实审计仍须用户对新 scope 精确授权。

机器真身：
`config/m6_csi800_production_head30_audit_lineage_entry_recovery_execution_failure_v1.json`。
