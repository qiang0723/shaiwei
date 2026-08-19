# pyqlib 0.9.7 publishes Linux artifacts for Python <=3.11. The project
# supports 3.10-3.12, so 3.11 is the portable ARM64 container baseline.
FROM python:3.11-slim

ARG SHAIWEI_RELEASE_GIT_HEAD=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLCONFIGDIR=/workspace/data/cache/matplotlib \
    SHAIWEI_RELEASE_GIT_HEAD=${SHAIWEI_RELEASE_GIT_HEAD}

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=5 update \
    && apt-get -o Acquire::Retries=5 install --yes --no-install-recommends build-essential git libgomp1

WORKDIR /workspace

COPY .dockerignore .env.example Dockerfile Dockerfile.ts-v5-llm Dockerfile.ts-v5-r3g Dockerfile.ts-v5-r3g1 Dockerfile.ts-v5-r3g2-benchmark Dockerfile.ts-v6-entry-quality Dockerfile.ts-v6-1-ranking Dockerfile.ts-v6-3-ranked-subset Dockerfile.ts-v6-4-no-takeprofit Dockerfile.ts-b-holdout Dockerfile.ts-rf-0b Dockerfile.ts-rf-diag Makefile pyproject.toml requirements.lock requirements.ts-v5-llm.lock ./
COPY compose.yaml compose.research.yaml compose.m6-attribution.yaml compose.m6-topk-conversion-release.yaml compose.ts-recovery.yaml compose.ts-v5-llm.yaml compose.ts-v5-r2.yaml compose.ts-v5-r3c.yaml compose.ts-v5-r3f.yaml compose.ts-v5-r3g.yaml compose.ts-v5-r3g1.yaml compose.ts-v5-r3g2-benchmark.yaml compose.ts-v5-r3g2-w7.yaml compose.ts-v5-r3g2-w7-recovery.yaml compose.ts-v5-r3g2-effect.yaml compose.ts-v5-r3g2-effect-recovery.yaml compose.ts-v5-r3g3-diagnostic.yaml compose.ts-v6-entry-quality.yaml compose.ts-v6-1-ranking.yaml compose.ts-v6-3-ranked-subset.yaml compose.ts-v6-4-no-takeprofit.yaml compose.ts-b-holdout.yaml compose.ts-rf-0b.yaml compose.ts-rf-diag.yaml ./
COPY src ./src
COPY config ./config
COPY templates ./templates
COPY tests ./tests
# PyPI publishes pyqlib 0.9.7 Linux wheels only for x86_64. Build the exact
# signed v0.9.7 release commit natively for Apple Silicon instead.
ARG QLIB_COMMIT=da920b7f954f48ab1bb64117c976710de198373e
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    python -m pip install --upgrade pip \
    && grep -Ev '^(pyqlib|torch)==' requirements.lock > /tmp/requirements-container.lock \
    && python -m pip install -r /tmp/requirements-container.lock \
    && python -m pip install --no-deps --index-url https://download.pytorch.org/whl/cpu "torch==2.13.0+cpu" \
    && python -c "import torch; assert torch.__version__ == '2.13.0+cpu'; assert not torch.cuda.is_available()" \
    && python -m pip install --no-deps "git+https://github.com/microsoft/qlib.git@${QLIB_COMMIT}" \
    && python -c "import qlib; assert qlib.__version__ == '0.9.7', qlib.__version__" \
    && python -m pip install --no-deps -e .

RUN mkdir -p /opt/shaiwei /workspace/data /workspace/ledger /workspace/logs /workspace/docs \
    && python -m shaiwei.provenance \
       --write-release-manifest /opt/shaiwei/release-manifest.json

ENV SHAIWEI_RELEASE_MANIFEST=/opt/shaiwei/release-manifest.json

CMD ["python", "-m", "shaiwei.pipeline.stage0", "--plan"]
