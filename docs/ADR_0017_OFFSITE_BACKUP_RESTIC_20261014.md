# ADR 0017 · 原始数据与运行证据的异地备份（restic，一次性 Docker 执行体）

- 日期：2026-10-14
- 状态：**ACCEPTED 2026-10-15**（用户对 §10 四问回复“按建议”：落点 D（外置盘 + 国内对象存储低频）；触发器为 Claude 桌面端
  定时任务 23:30 调用 `make backup`；纳入 `qlib_bin`；冻结镜像归档清单按 ADR/协议引用机械生成后由用户复核。外置盘与对象存储桶/
  子账号由用户准备；在 `config/backup_v1.yaml` 填入落点并经用户确认前，工程以 `target_kind: NONE` 运行，不写任何项目外目录。）
- 关联：docs/BACKUP_PLAN_PROPOSAL_20261014.md（分级清单、落点对比、机制细节）；AGENTS.md 备份条款（2026-10-14 修订）；
  STATE.md 2026-10-14 作废记录；ADR A1-3A（异机耐久性未就绪）；docs/SENTINELS.md S10；ADR 0016 §5.1（空闲判定复用）

## 1. 问题与结果目标

`data/`（7.3 GB，其中 raw 2.3 GB 为不可再生的 70,208 批原始 Parquet）、41 份账本、`logs/` 运行证据与 `.env` 只有本机一份；
原"等远程服务器就绪后再做异地备份"的前提已于 2026-10-14 作废。目标：RPO ≤1 个交易日、本地 RTO ≤1 小时、云端 RTO ≤4 小时；
每次备份可用账本中的 `content_sha256` 机械校验；每季一次真实恢复演练；不改变生产、不写入项目外目录直至用户批准落点。

## 2. 现状证据

体量与分级见提案 §1；Docker 镜像 168 GB 单列处理（提案 §5）；GitHub 已是代码层异地副本；A1-3B 因无异机副本阻断；
S10 跨机一致性"生产机上线后启用"至今未启用——恢复演练到另一台机器即可顺带启用它。

## 3. 候选方案

| 方案 | 判断 |
|---|---|
| restic（客户端加密、内容寻址去重、本地目录与 S3 兼容后端通用、`check --read-data` 全量校验） | **选** |
| borg（去重更强，但只支持本地/SSH 后端，无法直达对象存储） | 否 |
| rclone 同步（无版本、无加密原语，只能作传输层） | 否 |

**代价**：新增外部依赖（restic，打进一次性 Docker 镜像，不进生产 scheduler 镜像）；新账本 `ledger/backup_runs.csv` 与
`shaiwei.ledger.append_backup_run`；新配置 `config/backup_v1.yaml` + 独立 loader；新 Dockerfile/compose profile（须在
`config/build_asset_registry_v1.yaml` 恰好登记一次）；三个 make 目标；外部触发器。

## 4. 影响边界

- 对 `data/ ledger/ logs/` 只读挂载；不挂锁卷、不挂 `.git`、不挂 Docker socket；`network none`（本地落点）或仅允许对象存储域名。
- 不改生产 scheduler、compose.yaml、任何判据或口径；不新增常驻服务（AGENTS.md 禁止裸机守护，故不用 launchd/cron）。
- 密钥：restic 仓库口令与对象存储 AccessKey 只在 `.env`，变量名含 `SECRET`/`API_KEY`（受脱敏测试覆盖）；备份集本身含 `.env`，
  因此 restic 口令**不得**存于项目目录。对象存储子账号只给写+列举，不给删除；桶开版本控制。

## 5. 合同与数据

- `backup_runs.csv`：`run_id, started_at, finished_at, target_kind, repository_id, snapshot_id, status, included_paths_sha256,
  bytes_added, files_new, files_changed, verify_sampled, verify_mismatch, error_type, operator`。首次提交只含表头并登记进
  `tests/test_ledger_append_only.py::LEDGERS`。
- 一致性：只在**空闲窗口**执行（复用 ADR 0016 §5.1 的空闲判定：心跳 noop/pass、无周期锁、无子进程），默认 23:30；非空闲则
  最多推迟 4×30 分钟，仍冲突记 `SKIPPED_BUSY` 并通知，不强行快照。`logs/mlflow.db` 以 sqlite 在线备份导出副本后纳入。
- 校验：每次备份后 `restic check`；从 `ingest_batches.csv` 随机抽 20 行，`restic dump` 对应 Parquet 计算 sha256 比对；不一致即
  `status=FAIL`。每月 `check --read-data-subset=10%`；每季全量恢复到临时目录并跑 G0 逐批重哈希（`make g0-audit` 的 rehash 部分）。
- 保留：`--keep-daily 14 --keep-weekly 8 --keep-monthly 24`；G0 封存快照单独永久 tag。

## 6. 失败关闭

落点/口令未配置 → `NOT_READY`，不创建仓库；空闲判定失败 → 推迟/`SKIPPED_BUSY`；`restic check` 或抽样哈希不一致 → `FAIL`
并飞书告警（事件名 `backup_verify_failed`）；任何写项目外目录的动作在用户批准落点前被配置层拒绝（`target_kind: NONE`）。

## 7. 回滚

纯新增能力；停用即不再运行容器与触发器；已有快照保留。无数据迁移。

## 8. 验收指标

单元测试（配置 loader 拒绝未知字段；空闲判定各否定分支；账本 schema；抽样校验逻辑）；本地目录落点的端到端 fixture
（`.test-tmp` 内建仓库、备份、校验、恢复到临时目录并比对 sha256）；全仓测试、架构门、Ruff、脱敏；首次真实全量后立即一次抽样校验
并记 STATE；一个月内一次恢复演练 PASS。

## 9. 退出 / 复审触发器

落点变更或体量超过 50 GB 时复审方案；若季度演练连续失败则停用并另立方案。

## 10. 需要用户裁决

1. 落点：A 外置盘 / B NAS / C 云对象存储 / D A+C（建议 D，最少 C；云厂商建议阿里云 OSS 或腾讯云 COS 低频存储）。
2. 触发器：接受 Claude 桌面端定时任务每日 23:30 调用 `make backup`（与巡检同机制）？
3. 是否纳入 T2 派生缓存中的 `qlib_bin`（528 MB，G0 存证）？
4. 冻结研究镜像归档（`docker save` 到备份仓库）清单由谁定：按 ADR/协议引用机械生成，还是你指定？
