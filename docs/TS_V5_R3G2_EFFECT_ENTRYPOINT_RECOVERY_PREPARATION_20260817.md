# TS-v5 R3G-2 真实效果入口恢复准备（2026-08-17）

## 裁决

`RECOVERY_READY_FOR_NEW_EXACT_USER_APPROVAL_NOT_EXECUTED`。

原效果 release scope 已消费且永久不得重跑；新的 entrypoint recovery scope 已在结果盲状态下冻结，
但没有批准文件，runner 与 auditor 均未执行。真实分数值、排名、入场后行情、H00906 收益和留出期均未
读取，策略效果尝试仍为 0，`strategy_effective=NOT_EVALUATED`，
`production_authorization=none`。

## 原 scope 失败边界

- 原 scope：`961b62f288f61a6ae19f88ef04c0697f93f27bf52390ddb48b7c49064e19db75`；
  原批准 SHA-256：`fb597b870b99f6e9737b59d25d97fcb24d1a176d3629c0ddec09efe9dc16ba3d`。
- 唯一 runner 容器已创建，但 CLI 把公开参数 `release/approval` 直接传给只接受
  `release_path/approval_path` 的 `run()`，在进入真实执行函数前以 `TypeError` 失败。
- 失败回执 SHA-256：`8bfd0685724569ab17e48429782a5195fcf1c0ba039a054129499a94811858d2`；
  原效果目录只含该回执，原审计目录为空，auditor 未调用。
- 回执明确记录 `effect_read_started=false`、分数/排名读取 false、入场后价格/基准读取 false、效果尝试
  0。同一原 scope 重跑权限为 false；入口故障不是策略效果结论。

## 最小恢复与独立边界

- 恢复协议先行冻结提交：`37b2f78`；实现提交：`02da4f4`；干净镜像夹具去除宿主隐式依赖的测试修复
  提交：`9e295993ee4a6ad35ed40dc324621805b9703c4d`，与 `origin/main` 一致。
- 恢复只修 runner/auditor CLI 参数映射，并增加独立 authority selector、恢复控制、发布构建器和专用
  Docker profile。没有改变三个冻结参数点、样本期、买卖规则、成本、硬门或发现期防火墙。
- recovery 使用新协议、scope、批准 schema、镜像和输出目录；原 scope、批准、失败回执和原输出根
  被绑定为不可变前驱证据，原 scope 不能被恢复批准重新授权。
- 一次错误手工 Git 身份的镜像在 scope 写入前被身份门拒绝；没有生成 recovery scope、approval 或
  效果产物。随后按真实完整提交重建，不绕过身份门。

## 最终发布身份与预检

- 恢复协议 SHA-256：`34a115e93e29d854676ce3607c12dc184c400ccc0fe5372e016feaba29719f67`。
- 不可变镜像：`sha256:0081742e9f0f4b5a4a4683e99c0f2435dbdb85d96da968c3825de3839cd2874c`，
  `linux/arm64`，内嵌 Git 提交与 `HEAD=origin/main` 精确一致。
- 发布清单 SHA-256：`01f2e6ff36defbf28e7f633b7d883c184a8416a35529e27826eaab59c0e0c694`；
  938 个受控文件，代码快照
  `3df4ceaa4f7044023a6e9fcde310999fc46c1df112942209ee5e689a3f044ecb`，宿主逐文件复核一致。
- 断网、只读、无宿主真实证据挂载的 recovery fixture：18 PASS、1 项宿主前驱证据检查按设计 skip。
- 最终镜像 key-only 预检报告 SHA-256：
  `3cc735eeeb7f75e106330c69545ffded42d4de3be2438f08465ebc20903114d0`，裁决
  `GO_PRE_EFFECT_KEYS_ONLY`；复跑 `reused=true`，分数值、结果和基准值均未读，效果尝试 0。

## 唯一待批准 recovery scope

- recovery scope：`c78d6851187289644f93747e02b68fb5b0ffe35827843b7f860334ce0207193a`；
  文档 SHA-256：`698bc01052af0685732b1ea26f2569b7d44e0607cfdf7c8cd11c5f1a6aa95245`。
- 固定动作：
  `TS_R3G2_BREAKOUT_RETEST_EFFECT_ENTRYPOINT_RECOVERY_ONCE_WITH_DISCOVERY_FIREWALL_REPLAY_AND_INDEPENDENT_AUDIT`。
- 只允许一个 runner，内部 `first_pass + replay`，一个独立 auditor，恰好三个既有冻结尝试；发现期门
  失败时留出期保持物理未读。
- 原 scope 与 recovery scope 均不得重跑；继续禁止外网、2026、额外参数点、模型训练、实验账本、
  模拟仓、Web 和生产。
- scope 冻结时 recovery approval 不存在，恢复效果与审计目录为空，authority 明确
  `execution_authorized=false` 和 `strategy_effect_or_backtest=false`。

## 生产隔离

scheduler 仍为原容器 `183b8c6c5edd`、原镜像
`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`、原创建时间
`2026-08-03 17:39:34 +0800`，`healthy`、重启次数 0。本轮没有修改或重启生产服务。

## 下一合法动作

只有用户针对 recovery scope 给出新的逐字批准后，才可生成专用 approval 并运行一次 recovery runner
和一次独立 auditor。原批准不继承到 recovery scope；批准前不得读取任何真实效果。
