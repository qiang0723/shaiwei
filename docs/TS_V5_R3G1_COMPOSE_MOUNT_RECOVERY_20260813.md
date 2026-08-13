# TS-v5 R3G-1 Docker 挂载表达恢复加注

首次真实画像命令在容器创建前失败：Compose 把未加引号的 tmpfs 逗号选项解析成多个挂载路径，
Docker 报 `invalid mount path: 'nosuid'`。容器进程未启动，行情、密度、收益均未读取，输出目录为空；
生产 scheduler 仍是原容器 `183b8c6c5edd`、原镜像且 healthy。

R1 只把 tmpfs 项改成一个带引号的字符串；不改代码、数据逻辑、候选、431 点、时间角色、门槛或
输出目录。按新 Git 身份重建后只允许一次恢复画像和一次独立审计。
