"""Backtest a close-to-next-open portfolio of ten momentum stocks versus SPY.

The signal is intentionally lagged: the ranking used for an entry at close t is
calculated with prices available through close t-1. This avoids assuming the
final closing price was known before a closing-auction order was submitted.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from data_quality import load_price_frame
from overnight_execution import ranked_roster, simulate_roster, reporting_periods


ROOT = Path(__file__).resolve().parent
OFFICIAL = ROOT / "data" / "official"
SPY_FILE = ROOT / "data" / "external" / "spy_nasdaq_2023_2025.csv"
SP500_FILE = ROOT / "data" / "external" / "sp500_constituents_2025-01-02.csv"
CONFIG_FILE = ROOT / "overnight_config.json"
RESULTS = ROOT / "results"


def load_config() -> dict:
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def load_stock_panels() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    universe = pd.read_csv(OFFICIAL / "universe.csv")
    tickers = universe.loc[universe["category"].eq("equity"), "ticker"].tolist()
    opens: dict[str, pd.Series] = {}
    closes: dict[str, pd.Series] = {}
    for ticker in tickers:
        frame = load_price_frame(OFFICIAL / "prices" / f"{ticker}.csv", ticker=ticker)
        opens[ticker] = pd.to_numeric(frame["open"], errors="coerce")
        closes[ticker] = pd.to_numeric(frame["close"], errors="coerce")
    return pd.DataFrame(opens).sort_index(), pd.DataFrame(closes).sort_index(), tickers


def load_spy() -> pd.DataFrame:
    if not SPY_FILE.exists():
        raise FileNotFoundError("SPY data is missing. Run: python download_spy.py")
    frame = pd.read_csv(SPY_FILE, parse_dates=["date"]).set_index("date").sort_index()
    required = {"open", "close"}
    if not required.issubset(frame.columns):
        raise ValueError(f"SPY data must contain {sorted(required)}")
    return frame


def calculate_momentum(close: pd.DataFrame, lookback: int, lag: int) -> pd.DataFrame:
    if lookback <= 0 or lag < 1:
        raise ValueError("lookback must be positive and signal lag must be at least one day")
    return close.pct_change(lookback, fill_method=None).shift(lag)


def select_top_names(signal: pd.Series, entry_close: pd.Series, top_n: int) -> list[str]:
    valid = signal.replace([np.inf, -np.inf], np.nan).dropna()
    valid = valid.loc[entry_close.reindex(valid.index).gt(0).fillna(False)]
    return valid.nlargest(top_n).index.tolist()


def close_to_open_return(entry_close: pd.Series, next_open: pd.Series) -> pd.Series:
    return next_open / entry_close - 1.0


def build_daily_and_trades(
    open_: pd.DataFrame,
    close: pd.DataFrame,
    spy: pd.DataFrame,
    cfg: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    lookback, lag, top_n = int(cfg["momentum_lookback_days"]), int(cfg["signal_lag_days"]), int(cfg["top_n"])
    momentum = calculate_momentum(close, lookback, lag)
    selected = ranked_roster(momentum, top_n)
    # Sub-ten-name variants are explicitly labelled concentration diagnostics.
    max_weight = max(.1, 1/top_n)
    gross_book, trades = simulate_roster(open_, close, selected, n=top_n, max_weight=max_weight)
    available_dates = gross_book.index[gross_book.selected_count.gt(0)]
    start = available_dates[0] if len(available_dates) else gross_book.index[0]
    daily = gross_book.loc[start:].rename(columns={"return": "basket_overnight_gross"}).copy()
    requested_cost = 2*float(cfg["transaction_cost_bps_per_side"])
    for rt in sorted({0, 2, 5, 6, 8, 9, 10, 20, 40, requested_cost}):
        book = gross_book if rt == 0 else simulate_roster(open_, close, selected,
            n=top_n, max_weight=max_weight, round_trip_bp=rt)[0]
        daily[f"net_rt_{rt:g}bp"] = book["return"].reindex(daily.index)
    rt = 2*float(cfg["transaction_cost_bps_per_side"])
    daily["basket_overnight_net"] = daily[f"net_rt_{rt:g}bp"]
    daily["round_trip_cost"] = rt/10000
    daily["average_signal_momentum"] = momentum.where(selected).mean(axis=1).reindex(daily.index)
    benchmark = spy.reindex(close.index)
    spy_overnight = benchmark.open.shift(-1) / benchmark.close - 1
    spy_daytime = benchmark.close.shift(-1) / benchmark.open.shift(-1) - 1
    daily["spy_overnight_gross"] = spy_overnight.reindex(daily.index)
    side = rt/20000
    daily["spy_overnight_net"] = (1+daily.spy_overnight_gross)*(1-side)/(1+side)-1
    daily["spy_next_daytime_gross"] = spy_daytime.reindex(daily.index)
    # A gross equal-weight reference follows the same missing-quote policy.
    universe, _ = simulate_roster(open_, close, pd.DataFrame(True, index=close.index, columns=close.columns),
                                  n=len(close.columns), max_weight=1/len(close.columns))
    daily["universe_overnight_gross"] = universe["return"].reindex(daily.index)
    daytime = close.shift(-1)/open_.shift(-1)-1
    # This hypothetical decomposition is diagnostic only. Unknown selected
    # daytime returns remain unknown instead of survivor reweighting.
    selected_day = daytime.where(selected, 0)
    daily["basket_next_daytime_gross"] = selected_day.sum(axis=1, skipna=False).div(top_n).reindex(daily.index)
    daily["basket_minus_spy_gross"] = daily.basket_overnight_gross-daily.spy_overnight_gross
    daily["basket_net_minus_spy_gross"] = daily.basket_overnight_net-daily.spy_overnight_gross
    if len(trades):
        trades["momentum_signal"] = [momentum.at[d, t] for d,t in zip(trades.entry_date, trades.ticker)]
    daily["entry_date"] = daily.index
    daily.index = pd.DatetimeIndex(daily.exit_date, name="date")
    return daily, trades


def maximum_drawdown(returns: pd.Series) -> float:
    equity = (1.0 + returns.fillna(0.0)).cumprod()
    return float((equity / equity.cummax().clip(lower=1.0) - 1.0).min())


def series_metrics(returns: pd.Series) -> dict:
    values = returns.replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return {"observations": 0, **{key: np.nan for key in (
            "total_return", "annualized_return", "annualized_volatility", "sharpe_zero_rate",
            "maximum_drawdown", "win_rate", "average_return", "median_return",
            "standard_deviation", "profit_factor", "best_return", "worst_return")}}
    total = float((1.0 + values).prod() - 1.0)
    years = len(values) / 252.0
    standard_deviation = float(values.std(ddof=1))
    gains = float(values.loc[values > 0].sum())
    losses = float(-values.loc[values < 0].sum())
    return {
        "observations": int(len(values)),
        "total_return": total,
        "annualized_return": float((1.0 + total) ** (1.0 / years) - 1.0) if total > -1 and years > 0 else np.nan,
        "annualized_volatility": standard_deviation * math.sqrt(252.0),
        "sharpe_zero_rate": float(values.mean() / standard_deviation * math.sqrt(252.0)) if standard_deviation > 0 else np.nan,
        "maximum_drawdown": maximum_drawdown(values),
        "win_rate": float(values.gt(0).mean()),
        "average_return": float(values.mean()),
        "median_return": float(values.median()),
        "standard_deviation": standard_deviation,
        "profit_factor": gains / losses if losses > 0 else np.nan,
        "best_return": float(values.max()),
        "worst_return": float(values.min()),
    }


def build_metrics(daily: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    periods = {
        "development": (cfg["development_start"], cfg["development_end"]),
        "evaluation_2025": (cfg["evaluation_start"], cfg["evaluation_end"]),
    }
    if len(daily) and daily.index.max() > pd.Timestamp(cfg["evaluation_end"]):
        periods["continuation"] = (str((pd.Timestamp(cfg["evaluation_end"])+pd.Timedelta(days=1)).date()),
                                   str(daily.index.max().date()))
    strategies = {
        "top10_overnight_gross": "basket_overnight_gross",
        "top10_overnight_net": "basket_overnight_net",
        "spy_overnight_gross": "spy_overnight_gross",
        "spy_overnight_net": "spy_overnight_net",
        "eligible_universe_overnight_gross": "universe_overnight_gross",
        "top10_minus_spy_gross": "basket_minus_spy_gross",
        "top10_net_minus_spy_gross": "basket_net_minus_spy_gross",
        "top10_next_daytime_gross": "basket_next_daytime_gross",
    }
    rows: list[dict] = []
    for period, (start, end) in periods.items():
        subset = daily.loc[start:end]
        for strategy, column in strategies.items():
            complete = bool(subset[column].notna().all())
            # Do not compound an incomplete benchmark as if it covered a full period.
            stats = series_metrics(subset[column]) if complete else series_metrics(pd.Series(dtype=float))
            rows.append({"period": period, "strategy": strategy, "coverage_complete": complete,
                         "calendar_sessions": len(subset), **stats})
    return pd.DataFrame(rows)


def build_cost_sensitivity(daily: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    sample = daily.loc[cfg["evaluation_start"]:cfg["evaluation_end"]]
    rows: list[dict] = []
    for per_side_bp in [0.0, 1.0, 2.5, 4.0, 5.0, 10.0, 20.0]:
        returns = sample[f"net_rt_{2*per_side_bp:g}bp"]
        rows.append({"cost_per_side_bp": per_side_bp, **series_metrics(returns)})
    return pd.DataFrame(rows)


def build_monthly(daily: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    columns = [
        "basket_overnight_gross",
        "basket_overnight_net",
        "spy_overnight_gross",
        "basket_minus_spy_gross",
    ]
    evaluation = daily.loc[cfg["evaluation_start"]:cfg["evaluation_end"], columns]
    monthly = evaluation.groupby(evaluation.index.to_period("M")).apply(lambda frame: (1.0 + frame).prod() - 1.0)
    monthly.index = monthly.index.astype(str)
    monthly.index.name = "month"
    return monthly


def build_breadth_sensitivity(
    open_: pd.DataFrame,
    close: pd.DataFrame,
    spy: pd.DataFrame,
    cfg: dict,
    top10_daily: pd.DataFrame,
) -> pd.DataFrame:
    """Compare portfolio breadth without changing the frozen top-ten test.

    The one-, two-, three- and five-name variants are post-hoc sensitivity
    checks. The SPY-hedged result assumes a 100% long basket and a 100% short
    SPY leg; costs therefore apply to four sides per night.
    """
    per_side_cost = float(cfg["transaction_cost_bps_per_side"]) / 10_000.0
    rows: list[dict] = []
    for top_n in [1, 2, 3, 5, 10]:
        if top_n == int(cfg["top_n"]):
            daily = top10_daily
        else:
            variant_cfg = {**cfg, "top_n": top_n}
            daily, _ = build_daily_and_trades(open_, close, spy, variant_cfg)
        evaluation = daily.loc[cfg["evaluation_start"]:cfg["evaluation_end"]]
        gross = series_metrics(evaluation["basket_overnight_gross"])
        net = series_metrics(evaluation["basket_overnight_net"])
        hedged_gross_returns = (
            evaluation["basket_overnight_gross"] - evaluation["spy_overnight_gross"]
        )
        hedged_gross = series_metrics(hedged_gross_returns)
        rows.append(
            {
                "top_n": top_n,
                "live_name_cap_compliant": top_n >= 10,
                "hedge_diagnostic_note": "Gross synthetic long-minus-SPY spread; not executable portfolio NAV",
                "observations": gross["observations"],
                "gross_total_return": gross["total_return"],
                "gross_sharpe": gross["sharpe_zero_rate"],
                "gross_maximum_drawdown": gross["maximum_drawdown"],
                "gross_average_return_bp": gross["average_return"] * 10_000.0,
                "gross_break_even_cost_per_side_bp": gross["average_return"] * 5_000.0,
                "gross_worst_night": gross["worst_return"],
                "net_total_return_20bp_per_side": net["total_return"],
                "spy_hedged_gross_total_return": hedged_gross["total_return"],
                "spy_hedged_gross_sharpe": hedged_gross["sharpe_zero_rate"],
                "spy_hedged_gross_maximum_drawdown": hedged_gross["maximum_drawdown"],
            }
        )
    return pd.DataFrame(rows)


def build_mu_audit(
    open_: pd.DataFrame,
    close: pd.DataFrame,
    spy: pd.DataFrame,
    top10_trades: pd.DataFrame,
    cfg: dict,
) -> pd.DataFrame:
    """Audit the viral MU-only idea as a disclosed post-hoc case study."""
    if "MU" not in close.columns:
        raise ValueError("MU is not available in the supplied equity universe")
    selected_dates = set(pd.to_datetime(top10_trades.loc[top10_trades.ticker.eq("MU"), "entry_date"]))
    output = []
    for sample in ("MU_every_night", "MU_only_when_in_top10_momentum"):
        gate = pd.Series(True, index=close.index) if sample == "MU_every_night" else pd.Series(close.index.isin(selected_dates), index=close.index)
        selected = pd.DataFrame(True, index=close.index, columns=["MU"])
        books = {}
        for rt in (0, 6, 9, 40):
            daily, _ = simulate_roster(open_[["MU"]], close[["MU"]], selected, gate,
                                      n=1, max_weight=1, round_trip_bp=rt)
            daily.index = pd.DatetimeIndex(daily.exit_date, name="date")
            books[rt] = daily
        for period, bounds in {"development_context": (cfg["development_start"], cfg["development_end"]),
                               "evaluation_2025": (cfg["evaluation_start"], cfg["evaluation_end"])}.items():
            sub = books[0].loc[bounds[0]:bounds[1]]
            gross = series_metrics(sub["return"])
            active = sub.loc[sub.active, "return"]
            net = series_metrics(books[40].loc[bounds[0]:bounds[1], "return"])
            row = {"period": period, "sample": sample, "observations": int(sub.selected_count.gt(0).sum()),
                "calendar_sessions": len(sub), "gross_total_return": gross["total_return"],
                "gross_sharpe": gross["sharpe_zero_rate"], "gross_maximum_drawdown": gross["maximum_drawdown"],
                "gross_average_return_bp": active.mean()*1e4,
                "gross_break_even_cost_per_side_bp": active.mean()*5e3,
                "net_total_return_20bp_per_side": net["total_return"],
                "net_sharpe_20bp_per_side": net["sharpe_zero_rate"],
                "net_maximum_drawdown_20bp_per_side": net["maximum_drawdown"],
                "live_name_cap_compliant": False,
                "diagnostic_note": "100% MU concentration diagnostic; exceeds the live 10% name cap"}
            for rt in (6, 9):
                row[f"net_total_return_{rt}bp_round_trip"] = series_metrics(books[rt].loc[bounds[0]:bounds[1], "return"])["total_return"]
            output.append(row)
    return pd.DataFrame(output)


def fmt_pct(value: float) -> str:
    return "n/a" if pd.isna(value) else f"{value * 100:+.2f}%"


def draw_equity_chart(daily: pd.DataFrame, cfg: dict, path: Path) -> None:
    subset = daily.loc[cfg["evaluation_start"]:cfg["evaluation_end"]]
    series = {
        "Top 10 gross": (1.0 + subset["basket_overnight_gross"]).cumprod(),
        "SPY overnight": (1.0 + subset["spy_overnight_gross"]).cumprod(),
        "Eligible universe": (1.0 + subset["universe_overnight_gross"]).cumprod(),
        "Top 10 net": (1.0 + subset["basket_overnight_net"]).cumprod(),
    }
    width, height = 1400, 820
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    def chart_font(size: int, bold: bool = False):
        candidates = (
            ["DejaVuSans-Bold.ttf", "arialbd.ttf"]
            if bold
            else ["DejaVuSans.ttf", "arial.ttf"]
        )
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
        return ImageFont.load_default()

    title_font = chart_font(28, bold=True)
    axis_font = chart_font(20)
    legend_font = chart_font(20)
    left, top, right, bottom = 105, 100, width - 70, height - 105
    draw.text((left, 34), "2025 close-to-next-open equity", fill="#17365D", font=title_font)
    draw.rectangle((left, top, right, bottom), outline="#AAB2BD", width=2)

    all_values = np.concatenate([s.to_numpy(dtype=float) for s in series.values()])
    y_min = float(np.nanmin(all_values))
    y_max = float(np.nanmax(all_values))
    padding = max((y_max - y_min) * 0.08, 0.01)
    y_min -= padding
    y_max += padding
    colors = ["#2F6FB0", "#F28E2B", "#59A14F", "#C84C4C"]
    n = max(len(subset) - 1, 1)

    def xy(i: int, value: float) -> tuple[int, int]:
        x = left + int((right - left) * i / n)
        y = bottom - int((bottom - top) * (value - y_min) / (y_max - y_min))
        return x, y

    for tick in range(6):
        value = y_min + (y_max - y_min) * tick / 5
        y = xy(0, value)[1]
        draw.line((left, y, right, y), fill="#E5E7EB", width=1)
        draw.text((18, y - 11), f"{value:.2f}", fill="#555555", font=axis_font)

    for (label, values), color in zip(series.items(), colors):
        points = [xy(i, float(value)) for i, value in enumerate(values)]
        draw.line(points, fill=color, width=4)
    legend_x = left
    for (label, _), color in zip(series.items(), colors):
        draw.line((legend_x, height - 58, legend_x + 35, height - 58), fill=color, width=4)
        draw.text((legend_x + 43, height - 69), label, fill="#222222", font=legend_font)
        legend_x += 275
    image.save(path, dpi=(180, 180))


def write_report(
    metrics: pd.DataFrame,
    cost_sensitivity: pd.DataFrame,
    trades: pd.DataFrame,
    cfg: dict,
    universe_count: int,
) -> None:
    eval_metrics = metrics.loc[metrics["period"].eq("evaluation_2025")].set_index("strategy")
    gross = eval_metrics.loc["top10_overnight_gross"]
    net = eval_metrics.loc["top10_overnight_net"]
    spy = eval_metrics.loc["spy_overnight_gross"]
    excess = eval_metrics.loc["top10_minus_spy_gross"]
    daytime = eval_metrics.loc["top10_next_daytime_gross"]
    evaluation_trades = trades.loc[
        pd.to_datetime(trades["entry_date"]).between(cfg["evaluation_start"], cfg["evaluation_end"])
    ]
    most_selected = evaluation_trades["ticker"].value_counts().head(10)
    leaders = ", ".join(f"{ticker} ({count})" for ticker, count in most_selected.items())
    break_even_per_side_bp = gross["average_return"] * 10_000.0 / 2.0
    cost_rows = "\n".join(
        f"| {row.cost_per_side_bp:g} bp | {fmt_pct(row.total_return)} | {row.sharpe_zero_rate:.2f} |"
        for row in cost_sensitivity.itertuples()
    )
    conclusion = (
        "The stock-selection rule beat SPY before costs."
        if excess["total_return"] > 0
        else "The stock-selection rule did not beat SPY before costs."
    )
    tradability = (
        "It remained profitable after the prescribed round-trip cost."
        if net["total_return"] > 0
        else "It was not profitable after the prescribed round-trip cost."
    )
    report = f"""# Overnight momentum backtest — corrected research run

