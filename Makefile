.PHONY: bootstrap ingest sentinel test backtest-baseline check-ledger
VENV ?= .venv
PYTHON := $(VENV)/bin/python

bootstrap:        ## 创建隔离环境、安装依赖并校验配置
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"
	$(PYTHON) -c "from shaiwei.config import load; load(); print('config OK')"
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
