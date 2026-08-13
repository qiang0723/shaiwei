# TS-v5-R3C 六机制合同金丝雀预执行验收

日期：2026-08-13（UTC+8）

权威终态：`READY_FOR_EXPLICIT_LIVE_APPROVAL`

## 结论先行

R3C六机制小批合同金丝雀已完成结果前scope、六请求束、proposal响应分类/确定性编译、复用型transport
与费用控制、独立audit、短命Docker隔离和全量回归。当前只证明“真实调用前工程路径完整”，没有调用
DeepSeek、没有读取项目密钥、没有费用、没有行情/证券/收益、参数搜索、回测、模拟仓、Web或生产。

若用户明确批准唯一scope，下一步才会冻结绑定当前实现提交、终版镜像、空专属账本和请求bundle的
execution release，并在release推送与无secret预检后执行唯一批次。未经批准，环境中即使存在哨兵密钥，
live入口也会在release加载阶段退出码2，无法获得网络或provider权限。

## 冻结批次

- 六种机制各一个独立席位：波动自适应回调、周结构分位、突破回踩、均线恢复、收缩扩张、相对强度
  回调；恰好6份完成响应，串行，无反方、递补或第7次调用。
- 每份必须`finish_reason=stop`、非空JSON object、通过对应机制proposal Schema、确定性编译器和原冻结
  `MechanismCandidate`；非法完成响应同样消费席位。
- 6/6合法才是`GO_CONTRACT_PROJECTION_CANARY_ONLY`；4—5、1—3、0份合法分别停止为partial、weak、
  no-valid；任意未完成或计费不确定也停止且不补发。
- 沿用2026-08-13冻结价格口径；六席全cache miss最坏0.051156美元，批次硬熔断0.15美元。TS-v5总预算
  5美元不扩张本批，也不自动授权未来调用。

## 证据

- scope提交`c8bb9ed`先于实现和任何调用推送；scope SHA-256：
  `234621cf0280fceca82a8e5f82d6966b27979fde761d68b2508346a2ebd953ae`。
- 六请求均为11,290—12,328 bytes，互不相同；request bundle SHA-256：
  `f10e5e41805b711a96001e9e433ccaeb7e86d334cb3bc6b63f7998274449b6ff`。
- 零调用preflight payload SHA-256：
  `c32805c33f73863d27e69b050049dbca8ac18b407e897deb7864d1f65fa262ae`；报告文件
  `3d46958838bf63b0d2a19931d3610732acc70314b4fec92f48e95ad5ae4c66e9`。
- 独立audit完整重算PASS；文件 SHA-256：
  `920162c7938985d76fc757d9ddad7e4a76c23b2e3d8cfdafc67b465ed6bcbf16`。
- 实现提交`a2f215d`先行推送；路径越界和manifest绑定加固提交`3b85077`随后推送，HEAD与origin/main一致。
- 一次镜像build-arg手工转录错误已显式记为provisional，不得进入release；见
  `docs/TS_V5_R3C_IMAGE_IDENTITY_ADDENDUM_20260813.md`。终版镜像身份在补遗后重新生成并逐字段核对。
- 终版镜像在`network=none`、只读根、非root、无secret下重算preflight和独立audit均PASS；注入无效哨兵
  密钥但不给release时按预期失败，无provider调用。

## 架构与验证

R3C没有复制网络栈：沿用`DeepSeekProvider`、transport事件、标准TS-v5 attempt ledger、write-once、TLS、
统一token/费用公式和release模式；只新增proposal差异、六席编排和结果重算。公共JSON/transport审计原语
从旧R2审计抽出，R2同组回归不变。新增生产模块均不超过300行，函数不超过60行。

定向R3C/R2测试36项、TS-v5兼容链87项、架构13项和最终全仓1246项全部PASS；Ruff、compileall、
pip check、Compose配置、diff check和凭据扫描PASS。生产scheduler保持原`shaiwei:scheduler-current`，
Up 9 days且healthy，未重启。

## 唯一下一步

只有用户逐字批准scope SHA、六响应和0.15美元上限，才可新增execution release并执行真实批次。即使
真实六席全部合法，也只证明合同投影有效，不代表候选或TS策略有效；参数搜索、回测、模拟仓和生产仍
必须另立结果前协议和授权。
