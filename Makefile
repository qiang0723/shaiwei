.PHONY: bootstrap fix-lightgbm-macos runtime-check ingest ingest-dry-run crosscheck sentinel qlib-build test architecture-check backtest-baseline shadow shadow-cycle shadow-report paper-cycle paper-query paper-verify paper-acceptance alphagen-benchmark stage1-gp-preflight stage1-g1-preflight stage1-preflight g0-audit g1-schema g1-admit g8-spec ts-v3-data-gate ts-v3-recovery-release ts-v3-recovery-network ts-v3-recovery-profile ts-v3-recovery-audit docker-ts-recovery-build docker-ts-recovery-network docker-ts-recovery-profile docker-ts-recovery-audit docker-ts-r4-build docker-ts-r4-profile docker-ts-r4-audit docker-ts-v4-density-build docker-ts-v4-density-profile docker-ts-v4-density-audit docker-ts-v5-r3g-build docker-ts-v5-r3g-run docker-ts-v5-r3g-audit stage0-plan stage0-run check-ledger feishu-test network-check docker-build docker-network-check docker-stage0-plan docker-stage0-run docker-daily-plan docker-daily-once docker-shadow-cycle docker-paper-cycle docker-paper-verify docker-paper-acceptance docker-g1-admit docker-stage1-preflight docker-d1-fixture docker-d1-live docker-d1-review-live docker-d1-semantic-verify docker-m1-star50-build docker-m1-star50-preflight docker-m1-star50-live docker-m1-star50-review-build docker-m1-star50-review-preflight docker-m1-star50-review-live docker-m3-multi-pool-build docker-m3-multi-pool-preflight docker-m3-multi-pool-live-build docker-m3-multi-pool-live-preflight docker-m3-multi-pool-live docker-m3-multi-pool-review-build docker-m3-multi-pool-review-preflight docker-m3-multi-pool-review-live-build docker-m3-multi-pool-review-live-preflight docker-m3-multi-pool-review-live docker-m3-multi-pool-review-verify docker-llm-review-contract-v2 docker-f1-fundamental-pit-build docker-f1-fundamental-pit docker-f1-fundamental-pit-recovery-build docker-f1-fundamental-pit-recovery docker-f2-fundamental-dynamics-build docker-f2-fundamental-dynamics docker-f2-fundamental-dynamics-recovery-build docker-f2-fundamental-dynamics-recovery docker-f1-fundamental-effect-build docker-f1-fundamental-effect-residual docker-f1-fundamental-effect docker-f2-fundamental-effect-build docker-f2-fundamental-effect-residual docker-f2-fundamental-effect docker-g8-primary-build docker-g8-primary-capture docker-g8-primary-verify docker-m5-data-gate-build docker-m5-data-gate-fixture docker-m5-lineage-build docker-m5-lineage-fixture docker-m6-model-attribution-build docker-m6-model-attribution-preflight docker-m6-model-attribution-audit docker-m6-effect-build docker-m6-effect-fixture docker-m6-effect-run docker-m6-effect-audit docker-m6-audit-recovery-build docker-m6-audit-recovery-fixture docker-m6-audit-recovery-run docker-m6-topk-conversion-build docker-m6-topk-conversion-fixture docker-m6-topk-conversion-audit docker-m6-top30-diagnostic-build docker-m6-top30-diagnostic-fixture docker-m6-top30-diagnostic-original docker-m6-top30-diagnostic-current docker-m6-top30-diagnostic-audit docker-m6-top30-recovery-build docker-m6-top30-recovery-fixture docker-m6-top30-recovery-original docker-m6-top30-recovery-current docker-m6-top30-recovery-audit docker-m6-top30-provenance-build docker-m6-top30-provenance-fixture docker-m6-top30-provenance-original-probe docker-m6-top30-provenance-failed-probe docker-m6-top30-provenance-collect docker-m6-top30-provenance-audit docker-release-build docker-release-promote docker-release-rollback docker-release-start docker-release-guard docker-early-release-guard docker-release-status docker-scheduler-up docker-scheduler-status docker-scheduler-logs docker-scheduler-down docker-web-control-init docker-web-control-build docker-web-control-status docker-web-control-logs docker-web-build docker-web-research-project docker-web-strategy-factory-project docker-web-security-names-project docker-web-up docker-web-status docker-web-logs docker-web-down
.PHONY: docker-ts-v5-r3g3-build docker-ts-v5-r3g3-fixture docker-ts-v5-r3g3-run docker-ts-v5-r3g3-audit docker-ts-v6-build docker-ts-v6-fixture docker-ts-v6-profile docker-ts-v6-audit docker-ts-v6-1-build docker-ts-v6-1-fixture docker-ts-v6-1-profile docker-ts-v6-1-audit docker-ts-v6-3-build docker-ts-v6-3-fixture docker-ts-v6-3-preflight docker-ts-v6-3-run docker-ts-v6-3-audit docker-ts-v6-4-build docker-ts-v6-4-fixture docker-ts-v6-4-preflight docker-ts-v6-4-run docker-ts-v6-4-audit
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
architecture-check: ## 架构宪法：模块棘轮、依赖方向和入口绑定
	$(PYTHON) -m pytest -q tests/test_architecture_constitution.py tests/test_codebase_consolidation_policy.py tests/test_web_modularity.py

docker-ts-v5-r3g3-build: ## 构建断网R3G-3发现期失败诊断镜像
	SHAIWEI_TS_R3G3_DIAGNOSTIC_GIT_HEAD="$$(git rev-parse HEAD)" docker compose -f compose.ts-v5-r3g3-diagnostic.yaml --profile ts-v5-r3g3-diagnostic-fixture build ts-v5-r3g3-diagnostic-fixture

docker-ts-v5-r3g3-fixture: ## 运行R3G-3纯合成合同与诊断测试
	docker compose -f compose.ts-v5-r3g3-diagnostic.yaml --profile ts-v5-r3g3-diagnostic-fixture run --rm --no-deps ts-v5-r3g3-diagnostic-fixture

docker-ts-v5-r3g3-run: ## 唯一一次只读封存发现期诊断
	docker compose -f compose.ts-v5-r3g3-diagnostic.yaml --profile ts-v5-r3g3-diagnostic run --rm --no-deps ts-v5-r3g3-diagnostic-runner

docker-ts-v5-r3g3-audit: ## 独立复核R3G-3聚合诊断
	docker compose -f compose.ts-v5-r3g3-diagnostic.yaml --profile ts-v5-r3g3-diagnostic run --rm --no-deps ts-v5-r3g3-diagnostic-auditor

docker-ts-v6-build: ## 从已推送提交断网构建TS-v6零效果预检镜像
	@test -n "$(TS_V6_RELEASE_GIT_HEAD)" || (echo "TS_V6_RELEASE_GIT_HEAD is required"; exit 2)
	@test "$(TS_V6_RELEASE_GIT_HEAD)" = "$$(git rev-parse HEAD)" || (echo "TS-v6 release Git differs from HEAD"; exit 2)
	@test "$(TS_V6_RELEASE_GIT_HEAD)" = "$$(git rev-parse origin/main)" || (echo "TS-v6 release Git differs from origin/main"; exit 2)
	SHAIWEI_TS_V6_RELEASE_GIT_HEAD="$(TS_V6_RELEASE_GIT_HEAD)" docker compose -f compose.ts-v6-entry-quality.yaml --profile ts-v6-fixture build ts-v6-entry-quality-fixture

