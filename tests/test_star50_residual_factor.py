from __future__ import annotations

import numpy as np
import pandas as pd

from shaiwei.research.star50_residual.compute import (
    ResidualInputs,
    build_interval_returns,
    fit_candidates,
)
from shaiwei.research.star50_residual.contract import ResidualGateError, ResidualProtocol


def test_frozen_protocol_is_result_blind() -> None:
    protocol = ResidualProtocol.load()
    assert protocol.document["scope"]["label_read_authorized"] is False
    assert protocol.document["scope"]["llm_or_external_api_authorized"] is False
    assert len(protocol.document["candidates"]) == 3


def test_fit_candidates_is_deterministic_and_uses_fixed_shape() -> None:
    benchmark = np.linspace(-0.02, 0.02, 40)
    stock = 0.001 + 1.2 * benchmark + np.sin(np.arange(40)) * 0.003
    first = fit_candidates(
        stock,
        benchmark,
        benchmark_variance_minimum=1e-12,
        residual_scale_minimum=1e-12,
    )
    second = fit_candidates(
        stock,
        benchmark,
        benchmark_variance_minimum=1e-12,
        residual_scale_minimum=1e-12,
    )
    assert first == second
    assert first is not None
    assert set(first) == {
        "residual_momentum_35_skip5",
        "residual_reversal_5",
        "negative_idiosyncratic_volatility_40",
        "alpha",
        "beta",
        "residual_std",
    }
    assert fit_candidates(
        stock[:-1],
        benchmark[:-1],
        benchmark_variance_minimum=1e-12,
        residual_scale_minimum=1e-12,
    ) is None


def test_interval_benchmark_return_uses_same_suspension_endpoints() -> None:
    inputs = ResidualInputs(
        members=pd.DataFrame(),
        market=pd.DataFrame(
            {
                "ts_code": ["688001.SH", "688001.SH"],
                "trade_date": ["20200101", "20200103"],
                "close": [100.0, 110.0],
            }
        ),
        benchmark=pd.DataFrame(
            {
                "ts_code": ["000688.SH"] * 3,
                "trade_date": ["20200101", "20200102", "20200103"],
                "close": [100.0, 105.0, 121.0],
            }
        ),
        calendar=("20200101", "20200102", "20200103"),
    )
    row = build_interval_returns(inputs)["688001.SH"].iloc[0]
    assert row["start_date"] == "20200101"
    assert row["trade_date"] == "20200103"
    assert np.isclose(row["stock_return"], np.log(1.1))
    assert np.isclose(row["benchmark_return"], np.log(1.21))


def test_protocol_rejects_broadened_scope() -> None:
    protocol = ResidualProtocol.load()
    altered = dict(protocol.document)
    altered["scope"] = {**altered["scope"], "label_read_authorized": True}
    with np.testing.assert_raises(ResidualGateError):
        from shaiwei.research.star50_residual.contract import _validate_document

        _validate_document(altered)
