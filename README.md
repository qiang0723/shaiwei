# 筛微（Shai-Wei）
A 股中低频量化因子系统。筛者，准入闸门去伪存真；微者，防微杜渐，取细微而真实之超额。

- 规划基线：《筛微系统可行性技术报告 v0.5.4》（判据已冻结）
- 施工守则：CLAUDE.md ｜ 当前状态：STATE.md ｜ 口径卡：docs/DATA_SPEC.md ｜ 哨兵：docs/SENTINELS.md ｜ 判据：docs/GATES.md ｜ 日程：docs/DAY_PLAN.md
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
