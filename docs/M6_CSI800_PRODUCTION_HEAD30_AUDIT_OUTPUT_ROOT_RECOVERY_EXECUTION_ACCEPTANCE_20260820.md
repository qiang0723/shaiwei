# M6-4B-R7 生产 Head30 独立审计输出根恢复执行验收

## 裁决

R7 scope `c08605ca15ab480efaac4077db514b65a86ea40cf3872fd059029e932747b717`
按用户精确授权唯一运行成功：

- 独立审计：`PASS`。
- 权威研究裁决：`VALIDATED_RESEARCH_SCALE`。
- 生产授权：`none`。
- R7 scope 已关闭，不得重跑。

这意味着 R2 封存的生产 Head30 组合转换历史效果通过了冻结的独立审计，具备研究尺度的有效性；不等于
可以切换生产、自动交易或宣称实盘收益。

## 审计结果

独立审计完成 17 项实质检查，全部 PASS：

- R2 主结果匹配封存精确身份；首遍与 replay 物理身份一致。
- 独立重算与主结果通过相对/绝对 `1e-12` 容差门。
- 主结果与独立重算 decision 均为 `VALIDATED_RESEARCH_SCALE`。
- 当前独立重算 SHA 已记录为
  `1e7d00db1059b5c018400234de9179ad4e024775e98090ad3d9322b642445d13`。
- 历史独立 SHA 仍记录为
  `daac6d2a556fa67db95f021acdfbc4eeb330fd0f6dc577a1de104c2e0bf65abf`。
- 两个独立 SHA 不相等；按冻结 R6/R7 权威规则，这只是诊断事实，不是裁决门。

## 不变性与调用边界

- R2 effect 执行前后均为 5 文件、1,191,570 bytes，树 SHA-256
  `d3d84d104968bf01f88312bd665060f2e57727145e4064697b4753bd6fc545c1`。
- audit 输出恰好 2 文件：`audit.json` 与 `recovery-receipt.json`。
- audit SHA-256：`b5747321b478d63bf7d9c264e3af0e18337174af4b94f586acd94219262ec81a`。
- receipt SHA-256：`ccc741a63621238d6c730132ed9a6ddd135fa467d19968f1c3c2686003d81337`。
- auditor 调用 1；runner、Qlib、训练、预测、回测调用 0。
- 新增组合转换尝试 0；家族累计仍为 2。
- 未访问网络、凭据、前瞻、模拟仓、Web 或生产。
- scheduler 保持原容器 `183b8c6c5edd` 且 `healthy`，未重启。

## 状态解释与后续边界

M6-4B 的历史效果审计链现已闭合，权威状态从
`NOT_AUTHORIZED_PENDING_AUDIT_OUTPUT_ROOT_RECOVERY` 更新为 `VALIDATED_RESEARCH_SCALE`。

但本次没有授予生产权限。若继续推进，下一节点应另立生产前协议，优先评估 50 万元账户尺度下的整数股、
容量、成交和成本可行性，并结合自然 FORWARD 证据；不得直接把研究尺度裁决转换成生产或模拟仓切换。

机器真身：
`config/m6_csi800_production_head30_audit_output_root_recovery_execution_v1.json`。
