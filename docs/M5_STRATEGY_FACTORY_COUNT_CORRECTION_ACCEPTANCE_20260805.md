# M5-0A 策略工厂跨池评价单元计数补正验收

> 协议：`m5-strategy-factory-count-correction-v1`
>
> 冻结提交：`ee81403`
>
> 终态：`GO_M5_STRATEGY_FACTORY_COUNT_CORRECTION_ONLY`

## 1. 结论

M5-0A 已按追加式补正协议完成。M3 三自建池价量发现批现在分列为：

- 生成尝试：24；
- 跨池评价单元：72；
- 候选：24；
- 效果测试：0；
- 相关价量发现域累计尝试：`N=270`；
- 权威状态：`STOPPED_CONTRACT / NOT_EVALUATED / production_authorization=none`。

没有读取或改变候选效果、研究裁决、模型、回测、信号、模拟仓、前瞻或生产。该 GO 只解除 M5-1
历史计数输入的阻断，不授权 proposal-only 控制面或真实研究。

## 2. 不可改写与差异证据

- 旧 v1 目录全树 SHA-256 施工前后均为
  `d2a67f1f113bebd3e213fc961ccc6a6ea9ae0124d4ba9ef67a83320e9aeb2c35`；
- 旧快照 ID 仍为 `b24142867cf6e68b30724dd8d38a4864c2898e995de3bbf89bd2ea02594af9b3`；
- 新 v2 快照 ID 为 `fae1c53c410213e58bd10d938a5854afdd2cce1e3f4c9acd7affb73624c94a6b`；
- 新快照文件 SHA-256 为
  `36f750639f5643a67ac0c2f9eb7505949542a9404edad9ff3d7fb970f7bd6f2b`；
- 新 v2 目录全树 SHA-256 为
  `468d555fd8ba454c106cb6e8c95e36c24e7c18e3ca55e5f1ad07305166a7d02a`；
- authority addendum SHA-256 为
  `b2ff8baedf878992ebadf2d79f8e38691f8326501e5a9432d821a785c4a6fee6`。

对旧、新快照 `data` 做递归逐字段比较，唯一业务差异为：

`data.programs[6].evaluation_unit_count: 24 → 72`

新投影连续构建两次得到相同 pointer、snapshot ID 和文件 SHA；Docker 断网一次性投影再次复用同一
内容，没有覆盖旧目录或生成第二份冲突内容。

## 3. 实现边界

- 新增 165 行独立 `strategy_factory_authority.py`，严格校验基础目录、补正协议、两份 M3 证据、
  目标工作包旧值及六项不变量；未知字段、错误值、哈希漂移、符号链接或非唯一目标均失败关闭。
- 原投影构建器只增加 authority overlay 编排和组合代码身份，当前 331 行；查询加载器当前 197 行。
  没有向既有热点文件增加职责，全部低于架构硬门。
- v2 使用独立内容寻址目录；Web 查询默认切换 v2，现有 `web-query` 继续只允许 GET/HEAD。
- Compose 只给一次性投影器增加补正配置/协议和 M3 协议的只读挂载；无 `.env`、Docker socket、
  raw、研究结果或生产写挂载。

## 4. 验证

- `make architecture-check`：6 passed；
- 全仓 `make test`：603 passed，只有 1 条既有 Starlette/httpx 弃用提示；
- Ruff、compileall、pip check、Compose config、`git diff --check`：PASS；
- 补正专项及 Web 查询/代理回归：32 passed；
- 真实 `GET /api/v1/strategy-factory` 返回 M3 生成24、评价72、效果0；正式因子库0、活跃授权任务0、
  `.BJ=0`、外部调用0、真实研究运行0、生产授权none；
- 新 Web 镜像：`sha256:2f21449a6af0da2acfbf1ebf44a531e1fda4133d3c7b2d7e058ce45bb0f094d1`；
  `web-query=781255845d76`、`web-ui=5ef1e602a4f5`，均 healthy；
- scheduler 仍为容器 `183b8c6c5edd`、镜像
  `sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`、创建时间
  `2026-08-03T09:39:34.800579793Z`，施工前后 healthy 且未重启。

## 5. 下一步

M5-1 现在可以另立结果前 proposal-only 协议，但必须吸收专项复核：控制对象称“非权威研究提案”而
不是任务；状态最多到 `REVIEW_REQUIRED`；冻结、批准、排队、Worker、外部调用、效果读取、前瞻和
生产端点物理不存在。
