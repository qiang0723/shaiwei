# A1-1C M3 discovery identity合同解环验收

- 日期：2026-08-08（UTC+8）
- 施工父提交：`d271e42cb2bdcedcb03729d96095a592232dc78f`
- 裁决：`PASS_NO_BEHAVIOR_CHANGE`
- 后续授权：`NO_AUTOMATIC_REFACTOR_OR_RESEARCH_AUTHORIZATION`

## 结果

M3 execution release现在依赖`m3_multi_pool_contract.M3DiscoveryIdentityContract`所声明的8个只读属性，
不再导入data实现。具体`M3DiscoveryIdentity`仍原地定义在`m3_multi_pool_data`，因此旧import、类模块、
dataclass字段顺序和位置参数构造保持不变。data CLI仍按原路径、参数和JSON语义单向调用release。

这次只调整静态类型依赖，不改变M3协议、execution release、输入snapshot、PIT/复权/标签、候选、费用、
选择、错误、恢复、账本或研究结论。未读取真实M3数据和`.env`，未调用DeepSeek，未运行模型、回测、
前瞻或生产。

## 可复核事实

| 检查项 | 施工前 | 施工后 | 裁决 |
|---|---:|---:|---|
| Python强连通分量 | 1 | 0 | PASS；机器门锁定零循环 |
| M3 contract物理行 | 363 | 376 | PASS；低于400行 |
| M3 data物理行 | 295 | 295 | PASS；无增长 |
| M3 release物理行 | 258 | 257 | PASS；无增长 |
| identity字段数 | 8 | 8 | PASS；模块与顺序不变 |
| 外部/API/研究调用 | 0 | 0 | PASS |

## 架构与兼容边界

- release不得重新导入`shaiwei.research.m3_multi_pool_data`，全仓AST循环数必须保持0。
- 结构端口只包含release逐字段校验实际消费的8个属性，无runtime check、I/O或裁决实现。
- 新建`config/architecture_constitution_a1_1c_addendum_v1.yaml`，引用A1-1B增补SHA并冻结三个文件上限；
  不改写被历史release绑定的architecture v1。
- A1-1C提交是单一回滚点；没有迁移数据、配置、账本或调用方。

## 验证记录

- 施工前M3相关测试：41 PASS；新增characterization后：13 PASS。
- 施工后M3相关测试：42 PASS。
- 全仓：941 PASS（1条既有Starlette弃用warning）。
- 架构检查：13 PASS；AST强连通分量为空。
- Ruff、compileall、`pip check`、主/研究Compose展开、diff-check和脱敏扫描均PASS。
- scheduler终验仍为容器`183b8c6c5edd`、镜像内容`sha256:722f63de...13b76`、原创建时间且
  healthy，未重启。

## 生产与工作树

开工scheduler为容器`183b8c6c5edd`、镜像`shaiwei:scheduler-current`、镜像内容
`sha256:722f63de...13b76`、创建时间`2026-08-03 17:39:34 +0800`和healthy状态。本包不得重启、重建
或部署。七个scheduler自然更新CSV账本继续保留在工作树且不得暂存。
