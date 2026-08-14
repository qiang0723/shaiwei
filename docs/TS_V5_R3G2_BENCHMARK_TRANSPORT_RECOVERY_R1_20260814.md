# TS-v5 R3G-2 H00906 宿主传输恢复 R1

日期：2026-08-14（UTC+8）

状态：`RESULT_UNKNOWN_TRANSPORT_RECOVERY_FROZEN`

机器真身：`config/ts_v5_r3g2_benchmark_transport_recovery_r1.yaml`

## 1. 首轮为什么不重试

已推送实现和不可变镜像通过身份门后，网络容器在第一个中证指数官方事实表的 TLS 握手阶段收到
`SSL_UNEXPECTED_EOF_WHILE_READING`。没有取得任何完整 HTTP 响应，没有发出两次历史请求，没有写入
文件，也没有运行数据质量门或独立审计。候选收益、Alpha158数值、secret、模型、回测、模拟仓、Web、
scheduler和生产变更均为0。

这只证明 Docker 直连中证指数站点的 TLS 路径不可用，不是 H00906 数据不合格。原 scope 标记为
`BLOCKED_OFFICIAL_SOURCE_NETWORK` 并关闭，不在同 scope 重试。

## 2. R1只改变传输位置

R1 固定由宿主机串行传输三份公开官方文件：一份 000906 事实表、两份参数完全相同的 H00906 历史
响应。每个逻辑请求最多一次传输尝试，无重试、无递补、无其他来源，也不读取 `.env` 或任何密钥。

宿主机只保存原始 bytes，不解析、不裁决。随后使用新提交构建的同一隔离镜像，以 `network_mode:none`
读取三份文件，执行原协议完全相同的身份、双响应一致性、SSE日历覆盖、唯一键、close和可选OHLC门；
独立审计也必须断网。原协议、时间角色、质量门、输出和 GO/NO-GO 语义全部不变。

## 3. 停止边界

任一宿主请求失败、两份历史响应不一致、官方身份或覆盖不合格，R1直接停止并保留坏消息，不换代理、
不放宽门槛。数据门通过也只允许另立 R3G-2 结果前效果协议，策略仍`NOT_EVALUATED`、生产授权none。
