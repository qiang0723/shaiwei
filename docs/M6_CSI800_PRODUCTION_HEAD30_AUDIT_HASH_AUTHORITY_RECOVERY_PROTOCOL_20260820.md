# M6-4B-R6 生产 Head30 独立审计哈希权威恢复协议

## 冻结结论

R6 只删除 R5 实现多加的“本次独立重算 SHA 必须等于历史独立重算 SHA”权威门。R5 已唯一调用并
永久关闭；R5 证据表明其余主身份、重放、冻结 `1e-12` 容差等价和 decision 一致性门全部通过。

R6 不改变策略、结果、组合、成本、G0、主结果身份、数值容差或生产权限。当前独立 SHA 仍必须写入
audit；历史独立 SHA 也保留为谱系诊断，但两者是否逐字节相等不再参与判决。

## 发布对抗门

最终镜像的断网 daemon fixture 必须同时通过：

1. R5/R4/R3/R2 完整谱系与 authority 预检；
2. 历史独立 SHA 不同、但数值在 `1e-12` 容差内且 decision 一致时通过；
3. 任一数值超出冻结容差时失败关闭；
4. decision 不一致时失败关闭。

fixture 禁止挂载 R2 effect，因此不读取真实结果、不执行真实审计。

## 执行边界

R6 仍为断网 auditor-only，不挂载 Qlib、项目根、`.env`、Docker socket、生产账本、模型、预测或
其他项目。R2 effect 只读，新 R6 audit 目录可写。生成新 scope 后停止；真实审计必须取得用户对
新 scope SHA-256 的精确授权，R2/R3/R4/R5/R6 均不得重跑。

机器真身：
`config/m6_csi800_production_head30_audit_hash_authority_recovery_v1.yaml`。
