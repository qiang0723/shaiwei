.PHONY: bootstrap fix-lightgbm-macos runtime-check ingest ingest-dry-run crosscheck sentinel qlib-build test backtest-baseline shadow shadow-cycle shadow-report paper-cycle paper-query paper-verify paper-acceptance alphagen-benchmark stage1-gp-preflight stage1-g1-preflight stage1-preflight g0-audit g1-schema g1-admit g8-spec stage0-plan stage0-run check-ledger feishu-test network-check docker-build docker-network-check docker-stage0-plan docker-stage0-run docker-daily-plan docker-daily-once docker-shadow-cycle docker-paper-cycle docker-paper-verify docker-paper-acceptance docker-g1-admit docker-stage1-preflight docker-d1-fixture docker-d1-live docker-d1-review-live docker-release-build docker-release-promote docker-release-rollback docker-release-start docker-release-status docker-scheduler-up docker-scheduler-status docker-scheduler-logs docker-scheduler-down docker-web-build docker-web-up docker-web-status docker-web-logs docker-web-down
VENV ?= .venv
PYTHON_BASE ?= python3
PYTHON := $(VENV)/bin/python
MPLCONFIGDIR ?= $(CURDIR)/data/cache/matplotlib
G1_EVIDENCE ?=
RELEASE_IMAGE ?=
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
shadow-cycle:     ## 前瞻影子：续跑次日开盘对账并为最新日增量 PASS 生成信号
	$(PYTHON) -m shaiwei.pipeline.shadow_cycle
shadow-report:    ## 刷新前瞻影子运行审计报告
	$(PYTHON) -c "from shaiwei.config import load; from shaiwei.shadow.report import write_forward_report; print(write_forward_report(load()))"
paper-cycle:      ## 消费已对账信号，推进 model_baseline 模拟组合
	$(PYTHON) -m shaiwei.pipeline.paper_cycle
paper-query:      ## 只读打印最新模拟组合快照
	$(PYTHON) -m shaiwei.paper.query snapshot
paper-verify:     ## 从追加式事件账本独立重放并核对全部模拟组合产物
	$(PYTHON) -m shaiwei.paper.query verify
paper-acceptance: ## 机器判定首个自然 FORWARD 与飞书证据是否完整
	$(PYTHON) -m shaiwei.paper.query acceptance
alphagen-benchmark:## AlphaGen 单轮 CPU benchmark（必须先完成 qlib-build）
	$(PYTHON) -m shaiwei.benchmark.alphagen_cpu
stage1-gp-preflight: ## 2016-2018 极小预算 GP：40 候选、1 代，只生成并全量记账
	$(PYTHON) -m shaiwei.benchmark.alphagen_cpu --research-family stage1-gp-preflight-v1 --instrument csi800 --index-code 000906.SH --train-start 2016-01-01 --train-end 2018-12-31 --population-size 40 --tournament-size 10
stage1-g1-preflight: ## 提升前 2 个有效 GP 候选，自动取证并调用冻结 G1；不自动入库
	$(PYTHON) -m shaiwei.research.g1_pipeline --research-family stage1-gp-preflight-v1
stage1-preflight: stage1-gp-preflight stage1-g1-preflight
g0-audit:         ## 只汇总冻结 G0 和两项动手证据；永不进入阶段 1
	$(PYTHON) -m shaiwei.audit.g0
g1-schema:        ## 打印 G1 候选证据 JSON Schema；不运行研究或准入
	$(PYTHON) -m shaiwei.research.g1 --print-schema
g1-admit:         ## 对已记实验总账的候选作 G1 判定；用 G1_EVIDENCE=项目内JSON
	@test -n "$(G1_EVIDENCE)" || (echo "G1_EVIDENCE is required"; exit 2)
	$(PYTHON) -m shaiwei.research.g1 --evidence "$(G1_EVIDENCE)"
g8-spec:          ## 打印冻结的 G8 同风险公式、产品篮子哈希与规格哈希；不作提前裁决
	$(PYTHON) -m shaiwei.evaluation.g8
stage0-plan:      ## 查看阶段 0 自动流和凭据就绪状态；STAGE0_ARGS 可传 --as-of/步骤范围
	$(PYTHON) -m shaiwei.pipeline.stage0 --plan $(STAGE0_ARGS)
stage0-run:       ## 失败即停、可续跑的 Day0-7 全流程
	$(PYTHON) -m shaiwei.pipeline.stage0 $(STAGE0_ARGS)
check-ledger:     ## 账本 append-only 校验（也包含在 test 内）
	$(PYTHON) -m pytest -q tests/test_ledger_append_only.py
feishu-test:      ## 使用本地 .env 向飞书发送一条签名连通性测试消息
	$(PYTHON) -m shaiwei.notify --test
network-check:    ## 脱敏验证 Tushare 直连；不写数据、账本或 Token
	$(PYTHON) -m shaiwei.network_check
docker-build:     ## 构建统一 Docker 运行镜像
	docker compose build shaiwei