## Objective

Test whether ten high-momentum stocks bought at the close and sold at the next regular-session open outperform SPY over the identical overnight window.

## Retained rule

- Universe: {universe_count} names in the fixed supplied equity universe. The external membership snapshot does not filter this test.
- Momentum: trailing {cfg['momentum_lookback_days']} trading-day close-to-close return.
- Timing safeguard: the signal is lagged {cfg['signal_lag_days']} trading day, so a close-t entry uses information only through close t-1.
- Selection: top {cfg['top_n']} names, at most 10% each at entry. Entry fees are reserved from capital.
- Entry/exit: official close t to official open t+1.
- Cost: {cfg['transaction_cost_bps_per_side']} bp per side, or {2 * cfg['transaction_cost_bps_per_side']} bp per overnight round trip.
- Benchmark: SPY close t to open t+1.
- Evaluation: calendar 2025; 2023-2024 is development context. Added official prices produce separate continuation results without requiring new SPY observations.
- Missing quotes: unavailable entry leaves cash; unavailable next-open exit remains held and blocks all new entries until the first observed later open. Daily marks use observed close or the last available mark.
- Cash interest: zero; all annualized risk statistics use official-session returns including idle cash dates. Periods are assigned to the next-session valuation date, preserving 2025 results when later prices are added.