docker-ts-v6-fixture: ## 真实入口前断网运行合成CLI、分位、L9、子集与审计契约
	docker compose -f compose.ts-v6-entry-quality.yaml --profile ts-v6-fixture run --rm --no-deps ts-v6-entry-quality-fixture

docker-ts-v6-profile: ## 唯一一次读取结果盲真实特征与事件密度
	mkdir -p data/research/trend_swing/ts-v6-entry-quality-preflight-v1
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.ts-v6-entry-quality.yaml --profile ts-v6-live run --rm --no-deps ts-v6-entry-quality-profile

docker-ts-v6-audit: ## 独立复核TS-v6分位、九点、选择与条件密度
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.ts-v6-entry-quality.yaml --profile ts-v6-live run --rm --no-deps ts-v6-entry-quality-auditor

docker-ts-v6-1-build: ## 从已推送提交断网构建TS-v6-1排序预检镜像
	@test -n "$(TS_V6_1_RELEASE_GIT_HEAD)" || (echo "TS_V6_1_RELEASE_GIT_HEAD is required"; exit 2)
	@test "$(TS_V6_1_RELEASE_GIT_HEAD)" = "$$(git rev-parse HEAD)" || (echo "TS-v6-1 release Git differs from HEAD"; exit 2)
	@test "$(TS_V6_1_RELEASE_GIT_HEAD)" = "$$(git rev-parse origin/main)" || (echo "TS-v6-1 release Git differs from origin/main"; exit 2)
	SHAIWEI_TS_V6_1_RELEASE_GIT_HEAD="$(TS_V6_1_RELEASE_GIT_HEAD)" docker compose -f compose.ts-v6-1-ranking.yaml --profile ts-v6-1-fixture build ts-v6-1-ranking-fixture

docker-ts-v6-1-fixture: ## 真实入口前断网运行合成CLI、分位、排序与门禁契约
	docker compose -f compose.ts-v6-1-ranking.yaml --profile ts-v6-1-fixture run --rm --no-deps ts-v6-1-ranking-fixture

docker-ts-v6-1-profile: ## 唯一一次读取冻结观察并做排序密度画像
	mkdir -p data/research/trend_swing/ts-v6-1-entry-quality-ranking-preflight-v1
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.ts-v6-1-ranking.yaml --profile ts-v6-1-live run --rm --no-deps ts-v6-1-ranking-profile

docker-ts-v6-1-audit: ## 独立复核TS-v6-1分数、排序、Top-K与条件密度
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.ts-v6-1-ranking.yaml --profile ts-v6-1-live run --rm --no-deps ts-v6-1-ranking-auditor

docker-ts-v6-3-build: ## 从已推送提交断网构建TS-v6-3效果执行镜像
	@test -n "$(TS_V6_3_RELEASE_GIT_HEAD)" || (echo "TS_V6_3_RELEASE_GIT_HEAD is required"; exit 2)
	@test "$(TS_V6_3_RELEASE_GIT_HEAD)" = "$$(git rev-parse HEAD)" || (echo "TS-v6-3 release Git differs from HEAD"; exit 2)
	@test "$(TS_V6_3_RELEASE_GIT_HEAD)" = "$$(git rev-parse origin/main)" || (echo "TS-v6-3 release Git differs from origin/main"; exit 2)
	SHAIWEI_TS_V6_3_RELEASE_GIT_HEAD="$(TS_V6_3_RELEASE_GIT_HEAD)" docker compose -f compose.ts-v6-3-ranked-subset.yaml --profile ts-v6-3-fixture build ts-v6-3-effect-fixture

docker-ts-v6-3-fixture: ## 真实读取前断网运行合成fixture与合同测试
	docker compose -f compose.ts-v6-3-ranked-subset.yaml --profile ts-v6-3-fixture run --rm --no-deps ts-v6-3-effect-fixture

docker-ts-v6-3-preflight: ## 只读事件键与分数覆盖（不读收益）
	mkdir -p data/research/trend_swing/ts-v6-3-ranked-subset-effect-v1
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.ts-v6-3-ranked-subset.yaml --profile ts-v6-3-live run --rm --no-deps ts-v6-3-effect-preflight

docker-ts-v6-3-run: ## 唯一一次发现期效果读取（含确定性复算）
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.ts-v6-3-ranked-subset.yaml --profile ts-v6-3-live run --rm --no-deps ts-v6-3-effect-runner

docker-ts-v6-3-audit: ## 独立复核TS-v6-3汇总、门禁与裁决
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.ts-v6-3-ranked-subset.yaml --profile ts-v6-3-live run --rm --no-deps ts-v6-3-effect-auditor

docker-ts-v6-4-build: ## 从已推送提交断网构建TS-v6-4效果执行镜像
	@test -n "$(TS_V6_4_RELEASE_GIT_HEAD)" || (echo "TS_V6_4_RELEASE_GIT_HEAD is required"; exit 2)
	@test "$(TS_V6_4_RELEASE_GIT_HEAD)" = "$$(git rev-parse HEAD)" || (echo "TS-v6-4 release Git differs from HEAD"; exit 2)
	@test "$(TS_V6_4_RELEASE_GIT_HEAD)" = "$$(git rev-parse origin/main)" || (echo "TS-v6-4 release Git differs from origin/main"; exit 2)
	SHAIWEI_TS_V6_4_RELEASE_GIT_HEAD="$(TS_V6_4_RELEASE_GIT_HEAD)" docker compose -f compose.ts-v6-4-no-takeprofit.yaml --profile ts-v6-4-fixture build ts-v6-4-effect-fixture

docker-ts-v6-4-fixture: ## 真实读取前断网运行合成fixture与合同测试
	docker compose -f compose.ts-v6-4-no-takeprofit.yaml --profile ts-v6-4-fixture run --rm --no-deps ts-v6-4-effect-fixture

docker-ts-v6-4-preflight: ## 只读事件键与分数覆盖（不读收益）
	mkdir -p data/research/trend_swing/ts-v6-4-no-takeprofit-effect-v1
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.ts-v6-4-no-takeprofit.yaml --profile ts-v6-4-live run --rm --no-deps ts-v6-4-effect-preflight

docker-ts-v6-4-run: ## 唯一一次发现期效果读取（含确定性复算）
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.ts-v6-4-no-takeprofit.yaml --profile ts-v6-4-live run --rm --no-deps ts-v6-4-effect-runner

docker-ts-v6-4-audit: ## 独立复核TS-v6-4汇总、门禁与裁决
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.ts-v6-4-no-takeprofit.yaml --profile ts-v6-4-live run --rm --no-deps ts-v6-4-effect-auditor
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
ts-v3-data-gate:  ## TS-1A 唯一一次断网结果盲数据画像与独立审计
	$(PYTHON) -m shaiwei.research.trend_swing
ts-v3-recovery-release: ## 实现推送后冻结R3精确release scope；不读取密钥或联网
	$(PYTHON) -m shaiwei.research.trend_swing.recovery_release
ts-v3-recovery-network: ## TS-1A-R2 精确授权后两次指数补采；调用前必须有冻结release
	$(PYTHON) -m shaiwei.research.trend_swing.recovery_cli network
ts-v3-recovery-profile: ## 两批补采完成后唯一一次断网匿名候选画像
	$(PYTHON) -m shaiwei.research.trend_swing.recovery_cli profile
