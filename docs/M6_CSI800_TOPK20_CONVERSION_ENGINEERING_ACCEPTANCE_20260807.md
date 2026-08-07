# M6-3B 中证800 Top20 组合转换结果盲工程验收（2026-08-07）

## 裁决

`GO_ENGINEERING_ONLY`。

这只证明 Top20 单变量转换的执行适配、配对差分中的差分统计、Top20 直接组合门、四终态、不可变双跑
和独立审计已经能在纯合成输入上正确工作。它**不代表 Top20 有效**，也不代表任一替代模型、因子或
中证800生产策略有效；`strategy_effective=NOT_EVALUATED_FOR_PRODUCTION`，生产授权为`none`。

## 完成范围

- 严格继承 M6-3A：唯一变化是`portfolio.topk: 30 → 20`；三条既有分数面、W1—W6、Top30、
  `n_drop=3`、10日调仓、开盘执行、基准与三档成本均不变。
- `execution`只接收注入的分数与回测端口，不导入模型训练或评分；先逐内容验证 Top30，再允许计算
  Top20。
- 主要统计是两个既有替代臂的
  `(替代Top20-控制Top20)-(替代Top30-控制Top30)`，固定 NW(10)+Holm(2)；同时执行冻结的 Top20
  直接组合门。
- 四个互斥终态均被合成 fixture 命中：`TOPK20_CONVERSION_SUPPORTED`、
  `TOPK20_CONVERSION_NOT_SUPPORTED`、`MIXED_NOT_CONCLUSIVE`和`BLOCKED`。
- 15类边界失败关闭，包括Top30漂移、第二组合变量、错误臂/窗/TopK、重复成员日、`.BJ`、非有限收益、
  错误Holm族、路径逃逸、write-once冲突及审计篡改。

## 架构与运行边界

实现位于`src/shaiwei/research/topk_conversion`，八个生产职责模块相互分离；最大文件
`synthetic.py`为361行，低于新增模块400行软门。独立 auditor 不导入主指标、主执行或合成 runner。
本节点新增独立`compose.m6-topk-conversion.yaml`，没有继续扩大既有大型研究 Compose。

正式 runner 与 auditor 均为一次性非root容器：`network_mode:none`、只读根、capabilities 全部删除、
`no-new-privileges`，不挂`.env`、Docker socket、完整项目、Qlib、M6真实effect或业务账本。runner仅写
自己的合成目录；auditor只读runner目录并写独立audit目录。Tushare、DeepSeek和其他外部调用均为0。

## 发布身份纠错

首次镜像的代码快照本身可复算，但嵌入的完整Git提交号`60a2727a...`不是仓库中的真实提交；因此该批
runner/audit在验收前被判为provisional，完整保存在
`data/research/m6_csi800_topk20_conversion_v1/engineering/provisional_wrong_release_identity_02a325de`，
没有覆盖或冒充正式证据，也不消耗真实研究尝试。

随后增加强制发布身份绑定与审计：正式报告必须携带镜像内Git提交、代码快照和发布清单文件数，独立
auditor必须核对一致，缺失、非法或漂移均失败关闭。修复提交`2337076fac310d513050af9788ee1a69e3534a4f`
先推送，再构建正式镜像。

## 正式不可变证据

- 镜像：`sha256:e14fc6c3cf867ed7e1b5daf030186c9893acbcf6f20384c677adc6098e4953eb`
  (`linux/arm64`)；嵌入Git提交为`2337076fac310d513050af9788ee1a69e3534a4f`。
- 代码快照：`7857c0a3df50ffd67e1c450512b8619b780a5b7cd9b31080977b30b8077008ef`，
  发布清单524个文件；Top20工程代码包：`087b85b8...6c6eecc`。
- first-pass/replay：两个物理文件均为1,450,605字节，SHA-256均为
  `10fb244964fb96f190f366f55503fc2f96b70bcee8392a0238e7e8811b329a3c`。
- 正式报告：10,361字节，SHA-256
  `f3e5fd52d067615d2d2c8952ad7eb9ed16e247ed467c4f98464e5c927ea230fa`。
- 独立审计：`PASS`，1,133字节，SHA-256
  `e443a1e87c6719dd01a2d310689be654b3bf21c1b35a8685e106bc4905477690`；独立重建SHA-256
  `97babbc38d5630cb4e2de7f14bf2c66edebb347eed4cdfe7e818d1659c04cdcd`。
- 真实M6 effect读取0、Qlib读取0、真实拟合/预测/回测均0、实验账本新增0、真实证券代码0。

## 验证与生产隔离

- 全仓测试：903 PASS（1条既有Starlette弃用提示）；架构门10 PASS；M6-3专项28 PASS。
- Ruff、compileall、pip check、Compose展开、diff-check及敏感凭据模式扫描均PASS。
- scheduler仍为原容器`183b8c6c5edd`、原镜像`722f63de...13b76`，healthy、重启计数0；M6-3B
  一次性容器均已退出。

## 停止线与下一节点

M6-3B至此关闭。下一合法节点只能是新的 M6-3C 真实效果 release 准备：先绑定本manifest、正式镜像、
M6-3A协议和既有封存输入，生成新的精确scope；在用户明确批准前，不得读取真实M6 effect、运行Top20
真实组合评价、写实验账本、进入前瞻/模拟仓或生产。M6-3B的工程GO不会继承成真实运行授权。
