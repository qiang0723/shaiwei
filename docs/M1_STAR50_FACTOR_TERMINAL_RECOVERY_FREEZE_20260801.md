# M1-1 终态组装恢复附录（结果指标盲态冻结）

日期：2026-08-01（UTC+8）  
状态：`RECOVERY_FROZEN / API_FORBIDDEN`

M1-1 已完成恰好 40 个 DeepSeek 响应并累计约 0.07183143 USD。第 40 行及其对应实验、传输和静态
产物均已成功追加；随后终态报告组装在 `attempt_experiment_bijection` 门 fail closed，未生成终态报告，
也未再发请求。

离线分步复核证明：40 行序号连续，80 个传输事件含 40 个完成事件，40 份 write-once 原始响应和
14 份发现评价产物的静态证据全部通过。失败原因是通用 verifier 在全局 `experiments.csv` 中把所有
带 `protocol_id` 的历史 `LLM_DSL` 行都计作当前批次，而当前 M1 尝试账本按协议使用独立文件；因此
旧 D1 行会机械造成行数不等，即使本批 40 对链接逐条完整。

恢复配置 `config/m1_star50_factor_terminal_recovery_v1.yaml` 已绑定故障时三份账本、旧 D1 五份账本、
镜像、代码、协议与 release 身份。本修复只允许 verifier 接受可选的精确 `protocol_id`，M1 终态组装
显式传入冻结协议 ID，并以混合协议与孤儿行 fixture 证明 fail closed。旧调用保持原语义。

诊断时为定位全局账本混入范围，终端尾部输出意外显示了部分候选公式文本；没有读取任何发现
RankIC、覆盖率、日 IC、排序或 Top2，也没有读取验证窗。该事实永久披露。修复提交推送前不得查看
发现指标；修复后只从既有 40 份证据组装冻结排序，不得再调用 provider。