ts-v3-recovery-audit: ## 独立复核R2匿名日报、manifest和结果防火墙
	$(PYTHON) -m shaiwei.research.trend_swing.recovery_cli audit

ts-v5-llm-preflight:
	$(PYTHON) -m shaiwei.research.trend_swing.v5_live --release config/ts_v5_llm_execution_release_v2.yaml --preflight-only

ts-v5-llm-audit:
	$(PYTHON) -m shaiwei.research.trend_swing.v5_audit --release config/ts_v5_llm_execution_release_v2.yaml

ts-v5-r2-preflight:
	$(PYTHON) -m shaiwei.research.trend_swing.v5_r2_live --release config/ts_v5_r2_llm_execution_release_v1.yaml --preflight-only

ts-v5-r2-audit:
	$(PYTHON) -m shaiwei.research.trend_swing.v5_r2_audit --release config/ts_v5_r2_llm_execution_release_v1.yaml

ts-v5-r3c-preflight:
	$(PYTHON) -m shaiwei.research.trend_swing.v5_r3c_live --release config/ts_v5_r3c_llm_execution_release_v1.yaml --preflight-only

ts-v5-r3c-audit:
	$(PYTHON) -m shaiwei.research.trend_swing.v5_r3c_result_audit --release config/ts_v5_r3c_llm_execution_release_v1.yaml

ts-v5-r3f-preflight:
	$(PYTHON) -m shaiwei.research.trend_swing.v5_r3f_live --release config/ts_v5_r3f_llm_execution_release_v1.yaml --preflight-only

ts-v5-r3f-audit:
	$(PYTHON) -m shaiwei.research.trend_swing.v5_r3f_result_audit --release config/ts_v5_r3f_llm_execution_release_v1.yaml

docker-ts-v5-llm-build:
	@test -n "$(TS_V5_LLM_RELEASE_GIT_HEAD)" || (echo "TS_V5_LLM_RELEASE_GIT_HEAD is required"; exit 2)
	docker build -f Dockerfile.ts-v5-llm --build-arg SHAIWEI_RELEASE_GIT_HEAD="$(TS_V5_LLM_RELEASE_GIT_HEAD)" -t shaiwei:ts-v5-llm-batch-001 .

docker-ts-v5-llm-run:
	docker compose -f compose.ts-v5-llm.yaml --profile ts-v5-llm run --rm --no-deps ts-v5-llm

docker-ts-v5-llm-audit:
	docker compose -f compose.ts-v5-llm.yaml --profile ts-v5-llm-audit run --rm --no-deps ts-v5-llm-audit

docker-ts-v5-r2-build:
	@test -n "$(TS_V5_R2_RELEASE_GIT_HEAD)" || (echo "TS_V5_R2_RELEASE_GIT_HEAD is required"; exit 2)
	docker build -f Dockerfile.ts-v5-llm --build-arg SHAIWEI_RELEASE_GIT_HEAD="$(TS_V5_R2_RELEASE_GIT_HEAD)" -t shaiwei:ts-v5-r2-canary-001 .

docker-ts-v5-r2-run:
	docker compose -f compose.ts-v5-r2.yaml --profile ts-v5-r2 run --rm --no-deps ts-v5-r2

docker-ts-v5-r2-audit:
	docker compose -f compose.ts-v5-r2.yaml --profile ts-v5-r2-audit run --rm --no-deps ts-v5-r2-audit

docker-ts-v5-r3c-build:
	@test -n "$(TS_V5_R3C_RELEASE_GIT_HEAD)" || (echo "TS_V5_R3C_RELEASE_GIT_HEAD is required"; exit 2)
	docker build -f Dockerfile.ts-v5-llm --build-arg SHAIWEI_RELEASE_GIT_HEAD="$(TS_V5_R3C_RELEASE_GIT_HEAD)" -t shaiwei:ts-v5-r3c-canary-001 .

docker-ts-v5-r3c-run:
	docker compose -f compose.ts-v5-r3c.yaml --profile ts-v5-r3c run --rm --no-deps ts-v5-r3c

docker-ts-v5-r3c-audit:
	docker compose -f compose.ts-v5-r3c.yaml --profile ts-v5-r3c-audit run --rm --no-deps ts-v5-r3c-audit

docker-ts-v5-r3f-build:
	@test -n "$(TS_V5_R3F_RELEASE_GIT_HEAD)" || (echo "TS_V5_R3F_RELEASE_GIT_HEAD is required"; exit 2)
	docker build -f Dockerfile.ts-v5-llm --build-arg SHAIWEI_RELEASE_GIT_HEAD="$(TS_V5_R3F_RELEASE_GIT_HEAD)" -t shaiwei:ts-v5-r3f-canary-001 .

docker-ts-v5-r3f-run:
	docker compose -f compose.ts-v5-r3f.yaml --profile ts-v5-r3f run --rm --no-deps ts-v5-r3f

docker-ts-v5-r3f-audit:
	docker compose -f compose.ts-v5-r3f.yaml --profile ts-v5-r3f-audit run --rm --no-deps ts-v5-r3f-audit

docker-ts-v5-r3g-build:
	@test -n "$(TS_V5_R3G_RELEASE_GIT_HEAD)" || (echo "TS_V5_R3G_RELEASE_GIT_HEAD is required"; exit 2)
	docker build --network=none -f Dockerfile.ts-v5-r3g --build-arg SHAIWEI_RELEASE_GIT_HEAD="$(TS_V5_R3G_RELEASE_GIT_HEAD)" -t shaiwei:ts-v5-r3g-engineering-001 .

docker-ts-v5-r3g-run:
	docker compose -f compose.ts-v5-r3g.yaml --profile ts-v5-r3g run --rm --no-deps ts-v5-r3g

docker-ts-v5-r3g-audit:
	docker compose -f compose.ts-v5-r3g.yaml --profile ts-v5-r3g-audit run --rm --no-deps ts-v5-r3g-audit

docker-ts-v5-r3g1-build:
	@test -n "$(TS_V5_R3G1_RELEASE_GIT_HEAD)" || (echo "TS_V5_R3G1_RELEASE_GIT_HEAD is required"; exit 2)
	@test "$(TS_V5_R3G1_RELEASE_GIT_HEAD)" = "$$(git rev-parse HEAD)" || (echo "TS_V5_R3G1_RELEASE_GIT_HEAD differs from HEAD"; exit 2)
	@test "$(TS_V5_R3G1_RELEASE_GIT_HEAD)" = "$$(git rev-parse origin/main)" || (echo "TS_V5_R3G1_RELEASE_GIT_HEAD differs from origin/main"; exit 2)
	docker build --network=none -f Dockerfile.ts-v5-r3g1 --build-arg SHAIWEI_RELEASE_GIT_HEAD="$(TS_V5_R3G1_RELEASE_GIT_HEAD)" -t shaiwei:ts-v5-r3g1-recent-density-r2 .

docker-ts-v5-r3g1-profile:
	mkdir -p data/research/trend_swing/ts-v5-r3g1-recent-density-r2
	docker compose -f compose.ts-v5-r3g1.yaml --profile ts-v5-r3g1 run --rm --no-deps ts-v5-r3g1-profile

docker-ts-v5-r3g1-audit:
	docker compose -f compose.ts-v5-r3g1.yaml --profile ts-v5-r3g1-audit run --rm --no-deps ts-v5-r3g1-audit

