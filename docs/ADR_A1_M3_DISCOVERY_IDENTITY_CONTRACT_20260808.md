# ADR · A1-1C M3 discovery identity 合同解环

- 日期：2026-08-08（UTC+8）
- 状态：`ACCEPTED_IMPLEMENTED`
- 开工代码：`d271e42cb2bdcedcb03729d96095a592232dc78f`
- 决策范围：只解除M3 data/release循环，不改变数据、release、研究或CLI行为

## 问题与结果目标

`m3_multi_pool_release.py`只为读取8个身份字段而导入`m3_multi_pool_data.M3DiscoveryIdentity`；
`m3_multi_pool_data.py`的CLI在用户传入execution release时又局部导入`M3ExecutionRelease`。静态图因此
形成唯一剩余强连通分量，尽管release校验实际只需要一个只读字段形状，并不需要数据构建实现。

目标是让release只依赖M3内层合同，同时完整保留原`M3DiscoveryIdentity`类、旧导入路径、字段顺序、
位置参数构造、输入snapshot、release SHA、错误类型和CLI JSON。完成后全仓Python循环必须为0。

## 权威事实与不可触碰边界

- M3-1/M3-2/M3-3协议、execution release、prompt、知识、24次响应和研究结果均冻结，不修改。
- `M3DiscoveryIdentity`当前公开路径仍为`shaiwei.research.m3_multi_pool_data`，8个字段及顺序不变。
- 不读取真实M3数据、不调用DeepSeek、不读取`.env`、不运行候选、模型、回测、前瞻或生产。
- 不修改M3数据读取、PIT、复权、标签、选择、费用、恢复、账本或CLI输出。
- scheduler、Docker、Web和七个自然账本不修改。

## 候选方案

### 方案一：把具体dataclass移入现有M3合同

能消除循环，但会改变类的`__module__`身份；用手工伪装`__module__`会让类型真身与声明位置不一致。
本包没有必要承担该兼容风险，拒绝。

### 方案二：在M3合同定义结构化只读identity端口（采用）

在`m3_multi_pool_contract.py`新增只含8个属性的`Protocol`。release以该结构合同进行类型标注；具体
dataclass继续原地定义，data CLI仍可单向调用release。运行时校验逐字段逻辑完全不变，旧导入和序列化
身份也不变。

### 方案三：把data CLI迁到release或新建通用编排模块

可改变依赖方向，但扩大入口迁移、命令兼容和Docker调用面；为一个类型依赖引入新编排不合比例，拒绝。

## 合同、迁移与回滚

- 新端口只声明`M3ExecutionRelease.verify_input`实际读取的8个属性，不包含数据读取或release逻辑。
- 不迁移具体类、不增加runtime check、不改变异常分支；Python结构化类型保证现有dataclass满足端口。
- characterization先锁定具体类模块、字段顺序和release逐字段通过/失败行为，再替换单一import与注解。
- 单一回滚点为A1-1C提交的父提交；失败时完整revert本包，不保留半迁移路径。

## 验收

1. AST强连通分量由1降至0，且新增机器门阻止M3循环回归。
2. 旧`M3DiscoveryIdentity`类模块、字段顺序、构造和release校验行为不变。
3. M3专项、全仓、架构、Ruff、compileall、依赖、Compose、diff和脱敏门通过。
4. `m3_multi_pool_contract.py`仍低于400行；data/release均不增长或只作等长import替换。
5. scheduler原容器、镜像、创建时间与healthy状态不变；七个自然账本保持未暂存。

## 实施结果

- 新增8属性结构化identity端口，具体`M3DiscoveryIdentity`继续位于原模块，模块名和字段顺序不变。
- `m3_multi_pool_release.py`不再导入data实现；全仓AST强连通分量由1降至0。
- contract为376行、data保持295行、release由258降至257行，均低于400行软上限。
- M3协议、release配置、输入snapshot、CLI、研究产物和账本均未修改或运行。
