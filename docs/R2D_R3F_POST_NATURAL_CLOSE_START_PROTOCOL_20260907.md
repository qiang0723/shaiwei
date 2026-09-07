# R2D-R3F 旧生产自然闭环后 start-only 协议

## 结论

2026-09-07 21:56 UTC+8 的一次授权只读核验确认：20260907 已由旧生产自然完成，但候选仍未启动，
所以该日不能冒充候选首个自然交易日。R2D 保持开放，G1 不开工。本节点只冻结下一交易日的
start-only 工程边界，不生成或消费执行 scope，不授权 `start_current`、restart、promote、rollback
或任何其他生产动作。

## 20260907 自然闭环证据

- release state SHA-256 为
  `c879228f6514b3a07c0d1a6efec0c68832d0feab7444821e9376de1bfd86c454`；current 仍是候选
  `97d8c05e...7553` / `b64ae11...5ebe`，previous 仍是旧生产。
- release audit SHA-256 为
  `4524d2d0af6d57dbf1fad6c57dcb623f62eb39f63930d278c26999f895e1eea1`；34 条记录的哈希链
  PASS，末事件仍为 `PROMOTE_PASS`，末记录 SHA-256 为
  `aca0245b0e59e19612a2fd332dcb10188f0cfbfcd4eb5211f1167587819f477d`。
- 20260907 daily 1、shadow 1、paper 2，状态均为 PASS，代码身份仍为旧生产
  `4e5244b6...2708`。scheduler health 为 `noop / 20260907`，更新时间为
  `2026-09-07T13:53:51.562880+00:00`。
- Top30 最新 PASS 产物 SHA-256 为
  `29931c72063f171476a68da70f49d6f306f9844969713074a27b0ed12a042618`；Top20 为
  `aeb7bc1790c0f7118c6db5d292d3cfae80f0be032a45502c672e6b656b982174`。两份实际字节哈希、
  `FORWARD` mode 和身份均与账本一致；未读取或输出效果字段。
- 旧容器仍为 `7a55151d...80c4` / `722f63de...13b76`，running、healthy、restart 0、只读根，
  三个 bind 加 `shaiwei_runtime_locks_v1` 四挂载完整。候选镜像三个发布标签与冻结身份一致，
  lock authority 为 `docker-named-volume-v1`。
- 冻结日历
  `data/qlib_forward/versions/4e5244b6b027-f4430e0fdc0f/calendars/day.txt` SHA-256 为
  `c9916944c6865cf4e1e6b15af7ac90a54d2275320d25353873071f08d892b114`，20260907 后首个交易日
  为 20260908。

## R3F 唯一变量与身份迁移

新配置 `config/r2d_scheduler_release_guard_r3f_start_v1.yaml` 继续使用只允许 start 的
`r2d-scheduler-release-guard-r2-v1`，候选、旧生产、四挂载和 R3A fixture 均字节身份不变；只做：

1. target trade date 推进到 20260908，start window 固定为 16:40—19:00 UTC+8；
2. 最新双账户 FORWARD 绑定上述 20260907 两份产物；
3. 旧生产边界绑定 20260908 16:00 后自然形成的 `noop / 20260907`，且 20260908
   daily/shadow/paper 必须全部为 0；
4. 控制器由旧六组件迁移到已交付的 13 组件安全清单，source HEAD 为
   `69f0d913ebd60126ebe8d2f190053329858a45d6`，组件 SHA-256 为
   `f88f44a791e630c4d57dcd79f9c7a3684b263bf64a935e9f5829ed53a3d3f998`。

配置自身 SHA-256 为
`b81a04d5b9f9ce900ff406a6766b2343e0e62ccc19c827e00c741aa960c05f67`。

## 工程验证

- R3F 与 R2D 发布安全合同专项：61 PASS；
- 受保护全仓回归：2013 PASS、1 项真实 `.env` 密钥比对按已批准例外未执行、17 条既有警告；
- `make architecture-check`：13 PASS；
- 新测试 Ruff、YAML 模型解析、配置 SHA-256 与 `git diff --check`：PASS。

测试启用了项目内写入保护和禁网边界，合成临时文件仅进入既有 `.test-tmp`；未读取 `.env`、
效果或生产元数据，未调用 Docker，也未生成 scope 或执行生产动作。

## 20260908 执行前门与停止点

只有在配置提交推送、用户另行批准生成不可重跑 scope 后，才可在 2026-09-08 16:40—19:00 UTC+8
运行一次无 `--execute` 的只读预检。scope 必须绑定届时 HEAD/origin、配置全文与 SHA、release
state/audit 哈希、旧容器精确 ID、正确 Compose project、禁止派发后自动回滚及 3600 秒 health
新鲜度。预检还必须同时证明：

- current/previous、候选镜像、R3A fixture、13 组件控制器、旧容器、restart 0、只读根、四挂载和
  三个发布标签无漂移；
- readiness 为 PASS 且唯一新交易日为 20260908；
- 最新两账户仍精确等于冻结的 20260907 FORWARD；
- health 是 20260908 16:00 后自然形成的 `noop / 20260907`，且目标日三类账本仍全部为 0。

任一门失败即关闭，不生成批准文件、不启动、不重试或放宽门槛。只读预检 PASS 后报告唯一 scope
哈希和逐字批准文本；用户明确批准前停止。候选启动后还必须等待其 20260908 自然 daily/shadow/
双账户 FORWARD、身份、重放、新鲜度与通知门完整验收，才能正式关闭 R2D 并进入 G1。
