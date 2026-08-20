# M6-4B-R7 生产 Head30 独立审计输出根恢复协议

## 结论

R7 是结果盲、auditor-only 的输出根恢复，不改变 R6 审计语义，也不授权真实执行。

R6 唯一调用在 Docker 创建容器前失败，因为新的宿主 audit 根不存在，而冻结 Compose 正确设置了
`create_host_path=false`。R7 只允许显式创建一个新的空目录，并在 release scope 生成前由最终镜像的
daemon fixture 验证该目录确实可写、可读、内容哈希一致且哨兵可删除。

## 唯一变化

新宿主输出根固定为：

`data/research/m6_csi800_production_head30_v1/effect-r2-audit-output-root-recovery`

fixture 和未来真实服务必须绑定同一个宿主目录。fixture 必须：

1. 在运行前确认目录存在且为空；
2. 以非 root、只读容器根、断网环境挂载该目录为可写；
3. 写入固定哨兵，读回并核验 SHA-256；
4. 删除哨兵，并确认目录重新为空；
5. 不挂载 R2 effect，不进入独立审计。

`create_host_path=false` 保持不变，防止 Docker 静默创建错误路径。

## 完整继承

- 当前独立 SHA 必须记录；历史 SHA 只作诊断，不作跨运行字节级裁决。
- R2 主结果必须匹配封存精确身份，首遍与 replay 物理身份必须一致。
- 独立重算继续使用相对/绝对 `1e-12` 容差，decision 必须完全一致。
- R2 effect 前后树哈希必须一致。
- Qlib、runner、训练、预测、回测、实验账本、网络、凭据、前瞻、模拟仓、Web 与生产均禁止。
- 新增组合尝试为 0；家族累计仍为 2。

## 顺序与授权

本协议必须先提交并推送，然后才能实现 R7。最终镜像和同根目录 daemon fixture PASS 后，才能生成
新的精确 scope。scope 仍不是执行授权；真实 auditor-only 容器必须等待用户绑定完整 R7 scope SHA
与动作 `M6_PRODUCTION_HEAD30_AUDIT_OUTPUT_ROOT_RECOVERY_ONCE` 明确批准。
