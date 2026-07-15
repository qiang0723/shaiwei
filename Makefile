.PHONY: bootstrap fix-lightgbm-macos runtime-check ingest ingest-dry-run crosscheck sentinel qlib-build test backtest-baseline shadow alphagen-benchmark g0-audit stage0-plan stage0-run check-ledger
VENV ?= .venv
PYTHON_BASE ?= python3
PYTHON := $(VENV)/bin/python
MPLCONFIGDIR ?= $(CURDIR)/data/cache/matplotlib
export MPLCONFIGDIR

bootstrap:        ## 创建隔离环境、安装依赖并校验配置
	$(PYTHON_BASE) -c "import sys; assert (3, 10) <= sys.version_info[:2] < (3, 13), 'Python 3.10-3.12 required'"
	$(PYTHON_BASE) -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.lock
	$(PYTHON) -m pip install --no-deps -e .
	$(PYTHON) -c "from shaiwei.config import load; load(); print('config OK')"
fix-lightgbm-macos: ## 无 Homebrew/libomp 时，编译无 OpenMP 的 LightGBM
	$(PYTHON) -m pip install cmake ninja
	$(PYTHON) -m pip uninstall -y lightgbm
	CMAKE_ARGS="-DUSE_OPENMP=OFF" $(PYTHON) -m pip install --no-binary lightgbm "lightgbm==4.6.0"
	$(PYTHON) -c "import lightgbm; print('lightgbm', lightgbm.__version__)"
runtime-check:     ## 核对阶段 0 关键运行时确实可导入
	mkdir -p $(MPLCONFIGDIR)
	$(PYTHON) -c "import qlib, lightgbm, tushare, akshare; print('qlib', qlib.__version__); print('lightgbm', lightgbm.__version__); print('tushare', tushare.__version__); print('akshare', akshare.__version__)"
ingest:           ## Day1-5 数据采集（实现于 src/shaiwei/ingest/，每批必过 ledger.append_ingest_batch）
	$(PYTHON) -m shaiwei.ingest
ingest-dry-run:   ## 无凭据打印基础表请求计划
	$(PYTHON) -m shaiwei.ingest --dry-run
crosscheck:       ## S8 的 AKShare 冻结样本采集（支持账本续跑）
	$(PYTHON) -m shaiwei.ingest.akshare --resume
sentinel:         ## 跑全部哨兵（S1-S10），任一 FAIL 退出码非零
	$(PYTHON) -m shaiwei.sentinel
qlib-build:       ## 哨兵通过后构建 qlib 原生 bin
	$(PYTHON) -m shaiwei.transform.qlib_bin
test:             ## 单元测试 + 账本追加校验
	$(PYTHON) -m pytest -q
backtest-baseline:## Alpha158+LightGBM 双周基线，输出 G0 三条件数字与成本情景带
	$(PYTHON) -m shaiwei.backtest.baseline
shadow:           ## 复用当前快照生成不可覆盖影子信号 manifest
	$(PYTHON) -m shaiwei.shadow
alphagen-benchmark:## AlphaGen 单轮 CPU benchmark（必须先完成 qlib-build）
	$(PYTHON) -m shaiwei.benchmark.alphagen_cpu
g0-audit:         ## 只汇总冻结 G0 和两项动手证据；永不进入阶段 1
	$(PYTHON) -m shaiwei.audit.g0
stage0-plan:      ## 查看阶段 0 自动流和凭据就绪状态；STAGE0_ARGS 可传 --as-of/步骤范围
	$(PYTHON) -m shaiwei.pipeline.stage0 --plan $(STAGE0_ARGS)
stage0-run:       ## 失败即停、可续跑的 Day0-7 全流程
	$(PYTHON) -m shaiwei.pipeline.stage0 $(STAGE0_ARGS)
check-ledger:     ## 账本 append-only 校验（也包含在 test 内）
	$(PYTHON) -m pytest -q tests/test_ledger_append_only.py