.PHONY: docker-ts-v5-r3g2-w7-build docker-ts-v5-r3g2-w7-fixture docker-ts-v5-r3g2-w7-run docker-ts-v5-r3g2-w7-audit
docker-ts-v5-r3g2-w7-build: ## 以已推送实现构建W7断网谱系镜像，不训练或读取效果
	@test -n "$(TS_V5_R3G2_W7_RELEASE_GIT_HEAD)" || (echo "TS_V5_R3G2_W7_RELEASE_GIT_HEAD is required"; exit 2)
	@test "$(TS_V5_R3G2_W7_RELEASE_GIT_HEAD)" = "$$(git rev-parse HEAD)" || (echo "W7 release Git differs from HEAD"; exit 2)
	@test "$(TS_V5_R3G2_W7_RELEASE_GIT_HEAD)" = "$$(git rev-parse origin/main)" || (echo "W7 release Git differs from origin/main"; exit 2)
	SHAIWEI_TS_R3G2_W7_RELEASE_GIT_HEAD="$(TS_V5_R3G2_W7_RELEASE_GIT_HEAD)" docker compose -f compose.ts-v5-r3g2-w7.yaml --profile w7-fixture build ts-v5-r3g2-w7-fixture

docker-ts-v5-r3g2-w7-fixture: ## 最终W7镜像内断网运行合成双跑与独立审计
	docker compose -f compose.ts-v5-r3g2-w7.yaml --profile w7-fixture run --rm --no-deps ts-v5-r3g2-w7-fixture

docker-ts-v5-r3g2-w7-run: ## 精确scope获批后唯一一次W7训练与分数双跑，效果尝试仍为0
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.ts-v5-r3g2-w7.yaml --profile w7-live run --rm --no-deps ts-v5-r3g2-w7-runner

docker-ts-v5-r3g2-w7-audit: ## 无Qlib挂载的独立进程复核W7谱系
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.ts-v5-r3g2-w7.yaml --profile w7-live run --rm --no-deps ts-v5-r3g2-w7-auditor

.PHONY: docker-ts-v5-r3g2-w7-recovery-build docker-ts-v5-r3g2-w7-recovery-fixture docker-ts-v5-r3g2-w7-recovery-run docker-ts-v5-r3g2-w7-recovery-audit
docker-ts-v5-r3g2-w7-recovery-build: ## 以已推送修复构建W7入口恢复镜像，不读取真实W7
	@test -n "$(TS_V5_R3G2_W7_RECOVERY_GIT_HEAD)" || (echo "TS_V5_R3G2_W7_RECOVERY_GIT_HEAD is required"; exit 2)
	@test "$(TS_V5_R3G2_W7_RECOVERY_GIT_HEAD)" = "$$(git rev-parse HEAD)" || (echo "W7 recovery Git differs from HEAD"; exit 2)
	@test "$(TS_V5_R3G2_W7_RECOVERY_GIT_HEAD)" = "$$(git rev-parse origin/main)" || (echo "W7 recovery Git differs from origin/main"; exit 2)
	SHAIWEI_TS_R3G2_W7_RECOVERY_GIT_HEAD="$(TS_V5_R3G2_W7_RECOVERY_GIT_HEAD)" docker compose -f compose.ts-v5-r3g2-w7-recovery.yaml --profile w7-recovery-fixture build ts-v5-r3g2-w7-recovery-fixture

docker-ts-v5-r3g2-w7-recovery-fixture: ## 恢复镜像内断网运行合成双跑、CLI与独立审计测试
	docker compose -f compose.ts-v5-r3g2-w7-recovery.yaml --profile w7-recovery-fixture run --rm --no-deps ts-v5-r3g2-w7-recovery-fixture

docker-ts-v5-r3g2-w7-recovery-run: ## 新recovery scope获批后唯一一次W7分数谱系恢复
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.ts-v5-r3g2-w7-recovery.yaml --profile w7-recovery-live run --rm --no-deps ts-v5-r3g2-w7-recovery-runner

docker-ts-v5-r3g2-w7-recovery-audit: ## 无Qlib挂载的独立进程复核恢复W7谱系
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.ts-v5-r3g2-w7-recovery.yaml --profile w7-recovery-live run --rm --no-deps ts-v5-r3g2-w7-recovery-auditor

