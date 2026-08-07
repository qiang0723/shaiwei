# M6-3C 中证800 Top20 真实效果 release 准备验收

- 验收时间：2026-08-07 11:52:56（UTC+8）
- 裁决：`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`
- 策略有效性：`NOT_EVALUATED_FOR_PRODUCTION`
- 生产授权：`none`

## 1. 交付结论

M6-3C 已把 M6-3A 的唯一组合变量`TopK 30→20`和 M6-3B 的结果盲工程能力做成一次性真实效果
release。完整 release scope 已生成并自校验：

- scope SHA-256：`ba4d03be675e63fd94211271e5dc6d4812bc12954fbf8f77ef0eea85c5065fd9`
- scope 文件 SHA-256：`0d4f6e550b71acb6a8fa5bef00eb28bb6ec4b6e12cbdb2c52277275a8914535e`
- scope 真身：`config/m6_csi800_topk20_conversion_release_scope_v1.json`

当前`approval.json`不存在，正式 runner/auditor 均未启动；真实 Qlib、封存预测、Top30/Top20回测和
效果均未读取或生成，两个组合转换尝试尚未消费。

## 2. 结果前补正

真实接线前发现 M6-3B 的合成`scheduled_names`每窗口/臂只保存一组证券，不能覆盖10日调仓在一个窗口
内的全部截面。补遗在任何真实效果读取前独立提交并推送为`9046dc6`，机器 SHA-256 为
`16383ba10c93723959c2148b460c209d1be6614d0f974158fbab597a3aeccc06`。

补正后 schema 固定为`TopK→窗口→臂→调仓日→名单`，诊断值按 W1—W6 全部调仓日的 Top20交集比例
等权平均。它不参与裁决门，不改变假设、门槛、组合参数、尝试数或四终态；旧单列表失败关闭，主指标
与独立 auditor 各自实现。

## 3. 实现与执行边界

结果盲实现提交`322c599b616843ab76fd22c4d13f554f55614f40`已先推送`origin/main`。真实 release
拆为7个窄模块，最大292行：合同、封存输入、组合执行、runner、独立audit、release构建和纯合成
fixture；没有继续增长既有大型研究文件。

runner固定顺序为：

1. 校验 scope、approval、镜像、Qlib和封存树身份；
2. 读取 first-pass/replay 封存证据并要求逐文件身份完全相同；
3. 先完成18个常规窗和3个压力期 Top30兼容回测，日报与计划名单逐内容一致；
4. 只有兼容门通过才写`top20_effect_started.json`并消费恰好2个组合尝试；
5. 串行完成21个 Top20回测，first-pass/replay物理相同后形成主报告；
6. 第二个无 Qlib、无旧 effect 挂载的进程独立复算统计、门和终态。

任一 Top30不一致会在尝试消费前失败关闭；同 scope 不允许重跑。模型拟合和新预测数固定为0，实验
账本、前瞻、模拟仓、Web和生产均不在权限内。

## 4. 镜像与隔离

正式镜像：

- 引用：`shaiwei:m6-topk-conversion-release-v1`
- 内容 ID：`sha256:69c1a4976e4c89973789413d7a9635d575669e785c4fe4621d6b3f34e09afa17`
- 平台：`linux/arm64`
- 内嵌 Git：`322c599b616843ab76fd22c4d13f554f55614f40`
- 代码快照：`961f51adfdf67d0ae1d122ebb2caf204123abeae522fdd9e8c73142c7ad9cd2e`
- 发布清单：538文件，SHA-256
  `182ab20407a6a1a139f520f99db74a55c4f344e6f23d8a2d62ecafffa06584ee`

runner/auditor均断网、非root、只读根、drop ALL、no-new-privileges，无`.env`、Docker socket、整仓或
生产账本挂载。runner上限4 CPU/8GB/192 pids；auditor上限2 CPU/4GB/128 pids。当前两个镜像均无
残留容器；scheduler保持原`shaiwei:scheduler-current`，Up 3 days、healthy，未重启。

## 5. provisional 镜像留痕

首次构建时把短提交`322c599`错误手工补成不存在的40位值
`322c599eff2d1f6be0af34b34a9d4129177a66c4`。scope入口对镜像Git身份正确失败关闭，scope文件未生成，
真实输入和效果未读取。该镜像 ID
`sha256:21810132982db53e9a4b3aee02952018ded23bdfe9f7c354f4ae3364120eed08`已明确标为
`shaiwei:m6-topk-conversion-release-provisional-wrong-git-20260807`，不得用于正式运行；随后以Git实际
返回的完整提交重建并再次通过合成验收。

## 6. 证据与验证

- 最终镜像断网合成 runner：PASS；`real_data_read=false`、`qlib_read=false`、`real_backtest_count=0`；
  合成 report SHA-256 `94acf0cb2a813e40fecf9579c52199c03e4cbb09403b1ddeb988388368da88f4`。
- 最终镜像独立 auditor：PASS；audit SHA-256
  `d52b15be791be60cfca541995422f20b835cb7ba6857d60ea169d6ec969b705c`。
- 专项测试31 PASS；全仓918 PASS（1条既有第三方弃用提示）；架构门10 PASS。
- Ruff、compileall、Compose展开、发布清单逐文件复算、scope自哈希、diff-check和脱敏检查均通过。
- release生成时仅重算 M6 effect 199文件/84,957,571字节整树哈希、report和独立audit哈希；与冻结值
  完全一致，不解析结果作研究判断。

## 7. 精确批准门

后续若继续，用户必须逐字批准以下动作并绑定完整 scope SHA：

`M6_TOPK20_CONVERSION_EFFECT_ONCE_WITH_INTERNAL_REPLAY_AND_INDEPENDENT_AUDIT`

批准前不得创建 approval、不得启动 Compose、不得读取真实效果。获批后也只允许一次runner调用和一次
独立auditor调用，不授权外网、模型拟合、新预测、第三臂、其他TopK、重跑、前瞻、模拟仓或生产。
