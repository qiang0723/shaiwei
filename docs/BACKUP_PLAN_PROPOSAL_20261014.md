# 筛微异地备份方案（提案，2026-10-14）

状态：PROPOSAL → 由 `docs/ADR_0017_OFFSITE_BACKUP_RESTIC_20261014.md` 于 2026-10-15 接受（落点 D）。本文保留为该 ADR 的
细节附件；与 ADR 冲突处以 ADR 为准。未施工、未写入任何项目外目录。
背景：原「等远程服务器就绪后再做异地备份」前提于 2026-10-14 作废（阿里云弃用），7.3 GB 数据与全部运行证据目前只有本机一份。

## 1. 保护对象与分级

实测体量（2026-10-14，`du`/`docker system df`）：

| 层级 | 内容 | 体量 | 可否重建 | 结论 |
|---|---|---|---|---|
| **T0 不可再生** | `data/raw/`（Tushare/AKShare/Baostock 原始 Parquet，70,208 批） | 2.3 GB | 否。Tushare 历史可重拉但不保证逐字节一致，且 `ingest_batches.csv` 里的 sha256 会失配 | 必备 |
| **T0 不可再生** | `ledger/*.csv`（41 份账本） | 42 MB | 否 | 必备 |
| **T0 不可再生** | `logs/`（哨兵报告、飞书投递、调度时间线、`mlflow.db`） | 16 MB | 否 | 必备 |
| **T0 不可再生** | `.env`（Tushare token、飞书签名） | <4 KB | 可在供应商处重置 | 必备，单独加密 |
| **T1 研究证据** | `data/research/`、`data/control/`、`data/archive/`、`data/g8/`、`data/paper/`、`data/shadow/` | ≈4.6 GB | 理论上可从冻结协议重跑，但多数批次依赖已停用的外部调用（DeepSeek、监管 HTTP 源） | 必备 |
| **T2 派生缓存** | `data/qlib_bin/`（G0 冻结）、`data/qlib_forward/`（前瞻，保留 2 版）、`data/cache/` | 1.7 GB | 可由 raw 全量重建，整树哈希可复核 | 可选；建议带上 qlib_bin（G0 存证） |
| **T3 代码** | `.git`（715 提交，与 GitHub `origin` 同步） | 300 MB | GitHub 已是异地副本 | 本机仓库纳入即可，不必单列 |
| **T4 冻结镜像** | `shaiwei:*` 中被 ADR/协议引用的发布镜像（scheduler-current/previous、m6/m7/ts 冻结 release） | 每个 3.7 GB，共享底层；`docker system df` 镜像总计 168 GB、可回收 144 GB | Dockerfile 内容寻址，理论可重建；但 ADR_A1_3A 已指出 RepoDigest ≠ 异机存在 | 分开处理，见 §5 |
| 不备份 | `web-ui/node_modules`、`.venv`、Docker 构建缓存（185 GB）、`.test-tmp/`、`mlruns/`、`workspace/` | — | 全可重建 | 排除 |

**结论：主备份集 ≈ 7.5–9 GB，日增量 ≈ 50–100 MB（新 raw 分区 + 账本 + 日志 + qlib_forward 版本切换）。** 体量很小，落点选择由容灾等级而非成本决定。

## 2. 落点候选

| 方案 | 容灾等级 | 一次性成本 | 持续成本 | 恢复速度 | 风险 |
|---|---|---|---|---|---|
| A. 外置 SSD（USB-C，≥1 TB） | 防本机 SSD 故障，**不防**同地火灾/失窃/误操作连带 | 500–900 元 | 0 | 分钟级 | 常插着等于同机；需「插上→备份→拔下」纪律 |
| B. NAS（局域网） | 同 A，另防单盘故障（RAID） | 2,000+ 元 | 电费 | 分钟级 | 仍为同地 |
| C. 云对象存储（阿里云 OSS / 腾讯云 COS / Backblaze B2） | 异地，防同地灾难 | 0 | 10 GB 标准存储 ≈ 1–3 元/月；B2 ≈ $0.06/月；流量费可忽略 | 10 GB 约 10–30 分钟（取决于带宽） | 账号安全；需客户端加密 |
| D. A + C | 本地快恢复 + 异地容灾 | 同 A | 同 C | 最优 | 两套纪律 |

**推荐 D，若只选一个选 C。** 理由：体量不到 10 GB，云端月费是零头；而「只有外置盘」等于把风险从「一块 SSD 坏」缩到「一间屋子出事」，没有质变。GitHub 已经承担了代码层的异地副本，数据层也应有同等待遇。

国内外落点取舍：阿里云/腾讯云上传快、合规无虞；B2 便宜但跨境速度不稳。本机已有 Clash 海外路径（见 README 代理约定），但备份不该依赖代理可用性——**优先国内 OSS/COS，低频/归档存储类型即可**（恢复才读，读频次极低）。

## 3. 工具与机制

**推荐 restic**（单二进制、客户端 AES-256 加密、内容寻址去重、原生支持本地目录与 S3 兼容后端，OSS/COS/B2 均可直连；`restic check --read-data` 可做全量完整性校验）。
备选：borg（仅本地/SSH 后端，去重更强，但不支持对象存储）；rclone（仅同步无版本，不推荐作主工具，可作 OSS 传输层）。

