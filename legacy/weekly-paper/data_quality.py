"""Audited corporate actions applied in memory; supplied CSVs stay unchanged.

Continuation: append verified split rows to data/external/corporate_actions.csv.
Never infer a split factor from a price drop alone. An unexplained >=45% close
move stops the run for review; a genuine move can be recorded as an action
``verified_price_move`` with factor 1 and a primary-source URL after review.
Prices are split adjusted, not dividend-adjusted total-return series.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ACTION_FILE = Path(__file__).resolve().parent / "data" / "external" / "corporate_actions.csv"


def load_price_frame(path: Path, ticker: str | None = None,
                     actions_path: Path | None = None) -> pd.DataFrame:
    """Load official OHLCV, recognizing already adjusted listed split events."""
    path = Path(path)
    ticker = ticker or path.stem
    frame = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    if frame.index.has_duplicates or frame.index.isna().any():
        raise ValueError(f"{ticker}: duplicate or invalid price date")
    required = {"open", "close"}
    if not required.issubset(frame.columns):
        raise ValueError(f"{ticker}: missing price columns {required - set(frame.columns)}")
    for column in [c for c in ["open", "high", "low", "close", "volume"] if c in frame]:
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)
        observed = frame[column].dropna()
        if not np.isfinite(observed).all() or (observed < 0).any() or (column != "volume" and observed.eq(0).any()):
            raise ValueError(f"{ticker}: invalid {column} observation")
    action_file = Path(actions_path) if actions_path is not None else ACTION_FILE
    actions = pd.read_csv(action_file, parse_dates=["ex_date"])
    audit, reviewed_moves = [], set()
    # Later splits scale both prices around earlier events equally.
    for row in actions.loc[actions["ticker"].eq(ticker)].sort_values("ex_date").itertuples():
        if not isinstance(row.source_url, str) or not row.source_url.startswith("https://"):
            raise ValueError(f"{ticker}: corporate action needs a source URL")
        ex_date = pd.Timestamp(row.ex_date)
        if row.action == "verified_price_move":
            reviewed_moves.add(ex_date)
            continue
        if row.action != "split" or not np.isfinite(row.factor) or row.factor <= 0 or row.factor == 1:
            raise ValueError(f"{ticker}: invalid split metadata")
        before = frame.loc[frame.index < ex_date, "close"].dropna()
        after = frame.loc[frame.index >= ex_date, "close"].dropna()
        if before.empty or after.empty:
            continue
        ratio = float(after.iloc[0] / before.iloc[-1])
        if abs(ratio * row.factor - 1) <= .30:
            mask = frame.index < ex_date
            price_columns = [c for c in ["open", "high", "low", "close"] if c in frame]
            frame.loc[mask, price_columns] /= row.factor
            if "volume" in frame:
                frame.loc[mask, "volume"] *= row.factor
            status = "adjusted_in_memory"
        elif abs(ratio - 1) <= .30:
            status = "already_adjusted"
        else:
            raise ValueError(f"{ticker} {ex_date.date()}: split metadata does not reconcile to prices")
        audit.append({"ticker": ticker, "ex_date": str(ex_date.date()),
                      "factor": float(row.factor), "status": status,
                      "source_url": row.source_url})
    moves = frame["close"].dropna().pct_change(fill_method=None)
    unexplained = moves.loc[moves.abs().ge(.45) & ~moves.index.isin(reviewed_moves)]
    if len(unexplained):
        date, move = unexplained.index[0], unexplained.iloc[0]
        raise ValueError(f"{ticker} {date.date()}: unexplained {move:.1%} close move; verify corporate action before continuing")
    frame.attrs["corporate_action_audit"] = audit
    return frame


def calendar_short_rates(dates: pd.DatetimeIndex, sofr: pd.Series,
                         spread_pct: float = .5) -> pd.Series:
    """ACT/360 from prior close date inclusive to this close date exclusive.

    SOFR observations and spread are in annual percentage points. Each elapsed
    calendar day's available rate is used, including weekends and holidays.
    """
    dates = pd.DatetimeIndex(dates)
    output = pd.Series(0.0, index=dates)
    if len(dates) < 2:
        return output
    if not dates.is_monotonic_increasing or dates.has_duplicates:
        raise ValueError("Financing dates must increase strictly")
    calendar = pd.date_range(dates[0], dates[-1] - pd.Timedelta(days=1), freq="D")
    rates = sofr.sort_index().reindex(calendar, method="ffill")
    if rates.isna().any() or not np.isfinite(rates).all():
        raise ValueError("SOFR does not cover the requested financing interval")
    daily = (rates.astype(float) + float(spread_pct)) / 100.0 / 360.0
    cumulative = pd.Series(np.r_[0.0, daily.cumsum().to_numpy()],
                           index=pd.date_range(dates[0], dates[-1], freq="D"))
    output.iloc[1:] = np.diff(cumulative.reindex(dates).to_numpy())
    return output