docker-ts-recovery-build: ## 以已推送实现身份构建R3短命研究镜像
	@test -n "$(TS_RECOVERY_RELEASE_GIT_HEAD)" || (echo "TS_RECOVERY_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_TS_RECOVERY_RELEASE_GIT_HEAD="$(TS_RECOVERY_RELEASE_GIT_HEAD)" docker compose -f compose.ts-recovery.yaml --profile ts-recovery-network build ts-recovery-network
docker-ts-recovery-network: ## 精确授权后运行三次指数补采；只挂raw、ingest ledger和本scope
	docker compose -f compose.ts-recovery.yaml --profile ts-recovery-network run --rm --no-deps ts-recovery-network
docker-ts-recovery-profile: ## 三批提交后断网运行唯一匿名画像
	docker compose -f compose.ts-recovery.yaml --profile ts-recovery-offline run --rm --no-deps ts-recovery-profile
docker-ts-recovery-audit: ## 断网独立审计R3报告和匿名产物
	docker compose -f compose.ts-recovery.yaml --profile ts-recovery-offline run --rm --no-deps ts-recovery-auditor
docker-ts-r4-build: ## 以已推送实现身份构建R4结果盲短命镜像
	@test -n "$(TS_R4_RELEASE_GIT_HEAD)" || (echo "TS_R4_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_TS_R4_RELEASE_GIT_HEAD="$(TS_R4_RELEASE_GIT_HEAD)" docker compose -f compose.ts-recovery.yaml --profile ts-r4-offline build ts-r4-profile
docker-ts-r4-profile: ## 唯一一次断网回调状态匿名画像，禁止结果与分数值
	docker compose -f compose.ts-recovery.yaml --profile ts-r4-offline run --rm --no-deps ts-r4-profile
docker-ts-r4-audit: ## 独立复算R4匿名事件计数与结果防火墙
	docker compose -f compose.ts-recovery.yaml --profile ts-r4-offline run --rm --no-deps ts-r4-auditor
docker-ts-v4-density-build: ## 以已推送实现身份构建v4B结果盲密度镜像
	@test -n "$(TS_V4_DENSITY_RELEASE_GIT_HEAD)" || (echo "TS_V4_DENSITY_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_TS_R3_APPROVAL_SCOPE_SHA256=offline-not-used SHAIWEI_TS_V4_DENSITY_RELEASE_GIT_HEAD="$(TS_V4_DENSITY_RELEASE_GIT_HEAD)" docker compose -f compose.ts-recovery.yaml --profile ts-v4-density-offline build ts-v4-density-profile
docker-ts-v4-density-profile: ## 唯一一次断网四臂发现期密度画像，禁止收益与分数值
	mkdir -p data/research/trend_swing/ts-v4-density-preflight-r1
	SHAIWEI_TS_R3_APPROVAL_SCOPE_SHA256=offline-not-used docker compose -f compose.ts-recovery.yaml --profile ts-v4-density-offline run --rm --no-deps ts-v4-density-profile
docker-ts-v4-density-audit: ## 独立复算v4B四臂事件密度和结果防火墙
	SHAIWEI_TS_R3_APPROVAL_SCOPE_SHA256=offline-not-used docker compose -f compose.ts-recovery.yaml --profile ts-v4-density-offline run --rm --no-deps ts-v4-density-auditor
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
docker-d1-semantic-verify: ## D1语义门断网只读复核；零provider调用、不改旧批
	docker compose -f compose.research.yaml --profile research-semantic-verify run --rm d1-semantic-verify
docker-m1-star50-build: ## 以已提交身份构建M1-1一次性研究镜像
	@test -n "$(M1_RELEASE_GIT_HEAD)" || (echo "M1_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_M1_RELEASE_GIT_HEAD="$(M1_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile m1-star50-preflight build m1-star50-preflight
docker-m1-star50-preflight: ## 断网只读核对科创50发现输入；零候选结果、零provider调用
	docker compose -f compose.research.yaml --profile m1-star50-preflight run --rm --no-deps m1-star50-preflight
docker-m1-star50-live: ## M1-1受控40次生成；须先推送执行release并显式导出唯一DeepSeek secret
	docker compose -f compose.research.yaml --profile m1-star50-live run --rm --no-deps m1-star50-live
docker-m1-star50-review-build: ## 以已提交身份构建M1-2一次性盲审镜像
	@test -n "$(M1_REVIEW_RELEASE_GIT_HEAD)" || (echo "M1_REVIEW_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_M1_REVIEW_RELEASE_GIT_HEAD="$(M1_REVIEW_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile m1-star50-review-preflight build m1-star50-review-preflight
docker-m1-star50-review-preflight: ## 断网核对Top2/提示/语义门；零provider调用、零封存结果
	docker compose -f compose.research.yaml --profile m1-star50-review-preflight run --rm --no-deps m1-star50-review-preflight
docker-m1-star50-review-live: ## M1-2最多8次结果盲对抗复核；须先冻结并推送执行release
	docker compose -f compose.research.yaml --profile m1-star50-review-live run --rm --no-deps m1-star50-review-live
docker-m3-multi-pool-build: ## 以已提交身份构建M3-1断网三池预执行镜像
	@test -n "$(M3_RELEASE_GIT_HEAD)" || (echo "M3_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_M3_RELEASE_GIT_HEAD="$(M3_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile m3-multi-pool-preflight build m3-multi-pool-preflight
docker-m3-multi-pool-preflight: ## 断网只读核对M3三池真身与纯fixture；零候选结果、零provider调用
	docker compose -f compose.research.yaml --profile m3-multi-pool-preflight run --rm --no-deps m3-multi-pool-preflight
docker-m3-multi-pool-live-build: ## 以结果前提交身份构建M3-2一次性研究镜像
	@test -n "$(M3_LIVE_RELEASE_GIT_HEAD)" || (echo "M3_LIVE_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_M3_LIVE_RELEASE_GIT_HEAD="$(M3_LIVE_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile m3-multi-pool-live-preflight build m3-multi-pool-live-preflight
docker-m3-multi-pool-live-preflight: ## 断网只读核对M3-2复权行情、PIT暴露与release；零候选结果
	docker compose -f compose.research.yaml --profile m3-multi-pool-live-preflight run --rm --no-deps m3-multi-pool-live-preflight
docker-m3-multi-pool-live: ## M3-2受控24次生成；须先推送release并显式导出唯一DeepSeek secret
	docker compose -f compose.research.yaml --profile m3-multi-pool-live run --rm --no-deps m3-multi-pool-live
docker-m3-multi-pool-review-build: ## 以已提交身份构建M3-3断网盲审预执行镜像
	@test -n "$(M3_REVIEW_RELEASE_GIT_HEAD)" || (echo "M3_REVIEW_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_M3_REVIEW_RELEASE_GIT_HEAD="$(M3_REVIEW_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile m3-multi-pool-review-preflight build m3-multi-pool-review-preflight
docker-m3-multi-pool-review-preflight: ## 断网核对固定Top2、8请求和语义门；零secret、零provider调用
	docker compose -f compose.research.yaml --profile m3-multi-pool-review-preflight run --rm --no-deps m3-multi-pool-review-preflight
docker-m3-multi-pool-review-live-build: ## 以已提交实现身份构建M3-3受控8审查镜像
	@test -n "$(M3_REVIEW_LIVE_RELEASE_GIT_HEAD)" || (echo "M3_REVIEW_LIVE_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_M3_REVIEW_LIVE_RELEASE_GIT_HEAD="$(M3_REVIEW_LIVE_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile m3-multi-pool-review-live-preflight build m3-multi-pool-review-live-preflight
docker-m3-multi-pool-review-live-preflight: ## 断网核对用户授权、镜像、空账本和8请求；零secret、零provider调用
	docker compose -f compose.research.yaml --profile m3-multi-pool-review-live-preflight run --rm --no-deps m3-multi-pool-review-live-preflight
docker-m3-multi-pool-review-live: ## 串行执行恰好8份结果盲审查；只窄传项目.env中的DeepSeek secret
	docker compose --env-file .env -f compose.research.yaml --profile m3-multi-pool-review-live run --rm --no-deps m3-multi-pool-review-live
docker-m3-multi-pool-review-verify: ## 断网只读复核M3-3终态证据和幂等；零secret、零provider调用
	docker compose -f compose.research.yaml --profile m3-multi-pool-review-verify run --rm --no-deps m3-multi-pool-review-verify
docker-llm-review-contract-v2: ## 断网验证紧凑审查合同v2；零secret、零真实候选、零provider调用
	docker compose -f compose.research.yaml --profile llm-review-contract-v2 run --rm --no-deps llm-review-contract-v2
docker-f1-fundamental-pit-build: ## 构建F1-0断网基本面PIT数据门镜像
	@test -n "$(F1_RELEASE_GIT_HEAD)" || (echo "F1_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_F1_RELEASE_GIT_HEAD="$(F1_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile f1-fundamental-pit build f1-fundamental-pit
docker-f1-fundamental-pit: ## 断网读取本地不可变三表并构建F1-0数据/特征门
	docker compose -f compose.research.yaml --profile f1-fundamental-pit run --rm --no-deps f1-fundamental-pit
docker-f1-fundamental-pit-recovery-build: ## 构建F1-0R最新共同报告期恢复镜像
	@test -n "$(F1_RECOVERY_RELEASE_GIT_HEAD)" || (echo "F1_RECOVERY_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_F1_RECOVERY_RELEASE_GIT_HEAD="$(F1_RECOVERY_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile f1-fundamental-pit-recovery build f1-fundamental-pit-recovery
docker-f1-fundamental-pit-recovery: ## 断网复验F1-0R最新共同报告期数据门
	docker compose -f compose.research.yaml --profile f1-fundamental-pit-recovery run --rm --no-deps f1-fundamental-pit-recovery
docker-f2-fundamental-dynamics-build: ## 以结果前提交身份构建F2-0断网基本面动态数据门镜像
	@test -n "$(F2_RELEASE_GIT_HEAD)" || (echo "F2_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_F2_RELEASE_GIT_HEAD="$(F2_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile f2-fundamental-dynamics build f2-fundamental-dynamics
docker-f2-fundamental-dynamics: ## 断网构建连续年度基本面动态特征并运行数据门
	docker compose -f compose.research.yaml --profile f2-fundamental-dynamics run --rm --no-deps f2-fundamental-dynamics
docker-f2-fundamental-dynamics-recovery-build: ## 以结果前提交身份构建F2-0R恢复门镜像
	@test -n "$(F2_RECOVERY_RELEASE_GIT_HEAD)" || (echo "F2_RECOVERY_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_F2_RECOVERY_RELEASE_GIT_HEAD="$(F2_RECOVERY_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile f2-fundamental-dynamics-recovery build f2-fundamental-dynamics-recovery
docker-f2-fundamental-dynamics-recovery: ## 断网运行合法不可估计空值恢复门
	docker compose -f compose.research.yaml --profile f2-fundamental-dynamics-recovery run --rm --no-deps f2-fundamental-dynamics-recovery
docker-f1-fundamental-effect-build: ## 以结果前提交身份构建F1-1断网效果门镜像
	@test -n "$(F1_EFFECT_RELEASE_GIT_HEAD)" || (echo "F1_EFFECT_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_F1_EFFECT_RELEASE_GIT_HEAD="$(F1_EFFECT_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile f1-fundamental-effect build f1-fundamental-effect
docker-f1-fundamental-effect-residual: ## 断网构建无标签/收益的F1-1 core与incremental残差
	docker compose -f compose.research.yaml --profile f1-fundamental-effect run --rm --no-deps f1-fundamental-effect
docker-f1-fundamental-effect: ## 断网串行运行固定方向、六窗、成本与G1效果门
	docker compose -f compose.research.yaml --profile f1-fundamental-effect run --rm --no-deps f1-fundamental-effect python -m shaiwei.research.fundamental_effect --protocol /workspace/config/f1_csi800_fundamental_effect_v1.yaml --stage effect
docker-f2-fundamental-effect-build: ## 以结果前提交身份构建F2-1断网基本面动态效果门镜像
	@test -n "$(F2_EFFECT_RELEASE_GIT_HEAD)" || (echo "F2_EFFECT_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_F2_EFFECT_RELEASE_GIT_HEAD="$(F2_EFFECT_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile f2-fundamental-effect build f2-fundamental-effect
docker-f2-fundamental-effect-residual: ## 断网构建无标签/收益的F2-1 core与incremental残差
	docker compose -f compose.research.yaml --profile f2-fundamental-effect run --rm --no-deps f2-fundamental-effect
docker-f2-fundamental-effect: ## 断网串行运行F2固定方向、六窗、成本与累计N=12的G1
	docker compose -f compose.research.yaml --profile f2-fundamental-effect run --rm --no-deps f2-fundamental-effect python -m shaiwei.research.fundamental_dynamics_effect --protocol /workspace/config/f2_csi800_fundamental_effect_v1.yaml --stage effect
docker-m4-star50-effect-build: ## 以已提交实现构建M4-1断网效果镜像
	@test -n "$(M4_EFFECT_RELEASE_GIT_HEAD)" || (echo "M4_EFFECT_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_M4_EFFECT_RELEASE_GIT_HEAD="$(M4_EFFECT_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile m4-star50-residual-effect build m4-star50-residual-effect
docker-m4-star50-effect: ## release推送后断网执行M4-1首遍与确定性复跑
	docker compose -f compose.research.yaml --profile m4-star50-residual-effect run --rm --no-deps m4-star50-residual-effect
docker-m4-star50-effect-audit: ## 断网只读复核M4-1不可变产物与裁决
	docker compose -f compose.research.yaml --profile m4-star50-residual-effect run --rm --no-deps m4-star50-residual-effect python -m shaiwei.research.star50_residual_effect.audit --protocol /workspace/config/m4_star50_residual_effect_v1.yaml
docker-m4-star50-closure-build: ## 以已提交实现构建M4-1R2断网证据闭环镜像
	@test -n "$(M4_EFFECT_CLOSURE_RELEASE_GIT_HEAD)" || (echo "M4_EFFECT_CLOSURE_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_M4_EFFECT_CLOSURE_RELEASE_GIT_HEAD="$(M4_EFFECT_CLOSURE_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile m4-star50-residual-effect-closure build m4-star50-residual-effect-closure
docker-m4-star50-closure: ## 仅复用M4-1封存报告并补齐账本、manifest与独立审计
	docker compose -f compose.research.yaml --profile m4-star50-residual-effect-closure run --rm --no-deps m4-star50-residual-effect-closure
docker-m4-star50-closure-audit: ## 断网只读复核M4-1R2闭环后的全部证据
	docker compose -f compose.research.yaml --profile m4-star50-residual-effect-closure run --rm --no-deps m4-star50-residual-effect-closure python -m shaiwei.research.star50_residual_effect.audit --protocol /workspace/config/m4_star50_residual_effect_v1.yaml
docker-g8-primary-build: ## 以已提交代码身份构建 G8-1 无凭据一次性采集镜像
	@test -n "$(G8_RELEASE_GIT_HEAD)" || (echo "G8_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_G8_RELEASE_GIT_HEAD="$(G8_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile g8-primary-capture-live build g8-primary-capture
docker-g8-primary-capture: ## 串行双取监管 HTTP 原文；不读 .env、不运行 G8、不接 scheduler
	docker compose -f compose.research.yaml --profile g8-primary-capture-live run --rm --no-deps g8-primary-capture
docker-g8-primary-verify: ## 断网重算 G8-1 账本/证据包哈希与验收计数
	docker compose -f compose.research.yaml --profile g8-primary-capture-live run --rm --no-deps g8-primary-capture python -m shaiwei.ingest.g8_fund_evidence --protocol /workspace/config/g8_fund_primary_capture_v1.yaml --verify-only
docker-m5-data-gate-build: ## 构建M5-2B最小断网数据门镜像，不启动任何常驻服务
	docker compose -f compose.m5-gates.yaml --profile m5-gates-fixture build m5-fixture
docker-m5-data-gate-fixture: ## 只运行完全合成数据、独立审计和临时registry
	docker compose -f compose.m5-gates.yaml --profile m5-gates-fixture run --rm --no-deps m5-fixture

docker-m5-lineage-build: ## 构建M5-2B-R2最小断网谱系镜像，不启动常驻服务
	docker compose -f compose.m5-lineage.yaml --profile m5-lineage-fixture build m5-lineage-fixture

docker-m5-lineage-fixture: ## 只运行纯合成谱系、独立审计、对抗用例和临时registry
	docker compose -f compose.m5-lineage.yaml --profile m5-lineage-fixture run --rm --no-deps m5-lineage-fixture
docker-m6-model-attribution-build: ## 以已推送实现构建M6-1结果盲断网工程镜像
	@test -n "$(M6_ENGINEERING_RELEASE_GIT_HEAD)" || (echo "M6_ENGINEERING_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_M6_ENGINEERING_RELEASE_GIT_HEAD="$(M6_ENGINEERING_RELEASE_GIT_HEAD)" docker compose -f compose.research.yaml --profile m6-model-attribution-engineering build m6-model-attribution-engineering
docker-m6-model-attribution-preflight: ## 只读manifest/交易日历并运行纯合成三臂归因工程门
	mkdir -p data/research/m6_csi800_model_attribution_v1/engineering
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.research.yaml --profile m6-model-attribution-engineering run --rm --no-deps m6-model-attribution-engineering
docker-m6-model-attribution-audit: ## 独立复算M6-1合成报告、Holm与五类唯一终态
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.research.yaml --profile m6-model-attribution-engineering run --rm --no-deps m6-model-attribution-engineering python -m shaiwei.research.model_attribution.audit --calendar-path /inputs/m6_frozen_calendar.txt --report /workspace/data/research/m6_csi800_model_attribution_v1/engineering/report.json --output /workspace/data/research/m6_csi800_model_attribution_v1/engineering/audit.json
docker-m6-effect-build: ## 以已推送实现构建M6-2一次性真实归因镜像；不运行真实效果
	@test -n "$(M6_EFFECT_RELEASE_GIT_HEAD)" || (echo "M6_EFFECT_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_M6_EFFECT_RELEASE_GIT_HEAD="$(M6_EFFECT_RELEASE_GIT_HEAD)" docker compose -f compose.m6-attribution.yaml --profile m6-effect build m6-effect-runner
docker-m6-effect-fixture: ## 在最终镜像内断网运行纯合成runner/auditor合同；不挂载Qlib
	docker run --rm --network none --read-only --user "$$(id -u):$$(id -g)" --tmpfs /tmp:rw,noexec,nosuid,size=2g -e HOME=/tmp -e MPLCONFIGDIR=/tmp/matplotlib shaiwei:m6-model-attribution-release-v1 python -m shaiwei.research.model_attribution.effect_fixture --output-root /tmp/m6-fixture
docker-m6-effect-run: ## 仅在完整scope获明确批准并写入精确approval后执行唯一真实runner
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-attribution.yaml --profile m6-effect run --rm --no-deps m6-effect-runner
docker-m6-effect-audit: ## 唯一runner成功后由无Qlib挂载的第二进程独立复核
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-attribution.yaml --profile m6-effect run --rm --no-deps m6-effect-auditor
docker-m6-audit-recovery-build: ## 构建已推送实现的M6 auditor-only薄恢复镜像；不读真实效果
	@test -n "$(M6_AUDIT_RECOVERY_GIT_HEAD)" || (echo "M6_AUDIT_RECOVERY_GIT_HEAD is required"; exit 2)
	SHAIWEI_M6_AUDIT_RECOVERY_GIT_HEAD="$(M6_AUDIT_RECOVERY_GIT_HEAD)" docker compose -f compose.m6-audit-recovery.yaml --profile m6-audit-recovery build m6-audit-recovery
docker-m6-audit-recovery-fixture: ## 在最终薄镜像内断网运行纯合成入口合同；不挂载真实effect
	docker run --rm --network none --read-only --user "$$(id -u):$$(id -g)" --tmpfs /tmp:rw,noexec,nosuid,size=1g shaiwei:m6-audit-entrypoint-recovery-v1 python /opt/shaiwei/m6-audit-recovery/entrypoint.py --self-test
docker-m6-audit-recovery-run: ## 仅在新scope精确获批后运行一次auditor-only恢复
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-audit-recovery.yaml --profile m6-audit-recovery run --rm --no-deps m6-audit-recovery
docker-m6-topk-conversion-build: ## 以已推送实现构建M6-3B纯合成组合转换镜像
	@test -n "$(M6_TOPK_ENGINEERING_GIT_HEAD)" || (echo "M6_TOPK_ENGINEERING_GIT_HEAD is required"; exit 2)
	SHAIWEI_M6_TOPK_ENGINEERING_GIT_HEAD="$(M6_TOPK_ENGINEERING_GIT_HEAD)" docker compose -f compose.m6-topk-conversion.yaml --profile m6-topk-conversion build m6-topk-conversion-fixture
docker-m6-topk-conversion-fixture: ## 断网运行Top20组合转换first-pass/replay合成工程门
	mkdir -p data/research/m6_csi800_topk20_conversion_v1/engineering/runner
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-topk-conversion.yaml --profile m6-topk-conversion run --rm --no-deps m6-topk-conversion-fixture
docker-m6-topk-conversion-audit: ## 第二个无Qlib进程独立复算M6-3B合成证据
	mkdir -p data/research/m6_csi800_topk20_conversion_v1/engineering/audit
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-topk-conversion.yaml --profile m6-topk-conversion run --rm --no-deps m6-topk-conversion-auditor
docker-m6-topk-effect-build: ## 以已推送实现构建M6-3C一次性真实Top20镜像；不运行真实效果
	@test -n "$(M6_TOPK_EFFECT_RELEASE_GIT_HEAD)" || (echo "M6_TOPK_EFFECT_RELEASE_GIT_HEAD is required"; exit 2)
	SHAIWEI_M6_TOPK_EFFECT_RELEASE_GIT_HEAD="$(M6_TOPK_EFFECT_RELEASE_GIT_HEAD)" docker compose -f compose.m6-topk-conversion-release.yaml --profile m6-topk-effect build m6-topk-effect-runner
docker-m6-topk-effect-fixture: ## 在最终镜像内断网运行纯合成release合同；不挂载Qlib或M6 effect
	docker run --rm --network none --read-only --user "$$(id -u):$$(id -g)" --tmpfs /tmp:rw,noexec,nosuid,size=2g shaiwei:m6-topk-conversion-release-v1 python -m shaiwei.research.topk_conversion.real_fixture --output-root /tmp/m6-topk-real-fixture
docker-m6-topk-effect-run: ## 仅在完整scope获明确批准后执行唯一真实Top20 runner
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-topk-conversion-release.yaml --profile m6-topk-effect run --rm --no-deps m6-topk-effect-runner
docker-m6-topk-effect-audit: ## 唯一runner成功后由无Qlib/旧effect挂载的第二进程独立复核
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-topk-conversion-release.yaml --profile m6-topk-effect run --rm --no-deps m6-topk-effect-auditor
docker-m6-top30-diagnostic-build: ## 构建原M6/失败M6-3C两套薄诊断镜像；不读取真实数据
	@test -n "$(M6_TOP30_DIAGNOSTIC_GIT_HEAD)" || (echo "M6_TOP30_DIAGNOSTIC_GIT_HEAD is required"; exit 2)
	SHAIWEI_M6_TOP30_DIAGNOSTIC_GIT_HEAD="$(M6_TOP30_DIAGNOSTIC_GIT_HEAD)" docker compose -f compose.m6-top30-diagnostic.yaml --profile m6-top30-diagnostic build m6-top30-diagnostic-original m6-top30-diagnostic-current
docker-m6-top30-diagnostic-fixture: ## 两套最终镜像断网运行纯合成分类fixture
	docker run --rm --network none --read-only --user "$$(id -u):$$(id -g)" --tmpfs /tmp:rw,noexec,nosuid,size=256m shaiwei:m6-top30-diagnostic-original-v1 python -m shaiwei.research.top30_diagnostic.fixture
	docker run --rm --network none --read-only --user "$$(id -u):$$(id -g)" --tmpfs /tmp:rw,noexec,nosuid,size=256m shaiwei:m6-top30-diagnostic-current-v1 python -m shaiwei.research.top30_diagnostic.fixture
docker-m6-top30-diagnostic-original: ## 仅在精确scope获批后运行一次原镜像Top30双跑诊断
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-diagnostic.yaml --profile m6-top30-diagnostic run --rm --no-deps m6-top30-diagnostic-original
docker-m6-top30-diagnostic-current: ## 原镜像lane成功后运行一次失败镜像两适配器Top30诊断
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-diagnostic.yaml --profile m6-top30-diagnostic run --rm --no-deps m6-top30-diagnostic-current
docker-m6-top30-diagnostic-audit: ## 两个runner成功后由无Qlib第二进程独立精确分类
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-diagnostic.yaml --profile m6-top30-diagnostic run --rm --no-deps m6-top30-diagnostic-auditor
docker-m6-top30-recovery-build: ## 构建R2两套薄恢复镜像；不读取真实数据
	@test -n "$(M6_TOP30_RECOVERY_GIT_HEAD)" || (echo "M6_TOP30_RECOVERY_GIT_HEAD is required"; exit 2)
	SHAIWEI_M6_TOP30_RECOVERY_GIT_HEAD="$(M6_TOP30_RECOVERY_GIT_HEAD)" docker compose -f compose.m6-top30-diagnostic-recovery.yaml --profile m6-top30-diagnostic-recovery build m6-top30-diagnostic-recovery-original m6-top30-diagnostic-recovery-current
docker-m6-top30-recovery-fixture: ## 断网、无真实挂载验证R2三种Compose安全配置
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-diagnostic-recovery.yaml --profile m6-top30-diagnostic-recovery-fixture run --rm --no-deps m6-top30-diagnostic-recovery-original-fixture
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-diagnostic-recovery.yaml --profile m6-top30-diagnostic-recovery-fixture run --rm --no-deps m6-top30-diagnostic-recovery-current-fixture
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-diagnostic-recovery.yaml --profile m6-top30-diagnostic-recovery-fixture run --rm --no-deps m6-top30-diagnostic-recovery-auditor-fixture
docker-m6-top30-recovery-original: ## 仅在新scope获精确批准后调用一次R2 original lane
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-diagnostic-recovery.yaml --profile m6-top30-diagnostic-recovery run --rm --no-deps m6-top30-diagnostic-recovery-original
docker-m6-top30-recovery-current: ## R2 original成功后调用一次current两适配器lane
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-diagnostic-recovery.yaml --profile m6-top30-diagnostic-recovery run --rm --no-deps m6-top30-diagnostic-recovery-current
docker-m6-top30-recovery-audit: ## 两个R2 runner成功后调用一次无Qlib独立audit
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-diagnostic-recovery.yaml --profile m6-top30-diagnostic-recovery run --rm --no-deps m6-top30-diagnostic-recovery-auditor

docker-m6-top30-provenance-build: ## 构建R3两套只读取证薄镜像；不读取Qlib或运行回测
	@test -n "$(M6_TOP30_PROVENANCE_GIT_HEAD)" || (echo "M6_TOP30_PROVENANCE_GIT_HEAD is required" >&2; exit 2)
	SHAIWEI_M6_TOP30_PROVENANCE_GIT_HEAD="$(M6_TOP30_PROVENANCE_GIT_HEAD)" docker compose -f compose.m6-top30-provenance.yaml --profile m6-top30-provenance build m6-top30-provenance-original-probe m6-top30-provenance-failed-probe
docker-m6-top30-provenance-fixture: ## 两套R3镜像断网运行纯合成分类与ULP fixture
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-provenance.yaml --profile m6-top30-provenance-fixture run --rm --no-deps m6-top30-provenance-original-fixture
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-provenance.yaml --profile m6-top30-provenance-fixture run --rm --no-deps m6-top30-provenance-failed-fixture
docker-m6-top30-provenance-original-probe: ## R3正式scope下唯一一次原M6镜像元数据探针
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-provenance.yaml --profile m6-top30-provenance run --rm --no-deps m6-top30-provenance-original-probe
docker-m6-top30-provenance-failed-probe: ## R3正式scope下唯一一次失败M6-3C镜像元数据探针
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-provenance.yaml --profile m6-top30-provenance run --rm --no-deps m6-top30-provenance-failed-probe
docker-m6-top30-provenance-collect: ## 唯一一次收集既有Top30数值谱系；零新回测
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-provenance.yaml --profile m6-top30-provenance run --rm --no-deps m6-top30-provenance-collector
docker-m6-top30-provenance-audit: ## 唯一一次无Qlib独立复算R3分类
	SHAIWEI_HOST_UID="$$(id -u)" SHAIWEI_HOST_GID="$$(id -g)" docker compose -f compose.m6-top30-provenance.yaml --profile m6-top30-provenance run --rm --no-deps m6-top30-provenance-auditor
docker-release-build: ## 从干净工作树构建并验证内容寻址 scheduler 镜像
	$(PYTHON) -m shaiwei.release build
docker-release-promote: ## 提升 RELEASE_IMAGE；默认重建 scheduler 并验收隔离契约
	@test -n "$(RELEASE_IMAGE)" || (echo "RELEASE_IMAGE is required"; exit 2)
	$(PYTHON) -m shaiwei.release promote --image "$(RELEASE_IMAGE)"
docker-release-rollback: ## 回滚到上一不可变 scheduler 镜像并验收
	$(PYTHON) -m shaiwei.release rollback
docker-release-start: ## 启动已提升的 current 镜像并验收挂载/快照/健康
	$(PYTHON) -m shaiwei.release start
docker-release-guard: ## 只在冻结日期/时窗和精确身份门通过时单次启动 Top20 候选
	$(PYTHON) -m shaiwei.release_guard --execute
docker-early-release-guard: ## 只在冻结20260805窗口原子提升并启动早探测候选
	$(PYTHON) -m shaiwei.daily_early_release_guard --execute
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
docker-web-control-init: ## 创建本机 M5 控制面目录和不可回显的随机代理密钥；已有密钥不覆盖
	mkdir -p data/control/m5/runtime
	@if [ ! -s data/control/m5/proxy_token ]; then umask 077; openssl rand -hex 32 -out data/control/m5/proxy_token; fi
	@chmod 600 data/control/m5/proxy_token
docker-web-control-build: docker-web-control-init ## 构建独立 M5 proposal-only 控制服务，不启动
	docker compose -f compose.web.yaml --profile control build research-control
docker-web-control-status: ## 查看无宿主端口的 M5 控制服务状态
	docker compose -f compose.web.yaml --profile control ps research-control
docker-web-control-logs: ## 查看最近100行脱敏控制服务日志
	docker compose -f compose.web.yaml --profile control logs --tail=100 research-control
docker-web-build: docker-web-control-init ## 构建隔离 Web 与 proposal-only 控制镜像，不启动服务
	docker compose -f compose.web.yaml --profile web build web-query research-control
docker-web-research-project: ## 一次性构建 P3-3B 不可变研究投影；不启动 Web 或 scheduler
	docker compose -f compose.web.yaml --profile research-projection run --rm research-projector
docker-web-strategy-factory-project: ## 断网构建 M5-0 内容寻址策略工厂投影；不启动 Web 或 scheduler
	docker compose -f compose.web.yaml --profile strategy-factory-projection run --rm --no-deps strategy-factory-projector
docker-web-security-names-project: ## 断网构建内容寻址的证券简称投影；不启动 Web 或 scheduler
	docker compose -f compose.web.yaml --profile security-name-projection run --rm security-name-projector
docker-web-up: docker-web-control-init ## 显式启动 Web、只读查询和proposal-only控制；不触碰scheduler
	docker compose -f compose.web.yaml --profile web up -d web-query research-control web-ui
docker-web-status: ## 查看隔离 Web 服务状态
	docker compose -f compose.web.yaml --profile web ps web-query research-control web-ui
docker-web-logs: ## 查看 Web 最近 100 行脱敏运行日志
	docker compose -f compose.web.yaml --profile web logs --tail=100 web-query research-control web-ui
docker-web-down: ## 仅停止隔离 Web 服务
	docker compose -f compose.web.yaml --profile web down