## 2025 result

| Measure | Top 10 gross | Top 10 net | SPY gross | Top 10 minus SPY gross |
|---|---:|---:|---:|---:|
| Total return | {fmt_pct(gross['total_return'])} | {fmt_pct(net['total_return'])} | {fmt_pct(spy['total_return'])} | {fmt_pct(excess['total_return'])} |
| Average daily return | {fmt_pct(gross['average_return'])} | {fmt_pct(net['average_return'])} | {fmt_pct(spy['average_return'])} | {fmt_pct(excess['average_return'])} |
| Win rate | {gross['win_rate'] * 100:.1f}% | {net['win_rate'] * 100:.1f}% | {spy['win_rate'] * 100:.1f}% | {excess['win_rate'] * 100:.1f}% |
| Sharpe (zero rate) | {gross['sharpe_zero_rate']:.2f} | {net['sharpe_zero_rate']:.2f} | {spy['sharpe_zero_rate']:.2f} | {excess['sharpe_zero_rate']:.2f} |
| Maximum drawdown | {fmt_pct(gross['maximum_drawdown'])} | {fmt_pct(net['maximum_drawdown'])} | {fmt_pct(spy['maximum_drawdown'])} | {fmt_pct(excess['maximum_drawdown'])} |

The same selected stocks produced {fmt_pct(daytime['total_return'])} gross when measured from the next open to that session's close. This decomposition indicates whether the observed return was concentrated overnight or during regular hours.