### 一致性
- `data/raw/` 只增不改，任何时刻快照都一致。
- `ledger/*.csv` 由调度器追加写；在日链结束后（20261013 实测 22:25 收尾）再备份，避开写窗口。**备份时间定在 23:30 北京时间**；若调度器正在运行（`logs/scheduler/health.json` 的心跳 + `daily_runs.csv` 当日尾行状态），则推迟 30 分钟重试，最多 4 次，仍冲突则告警不备份。
- `logs/mlflow.db` 是 SQLite：用 `sqlite3 .backup` 导出副本后纳入，不直接拷热文件。
- 不依赖 Docker 内部状态：runtime_locks named volume 只有 40 KB 锁文件，恢复时重建即可，不备份。

### 加密与密钥
- restic 仓库口令：随机 32 字节，存 1Password + 一份纸质；**不存在项目目录、不入 git、不进 `.env`**（`.env` 本身在备份集里）。
- OSS/COS 用只写+列举权限的子账号 AccessKey（RAM/CAM），禁止删除权限 → 本机被入侵也删不掉历史快照；再开桶级版本控制/WORM 作第二道。

### 保留策略
`--keep-daily 14 --keep-weekly 8 --keep-monthly 24`；G0 封存快照（`stage0_complete` 对应的 raw + qlib_bin）单独打一个永久 tag。

## 4. 校验与恢复演练（没有这一节的备份不算备份）

1. **每次备份后**：`restic check`（元数据）；随机抽 20 个 `ingest_batches.csv` 行，从快照里 `restic dump` 对应 Parquet，sha256 与账本 `content_sha256` 逐一比对。账本本身就是现成的校验谕示，这是本项目独有的优势。
2. **每月**：`restic check --read-data-subset=10%`。
3. **每季**：全量恢复到临时目录（或另一台机器），跑 G0 的逐批重哈希审计（`make g0-audit` 的 rehash 部分）和 S1/S6 哨兵；PASS 才算这一季的备份有效。这同时可以把 `docs/SENTINELS.md` 里一直「生产机上线后启用」的 **S10 跨机一致性**真正启用。
4. 演练结果记入 `ledger/`（新账本 `backup_runs.csv`，走 `shaiwei.ledger.append_*`）和 STATE.md。

RPO 目标：1 个交易日。RTO 目标：本地盘 1 小时内、云端 4 小时内恢复到可跑日链。

## 5. 冻结镜像的处理（单列）

168 GB 镜像不进主备份。处理原则：
- **可重建的**（有 Dockerfile + 锁文件 + git 提交的）：不备份，记录 image ID ↔ 构建提交的映射即可（`logs/releases/*.jsonl` 已有）。
- **被 ADR/验收引用、要求逐字节保真的**：`docker save | zstd` 成 tar，放入 restic 仓库的独立路径，并把 tar 的 sha256 记账。初步清单：`scheduler-current`、`scheduler-previous`、`web-runtime-release-b026ed34`、`research-control-release-b026ed34`、以及 `docs/ADR_A1_3A_M7_ARCHIVE_READINESS_20260809.md` 点名的 M7 冻结镜像。预计 6–10 个、压缩后 ≈ 10–15 GB。
- 其余 ≈ 90 个一次性研究批次镜像：先列清单到 STATE 待答点，由用户决定是否 `docker image prune`（可回收 144 GB）；**本提案不执行任何清理**。

## 6. 施工顺序（落点确定后）

1. `config/backup_v1.yaml`（路径、排除、时间窗、保留策略；后端地址与桶名）；口令与 AccessKey 走 `.env`/1Password。
2. Make 目标：`make backup`（含运行窗口检查）、`make backup-verify`（抽样哈希比对）、`make backup-restore-drill DEST=...`。
3. `ledger/backup_runs.csv` + `shaiwei.ledger.append_backup_run`。
4. 首次全量 → 立即做一次抽样校验 → 记 STATE。
5. 执行载体：**一次性 Docker 容器**（独立 `compose.ops.yaml` profile，restic 打进镜像，只读挂载
   `data/ ledger/ logs/`，可写挂载备份目标；`network none` 或仅允许对象存储域名），不进生产
   scheduler，也不新增常驻守护——AGENTS.md「常驻任务使用 Docker，不得擅自改为裸机守护」禁止 launchd/cron
   裸机方案（本提案初稿曾写 launchd，2026-10-14 据此更正）。新 Dockerfile/compose 须在
   `config/build_asset_registry_v1.yaml` 恰好登记一次。
6. 触发：每日 23:30 由 Claude 桌面端定时任务调用 `make backup`（只是触发器，逻辑全在仓库内、可手动重放）；
   或用户手动执行。是否接受 Claude 定时任务作为触发器，由用户裁决。
7. 一个月后做首次季度级恢复演练。
8. 本方案触发宪法 §5 的 ADR：新增外部依赖（restic）与新账本 schema（`backup_runs.csv`）。施工前先写 ADR。

## 7. 需要用户决定的点

- 落点：A / B / C / D（§2）。推荐 D，最少 C。
- 云厂商与地域（若选 C/D）：建议阿里云 OSS 华东或腾讯云 COS，低频存储。
- 是否把 T2 派生缓存（1.7 GB）纳入——建议纳入 qlib_bin，排除 qlib_forward 与 cache。
- 90 个一次性研究镜像是否清理（与备份无关，但同在磁盘账上）。
