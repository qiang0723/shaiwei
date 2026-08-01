# M1-2 科创50机械 Top2 审查：零调用基础设施恢复附录

日期：2026-08-01（UTC+8）  
状态：`M1_2_ZERO_CALL_INFRASTRUCTURE_RECOVERY_FROZEN`  
生产授权：`none`

执行 release `575d61b800b428bcd8d76dfddd674a4b25e0aa6c` 推送后，首次 Docker 启动因专属输出目录
尚不存在而在容器创建前失败。仅在项目内创建协议已登记目录后，第二次启动进入容器但在首个请求前
fail closed。此时两份专属账本仍各只有表头，输出文件为 0，provider 调用与费用均为 0。

根因是 `m1-star50-review-live` 未挂载表达式安全审计依赖的 `vendor/alphagen`；同协议的 preflight
profile 已正确使用该只读挂载。`M1ReviewProtocol.load()` 在 TLS 探针、secret 读取和 provider 创建前
调用表达式审计，因此该失败没有对外发送候选、提示、数据或密钥。

本附录只授权以下恢复：

1. 给 live service 增加 `./vendor/alphagen → /workspace/vendor/alphagen` 只读挂载；
2. 增加回归测试，锁定该挂载存在、只读且不扩大可写集合；
3. 提交推送后以新的真实完整 Git 身份重建一次性镜像；
4. 在首次 API 请求前只更新 execution release 的实现 Git、镜像与代码快照身份，再次提交推送；
5. 复跑零联网预检、专项/全仓测试和 scheduler 身份核验后，从 0/8 开始原批次。

禁止修改协议、prompt、候选、表达式、方向、角色顺序、判定规则、provider、预算、数据访问范围和
语义门；禁止访问封存验证、压力期、G1、模型、组合、前瞻或生产。该恢复不新增请求、不重发响应，
也不把未使用预算视为新授权。
