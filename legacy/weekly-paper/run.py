"""Compact, reproducible eToro statistical-arbitrage assignment.

Run from this folder with: python run.py
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from data_quality import calendar_short_rates, load_price_frame


ROOT = Path(__file__).resolve().parent
OFFICIAL = ROOT / "data" / "official"
EXTERNAL = ROOT / "data" / "external" / "flow-114.xlsx"
RESULTS = ROOT / "results"

ETF_TICKERS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]

SECTOR_TO_ETF = {
    "Finance": "XLF",
    "Health Technology": "XLV",
    "Health Services": "XLV",
    "Electronic Technology": "XLK",
    "Technology Services": "XLK",
    "Energy Minerals": "XLE",
    "Utilities": "XLU",
    "Process Industries": "XLB",
    "Non-Energy Minerals": "XLB",
    "Non Energy Minerals": "XLB",
    "Producer Manufacturing": "XLI",
    "Industrial Services": "XLI",
    "Transportation": "XLI",
    "Commercial Services": "XLI",
    "Distribution Services": "XLI",
    "Consumer Durables": "XLY",
    "Retail Trade": "XLY",
    "Consumer Services": "XLY",
    "Consumer Non-Durables": "XLP",
    "Communications": "XLC",
}

OVERRIDES = {
    # Real estate
    "PLD": "XLRE", "AMT": "XLRE", "EQIX": "XLRE", "CCI": "XLRE",
    # Communication services
    "VZ": "XLC", "T": "XLC", "TMUS": "XLC", "DIS": "XLC", "CMCSA": "XLC",
    "CHTR": "XLC", "WBD": "XLC", "META": "XLC", "GOOGL": "XLC", "GOOG": "XLC",
    "NFLX": "XLC", "TTWO": "XLC",
    # Consumer staples / discretionary
    "PG": "XLP", "KO": "XLP", "PEP": "XLP", "PM": "XLP", "MDLZ": "XLP",
    "MO": "XLP", "CL": "XLP", "KDP": "XLP", "KHC": "XLP", "GIS": "XLP",
    "COST": "XLP", "WMT": "XLP", "KR": "XLP", "NKE": "XLY", "EL": "XLY",
    # Health care
    "CVS": "XLV", "MCK": "XLV",
    # Energy
    "SLB": "XLE", "HAL": "XLE", "KMI": "XLE", "BKR": "XLE",
    # Financial services
    "PYPL": "XLF", "SPGI": "XLF", "FISV": "XLF", "FIS": "XLF",
    # Industrials / technology boundary
    "BA": "XLI", "LMT": "XLI", "HON": "XLI", "GE": "XLI", "RTX": "XLI",
    "NOC": "XLI", "GD": "XLI", "LHX": "XLI", "EMR": "XLI", "WM": "XLI",
    "ADP": "XLI", "CAT": "XLI", "DE": "XLI", "MMM": "XLI", "ETN": "XLI",
    "AMAT": "XLK", "ENPH": "XLK", "LRCX": "XLK", "SEDG": "XLK",
}


def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def load_official_data(evaluation_date: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series]:
    universe = pd.read_csv(OFFICIAL / "universe.csv")
    if universe["ticker"].duplicated().any() or universe["category"].eq("equity").sum() != 200:
        raise ValueError("The assignment requires the fixed 200-stock official universe.")
    frames = {}
    action_audit = []
    for ticker in universe["ticker"]:
        path = OFFICIAL / "prices" / f"{ticker}.csv"
        frame = load_price_frame(path, ticker=ticker)
        action_audit.extend(frame.attrs["corporate_action_audit"])
        if evaluation_date is not None:
            frame = frame.loc[:evaluation_date]
        frames[ticker] = frame
    close = pd.concat({ticker: frame["close"] for ticker, frame in frames.items()}, axis=1)
    open_ = pd.concat({ticker: frame["open"] for ticker, frame in frames.items()}, axis=1)
    volume = pd.concat({ticker: frame["volume"] for ticker, frame in frames.items()}, axis=1)
    close.attrs["corporate_action_audit"] = action_audit
    sofr = pd.read_csv(OFFICIAL / "sofr.csv", parse_dates=["date"]).set_index("date")["sofr_rate_pct"]
    return universe, close, open_, volume, sofr


def build_sector_map(universe: pd.DataFrame) -> pd.DataFrame:
    stocks = universe.loc[universe["category"].eq("equity"), ["ticker", "sector", "industry"]].copy()
    stocks["sector_etf"] = stocks["sector"].map(SECTOR_TO_ETF)
    stocks["mapping_source"] = "taxonomy_rule"
    for ticker, etf in OVERRIDES.items():
        mask = stocks["ticker"].eq(ticker)
        stocks.loc[mask, "sector_etf"] = etf
        stocks.loc[mask, "mapping_source"] = "documented_override"
    missing = stocks.loc[stocks["sector_etf"].isna(), "ticker"].tolist()
    invalid = sorted(set(stocks["sector_etf"].dropna()) - set(ETF_TICKERS))
    if missing or invalid:
        raise ValueError(f"Sector mapping incomplete. Missing={missing}, invalid={invalid}")
    return stocks.reset_index(drop=True)


def ar1_s_score(stock_returns: np.ndarray, etf_returns: np.ndarray, max_days: int) -> tuple[float, float, float]:
    """Return raw equilibrium mean m, equilibrium sigma, and hedge beta."""
    valid = np.isfinite(stock_returns) & np.isfinite(etf_returns)
    y, x = stock_returns[valid], etf_returns[valid]
    if len(y) < 50 or np.var(x) <= 1e-14:
        return np.nan, np.nan, np.nan
    design = np.column_stack([np.ones(len(x)), x])
    alpha, beta = np.linalg.lstsq(design, y, rcond=None)[0]
    residual = y - alpha - beta * x
    cumulative = np.cumsum(residual)
    lag, lead = cumulative[:-1], cumulative[1:]
    if np.var(lag) <= 1e-14:
        return np.nan, np.nan, np.nan
    a, b = np.linalg.lstsq(np.column_stack([np.ones(len(lag)), lag]), lead, rcond=None)[0]
    b_limit = math.exp(-1.0 / max_days)
    if not (0.0 < b < b_limit):
        return np.nan, np.nan, float(beta)
    innovation = lead - a - b * lag
    innovation_var = np.var(innovation, ddof=1)
    if innovation_var <= 0 or (1.0 - b * b) <= 0:
        return np.nan, np.nan, float(beta)
    equilibrium_mean = a / (1.0 - b)
    equilibrium_sigma = math.sqrt(innovation_var / (1.0 - b * b))
    return float(equilibrium_mean), float(equilibrium_sigma), float(beta)


def calculate_signals(close: pd.DataFrame, sector_map: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    returns = close.pct_change(fill_method=None)
    stocks = sector_map["ticker"].tolist()
    etf_for = sector_map.set_index("ticker")["sector_etf"].to_dict()
    dates = returns.index
    scores = pd.DataFrame(np.nan, index=dates, columns=stocks)
    betas = pd.DataFrame(np.nan, index=dates, columns=stocks)
    lookback = int(cfg["lookback_days"])
    for i in range(lookback, len(dates)):
        m_values, sigma_values, beta_values = {}, {}, {}
        window = returns.iloc[i - lookback + 1:i + 1]
        for stock in stocks:
            m, sigma, beta = ar1_s_score(
                window[stock].to_numpy(), window[etf_for[stock]].to_numpy(),
                int(cfg["max_mean_reversion_days"]),
            )
            m_values[stock], sigma_values[stock], beta_values[stock] = m, sigma, beta
        valid_m = np.array([v for v in m_values.values() if np.isfinite(v)])
        if len(valid_m) == 0:
            continue
        mean_m = float(valid_m.mean())
        for stock in stocks:
            m, sigma = m_values[stock], sigma_values[stock]
            if np.isfinite(m) and np.isfinite(sigma) and sigma > 0:
                scores.at[dates[i], stock] = -(m - mean_m) / sigma
                betas.at[dates[i], stock] = beta_values[stock]
    return scores, betas


def clean_option_flow(path: Path, dates: pd.DatetimeIndex, cfg: dict) -> tuple[pd.DataFrame, dict]:
    sheets = []
    input_rows = 0
    for sheet_name in ["Flow Analytics (Stocks)", "Flow Analytics (ETFs)"]:
        frame = pd.read_excel(path, sheet_name=sheet_name, header=4, usecols="A:J")
        frame = frame.dropna(how="all")
        input_rows += len(frame)
        frame["source_sheet"] = sheet_name
        sheets.append(frame)
    flow = pd.concat(sheets, ignore_index=True)
    before_dedup = len(flow)
    flow = flow.drop_duplicates()
    required = ["Date", "Symbol", "DTE", "Side", "Sentiment", "Premium", "Quantity", "Open Interest"]
    missing = [column for column in required if column not in flow.columns]
    if missing:
        raise ValueError(f"External flow columns missing: {missing}")
    flow["Date"] = pd.to_datetime(flow["Date"], errors="coerce").dt.normalize()
    for column in ["DTE", "Premium", "Quantity", "Open Interest"]:
        flow[column] = pd.to_numeric(flow[column], errors="coerce")
    flow["Symbol"] = flow["Symbol"].astype(str).str.upper().str.strip()
    side_ok = flow["Side"].astype(str).str.lower().str.contains("ask", na=False)
    sentiment = flow["Sentiment"].astype(str).str.upper().str.strip()
    is_sector_etf = flow["Symbol"].isin(ETF_TICKERS)
    source_ok = np.where(
        is_sector_etf,
        flow["source_sheet"].eq("Flow Analytics (ETFs)"),
        flow["source_sheet"].eq("Flow Analytics (Stocks)"),
    )
    mask = (
        source_ok
        & side_ok
        & flow["Premium"].ge(cfg["flow_min_premium"])
        & flow["Quantity"].gt(flow["Open Interest"])
        & flow["DTE"].between(cfg["flow_min_dte"], cfg["flow_max_dte"])
        & sentiment.isin(["BULLISH", "BEARISH"])
    )
    selected = flow.loc[mask].copy()
    selected["signed_premium"] = np.where(sentiment.loc[mask].eq("BULLISH"), selected["Premium"], -selected["Premium"])
    daily = selected.groupby(["Date", "Symbol"])["signed_premium"].sum().unstack().fillna(0.0).astype(float)
    daily = daily.reindex(dates, fill_value=0.0)
    daily = daily.rolling(int(cfg["flow_aggregation_days"]), min_periods=1).sum()
    lookback = int(cfg["flow_z_lookback"])
    minimum = int(cfg["flow_z_min_periods"])
    history_mean = daily.rolling(lookback, min_periods=minimum).mean().shift(1)
    history_std = daily.rolling(lookback, min_periods=minimum).std(ddof=1).shift(1).replace(0, np.nan)
    z_scores = ((daily - history_mean) / history_std).clip(-5, 5)
    diagnostics = {
        "input_rows": int(input_rows),
        "exact_duplicate_rows_removed": int(before_dedup - len(flow)),
        "rows_after_quality_filters": int(len(selected)),
        "selected_premium_usd": float(selected["Premium"].sum()),
        "first_flow_date": str(selected["Date"].min().date()) if len(selected) else None,
        "last_flow_date": str(selected["Date"].max().date()) if len(selected) else None,
        "filters": "source-sheet validation; ask-side; premium floor; quantity > open interest; 180-730 DTE; bullish/bearish; five-day aggregation",
    }
    return z_scores, diagnostics


def relative_flow_scores(flow_z: pd.DataFrame, sector_map: pd.DataFrame) -> pd.DataFrame:
    relative = pd.DataFrame(np.nan, index=flow_z.index, columns=sector_map["ticker"])
    mapping = sector_map.set_index("ticker")["sector_etf"].to_dict()
    for stock, etf in mapping.items():
        if stock in flow_z.columns and etf in flow_z.columns:
            relative[stock] = flow_z[stock] - flow_z[etf]
    return relative


def state_positions(
    scores: pd.DataFrame,
    cfg: dict,
    relative_flow: pd.DataFrame | None = None,
    entry_margin: float = 0.0,
) -> pd.DataFrame:
    positions = pd.DataFrame(0.0, index=scores.index, columns=scores.columns)
    state = pd.Series(0.0, index=scores.columns)
    threshold = float(cfg["flow_confirmation_z"])
    for date in scores.index:
        today = scores.loc[date]
        for stock in scores.columns:
            score = today[stock]
            old = state[stock]
            if not np.isfinite(score):
                state[stock] = 0.0
            elif old > 0 and score > cfg["exit_long_s"]:
                state[stock] = 0.0
            elif old < 0 and score < cfg["exit_short_s"]:
                state[stock] = 0.0
            elif old == 0:
                flow_value = np.nan if relative_flow is None else relative_flow.at[date, stock]
                long_confirmed = relative_flow is None or (np.isfinite(flow_value) and flow_value > threshold)
                short_confirmed = relative_flow is None or (np.isfinite(flow_value) and flow_value < -threshold)
                if score < cfg["entry_long_s"] - entry_margin and long_confirmed:
                    state[stock] = 1.0
                elif score > cfg["entry_short_s"] + entry_margin and short_confirmed:
                    state[stock] = -1.0
        positions.loc[date] = state
    return positions


def target_weights(states: pd.DataFrame, betas: pd.DataFrame, sector_map: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    stocks = states.columns.tolist()
    weights = pd.DataFrame(0.0, index=states.index, columns=stocks + ETF_TICKERS)
    stock_weight = float(cfg["stock_weight"])
    mapping = sector_map.set_index("ticker")["sector_etf"].to_dict()
    for date in states.index:
        stock_targets = states.loc[date] * stock_weight
        weights.loc[date, stocks] = stock_targets
        for stock in stocks:
            beta = betas.at[date, stock]
            if stock_targets[stock] != 0 and np.isfinite(beta):
                weights.at[date, mapping[stock]] -= stock_targets[stock] * beta
        gross = weights.loc[date].abs().sum()
        if gross > cfg["gross_cap"]:
            weights.loc[date] *= cfg["gross_cap"] / gross
    return weights


def apply_no_trade_buffer(target: pd.DataFrame, buffer: float, gross_cap: float | None = None) -> pd.DataFrame:
    actual = pd.DataFrame(0.0, index=target.index, columns=target.columns)
    previous = pd.Series(0.0, index=target.columns)
    for date in target.index:
        desired = target.loc[date]
        mandatory = desired.eq(0) | previous.eq(0) | (np.sign(desired) != np.sign(previous))
        update = mandatory | desired.sub(previous).abs().ge(buffer)
        previous = previous.where(~update, desired)
        if gross_cap is not None and previous.abs().sum() > gross_cap:
            previous *= gross_cap / previous.abs().sum()
        actual.loc[date] = previous
    return actual


def backtest(weights: pd.DataFrame, close: pd.DataFrame, sofr: pd.Series, cost_bps: float,
             short_spread_pct: float = .5) -> pd.DataFrame:
    """Self-financing close ledger with a full prior-close information lag.

    ``weights[t]`` is formed using close t, executed at close t+1, and first
    earns the t+1-to-t+2 return. Trading fees hit the actual execution date.
    Holdings drift between trades. Missing execution quotes defer that asset's
    trade; existing shares keep their last mark until a fresh quote catches up.
    Targets are fractions of NAV after fees, solved jointly with those fees.
    Cash earns zero; the assignment's SOFR+spread accrues on short notional.
    """
    if cost_bps < 0 or not np.isfinite(cost_bps):
        raise ValueError("Per-side transaction cost must be finite and nonnegative")
    if weights.isna().any().any() or not np.isfinite(weights.to_numpy()).all():
        raise ValueError("Target weights must be finite")
    quotes = close.reindex(index=weights.index, columns=weights.columns)
    available = quotes.gt(0) & np.isfinite(quotes)
    marks = quotes.where(available).ffill()
    asset_returns = marks.pct_change(fill_method=None).fillna(0.0).to_numpy()
    desired = weights.shift(1).fillna(0.0).to_numpy()
    executable = available.to_numpy()
    rate = calendar_short_rates(weights.index, sofr, short_spread_pct).to_numpy()
    fee_rate = float(cost_bps) / 10000.0
    nav, values = 1.0, np.zeros(len(weights.columns))
    rows, actual_weights = [], []
    for i, date in enumerate(weights.index):
        prior_nav = nav
        held = values / prior_nav
        gross_pnl = float(values @ asset_returns[i])
        financing = float(np.maximum(-values, 0).sum() * rate[i])
        marked = values * (1.0 + asset_returns[i])
        pre_trade_nav = prior_nav + gross_pnl - financing
        if pre_trade_nav <= 0:
            raise ValueError(f"Portfolio insolvent on {date.date()}")
        can_trade = executable[i]
        target = desired[i]
        if fee_rate * np.abs(target[can_trade]).sum() >= 1:
            raise ValueError("Transaction costs and target leverage do not admit a stable NAV solution")
        post_nav = pre_trade_nav
        for _ in range(100):
            traded = np.where(can_trade, target * post_nav - marked, 0.0)
            fees = float(np.abs(traded).sum() * fee_rate)
            new_nav = pre_trade_nav - fees
            if abs(new_nav - post_nav) <= 1e-13 * prior_nav:
                post_nav = new_nav
                break
            post_nav = new_nav
        else:
            raise RuntimeError("Post-fee NAV did not converge")
        if post_nav <= 0:
            raise ValueError(f"Trading costs exhaust NAV on {date.date()}")
        values = np.where(can_trade, target * post_nav, marked)
        traded = values - marked
        fees = float(np.abs(traded).sum() * fee_rate)
        nav = pre_trade_nav - fees
        missing_orders = ~can_trade & (np.abs(target * nav - marked) > 1e-12 * nav)
        rows.append({
            "gross_return": gross_pnl / prior_nav,
            "turnover": float(np.abs(traded).sum() / prior_nav),
            "transaction_cost": fees / prior_nav,
            "short_financing": financing / prior_nav,
            "net_return": nav / prior_nav - 1.0,
            "gross_exposure": float(np.abs(held).sum()),
            "net_exposure": float(held.sum()),
            "active_positions": int(np.count_nonzero(held)),
            "unavailable_orders": int(missing_orders.sum()),
            "stale_positions": int((~can_trade & (np.abs(marked) > 1e-12 * nav)).sum()),
            "post_trade_gross_exposure": float(np.abs(values).sum() / nav),
            "cash_weight": float(1.0 - values.sum() / nav),
            "equity": nav,
        })
        actual_weights.append(values / nav)
    result = pd.DataFrame(rows, index=weights.index)
    result.attrs["executed_weights"] = pd.DataFrame(actual_weights, index=weights.index, columns=weights.columns)
    return result


def performance_metrics(result: pd.DataFrame, states: pd.DataFrame, start: str, end: str) -> dict:
    frame = result.loc[start:end].dropna(subset=["net_return"])
    returns = frame["net_return"]
    gross_returns = frame["gross_return"]
    years = len(returns) / 252.0
    total = float((1.0 + returns).prod() - 1.0)
    annual_return = float((1.0 + total) ** (1.0 / years) - 1.0) if years > 0 and total > -1 else np.nan
    annual_vol = float(returns.std(ddof=1) * math.sqrt(252))
    sharpe = float(returns.mean() / returns.std(ddof=1) * math.sqrt(252)) if returns.std(ddof=1) > 0 else np.nan
    equity = (1.0 + returns).cumprod()
    max_drawdown = float((equity / equity.cummax().clip(lower=1.0) - 1.0).min())
    active_days = returns.ne(0)
    trade_states = states.loc[start:end]
    runs = []
    for stock in trade_states.columns:
        values = trade_states[stock].to_numpy()
        length = 0
        previous = 0
        for value in values:
            if value != 0 and value == previous:
                length += 1
            else:
                if previous != 0 and length:
                    runs.append(length)
                length = 1 if value != 0 else 0
            previous = value
        if previous != 0 and length:
            runs.append(length)
    return {
        "gross_annual_return": float((1.0 + gross_returns).prod() ** (252.0 / len(gross_returns)) - 1.0) if len(gross_returns) else np.nan,
        "gross_sharpe": float(gross_returns.mean() / gross_returns.std(ddof=1) * math.sqrt(252)) if gross_returns.std(ddof=1) > 0 else np.nan,
        "annual_return": annual_return,
        "annual_volatility": annual_vol,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "positive_day_rate": float((returns[active_days] > 0).mean()) if active_days.any() else np.nan,
        "average_daily_turnover": float(frame["turnover"].mean()),
        "total_transaction_cost": float(frame["transaction_cost"].sum()),
        "total_short_financing": float(frame["short_financing"].sum()),
        "average_gross_exposure": float(frame["gross_exposure"].mean()),
        "average_active_positions": float(frame["active_positions"].mean()),
        "average_holding_days": float(np.mean(runs)) if runs else np.nan,
        "observations": int(len(frame)),
    }


def make_equity_chart(results: dict[str, pd.DataFrame], start: str, end: str, path: Path,
                      title: str = "2025 out-of-sample equity (after costs)") -> None:
    width, height, margin = 1200, 700, 90
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=20)
    small = ImageFont.load_default(size=16)
    curves = {}
    for name, result in results.items():
        returns = result.loc[start:end, "net_return"].fillna(0.0)
        curves[name] = (1.0 + returns).cumprod()
    all_values = np.concatenate([curve.to_numpy() for curve in curves.values()])
    if not len(all_values):
        draw.text((margin, margin), "No prices available for this period", fill="black", font=font)
        image.save(path)
        return
    y_min, y_max = float(all_values.min()), float(all_values.max())
    padding = max((y_max - y_min) * 0.08, 0.01)
    y_min, y_max = y_min - padding, y_max + padding
    draw.text((margin, 24), title, fill="black", font=font)
    draw.line((margin, height - margin, width - margin, height - margin), fill="black", width=2)
    draw.line((margin, margin, margin, height - margin), fill="black", width=2)
    colors = {"baseline": "#315E9D", "buffer": "#E08B2C", "flow_gate": "#2A8F5B"}
    for j in range(5):
        value = y_min + (y_max - y_min) * j / 4
        y = height - margin - (height - 2 * margin) * j / 4
        draw.line((margin, y, width - margin, y), fill="#dddddd", width=1)
        draw.text((12, y - 9), f"{value:.2f}", fill="black", font=small)
    for name, curve in curves.items():
        values = curve.to_numpy()
        points = []
        for i, value in enumerate(values):
            x = margin + (width - 2 * margin) * i / max(len(values) - 1, 1)
            y = height - margin - (height - 2 * margin) * (value - y_min) / (y_max - y_min)
            points.append((x, y))
        if len(points) > 1:
            draw.line(points, fill=colors[name], width=4)
        lx, ly = width - 340, 30 + 28 * list(curves).index(name)
        draw.line((lx, ly + 8, lx + 38, ly + 8), fill=colors[name], width=4)
        draw.text((lx + 50, ly), name, fill="black", font=small)
    image.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the compact statistical-arbitrage study.")
    parser.add_argument("--skip-flow", action="store_true", help="Run price-based models and the supplied SPY comparison; skip proprietary evidence and PDF generation.")
    parser.add_argument("--evaluation-date", help="Last input date to use (YYYY-MM-DD); defaults to the last supplied price date. 2026+ results are separate continuation evidence.")
    args = parser.parse_args()
    evaluation_date = None
    if args.evaluation_date is not None:
        try:
            evaluation_date = pd.Timestamp(args.evaluation_date).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            parser.error("--evaluation-date must be a valid YYYY-MM-DD date")
    RESULTS.mkdir(exist_ok=True)
    cfg = load_config()
    universe, close, open_, volume, sofr = load_official_data(evaluation_date)
    if close.empty or close.isna().all(axis=1).any() or not close.index.is_monotonic_increasing:
        raise ValueError("Official close-price panel failed validation.")
    evaluation_date = str(close.index.max().date())
    periods = [
        ("development", str(close.index.min().date()), cfg["development_end"]),
        ("out_of_sample", cfg["out_of_sample_start"], cfg["out_of_sample_end"]),
    ]
    continuation_start = str((pd.Timestamp(cfg["out_of_sample_end"]) + pd.Timedelta(days=1)).date())
    if close.index.max() >= pd.Timestamp(continuation_start):
        periods.append(("continuation", continuation_start, evaluation_date))
    sector_map = build_sector_map(universe)
    sector_map.to_csv(RESULTS / "sector_map.csv", index=False)
    scores, betas = calculate_signals(close, sector_map, cfg)
    baseline_states = state_positions(scores, cfg)
    replication_daily = pd.DataFrame({
        "valid_mean_reversion_models": scores.notna().sum(axis=1),
        "long_entry_candidates": scores.lt(float(cfg["entry_long_s"])).sum(axis=1),
        "short_entry_candidates": scores.gt(float(cfg["entry_short_s"])).sum(axis=1),
        "median_absolute_s_score": scores.abs().median(axis=1),
        "mean_valid_beta": betas.where(scores.notna()).mean(axis=1),
    })
    replication_daily.to_csv(RESULTS / "replication_diagnostics.csv")
    baseline_target = target_weights(baseline_states, betas, sector_map, cfg)
    buffered_states = state_positions(scores, cfg, entry_margin=float(cfg["entry_no_trade_s"]))
    buffered_target = target_weights(buffered_states, betas, sector_map, cfg)
    buffered_weights = apply_no_trade_buffer(buffered_target, float(cfg["no_trade_buffer"]), float(cfg["gross_cap"]))
    strategy_weights = {"baseline": baseline_target, "buffer": buffered_weights}
    strategy_states = {"baseline": baseline_states, "buffer": buffered_states}
    flow_diagnostics = {"status": "skipped"}
    if not args.skip_flow and not EXTERNAL.exists():
        raise SystemExit(
            f"\nThe proprietary option-flow workbook is not present at:\n    {EXTERNAL}\n\n"
            "The price-based models and supplied SPY comparison can run without the\n"
            "proprietary evidence workbooks. This mode skips the full PDF:\n\n"
            "    python run.py --skip-flow\n")
    if not args.skip_flow:
        flow_z, flow_diagnostics = clean_option_flow(EXTERNAL, close.index, cfg)
        relative = relative_flow_scores(flow_z, sector_map)
        flow_states = state_positions(scores, cfg, relative, entry_margin=float(cfg["entry_no_trade_s"]))
        flow_target = target_weights(flow_states, betas, sector_map, cfg)
        strategy_weights["flow_gate"] = apply_no_trade_buffer(flow_target, float(cfg["no_trade_buffer"]), float(cfg["gross_cap"]))
        strategy_states["flow_gate"] = flow_states
        relative.to_csv(RESULTS / "relative_flow_scores.csv.gz", compression="gzip")
    all_results, rows = {}, []
    for name, weights in strategy_weights.items():
        result = backtest(weights, close, sofr, float(cfg["transaction_cost_bps"]), float(cfg["short_spread_pct"]))
        all_results[name] = result
        weights.to_csv(RESULTS / f"signal_targets_{name}.csv.gz", compression="gzip")
        actual = result.attrs["executed_weights"]
        actual.to_csv(RESULTS / f"weights_{name}.csv.gz", compression="gzip")
        result.to_csv(RESULTS / f"daily_{name}.csv")
        actual_stock_states = np.sign(actual.reindex(columns=sector_map["ticker"]))
        for period, start, end in periods:
            metrics = performance_metrics(result, actual_stock_states, start, end)
            rows.append({"strategy": name, "period": period, **metrics})
    metrics_frame = pd.DataFrame(rows)
    metrics_frame.to_csv(RESULTS / "metrics.csv", index=False)
    replication_summary = {}
    for period, start, end in periods:
        diag = replication_daily.loc[start:end]
        states = baseline_states.loc[start:end]
        entries = states.ne(0) & states.shift(1).fillna(0).eq(0)
        replication_summary[period] = {
            "average_valid_mean_reversion_models": float(diag["valid_mean_reversion_models"].mean()),
            "median_valid_mean_reversion_models": float(diag["valid_mean_reversion_models"].median()),
            "average_long_entry_candidates": float(diag["long_entry_candidates"].mean()),
            "average_short_entry_candidates": float(diag["short_entry_candidates"].mean()),
            "total_new_stock_entries": int(entries.sum().sum()),
            "average_valid_beta": float(diag["mean_valid_beta"].mean()),
        }
    (RESULTS / "replication_summary.json").write_text(json.dumps(replication_summary, indent=2), encoding="utf-8")
    (RESULTS / "flow_diagnostics.json").write_text(json.dumps(flow_diagnostics, indent=2), encoding="utf-8")
    sensitivity = []
    for bps in [10, 20, 30, 40]:
        for name, weights in strategy_weights.items():
            result = backtest(weights, close, sofr, float(bps), float(cfg["short_spread_pct"]))
            actual_states = np.sign(result.attrs["executed_weights"].reindex(columns=sector_map["ticker"]))
            metric = performance_metrics(result, actual_states, cfg["out_of_sample_start"], cfg["out_of_sample_end"])
            sensitivity.append({"strategy": name, "cost_bps": bps, **metric})
    pd.DataFrame(sensitivity).to_csv(RESULTS / "cost_sensitivity.csv", index=False)
    make_equity_chart(all_results, cfg["out_of_sample_start"], cfg["out_of_sample_end"], RESULTS / "oos_equity.png")
    make_equity_chart(all_results, str(close.index.min().date()), evaluation_date,
                      RESULTS / "full_period_equity.png", "Full-period equity (after costs; development / 2025 / continuation)")
    summary = {
        "official_price_dates": [str(close.index.min().date()), str(close.index.max().date())],
        "stock_count": int(len(sector_map)),
        "etf_count": int(len(ETF_TICKERS)),
        "missing_close_observations": int(close.isna().sum().sum()),
        "missing_close_handling": "Pairwise regressions use available observations. No execution without a positive current quote. Existing shares retain their last mark and catch up when the next quote arrives.",
        "corporate_actions": close.attrs["corporate_action_audit"],
        "requested_evaluation_date": args.evaluation_date,
        "effective_evaluation_date": evaluation_date,
        "continuation_status": "available" if len(periods) > 2 else "No supplied prices after 2025; no 2026 trading result is claimed.",
        "short_financing_convention": "ACT/360; sum SOFR+0.5 percentage points for each calendar day from previous close inclusive to current close exclusive, on previous close short notional.",
        "cash_return_assumption": "0%; dividends and interest on cash balances excluded; official prices are split-adjusted price returns.",
        "execution_accounting": "Trades versus drifted signed holdings; target weights are fractions of post-fee NAV. Fees charged at execution close, including first entry and all rebalancing. Final positions marked, not forcibly liquidated.",
        "unavailable_orders": {name: int(result["unavailable_orders"].sum()) for name, result in all_results.items()},
        "strategies_run": list(strategy_weights),
        "note": "Signals formed at close t execute at close t+1 and first earn the close t+1 to close t+2 return.",
    }
    (RESULTS / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    from overnight_backtest import main as build_overnight_report
    build_overnight_report(evaluation_date=evaluation_date)
    from overnight_strategy_v6 import main as build_gated_strategy
    build_gated_strategy(evaluation_date=evaluation_date)
    if not args.skip_flow:
        from evidence_summary import main as build_evidence
        build_evidence()
        from build_report import main as build_pdf
        build_pdf()
    print(metrics_frame.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"\nResults written to {RESULTS}")


if __name__ == "__main__":
    main()
