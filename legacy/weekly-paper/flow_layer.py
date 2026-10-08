"""Options-flow loading and exploratory evidence helpers.

Run ``python flow_layer.py`` for the bounded Rev11 coverage and information
export in results/evidence. It uses the fixed 200 equities, corrected prices,
and the candidate-provided flow-114 snapshot. The research workbook contributes
coverage and examples only. No parameter sweep is part of this entry point.

Unused exploratory roster helpers were retired; no alternate backtest is run here.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from data_quality import load_price_frame

ROOT = Path(__file__).resolve().parent
OFFICIAL = ROOT / "data" / "official"
EXTERNAL = ROOT / "data" / "external"
OUT = ROOT / "results" / "rev4_flow"

EVAL, DEV = ("2025-01-01", "2025-12-31"), ("2023-01-03", "2024-12-31")
FLOW_SHEETS = ["Flow Analytics (Stocks)", "Flow Analytics (ETFs)"]
# frozen flow filter — unchanged from Rev 3
MIN_PREMIUM, DTE_LO, DTE_HI = 100_000, 180, 730
MOM_LOOKBACK, SIGNAL_LAG = 60, 1


# ------------------------------------------------------------------ loading
def load_prices() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    universe = pd.read_csv(OFFICIAL / "universe.csv")
    tickers = universe.loc[universe["category"].eq("equity"), "ticker"].tolist()
    o, c, v = {}, {}, {}
    for t in tickers:
        f = load_price_frame(OFFICIAL / "prices" / f"{t}.csv", ticker=t)
        o[t] = pd.to_numeric(f["open"], errors="coerce")
        c[t] = pd.to_numeric(f["close"], errors="coerce")
        v[t] = pd.to_numeric(f["volume"], errors="coerce")
    spy = pd.read_csv(EXTERNAL / "spy_nasdaq_2023_2025.csv", parse_dates=["date"]).set_index("date").sort_index()
    return (pd.DataFrame(o).sort_index(), pd.DataFrame(c).sort_index(),
            pd.DataFrame(v).sort_index(), spy, tickers)


def find_flow_workbook() -> Path:
    for name in ("flow-114.xlsx", "flow114.xlsx", "flow-112.xlsx", "flow112.xlsx"):
        if (EXTERNAL / name).exists():
            return EXTERNAL / name
    hits = sorted(EXTERNAL.glob("flow*.xlsx"))
    if not hits:
        raise FileNotFoundError(f"No flow workbook found in {EXTERNAL}")
    return hits[0]


def load_flow_records(path: Path) -> pd.DataFrame:
    """Read source records, keeping Excel coordinates and first exact duplicate.

    The snapshot is an incomplete historical record; dates alone do not prove
    that records were available on those dates. No availability timestamp is
    supplied. This function makes no point-in-time completeness claim.
    """
    frames = []
    for sheet in FLOW_SHEETS:
        f = pd.read_excel(path, sheet_name=sheet, header=4, usecols="A:J")
        f["source_row"] = f.index + 6
        f["source_sheet"] = sheet
        f = f.dropna(subset=["Date", "Symbol"], how="all")
        frames.append(f)
    flow = pd.concat(frames, ignore_index=True)
    input_rows = len(flow)
    source_columns = [c for c in flow.columns if not c.startswith("source_")]
    flow = flow.drop_duplicates(subset=source_columns)
    flow.attrs["input_rows"] = input_rows
    flow.attrs["exact_duplicate_rows_removed"] = input_rows - len(flow)
    flow["Date"] = pd.to_datetime(flow["Date"], errors="coerce").dt.normalize()
    for col in ("DTE", "Premium", "Quantity", "Open Interest"):
        flow[col] = pd.to_numeric(flow[col], errors="coerce")
    flow["Symbol"] = flow["Symbol"].astype(str).str.upper().str.strip()
    return flow


def qualifying_mask(flow: pd.DataFrame) -> pd.Series:
    """Frozen exploratory filter, using trade-date DTE recorded in the snapshot."""
    sentiment = flow["Sentiment"].astype(str).str.upper().str.strip()
    return (flow["Date"].notna()
            & flow["Side"].astype(str).str.lower().str.contains("ask", na=False)
            & flow["Premium"].ge(MIN_PREMIUM)
            & flow["Quantity"].gt(flow["Open Interest"])
            & flow["DTE"].between(DTE_LO, DTE_HI)
            & sentiment.isin(["BULLISH", "BEARISH"]))


def load_qualifying_flow(path: Path) -> pd.DataFrame:
    flow = load_flow_records(path)
    keep = qualifying_mask(flow)
    sel = flow.loc[keep].copy()
    bullish = sel["Sentiment"].astype(str).str.upper().str.strip().eq("BULLISH")
    sel["signed_premium"] = np.where(bullish, sel["Premium"], -sel["Premium"])
    return sel


def daily_premium_panel(qualifying: pd.DataFrame, dates: pd.DatetimeIndex,
                        tickers: list[str]) -> pd.DataFrame:
    panel = (qualifying.groupby(["Date", "Symbol"])["signed_premium"].sum().unstack()
                       .reindex(index=dates, columns=tickers).fillna(0.0).astype(float))
    return panel


# ------------------------------------------------------------------ scoring
def conviction_score(premium: pd.DataFrame, dollar_volume: pd.DataFrame, window: int) -> pd.DataFrame:
    """Signed premium over `window` sessions per unit of the stock's own liquidity.

    Scaling by median dollar volume rather than z-scoring avoids dividing by the
    standard deviation of a series that is mostly zeros, and reads directly as
    conviction per unit of liquidity rather than as a proxy for market cap.
    Shifted one session so it is known at the decision point.
    """
    rolled = premium.rolling(window, min_periods=1).sum()
    liquidity = dollar_volume.rolling(60, min_periods=20).median()
    return (rolled / liquidity).clip(-2, 2).shift(SIGNAL_LAG)


# ------------------------------------------------------------------ metrics
def newey_west_t(x: np.ndarray, lags: int = 5) -> float:
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 10:
        return float("nan")
    e = x - x.mean()
    s = (e @ e) / n
    for L in range(1, lags + 1):
        s += 2 * (1 - L / (lags + 1)) * ((e[L:] @ e[:-L]) / n)
    return float(x.mean() / math.sqrt(s / n)) if s > 0 else float("nan")


# ------------------------------------------------------------------ main
def main() -> None:
    """Default entry point: fixed coverage and information tests, no parameter sweep."""
    ap = argparse.ArgumentParser(description="Rev11 reproducible workbook evidence.")
    ap.add_argument("--angles", type=Path,
                    default=EXTERNAL / "hidden_angle_flow_database_SEP_6th_2026_updated.xlsx",
                    help="Path to the candidate-provided Hidden Angles workbook.")
    args = ap.parse_args()
    from evidence_summary import main as evidence_main
    evidence_main(args.angles)


if __name__ == "__main__":
    main()
