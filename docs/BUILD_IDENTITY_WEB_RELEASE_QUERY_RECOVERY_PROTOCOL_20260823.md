# A1-4C-R1 Web 通知证据分组与 successor release 恢复协议

- 协议 ID：`a1-4c-r1-web-query-release-recovery-v1`
- 状态：`FROZEN_AFTER_ACCEPTANCE_FINDING_BEFORE_FIX`
- 日期：2026-08-23（UTC+8）
- 上游工程提交：`a6d20f46cd1f6a4a9cf4f60c6b62d4231716dbc7`
- 上游真实候选：`70d2cf6f563478692f4f422aeef835af091a8fd288dee81244064342c35b3ee9`
- 上游 release identity：`373ef4f20bed9bb6b23eebe9a8dd052525917838d30da8a56a9c95f5372228b7`

## 1. 发现与当前裁决

A1-4C 两个候选镜像均只构建一次，v2 attestation、daemon 标签、内嵌源码 manifest、三段
“新 → 精确旧 → 同一新”回滚演练和 scheduler 不变门均 PASS。最终新镜像为：

- `research-control`：`sha256:bb81a2fb8ccfc86eea1073b81e663e8acfe6c62095aca9e5f4c187df2d15e94a`；
- `web-runtime`：`sha256:61889afd35fa0ee486bba2995feff6f0dc65f9b92f30848419209e8a33cfe252`。

真实浏览器验收随后发现数据质量和系统运行查询以“单消息通知尝试超过固定上限”失败关闭。项目内
脱敏通知日志的同一 `message_id` 累计最高为 25 和 20 行，而硬上限为 16。旧 `web-runtime` 与新
候选中 `src/shaiwei/web/operations.py` 的 SHA-256 同为
`fc0f9b03a7bdfdc65a6b553a16903f23d636e89b7af4acf116e63e9d1d2f692c`，证明这是数据自然增长触发的
既有查询缺陷，不是 release 代码漂移；回到旧镜像不能恢复页面。

因此 A1-4C 身份、构建和回滚工程 PASS，但最终裁决暂为 `BLOCKED_QUERY_ACCEPTANCE`，不得提前记
`GO_LOCAL_READ_ONLY_RELEASED`。新 release 保持本机只读运行，因为它与旧镜像业务代码相同、权限更
可证且故障为失败关闭；不以无效旧版回滚冒充恢复。

## 2. 根因与冻结语义

通知生产端的 `message_id` 是 `event + title + 脱敏 fields` 的稳定内容身份。同一日常事件在不同日期
内容相同时会合法复用该身份；一次 `send()` 内的有界重试共享同一个 `message_id`，`attempt` 从 1
递增。现查询层把历史上相同 `message_id` 的所有投递误当成一次重试序列，故累计行数超过 16 后错误
阻断。

R1 冻结以下解释，结果前不得修改：

1. `message_id` 继续表示内容身份，不回写或重造历史 ID；
2. 每个 `attempt=1` 开启一次新的投递 occurrence，后续必须严格为 `2..n`；
3. 单 occurrence 的 `attempt` 不得超过其声明的 `max_attempts`，且记录数仍不得超过硬上限 16；
4. 相同 `message_id` 可有多个 occurrence，但必须始终绑定同一 event；
5. 通知详情路径保持兼容，返回截止 `as_of` 的最新 occurrence；系统当日统计继续读取当日全部尝试；
6. 缺首个 attempt、跳号、重复身份、字段越界、跨 event、单 occurrence 超限继续失败关闭；
7. 不删除、合并、改写或截断任何通知日志，不改变飞书发送、重试、message ID 或 scheduler。

## 3. 实现与架构边界

- 从已冻结 1,160 行上限的 `web/operations.py` 抽出纯通知证据解析模块，使热点文件只缩小不增长；
- 新模块只接收文件相对路径、字节内容和 `as_of`，不读取 `.env`、网络、Docker 或业务数据；
- 保持现有 API 主字段与前端解释不变，不新增写接口，不降低坏消息可见性；
- 增加“跨日期同内容超过 16 行仍可解析”和缺首项/跳号/单 occurrence 超限等对抗测试；
- 将真实 release HTTP 门从 overview 扩至 data-quality、system、paper、signal、factor、experiment、
  strategy-factory 等关键只读 API，禁止再次以单一健康端点冒充七页可用。

## 4. successor release 与回滚

现有 candidate、state 和哈希链审计均须保留在项目 Git 忽略区。R1 必须显式归档旧 candidate/state，
不得静默覆盖；当前已验证 v2 双镜像作为 successor 的精确 previous release。

实现提交推送、构建域干净后，只允许各构建一次新的双镜像候选。提升必须完成：

1. 当前 v2 release 容器/镜像/权限基线通过；
2. 新 successor release 全关键 API PASS；
3. 精确回滚当前 v2 release，容器合同和既有可用页面 PASS；
4. 重新提升同一 successor，全部关键 API、CSP、前端单元和浏览器页面 PASS；
5. scheduler 容器、镜像、代码快照与健康身份前后完全相同。

若 successor 任一步失败，恢复当前 v2 release 并保留失败候选、状态和审计。不得删除旧镜像，不得
用重建 scheduler、修改日志或放宽通知单次重试门完成恢复。

## 5. 最终验收

只有同时满足通知 occurrence 对抗门、真实 data/system 查询恢复、七页关键只读 API/浏览器验收、
successor 新→旧v2→同一新演练、全仓/架构/Ruff/Compose/脱敏门和 scheduler 不变，才可把 A1-4C/R1
合并裁为 `GO_LOCAL_READ_ONLY_RELEASED`。策略效果仍为 `NOT_EVALUATED`，生产授权仍为 `none`。