docker-network-check: ## 容器内脱敏验证 Tushare 直连
	docker compose run --rm shaiwei python -m shaiwei.network_check
docker-stage0-plan: ## 容器内查看阶段 0 执行计划
	docker compose run --rm shaiwei python -m shaiwei.pipeline.stage0 --plan $(STAGE0_ARGS)
docker-stage0-run: ## 容器内执行阶段 0 流水线
	docker compose run --rm shaiwei python -m shaiwei.pipeline.stage0 $(STAGE0_ARGS)
docker-daily-plan: ## 只读查看日增量缺口，不访问网络
	docker compose run --rm shaiwei python -m shaiwei.pipeline.daily --plan
docker-daily-once: ## 容器内立即对账并补采一次
	docker compose run --rm shaiwei python -m shaiwei.pipeline.scheduler --once
docker-shadow-cycle: ## 容器内单独续跑一次前瞻影子闭环
	docker compose run --rm shaiwei python -m shaiwei.pipeline.shadow_cycle
docker-paper-cycle: ## 容器内单独推进一次模拟组合闭环
	docker compose run --rm shaiwei python -m shaiwei.pipeline.paper_cycle
docker-paper-verify: ## 容器内从追加式事件账本独立重放模拟组合
	docker compose run --rm shaiwei python -m shaiwei.paper.query verify
docker-paper-acceptance: ## 容器内机器判定首个自然 FORWARD 验收
	docker compose run --rm shaiwei python -m shaiwei.paper.query acceptance
docker-g1-admit:  ## 容器内执行冻结 G1 裁决；不启动因子生成
	@test -n "$(G1_EVIDENCE)" || (echo "G1_EVIDENCE is required"; exit 2)
	docker compose run --rm shaiwei python -m shaiwei.research.g1 --evidence "$(G1_EVIDENCE)"
docker-stage1-preflight: ## 容器内极小预算 GP → 自动证据 → G1 REJECT/PASS；零自动入库
	docker compose run --rm shaiwei python -m shaiwei.benchmark.alphagen_cpu --research-family stage1-gp-preflight-v1 --instrument csi800 --index-code 000906.SH --train-start 2016-01-01 --train-end 2018-12-31 --population-size 40 --tournament-size 10
	docker compose run --rm shaiwei python -m shaiwei.research.g1_pipeline --research-family stage1-gp-preflight-v1
docker-d1-fixture: ## D1-2A 断网 prompt/知识/mock传输/schema/DSL/账本 fixture；不加载 .env、不读市场数据
	docker compose -f compose.research.yaml --profile research run --rm d1-fixture

docker-d1-live: ## D1-2B 受控真实40次生成；调用前须冻结提交、显式导出唯一 DeepSeek secret
	docker compose -f compose.research.yaml --profile research-live run --rm d1-live
docker-d1-review-live: ## D1-3A 恰好8次盲态对抗复核；不生成候选、不读W1-W6或运行G1
	docker compose -f compose.research.yaml --profile research-review-live run --rm d1-review-live
docker-release-build: ## 从干净工作树构建并验证内容寻址 scheduler 镜像
	$(PYTHON) -m shaiwei.release build
docker-release-promote: ## 提升 RELEASE_IMAGE；默认重建 scheduler 并验收隔离契约
	@test -n "$(RELEASE_IMAGE)" || (echo "RELEASE_IMAGE is required"; exit 2)
	$(PYTHON) -m shaiwei.release promote --image "$(RELEASE_IMAGE)"
docker-release-rollback: ## 回滚到上一不可变 scheduler 镜像并验收
	$(PYTHON) -m shaiwei.release rollback
docker-release-start: ## 启动已提升的 current 镜像并验收挂载/快照/健康
	$(PYTHON) -m shaiwei.release start
docker-release-status: ## 校验本地发布状态与哈希链审计
	$(PYTHON) -m shaiwei.release status
docker-scheduler-up: ## 启动已提升的不可变 scheduler 镜像；不隐式构建
	docker compose up -d scheduler
docker-scheduler-status: ## 查看守护容器与健康状态
	docker compose ps scheduler
docker-scheduler-logs: ## 查看最近 100 行脱敏守护日志
	docker compose logs --tail=100 scheduler
docker-scheduler-down: ## 停止日增量守护，不删除本地数据
	docker compose stop scheduler
docker-web-build: ## 构建隔离的 P3-0 只读 Web 镜像，不启动服务
	docker compose -f compose.web.yaml --profile web build web-query
docker-web-up: ## 显式启动两个 Web 服务；不会启动或重建 scheduler
	docker compose -f compose.web.yaml --profile web up -d web-query web-ui
docker-web-status: ## 查看隔离 Web 服务状态
	docker compose -f compose.web.yaml --profile web ps web-query web-ui
docker-web-logs: ## 查看 Web 最近 100 行脱敏运行日志
	docker compose -f compose.web.yaml --profile web logs --tail=100 web-query web-ui
docker-web-down: ## 仅停止隔离 Web 服务
	docker compose -f compose.web.yaml --profile web down
