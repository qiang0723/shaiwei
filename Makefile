.PHONY: bootstrap fix-lightgbm-macos runtime-check ingest sentinel test backtest-baseline check-ledger
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
sentinel:         ## 跑全部哨兵（S1-S10），任一 FAIL 退出码非零
	$(PYTHON) -m shaiwei.sentinel
test:             ## 单元测试 + 账本追加校验
	$(PYTHON) -m pytest -q
backtest-baseline:## Alpha158+LightGBM 双周基线，输出 G0 三条件数字与成本情景带
	$(PYTHON) -m shaiwei.backtest.baseline
check-ledger:     ## 账本 append-only 校验（也包含在 test 内）
	$(PYTHON) -m pytest -q tests/test_ledger_append_only.py
