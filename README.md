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

## 阶段 0 目标流

先看计划和凭据是否就绪（不会访问网络）：

```bash
make stage0-plan STAGE0_ARGS="--as-of 2026-07-15"
```

在本机 `.env` 填好 `TUSHARE_TOKEN` 后启动：

```bash
make stage0-run STAGE0_ARGS="--as-of 2026-07-15"
```

流程按「测试/运行时 → 基础表 → 停复牌/历史名称/公司行为/申万历史行业 → 行情/财务 →
AKShare 交叉源 → S1-S10 → qlib → 六窗口基线 → 影子信号 → AlphaGen CPU → G0 审计」运行，
首个非零退出码即停止。采集按请求参数和已提交 Parquet 哈希续跑；流水线成功事件同时绑定
`as-of + 代码快照 + 数据快照`，写入 `logs/pipeline/`。修复后重跑同一命令即可；需强制重验成功步骤时
加 `--no-resume`。最终审计会重新核验每个原始 Parquet 的行数和 SHA256，并要求数据账本、六窗口实验、
影子实验/清单及 AlphaGen 候选账本相互匹配。流程中没有阶段 1 命令，G0 失败只形成报告。
