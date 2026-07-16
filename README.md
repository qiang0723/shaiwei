# 筛微（Shai-Wei）
A 股中低频量化因子系统。筛者，准入闸门去伪存真；微者，防微杜渐，取细微而真实之超额。

- 规划基线：《筛微系统可行性技术报告 v0.5.4》（判据已冻结）
- 施工守则：CLAUDE.md ｜ 当前状态：STATE.md ｜ 口径卡：docs/DATA_SPEC.md ｜ 哨兵：docs/SENTINELS.md ｜ 判据：docs/GATES.md ｜ 日程：docs/DAY_PLAN.md ｜ 产品篮子：docs/FUND_COMPARATOR_SPEC.md
- 铁规三条：git 为真身；数据只增不改写；实验必记账。

## 开工

要求 Python 3.10-3.12。若系统 `python3` 不满足，显式传入合格解释器：

```bash
make bootstrap PYTHON_BASE=/path/to/python3.12
cp .env.example .env
# 仅在本机 .env 中填写 TUSHARE_TOKEN
make test
make runtime-check
```

若 macOS ARM64 没有 Homebrew/libomp，LightGBM 官方 wheel 会导入失败；本项目使用无 OpenMP 的本地编译回退：

```bash
make fix-lightgbm-macos
```

阶段 0 的自动执行顺序以 `docs/DAY_PLAN.md` 为准；任一哨兵失败或 G0 未通过均停止，不自动进入阶段 1。

## 飞书守护告警

告警凭据只放在被 Git 忽略的本地 `.env`，变量名见 `.env.example`。阶段流水线会发送启动、失败、完成事件；单个步骤运行超过 `FEISHU_HEARTBEAT_SECONDS` 后持续发送守护心跳。通知失败只写入 `logs/notifications/` 的脱敏投递账本，不改变研究流水线退出码。

```bash
make feishu-test
```

Docker 启动时通过 Compose 的 `env_file: .env` 注入相同变量，禁止把 webhook 或签名密钥写进镜像和 compose 文件。

## Docker 与国内数据源直连

完整 Stage 0 建议为 Docker Desktop 分配至少 **16 GiB** 内存。本机 1,058 万行行情的
S1-S10 门禁实测最大 RSS 约 10.0 GiB、峰值 footprint 约 14.1 GiB；Docker 默认约
8 GiB 会在 sentinel 阶段触发 OOM（退出码 `-9`）。本机当前使用约 20 GiB 上限。

Codex 桌面客户端继续使用 macOS 系统代理；筛微容器显式清空 HTTP/HTTPS/ALL
代理变量，并通过 `NO_PROXY` 对 Tushare、Sina、Eastmoney 和 Baostock 做直连。无需关闭
Clash，也不要把本机代理地址写进 `.env` 或 Compose。

Docker Desktop 使用手动代理时，还需要在 **Settings → Resources → Proxies** 的代理绕过
名单中加入下列域名。Docker Desktop 的网络后端独立于容器环境变量；缺少这项配置时，
容器仍可能经境外代理访问数据源，表现为 Tushare 延迟约 20 秒后返回空表。

```text
api.waditu.com,*.waditu.com,*.sina.com.cn,*.eastmoney.com,*.baostock.com,localhost,127.0.0.1
```

镜像仓库域名不要加入绕过名单，镜像拉取仍可经 Clash 代理完成。`network-check` 将交易
日历空表视为失败，避免把区域拒绝误报为网络正常。

```bash
make docker-build
make docker-network-check   # 只查询最近 7 天上交所交易日历，不写数据或账本
make docker-stage0-plan STAGE0_ARGS="--as-of 2026-07-15"
make docker-stage0-run  STAGE0_ARGS="--as-of 2026-07-15"
```

项目目录整体挂载到 `/workspace`，因此 `data/`、`logs/`、`ledger/`、`signals/` 和
`vendor/` 始终保留在本地 `shaiwei_init` 文件夹，迁移时不依赖 Docker 命名卷。

## Docker 日增量守护

日增量不依赖 macOS 的 cron/launchd，也不要求屏幕常亮。`scheduler` 容器每 15 分钟读取
交易日历与 `ledger/daily_runs.csv` 对账；北京时间 19:30 后才接纳当日数据。电脑熄屏不影响，
电脑真正休眠时容器会暂停，唤醒后的下一轮会按交易日逐日补齐。单轮最多补 20 个交易日，
每个交易日只有在行情、复权因子、每日指标、停牌和中证 800 指数数据全部通过行数、日期、
唯一键、跨接口覆盖和北交所排除校验后，才写入 PASS。

```bash
make docker-daily-plan       # 只读查看当前缺口
make docker-daily-once       # 手工跑一个对账周期
make docker-scheduler-up     # 常驻启动，restart: unless-stopped
make docker-scheduler-status # 查看健康状态
make docker-scheduler-logs   # 查看最近日志
make docker-scheduler-down   # 停止守护，数据与账本保留
```

原始 Parquet、日任务账本和健康文件都落在项目目录。Tushare 请求部分成功后再次运行会复用
已经过哈希校验的精确请求批次；只有整日 PASS 才推进水位。开始补采、完成和失败会发飞书，
无缺口的 15 分钟轮询不会刷屏。Docker 健康文件位于 `logs/scheduler/health.json`。

## 阶段 0 目标流

先看计划和凭据是否就绪（不会访问网络）：

```bash
make stage0-plan STAGE0_ARGS="--as-of 2026-07-15"
```

在本机 `.env` 填好 `TUSHARE_TOKEN` 后启动：

```bash
make stage0-run STAGE0_ARGS="--as-of 2026-07-15"
```

流程按「测试/运行时 → 基础表 → 停复牌/历史名称/公司行为/申万历史行业 → 行情 →
Baostock 歧义交易状态 → 财务 → AKShare 交叉源 → S1-S10 → qlib → 六窗口基线 →
影子信号 → AlphaGen CPU → G0 审计」运行，
首个非零退出码即停止。采集按请求参数和已提交 Parquet 哈希续跑；流水线成功事件同时绑定
`as-of + 代码快照 + 数据快照`，写入 `logs/pipeline/`。修复后重跑同一命令即可；需强制重验成功步骤时
加 `--no-resume`。最终审计会重新核验每个原始 Parquet 与 qlib 派生树的行数/内容哈希，从六窗口明细
重算 G0，且要求影子清单和 AlphaGen 候选逐项绑定实验账本。流程中没有阶段 1 命令，G0 失败只形成报告。
