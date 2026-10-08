"""Shared unlevered overnight accounting; unavailable exits remain real holdings.

Rows are labelled by close-t entry/valuation date and end at close t+1. Normally
all holdings sell at open t+1; an unavailable open carries the position, marked
at the next observed close (otherwise its last observed mark). New entries are
suspended until all delayed exits have executed. Cash earns zero, as does the
zero-rate Sharpe benchmark. Costs are charged on actual buy/sell notional.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ranked_roster(scores: pd.DataFrame, n: int) -> pd.DataFrame:
    """Break ties by ticker, using the supplied (already lagged) scores only."""
    ordered = scores.reindex(sorted(scores.columns), axis=1)
    return ordered.replace([np.inf, -np.inf], np.nan).rank(
        axis=1, ascending=False, method="first").le(n).reindex(columns=scores.columns)


def simulate_roster(open_: pd.DataFrame, close: pd.DataFrame,
                    selected: pd.DataFrame, gate: pd.Series | None = None,
                    n: int = 10, round_trip_bp: float = 0.0,
                    max_weight: float = 0.10) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Trade a precomputed causal roster without looking at future fills.

    Weights are capped at entry; subsequent price drift is retained. Entry fees
    are reserved before sizing so the cash balance never becomes negative.
    Breadth diagnostics may explicitly pass a different max_weight; the main
    ten-name portfolios always use 10%. No final synthetic liquidation occurs.
    """
    if n < 1 or not 0 < max_weight <= 1 or round_trip_bp < 0:
        raise ValueError("Invalid overnight sizing/cost parameters")
    close = close.sort_index()
    dates, columns = close.index, close.columns
    o = open_.reindex(index=dates, columns=columns).to_numpy(float)
    c = close.to_numpy(float)
    roster = selected.reindex(index=dates, columns=columns).fillna(False).to_numpy(bool)
    allowed = np.ones(len(dates), bool) if gate is None else gate.reindex(dates).fillna(False).to_numpy(bool)
    side = round_trip_bp / 20_000.0
    cash, equity = 1.0, 1.0
    held: dict[int, dict] = {}
    rows, trades = [], []
    for i, date in enumerate(dates[:-1]):
        initial_equity = equity
        starting_pending = len(held)
        intended = np.flatnonzero(roster[i]) if allowed[i] else np.array([], dtype=int)
        filled, unavailable, bought = [], [], 0.0
        # An outstanding exit blocks the entire next roster, independent of
        # whether that outstanding name is selected again.
        if not held and allowed[i]:
            weight = min(1.0 / n, max_weight)
            notional = initial_equity * weight / (1.0 + side)
            for j in intended:
                price = c[i, j]
                if not np.isfinite(price) or price <= 0:
                    unavailable.append(str(columns[j]))
                    continue
                if notional * (1 + side) > cash + 1e-10:
                    raise AssertionError("Overnight orders exceed available capital")
                shares = notional / price
                cash -= notional * (1 + side)
                bought += notional
                filled.append(str(columns[j]))
                held[j] = {"shares": shares, "mark": price, "entry_close": price,
                           "entry_date": date, "entry_weight": notional / initial_equity,
                           "entry_notional": notional, "rank": len(filled)}
        entry_gross = sum(h["shares"] * h["mark"] for h in held.values()) / initial_equity
        entry_cash = cash / initial_equity
        sold = 0.0
        for j, holding in list(held.items()):
            price = o[i + 1, j]
            if np.isfinite(price) and price > 0:
                proceeds = holding["shares"] * price
                cash += proceeds * (1 - side)
                sold += proceeds
                stock_return = price / holding["entry_close"] - 1
                trades.append({"entry_date": holding["entry_date"], "exit_date": dates[i + 1],
                    "ticker": str(columns[j]), "rank": holding["rank"],
                    "entry_close": holding["entry_close"], "exit_open": price,
                    "entry_weight": holding["entry_weight"],
                    "overnight_return_gross": stock_return,
                    "overnight_return_net": (1 + stock_return) * (1 - side) / (1 + side) - 1,
                    "delayed_exit": holding["entry_date"] != date,
                    "next_close": c[i + 1, j],
                    "next_daytime_return": c[i + 1, j] / price - 1,
                    "status": "closed"})
                del held[j]
            elif np.isfinite(c[i + 1, j]) and c[i + 1, j] > 0:
                holding["mark"] = c[i + 1, j]
        equity = cash + sum(h["shares"] * h["mark"] for h in held.values())
        if cash < -1e-9 or equity <= 0:
            raise AssertionError("Invalid unlevered overnight account")
        rows.append({"entry_date": date, "exit_date": dates[i + 1],
            "return": equity / initial_equity - 1,
            "equity": equity, "selected_names": "|".join(filled),
            "intended_names": "|".join(str(columns[j]) for j in intended),
            "selected_count": len(filled), "active": bool(filled or starting_pending),
            "entry_gross": entry_gross, "cash_weight_after_entry": entry_cash,
            "buy_turnover": bought / initial_equity, "sell_turnover": sold / initial_equity,
            "cost_return": side * (bought + sold) / initial_equity,
            "unavailable_entries": "|".join(unavailable),
            "pending_exits": "|".join(str(columns[j]) for j in held),
            "new_entries_blocked": bool(starting_pending)})
    for j, holding in held.items():
        trades.append({"entry_date": holding["entry_date"], "exit_date": pd.NaT,
            "ticker": str(columns[j]), "rank": holding["rank"],
            "entry_close": holding["entry_close"], "exit_open": np.nan,
            "entry_weight": holding["entry_weight"], "overnight_return_gross": np.nan,
            "overnight_return_net": np.nan, "delayed_exit": True,
            "next_close": np.nan, "next_daytime_return": np.nan, "status": "open"})
    daily = pd.DataFrame(rows).set_index("entry_date")
    columns_out = ["entry_date", "exit_date", "ticker", "rank", "entry_close", "exit_open",
        "entry_weight", "overnight_return_gross", "overnight_return_net", "delayed_exit",
        "next_close", "next_daytime_return", "status"]
    return daily, pd.DataFrame(trades, columns=columns_out)


def reporting_periods(index: pd.DatetimeIndex, cfg: dict) -> dict:
    periods = {"2023-24": (cfg["development_start"], cfg["development_end"]),
               "2025": (cfg["evaluation_start"], cfg["evaluation_end"]),
               "combined": (cfg["development_start"], cfg["evaluation_end"])}
    continuation_start = pd.Timestamp(cfg["evaluation_end"]) + pd.Timedelta(days=1)
    if len(index) and index.max() >= continuation_start:
        periods["continuation"] = (str(continuation_start.date()), str(index.max().date()))
        periods["all_available"] = (cfg["development_start"], str(index.max().date()))
    return periods
