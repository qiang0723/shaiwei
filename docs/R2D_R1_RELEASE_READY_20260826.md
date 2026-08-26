# R2D-R1 旧时钟边界恢复发布就绪验收

## 裁决

`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`。

R2D-R1只修复原Phase B无法在16:05—19:00获得旧19:30 scheduler `waiting_source`的证据合同。
候选镜像、旧生产、R2C-R1 fixture、四挂载、Top30/Top20和首个自然周期验收均未改变。

## 实现边界

- 新恢复协议只能运行`start`，调用`prepare`会在环境访问和mutation前失败关闭；
- 旧生产边界必须是目标日16:00后新鲜写出的`noop / 20260826`；
- daily、shadow和paper按目标日统计所有记录，不按PASS过滤，任一失败或部分尝试也会关闭门禁；
- readiness仍必须是`CROSS_SNAPSHOT_WITH_NEW_DATA`且唯一日期为`20260827`；
- 原R2D协议继续使用旧四组件身份与`waiting_source`语义，可加载、可复核，历史证据未被改写；
- 恢复控制器采用五组件精确哈希，不把新模块隐式塞进旧身份。

实现提交为`106a84361f86998bf51d73eb614ee7447d851c2a`，已先推送至`origin/main`；组件SHA-256为
`8c4660c24c1abb79bd2d9493362c23d24a027caebf9a4e5e922140b11ea120e5`。

## 验证

- R2D恢复、旧协议与release context专项：28 PASS；
- 全仓：1,925 PASS，只有既有1条Starlette弃用提示与16条Pandas未来行为提示；
- Ruff与`git diff --check` PASS；
- 生产候选build、fixture、promote、start/restart、手工跑批、密钥、外网和业务写入均为0。

## 精确停止点

精确scope为`bb74c299a4ce5d76dc0cafd337b4d6529d6b433de72c012bcc6c54531297119a`，动作
`R2D_R1_START_CURRENT_20260827_ONCE_AFTER_LEGACY_NOOP_BOUNDARY`。它只授权在20260827
16:05—19:00全部门禁通过后调用一次`start_current`；不授权重复Phase A、重建候选或重跑fixture。

用户逐字批准该scope前不得执行。窗口过期、身份漂移、目标日已有任何写入或readiness不再唯一，scope
自动失效，不顺延、不重用。
