# TS-v5 R3G-2 H00906 镜像引用恢复加注

日期：2026-08-14（UTC+8）

首轮镜像构建在任何容器启动、官方请求、数据读取或产物写入前失败。原因是 BuildKit 将
`shaiwei@sha256:3b81e501...a42d9` 解析为 Docker Hub 的公共镜像引用并尝试取匿名令牌，没有使用本机
已经核验为同一 ID 的 `shaiwei:ts-v5-r3g1-recent-density-r2`。

恢复只把 Dockerfile 的 `FROM` 改成本地标签，并把冻结父镜像完整 ID 写入不可变 image label 和回归
测试。再次构建前必须用 `docker image inspect` 断言该本地标签仍精确等于
`sha256:3b81e501c134e7d91217d6102f4d033e16047310b89496dd1296d1684c9a42d9`；构建后还须核对新镜像 label、
内嵌 Git 与代码快照。父镜像、协议、H00906 请求、质量门和权限边界均未改变。

该失败不消耗协议规定的一次事实表请求和两次历史请求；外部请求、secret读取、数据门评价、策略效果、
模型、回测、模拟仓、Web、scheduler和生产变更均为0。
