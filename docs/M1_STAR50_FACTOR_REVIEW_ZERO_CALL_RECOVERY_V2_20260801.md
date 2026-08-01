# M1-2 科创50机械 Top2 审查：零调用受控树覆盖恢复附录

日期：2026-08-01（UTC+8）  
状态：`M1_2_ZERO_CALL_CONTROLLED_OVERLAY_RECOVERY_FROZEN`  
生产授权：`none`

用户明确批准本批 DeepSeek 外发后，live 入口两次在首请求文件写入前 fail closed。两份专属账本仍
各只有表头、结果目录为 0 文件、provider 调用和费用均为 0。中间以空密钥、零研究载荷执行的 TLS
主机探针成功，排除持续 DNS/TLS 阻断；随后在同一 live 挂载边界内独立复算代码快照，精确得到
`release controlled-file content differs from the embedded manifest`。

根因是 execution release 从宿主覆盖挂载到 `/workspace/config/...`。`config/` 被不可变镜像 release
manifest 纳入受控树，而该 release 在镜像构建后按最终镜像身份更新；运行时覆盖因此必然触发内容
不一致。这是身份编排缺陷，不涉及候选、模型响应、研究结果或计费不确定性。

本附录只授权：

1. 把同一宿主 release 文件只读挂载到镜像已有、且不属于受控源码树的
   `/opt/shaiwei/m1_star50_factor_review_execution_v1.yaml`；
2. live 命令只改 `--execution-release` 路径，并增加测试锁定 release 不得覆盖 `/workspace/config`；
3. 提交推送、重建镜像、更新 release 的实现 Git/镜像/代码快照身份并再次先行推送；
4. 用空密钥验证 live 协议、release 与嵌入式代码快照全部通过后，才从 0/8 启动原批次。

禁止改变协议、prompt、候选、公式、方向、角色、判定、语义门、provider、预算和数据访问边界；
禁止读取封存验证、压力期、G1、模型、组合、前瞻或生产。TLS 探针不携带候选或研究正文，不计为
provider 请求；后续仍只允许原计划最多 8 个完成响应。
