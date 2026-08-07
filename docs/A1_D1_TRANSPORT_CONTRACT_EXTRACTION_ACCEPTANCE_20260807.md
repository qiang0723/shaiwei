# A1-1B D1传输合同解环验收

- 日期：2026-08-07（UTC+8）
- 施工父提交：`6b2320f8578c4a7b66a8275636bdd115ad1242c8`
- 裁决：`PASS_NO_BEHAVIOR_CHANGE`
- 后续授权：`A1_1C_NOT_AUTHORIZED`

## 结果

A1-1B已把D1协议、候选schema、attempt/request规划、provider response值对象和敏感输出规则抽到
`src/shaiwei/research/llm_factor_contract.py`。DeepSeek适配器与控制生命周期都单向依赖该窄合同，
不再相互依赖；旧`shaiwei.research.llm_factor`继续re-export同一对象，调用方无需迁移。

该变化只调整代码依赖边界，不改变D1研究、候选、费用、错误、恢复或秘密处理语义。未读取`.env`，
未创建live transport，未调用DeepSeek，未读取行情或封存研究效果，未写研究/生产账本。

## 可复核事实

| 检查项 | 施工前 | 施工后 | 裁决 |
|---|---:|---:|---|
| Python强连通分量 | 2 | 1 | PASS；仅剩已登记M3循环 |
| `llm_factor.py`物理行 | 1,254 | 944 | PASS；由版本化增补收紧上限 |
| `deepseek_client.py`物理行 | 808 | 808 | PASS；无职责增长 |
| 新合同模块物理行 | 0 | 357 | PASS；低于400行软上限 |
| ordinal 1请求SHA | `8ddb033e...e21c` | 同左 | PASS |
| LLM/API调用 | 0 | 0 | PASS |

完整请求SHA为
`8ddb033eac5a8b2d0595868ed38f8fb424afb9404c56353e1cfa08d0fb14e21c`。characterization在拆分前先
锁定该身份；拆分后旧/新入口均由同一函数对象生成请求。

## 架构边界

- 新合同模块不导入`httpx`、`shaiwei.ledger`、`llm_factor`或`deepseek_client`。
- `deepseek_client`只从合同模块读取六项传输所需符号，不再导入控制生命周期。
- 合同层无环境读取、HTTP能力、账本写入和研究执行；文件SHA在本模块内部以私有纯函数计算。
- 旧architecture v1被历史release按物理SHA冻结，保持原字节；新建
  `config/architecture_constitution_a1_1b_addendum_v1.yaml`把`llm_factor.py`上限收紧到944，防止职责
  回流且不改写旧证据。
- 未增加`common/utils`，未迁移fixture或账本生命周期，避免本包扩大。

## 验证记录

- 拆分前D1 characterization：33 PASS。
- 拆分后D1控制与DeepSeek专项：35 PASS。
- Ruff与三模块`py_compile`：PASS。
- AST依赖图：D1循环消除，循环总数为1。
- 全仓：939 PASS（1条既有Starlette弃用warning）。
- 架构：12 PASS；Ruff、compileall、`pip check`、主/研究Compose展开、diff-check与脱敏扫描均PASS。
- scheduler终验仍为容器`183b8c6c5edd`、镜像内容`sha256:722f63de...13b76`、原创建时间且
  healthy，未重启。

## 生产与工作树

scheduler必须保持施工前容器`183b8c6c5edd`、镜像`shaiwei:scheduler-current`、创建时间
`2026-08-03 17:39:34 +0800`和healthy状态；本包不重启、不重建、不部署。七个scheduler自然更新的
CSV账本继续保留在工作树且不得暂存。本包通过后即停止，A1-1C须用户另行继续。
