# R2D-R1 16:05 预检失败关闭记录

## 裁决

`BLOCKED_BEFORE_MUTATION / R2D_R1_SCOPE_CLOSED_NO_RETRY`。

2026-08-27 16:05:07（UTC+8）按已批准 scope
`bb74c299a4ce5d76dc0cafd337b4d6529d6b433de72c012bcc6c54531297119a` 只运行一次
R2D-R1 start 的只读预检。预检返回：

```text
legacy noop evidence is outside the target boundary
```

预检没有调用 `start_current`，没有启动候选、停止旧容器、触发业务、读取密钥、访问外网或写入生产
账本。按该 scope 的失败关闭约束，R2D-R1 不重试、不顺延、不复用。

## 证据

- Git：`HEAD=origin/main=374fba52e8aebdb4c936b1e80d44ebc28ebbf117`；
- 旧 scheduler：容器 `183b8c6c5edd`、镜像 ID `722f63de...13b76`，持续 healthy；
- 16:05 预检读取的健康证据为 `noop / 20260826`，但 `updated_at` 对应 UTC+8 15:58:45，早于
  冻结的 16:00 新鲜度下限；
- 旧 scheduler 后续在 16:29:00 自然刷新为同一 `noop / 20260826`。该后续事实只用于定位探测节拍，
  不用于恢复或重跑已经关闭的 R2D-R1；
- R2C-R1 候选、fixture、release current/previous 和旧生产身份均未改变。

## 根因与边界

R2D-R1 的业务语义门没有被否证：16:00 后新鲜 `noop`、目标日零业务写入和唯一 readiness 仍是正确
边界。失败来自自动触发时点与旧 scheduler 约 30 分钟探测节拍没有对齐：16:05 时第一份 16:00 后
健康观察尚未形成。

后继不得放宽 16:00 新鲜度、零业务写入、唯一交易日、候选/旧生产身份、四挂载或 fixture 门。只能
另立新日期、新 scope，把唯一 start 检查安排在有充分节拍余量的时点；旧 R2D-R1 永久保留为失败
证据。