Most frequently selected names in 2025: {leaders}.

## Cost sensitivity

The average gross edge was {gross['average_return'] * 10_000:.2f} basis points per night. Its arithmetic break-even cost was therefore approximately {break_even_per_side_bp:.2f} basis points per side.

| Assumed cost per side | 2025 total return | Sharpe |
|---:|---:|---:|
{cost_rows}

## Initial interpretation

{conclusion} {tradability} This is a mechanical hypothesis test, not evidence that a live order would receive the official closing or opening print.

## Limitations

- Fixed supplied universe, not a survivorship-free historical universe; verified raw stock splits are corrected by the shared price loader.
- Stock OHLC excludes cash dividends, so ex-dividend overnight total returns are understated for long positions.
- Official daily open and close prices omit bid-ask spread and opening-auction slippage; the prescribed 20 bp per side is the implementation allowance.
- Earnings dates and overnight news are not included in this first mechanical run.
- SPY OHLC is an external benchmark downloaded from Nasdaq and stored with source metadata.
"""
    (ROOT / "OVERNIGHT_BACKTEST.md").write_text(report, encoding="utf-8")


def main(evaluation_date: str | None = None) -> None:
    cfg = load_config()
    open_, close, tickers = load_stock_panels()
    if evaluation_date is not None:
        open_, close = open_.loc[:evaluation_date], close.loc[:evaluation_date]
    spy = load_spy()
    daily, trades = build_daily_and_trades(open_, close, spy, cfg)
    metrics = build_metrics(daily, cfg)
    cost_sensitivity = build_cost_sensitivity(daily, cfg)
    monthly = build_monthly(daily, cfg)
    breadth_sensitivity = build_breadth_sensitivity(open_, close, spy, cfg, daily)
    mu_audit = build_mu_audit(open_, close, spy, trades, cfg)
    RESULTS.mkdir(parents=True, exist_ok=True)
    daily.to_csv(RESULTS / "overnight_daily.csv", date_format="%Y-%m-%d")
    trades.to_csv(RESULTS / "overnight_trades.csv", index=False, date_format="%Y-%m-%d")
    metrics.to_csv(RESULTS / "overnight_metrics.csv", index=False)
    cost_sensitivity.to_csv(RESULTS / "overnight_cost_sensitivity.csv", index=False)
    monthly.to_csv(RESULTS / "overnight_monthly_2025.csv")
    breadth_sensitivity.to_csv(RESULTS / "overnight_breadth_sensitivity.csv", index=False)
    mu_audit.to_csv(RESULTS / "overnight_mu_audit.csv", index=False)
    draw_equity_chart(daily, cfg, RESULTS / "overnight_equity.png")
    write_report(metrics, cost_sensitivity, trades, cfg, len(tickers))

    evaluation = metrics.loc[metrics["period"].eq("evaluation_2025")].set_index("strategy")
    summary = {
        "method": "top 10 fixed supplied equities by 60-day momentum known at t-1; buy close t and attempt exit open t+1; unavailable exits carried",
        "universe_count": len(tickers),
        "evaluation_days": int(evaluation.loc["top10_overnight_gross", "observations"]),
        "top10_gross_total_return": float(evaluation.loc["top10_overnight_gross", "total_return"]),
        "top10_net_total_return": float(evaluation.loc["top10_overnight_net", "total_return"]),
        "spy_gross_total_return": float(evaluation.loc["spy_overnight_gross", "total_return"]),
        "top10_minus_spy_gross_total_return": float(evaluation.loc["top10_minus_spy_gross", "total_return"]),
        "gross_average_return_bp_per_night": float(evaluation.loc["top10_overnight_gross", "average_return"] * 10_000.0),
        "arithmetic_break_even_cost_per_side_bp": float(evaluation.loc["top10_overnight_gross", "average_return"] * 10_000.0 / 2.0),
        "gross_positive_months": int(monthly["basket_overnight_gross"].gt(0).sum()),
        "gross_excess_positive_months": int(monthly["basket_minus_spy_gross"].gt(0).sum()),
        "round_trip_cost": 2.0 * float(cfg["transaction_cost_bps_per_side"]) / 10_000.0,
        "cash_interest_rate": 0,
        "reporting_calendar": "Next-session valuation date; includes zero-return cash days; fixed2025 unaffected by later entry outcomes",
        "continuation_available": bool((daily.index > pd.Timestamp(cfg["evaluation_end"])).any()),
        "post_hoc_robustness": {
            "top5_gross_total_return": float(
                breadth_sensitivity.loc[breadth_sensitivity["top_n"].eq(5), "gross_total_return"].iloc[0]
            ),
            "top5_net_total_return_20bp_per_side": float(
                breadth_sensitivity.loc[
                    breadth_sensitivity["top_n"].eq(5), "net_total_return_20bp_per_side"
                ].iloc[0]
            ),
            "top10_spy_hedged_gross_total_return": float(
                breadth_sensitivity.loc[
                    breadth_sensitivity["top_n"].eq(10), "spy_hedged_gross_total_return"
                ].iloc[0]
            ),
            "mu_2025_every_night_gross_total_return": float(
                mu_audit.loc[
                    mu_audit["period"].eq("evaluation_2025")
                    & mu_audit["sample"].eq("MU_every_night"),
                    "gross_total_return",
                ].iloc[0]
            ),
            "mu_2025_every_night_net_total_return_20bp_per_side": float(
                mu_audit.loc[
                    mu_audit["period"].eq("evaluation_2025")
                    & mu_audit["sample"].eq("MU_every_night"),
                    "net_total_return_20bp_per_side",
                ].iloc[0]
            ),
            "mu_2025_top10_filter_observations": int(
                mu_audit.loc[
                    mu_audit["period"].eq("evaluation_2025")
                    & mu_audit["sample"].eq("MU_only_when_in_top10_momentum"),
                    "observations",
                ].iloc[0]
            ),
            "mu_2025_top10_filter_net_total_return_20bp_per_side": float(
                mu_audit.loc[
                    mu_audit["period"].eq("evaluation_2025")
                    & mu_audit["sample"].eq("MU_only_when_in_top10_momentum"),
                    "net_total_return_20bp_per_side",
                ].iloc[0]
            ),
        },
        "limitations": [
            "fixed supplied universe is not a point-in-time historical universe",
            "cash dividends omitted from stock returns",
            "official prints may not be achievable live",
            "earnings and overnight-news filters not yet applied",
        ],
    }
    (RESULTS / "overnight_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
