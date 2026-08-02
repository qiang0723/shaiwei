# L2-0 因子审查合同 v2 工程验收

日期：2026-08-02（UTC+8）

裁决：`GO_COMPACT_REVIEW_CONTRACT_V2_ENGINEERING_ONLY`

真实 API 调用：`0`

策略有效性：`NOT_EVALUATED`

生产授权：`none`

## 结论

未来新因子批可复用的紧凑审查合同 v2 已完成工程门。它修复的是旧合同中“合法 schema 最大尺寸没有
证明能放入 provider 输出上限”的结构矛盾，并收窄自由文本修复建议的泄漏面；不改写 M1-2、M3-3
终态，也不授权重发、续跑、替换候选或进入验证/G1。

结果前协议提交 `50d0db788ab4323b8201627082ee0b73cfc7da67` 已先推送；独立实现提交
`ba913567a3e29fc004fee4a3efd6302305685afd` 随后推送。两份旧审查的协议、release、执行模块、账本、
报告和不可变响应均未修改。

## 合同收窄结果

- 显式使用 non-thinking JSON；不传 `reasoning_effort`，避免 returned reasoning 与可见 JSON 竞争同一
  输出预算。
- summary 最多 320 字符，finding 为 1—3 条，statement/falsification condition 最多 320/240
  字符；类别、结论和 disposition 均为冻结枚举。
- 最大合法规范 payload 实测为 `2,655 bytes`，通过 `4,096-byte` 硬门，并严格小于未来
  `6,000 max_tokens` 的一字节一 token 保守上界。
- 响应不再提供自由格式 repair/resolution；阻断只能拒绝原式，无阻断只能允许未来另立封存验证协议。
- schema 后仍复用哈希为 `8faf36d3...f15a` 的既有自由文本语义门；公式修改、业绩/准入声称和模糊
  变体建议全部失败关闭。

## 对抗与确定性证据

12 类机器 fixture 全部符合预期：合法 schema+语义、最大 payload、finding 超数、非 ASCII、结论/
disposition 不一致、公式文本重复、公式修改、业绩声称与模糊变体。宿主两次报告和断网 Docker 报告
逐字段一致：

- response schema SHA-256：`dbadd395d5e2aa0d3550a01546b96774e10e4ab869759153790a6cb7c00c5469`
- maximum payload SHA-256：`b153f7f6fbb572b38dd01e6e2155b2c3ae88bdf84e3b25e891ecf096fc3cc22c`
- `provider_calls=0`、`api_key_read=false`、`real_candidate_or_result_read=false`
- `prior_batches_reopened=false`、`production_authorization=none`

专项测试 16 PASS，全仓 504 PASS；Ruff、compileall、pip check、Compose config、diff-check 和脱敏检查
通过。唯一测试提示仍是既有 Starlette 第三方弃用 warning。

## 维护性与隔离

实现按职责拆为 253 行契约/校验模块和 213 行 fixture/预执行模块，没有向既有 920 行旧控制器继续
加入职责。Docker profile 为只读根、`network_mode:none`、无 `.env`、无端口、无 Docker socket，
只挂载新代码与两份冻结配置。

生产 scheduler 施工前后保持同一容器 `fd8e96152b53...a5adbb`、同一镜像
`sha256:de87ec74...0261`、原创建时间且 `running/healthy`，未重启。

## 费用与后续边界

本阶段实际费用为 0。按 2026-08-02 官方价，仅作未来 release 的保守算术参考：12,000 cache-miss
输入 + 6,000 输出时单次 `$0.01044`，8 次 `$0.08352`。未来执行前仍必须重新核对模型和价格，并
获得用户对具体候选、载荷、次数和费用的明确授权。

本裁决只说明合同工程可用，不说明任何因子有效。M1-2 和 M3-3 继续保持原 STOP，M1-3/M3-4 均未
授权；未来新研究批必须独立预注册，不能把 v2 当成旧批恢复工具。
