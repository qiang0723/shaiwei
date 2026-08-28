# R2D-R3A 健康收敛真实 Fixture 执行验收

## 裁决

`PASS_FIXTURE_ONLY / PRODUCTION_AUTHORIZATION_NONE`。

原 scope `fb3bcefb...2708` 完成唯一候选构建后，因构建动作按设计追加 `BUILD_PASS`，其构建前 release-audit 身份已不再适合作为 fixture 前置身份，故在 fixture 命令前失败关闭；候选未重建，fixture 调用次数为 0。恢复 scope `49a322aef...27017` 绑定构建后 release-audit 后，复用同一候选执行唯一一次断网真实 named-volume fixture，六门全部 PASS。

## 精确证据

- 候选：`shaiwei:scheduler-97d8c05eab2a1e8c`；镜像 ID `sha256:b64ae11b...c5ebe`；代码快照 `97d8c05e...7553`；
- report SHA-256：`c73cbe4f6efe4b3b5b953b8fc42da2055b270d890186a78545f70724219bfb8c`；
- tree 文件/内容 SHA-256：`d01fbf5a...ef02` / `d1febbf3...3c07`；
- receipt SHA-256：`f50f7088...bd40`；
- 六门：生产 release 证据匹配、候选标签、真实 `starting`、共享合同收敛 `healthy`、守卫成功路径零 rollback、生产证据前后不变，均 PASS。

## 边界

候选构建恰好 1 次、恢复 fixture 恰好 1 次；未读取 `.env`/密钥或业务数据，未访问业务外网，未 promote、start、restart 或手工跑批。旧生产 release state/audit 哈希在 fixture 前后不变，scheduler 保持旧生产身份与 healthy。该 PASS 只证明发布路径工程可用，不证明自然交易日运行，更不证明策略有效。
