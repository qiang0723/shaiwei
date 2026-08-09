# M7-0R3-P1 真实 key-only 目标投影 release 就绪验收

## 当前裁决

`READY_FOR_EXACT_SCOPE_APPROVAL / REAL_PROJECTION_NOT_EXECUTED`。

精确 release scope 已生成，但其中 `execution_authorized=false`。用户绑定 scope SHA 明确批准前，不得创建
approval envelope，不得读取 R2 输入束中的真实证券键，不得启动 projector 或 auditor。

## 内容寻址身份

- 协议 v2 SHA：`345316477d789b255aeb259adcf3411a5f8c7889ed4eecd6f0a34d7e33dac1fd`；
- 已推送实现提交：`23f06b2479ac6f394fbc8599cff4d98dd6ee55ce`；
- 代码束 SHA：`17997e655421b0f9192a506cb9c4bc471290887e357e591c5a4dc97facbc26d0`；
- arm64 镜像 ID：`sha256:ea77e1716ae14774f2eb98e33fcab58136b62aa8be3fd567155fcbddf82ed007`；
- R2 input manifest：`5f3e2808...f9a7`；bundle manifest：`3f4a6cc3...005eb`，10,927 文件；
- authoritative lineage core：`df5de3990428...eeca`；
- release scope SHA：`9aca04576362455af66c5426bd0b4b6211d7edecc8b141de5ecee96ae5781614`。
- tracked release 文件物理 SHA：`4eb79454a17de4aec35575db67172f345f24d6a6ef3fe380001e490d6e50b718`。

scope 同时绑定 projector/auditor 命令、角色专属挂载、CPU/内存、非 root、只读根、cap drop、
`network_mode=none`，且拒绝 provider、资金流数值、研究效果和生产权限。

## 最终预执行复核

- 最终镜像合成运行：A=908、B=541，主/审集合精确一致，重复调用在语义读取前停止；
- tracked scope 可由正式 loader 解析，代码束从列明的17个窄根重算一致；
- 全仓1,039、架构13、投影专项19 PASS，Ruff/compileall/pip/Compose/脱敏门均PASS；
- 当前无 approval 文件、无目标 Parquet、无 projector/auditor claim；
- 真实证券键、资金流数值、provider、网络、候选、效果、研究尝试均为0；
- scheduler 保持原容器/镜像/创建时间且 healthy，未重启。

## 唯一下一动作

只有用户明确批准上述完整 scope SHA 和动作
`M7_MONEYFLOW_RECOVERY_TARGET_PROJECTION_ONCE`，才允许各执行一次断网 projector 与 auditor。同 scope
不得重跑；投影 GO 也只授权后续生成另一个网络 recovery scope，不自动授权任何 provider 调用。
