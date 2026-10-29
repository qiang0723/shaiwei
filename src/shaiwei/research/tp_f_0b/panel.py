"""TP-F-0B member-day panel: the reused PIT CSI800 store plus label clock, industry, listing rank and qlib values."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping

import duckdb
import numpy as np
import pandas as pd

from shaiwei.research.tp_f_0b.contract import TPFError
from shaiwei.research.trend_swing.recovery_store import prepare_core_tables
from shaiwei.transform.market import attach_trade_limit_flags
from shaiwei.transform.qlib_bin import qlib_code


QLIB_FACTOR = "factor"
ADJUSTMENT_RTOL = 1e-5  # bin 为 float32（相对精度约 6e-8）；qlib close×factor 对原始收盘实测相对差约 3e-8
_CLOCK = re.compile(r"^t_plus_(\d+)_open$")


@dataclass(frozen=True)
class PanelParams:
    period: tuple[str, str]
    warmup: int
    entry_offset: int
    exit_offset: int
    qlib_features: tuple[str, ...]

    @classmethod
    def from_protocol(cls, document: Mapping[str, Any]) -> "PanelParams":
        scope = document["profile_scope"]
        offsets = [_CLOCK.fullmatch(scope["label_clock"][key]) for key in ("entry", "exit")]
        if None in offsets:
            raise TPFError("TP-F-0B label clock is not a t_plus_N_open rule")
        features = tuple(name.removeprefix("$") for name in scope["qlib_features"])
        if [f"${name}" for name in features] != document["candidate_grammar"]["features"]:
            raise TPFError("TP-F-0B qlib features differ from the candidate grammar")
        return cls(
            period=(scope["signal_period"]["start"], scope["signal_period"]["end"]),
            warmup=int(scope["warmup_trading_days"]),
            entry_offset=int(offsets[0].group(1)),  # type: ignore[union-attr]
            exit_offset=int(offsets[1].group(1)),  # type: ignore[union-attr]
            qlib_features=features,
        )


_STATEMENTS = (
    """
    CREATE TEMP TABLE tp_calendar AS
    SELECT trade_date, row_number() OVER (ORDER BY trade_date) AS calendar_rank
    FROM (SELECT DISTINCT CAST(cal_date AS VARCHAR) AS trade_date FROM trade_cal
          WHERE CAST(exchange AS VARCHAR)='SSE' AND CAST(is_open AS VARCHAR) IN ('1','1.0'))
    """,
    """
    CREATE TEMP TABLE tp_clock AS
    SELECT c.trade_date, c.calendar_rank, n.trade_date AS entry_date, x.trade_date AS exit_date
    FROM tp_calendar c
    LEFT JOIN tp_calendar n ON n.calendar_rank = c.calendar_rank + $entry
    LEFT JOIN tp_calendar x ON x.calendar_rank = c.calendar_rank + $exit
    """,
    """
    CREATE TEMP TABLE tp_bars AS
    SELECT CAST(ts_code AS VARCHAR) AS ts_code, CAST(trade_date AS VARCHAR) AS trade_date,
           max(try_cast(open AS DOUBLE)) AS open, max(try_cast(pre_close AS DOUBLE)) AS pre_close
    FROM daily GROUP BY 1,2
    """,
    """
    CREATE TEMP TABLE tp_daily AS
    SELECT CAST(d.ts_code AS VARCHAR) AS ts_code, CAST(d.trade_date AS VARCHAR) AS trade_date,
           count(*) AS bar_record_count,
           count(DISTINCT hash(d.open,d.high,d.low,d.close,d.pre_close,d.vol,d.amount)) AS bar_variant_count,
           max(try_cast(d.open AS DOUBLE)) AS open, max(try_cast(d.high AS DOUBLE)) AS high,
           max(try_cast(d.low AS DOUBLE)) AS low, max(try_cast(d.close AS DOUBLE)) AS close,
           max(try_cast(d.pre_close AS DOUBLE)) AS pre_close, max(try_cast(d.vol AS DOUBLE)) AS vol
    FROM daily d JOIN expected e
      ON CAST(d.ts_code AS VARCHAR)=e.ts_code AND CAST(d.trade_date AS VARCHAR)=e.trade_date
    GROUP BY 1,2
    """,
    """
    CREATE TEMP TABLE tp_listing AS
    SELECT l.ts_code, min(c.calendar_rank) AS listing_rank
    FROM lifecycle l JOIN tp_calendar c ON c.trade_date >= l.list_date
    WHERE l.list_date >= (SELECT min(trade_date) FROM tp_calendar)
    GROUP BY 1
    """,
    """
    CREATE TEMP TABLE tp_industry_raw AS
    SELECT e.ts_code, e.trade_date, count(DISTINCT CAST(i.l1_code AS VARCHAR)) AS raw_l1_count
    FROM expected e JOIN index_member_all i
      ON CAST(i.ts_code AS VARCHAR)=e.ts_code AND CAST(i.in_date AS VARCHAR)<=e.trade_date
     AND (nullif(CAST(i.out_date AS VARCHAR),'') IS NULL OR CAST(i.out_date AS VARCHAR)>=e.trade_date)
    GROUP BY 1,2
    """,
    """
    CREATE TEMP TABLE tp_panel AS
    SELECT e.ts_code, e.trade_date, e.list_date, e.market_rank,
           (SELECT max(market_rank) FROM open_days) AS period_last_rank,
           coalesce(r.bar_record_count, 0) AS bar_record_count,
           coalesce(r.bar_variant_count, 0) AS bar_variant_count,
           r.open, r.high, r.low, r.close, r.pre_close, r.vol,
           a.adj_factor,
           lag(a.adj_factor) OVER w AS prior_adj_factor,
           lag(r.close) OVER w AS prior_bar_close,
           coalesce(p.ts_code IS NOT NULL, false) AS primary_suspended,
           coalesce(v.independent_status, '') AS independent_status,
           k.calendar_rank, k.entry_date, k.exit_date,
           b1.open AS entry_open, b1.pre_close AS entry_pre_close, b11.open AS exit_open,
           t.listing_rank,
           coalesce(i.industry_count, 0) AS industry_count, i.industry,
           lag(i.industry) OVER w AS prior_industry,
           coalesce(q.raw_l1_count, 0) AS raw_l1_count,
           lag(e.market_rank) OVER w AS prior_member_rank,
           lead(e.market_rank) OVER w AS next_member_rank
    FROM expected e
    LEFT JOIN tp_daily r USING(ts_code, trade_date)
    LEFT JOIN adj_keys a USING(ts_code, trade_date)
    LEFT JOIN primary_suspension p USING(ts_code, trade_date)
    LEFT JOIN availability v USING(ts_code, trade_date)
    LEFT JOIN industry_hits i USING(ts_code, trade_date)
    LEFT JOIN tp_industry_raw q USING(ts_code, trade_date)
    LEFT JOIN tp_listing t USING(ts_code)
    LEFT JOIN tp_clock k ON k.trade_date = e.trade_date
    LEFT JOIN tp_bars b1 ON b1.ts_code = e.ts_code AND b1.trade_date = k.entry_date
    LEFT JOIN tp_bars b11 ON b11.ts_code = e.ts_code AND b11.trade_date = k.exit_date
    WINDOW w AS (PARTITION BY e.ts_code ORDER BY e.trade_date)
    """,
)


def attach_qlib(panel: pd.DataFrame, qlib_root: Path, features: tuple[str, ...]) -> pd.DataFrame:
    """Read qlib day bins directly (first float = start calendar index); absent dates stay NaN, never filled."""
    calendar = (qlib_root / "calendars/day.txt").read_text(encoding="utf-8").split()
    index = pd.Series(np.arange(len(calendar)), index=calendar)
    positions = panel["trade_date"].map(index)
    if positions.isna().any():
        raise TPFError("TP-F-0B signal date lies outside the qlib calendar")
    positions = positions.to_numpy(dtype=np.int64)
    columns = {name: np.full(len(panel), np.nan) for name in (*features, QLIB_FACTOR)}
    for ts_code, rows in panel.groupby("ts_code", sort=True).indices.items():
        directory = qlib_root / "features" / qlib_code(ts_code).lower()
        for name, values in columns.items():
            path = directory / f"{name}.day.bin"
            if not path.is_file():
                continue
            payload = np.fromfile(path, dtype="<f4")
            offset = positions[rows] - int(payload[0])
            inside = (offset >= 0) & (offset < len(payload) - 1)
            values[rows[inside]] = payload[1:][offset[inside]]
    for name, values in columns.items():
        panel[f"qlib_{name}"] = values
    panel["qlib_calendar_index"] = positions
    return panel


def attach_entry_limits(panel: pd.DataFrame, connection: duckdb.DuckDBPyConnection, limits: Mapping[str, float]) -> pd.DataFrame:
    """t+1 open at limit, judged by the production board/date/ST/listing rules on the open change (report only)."""
    rows = panel.index[
        (panel["bar_record_count"] > 0) & (panel["entry_open"] > 0) & (panel["entry_pre_close"] > 0)
        & ~panel["ts_code"].str.endswith(".BJ")
    ]
    panel["entry_limit_up"] = False
    panel["entry_limit_down"] = False
    if len(rows):
        market = pd.DataFrame({
            "ts_code": panel.loc[rows, "ts_code"].to_numpy(),
            "trade_date": panel.loc[rows, "entry_date"].to_numpy(),
            "change": (panel.loc[rows, "entry_open"] / panel.loc[rows, "entry_pre_close"] - 1).to_numpy(),
        })
        stock_basic = connection.execute(
            "SELECT CAST(ts_code AS VARCHAR) AS ts_code, CAST(list_date AS VARCHAR) AS list_date FROM stock_basic"
        ).fetchdf()
        namechange = connection.execute(
            """
            SELECT CAST(ts_code AS VARCHAR) AS ts_code, CAST(name AS VARCHAR) AS name,
                   CAST(start_date AS VARCHAR) AS start_date, CAST(end_date AS VARCHAR) AS end_date
            FROM namechange
            """
        ).fetchdf()
        flagged = attach_trade_limit_flags(market, stock_basic, namechange, limits, copy=False)
        panel.loc[rows, "entry_limit_up"] = flagged["limit_buy"].to_numpy()
        panel.loc[rows, "entry_limit_down"] = flagged["limit_sell"].to_numpy()
    return panel


def attach_adjustment_check(panel: pd.DataFrame) -> pd.DataFrame:
    """Adjusted continuity: qlib close x factor equals raw close, and factor x raw adj_factor is flat across ex-rights."""
    has_bar = panel["bar_record_count"] > 0
    price_gap = (panel["qlib_close"] * panel["qlib_factor"] / panel["close"] - 1).abs()
    product = (panel["qlib_factor"] * panel["adj_factor"]).where(has_bar)
    # 只作比较参照：取同票上一个有值的乘积，不改动任何数据
    prior = product.groupby(panel["ts_code"], sort=False).transform(lambda series: series.ffill().shift())
    jump = (product / prior - 1).abs()
    panel["adjustment_inconsistent"] = has_bar & ((price_gap > ADJUSTMENT_RTOL) | (jump > ADJUSTMENT_RTOL))
    return panel


def build_panel(
    connection: duckdb.DuckDBPyConnection,
    manifest: Mapping[str, Any],
    params: PanelParams,
    *,
    root: Path,
    qlib_root: Path,
    limits: Mapping[str, float],
) -> pd.DataFrame:
    prepare_core_tables(connection, dict(manifest), start_date=params.period[0], end_date=params.period[1], root=root)
    for statement in _STATEMENTS:
        connection.execute(statement, {"entry": params.entry_offset, "exit": params.exit_offset} if "$entry" in statement else None)
    panel = connection.execute("SELECT * FROM tp_panel ORDER BY ts_code, trade_date").fetchdf()
    if panel.empty:
        raise TPFError("TP-F-0B member-day panel is empty")
    panel = attach_qlib(panel, qlib_root, params.qlib_features)
    panel = attach_entry_limits(panel, connection, limits)
    return attach_adjustment_check(panel)
