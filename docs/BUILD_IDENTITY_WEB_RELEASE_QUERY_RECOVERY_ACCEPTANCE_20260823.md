# A1-4C-R1 Web 查询与 successor release 恢复验收

- 协议：`a1-4c-r1-web-query-release-recovery-v1`
- 日期：2026-08-23（UTC+8）
- 最终裁决：`GO_LOCAL_READ_ONLY_RELEASED`
- 策略效果：`NOT_EVALUATED`
- 生产授权：`none`

## 1. 通知证据语义恢复

查询层不再把跨日复用的稳定内容 `message_id` 误当成一条无限增长的重试链。纯解析模块
`web/notification_evidence.py` 以每个 `attempt=1` 开启一次 occurrence，并保持以下失败关闭门：

- 每个 occurrence 必须从 1 开始、连续递增，声明的 `max_attempts` 唯一且不超过硬上限 16；
- 相同内容身份必须始终绑定同一事件；重复尝试身份、字段越界、缺首项、跳号和跨事件均拒绝；
- 通知详情返回截止日期最新 occurrence，同日系统统计仍保留当天全部尝试；
- 不改通知日志、发送端、内容身份、重试实现或 scheduler。

20 个交易日复用同一内容身份的 fixture 已通过；真实本地证据截至 2026-08-21 可稳定生成：数据质量
`PASS`、系统运行 `PASS`、通知 `WARN`，其中 9 个消息、12 次尝试、3 次失败和 3 次恢复均保留，40 条
早期不可寻址记录仍如实披露。

## 2. 发布门与架构

- `operations.py` 从冻结的 1,160 行降至 1,060 行；新解析模块 172 行，未扩大热点文件；
- 真实 HTTP 门由健康/总览扩至数据质量、系统运行、策略工厂、因子、实验、模拟组合和信号等关键
  只读接口，并继续检查 UI 根路径与 CSP；
- release state 同时严格读取冻结 v1 和 successor v2；v2 记录发布代际、当前/前一候选和精确镜像；
- 新的显式 `prepare-successor` 动作先核对 deployed state 与旧 candidate 自哈希，再不可覆盖归档旧
  candidate；归档损坏或内容漂移会失败关闭；
- successor 提升固定为“新候选全接口 → 精确 previous 只读基线 → 同一新候选全接口”，任一步失败
  恢复 previous state 和镜像；不触碰 scheduler。

所有新增生产模块均低于 400 行；没有新增依赖、写接口、生产模型或交易授权。

## 3. 工程验证

- 通知/query/release/state/successor 专项：58 PASS；
- 架构宪法：13 PASS；
- 全仓：1,766 PASS，17 条均为既有第三方或 pandas 未来行为警告；
- 账本追加门：86 PASS；
- Ruff、compileall、pip check、Compose config、diff-check：PASS；
- 当前阶段未归档旧 candidate、未构建 successor、未重启 Web，scheduler 未改变。

## 4. 真实 successor 发布

- 实现提交：`ea987be979837938523eb17d33c3c7ec180afb05`，构建前已与 `origin/main` 同步；
- 已归档 previous candidate：
  `70d2cf6f563478692f4f422aeef835af091a8fd288dee81244064342c35b3ee9`；
- successor candidate：
  `9c7ac1a81f003c68cd86bcab602a15dd19ff07f3550d133dbdb45160df8d3b27`；
- release identity：
  `60d15cbb22b6a175fa77c7110b5549a692aca9faeba8ac1827d86558896a2b13`；
- `research-control` 镜像：
  `sha256:6e10aa2d7edae20386fbf584009e3a1f3695ac291a03df9c19d87b27b70d6fe1`；
- `web-runtime` 镜像：
  `sha256:1646a3a86e92e190007e90637ca350affd477421b007edd17d4eebe4c1364c7a`。

两角色构建计数均为 1，第二次 build 调用仅验证并复用同一候选。发布按“successor 全关键 API →
previous v2 健康/总览 → 同一 successor 全关键 API”完成，rollback drill PASS；previous state 与 candidate
均按身份归档，当前 state 为 v2、第 2 代。

## 5. 运行与界面验收

- `make docker-web-status`：PASS，三容器均为预期镜像、只读根、精确网络/挂载，UI 仅监听
  `127.0.0.1:8080`；
- 全关键只读 HTTP API 与 CSP：PASS；
- 真实浏览器：总览、策略工厂、因子工厂、研究证据、模拟组合、股票池与信号、数据质量、系统运行
  共 8 页均加载主标题，无通知上限错误或加载失败；数据质量 PASS、核心运行 PASS、通知 WARN 及恢复
  历史均如实展示；
- 一次性只读、无特权 Node 容器 fresh 安装锁定依赖后，前端 33/33 PASS；完整依赖树有 1 个高危开发
  依赖提示，`npm audit --omit=dev` 为 0 个生产依赖漏洞；
- scheduler 的容器、镜像、代码快照、Git revision 和 healthy 状态在候选构建、三段演练及终检前后
  完全相同；未重启或重建 scheduler。

最终仅授权本机只读 Web 运行，不授权外网开放、写操作、模型切换、模拟仓写入、交易或生产策略变更。
A1-4C 初次发现的 `BLOCKED_QUERY_ACCEPTANCE` 作为历史发现永久保留，本 R1 以新证据完成恢复，不改写
原记录。
