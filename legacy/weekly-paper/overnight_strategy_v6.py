"""Rev 6 — the gated overnight strategy, its parameter search, and its adversarial checks.

Replaces the three Rev 5 scripts (overnight_strategy.py, validate_strategy.py,
overnight_economics.py), which carried absolute paths and are superseded.

Run standalone:      python overnight_strategy_v6.py
Or via the pipeline: python run.py   (which calls main() at the end)

Reads only files already in the repository:
    data/official/universe.csv
    data/official/prices/{TICKER}.csv
    data/external/corporate_actions.csv (verified split adjustments)
    data/external/spy_nasdaq_2023_2025.csv
Writes results/rev6/.

Design note on causality. Every gate threshold is an EXPANDING quantile of prior
data only, and no gate fires until 252 sessions of history exist. The momentum
signal is lagged one full session so a close-t entry ranks on prices through
close t-1. The dispersion series is lagged again before its own threshold is
computed, which makes the gate deliberately conservative rather than borderline.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from overnight_execution import ranked_roster, simulate_roster, reporting_periods

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OFFICIAL = ROOT / "data" / "official"
EXTERNAL = ROOT / "data" / "external"
OUT = ROOT / "results" / "rev6"

EVAL = ("2025-01-01", "2025-12-31")
DEV = ("2023-01-03", "2024-12-31")
MOM_LOOKBACK, SIGNAL_LAG = 60, 1
POOL = 30                 # candidate pool drawn from the momentum screen
MIN_HIST = 252            # sessions of history required before any gate may fire
PERSIST_WINDOW = 20       # trailing window for the overnight-persistence ranker
HEADLINE = {"gate": "dispersion > expanding median",
            "ranker": "20d mean overnight return", "n": 10}


# --------------------------------------------------------------------- data
def load(evaluation_date: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    from overnight_backtest import load_stock_panels, load_spy
    open_, close, tickers = load_stock_panels()
    if evaluation_date is not None:
        open_, close = open_.loc[:evaluation_date], close.loc[:evaluation_date]
    return open_, close, load_spy(), tickers


# ---------------------------------------------------------------- inference
def newey_west_t(x: np.ndarray, lags: int = 5) -> float:
    """t-statistic on the mean, robust to serial correlation (Bartlett kernel)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 10:
        return float("nan")
    e = x - x.mean()
    s = (e @ e) / n
    for L in range(1, lags + 1):
        s += 2 * (1 - L / (lags + 1)) * ((e[L:] @ e[:-L]) / n)
    return float(x.mean() / math.sqrt(s / n)) if s > 0 else float("nan")


def describe(r: pd.Series) -> dict:
    r = pd.Series(r).replace([np.inf, -np.inf], np.nan).dropna()
    if len(r) < 5:
        return {"n": int(len(r))}
    mu, sd = r.mean(), r.std(ddof=1)
    eq = (1 + r).cumprod()
    return {"n": int(len(r)), "total": float((1 + r).prod() - 1), "bp": float(mu * 1e4),
            "sharpe": float(mu / sd * math.sqrt(252)) if sd > 0 else np.nan,
            "t": newey_west_t(r.to_numpy()),
            "dd": float((eq / eq.cummax().clip(lower=1.0) - 1).min()), "hit": float((r > 0).mean())}


def block_bootstrap(r: pd.Series, block: int = 10, draws: int = 10_000, seed: int = 11) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = pd.Series(r).dropna().to_numpy()
    n = len(x)
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, n, (draws, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(draws, -1)[:, :n] % n
    return np.prod(1 + x[idx], axis=1) - 1


# ---------------------------------------------------------------- strategy
class Signals:
    def __init__(self, open_: pd.DataFrame, close: pd.DataFrame, spy: pd.DataFrame):
        self.open = open_
        self.close = close
        self.momentum = close.pct_change(MOM_LOOKBACK, fill_method=None).shift(SIGNAL_LAG)
        self.overnight_next = (open_.shift(-1) / close - 1.0).iloc[:-1]
        own = open_ / close.shift(1) - 1.0
        self.persistence = own.rolling(PERSIST_WINDOW).mean().shift(SIGNAL_LAG)
        self.hit_rate = own.gt(0).where(own.notna()).rolling(PERSIST_WINDOW).mean().shift(SIGNAL_LAG)
        self.dispersion = self.momentum.std(axis=1)
        self.spy_vol = spy["close"].pct_change(fill_method=None).rolling(20).std().shift(1).reindex(close.index)
        self.pool = ranked_roster(self.momentum, POOL)

    def gate(self, series: pd.Series, quantile: float = 0.50, above: bool = True) -> pd.Series:
        """True when `series` sits above (or below) its own expanding quantile.

        The threshold is shifted so it uses only data strictly before the
        comparison date. Returns False until MIN_HIST observations exist.
        """
        threshold = series.expanding(MIN_HIST).quantile(quantile).shift(1)
        g = series > threshold if above else series < threshold
        return g.fillna(False)

    def gates(self) -> dict[str, pd.Series]:
        return {
            "always on": pd.Series(True, index=self.close.index),
            "dispersion > expanding median": self.gate(self.dispersion.shift(1)),
            "SPY 20d vol > expanding median": self.gate(self.spy_vol),
            "SPY 20d vol < expanding median": self.gate(self.spy_vol, above=False),
        }

    def rankers(self) -> dict[str, pd.DataFrame]:
        return {"momentum": self.momentum,
                "20d mean overnight return": self.persistence,
                "20d overnight hit rate": self.hit_rate}

    def selected(self, ranker: pd.DataFrame, n: int) -> pd.DataFrame:
        ranked = ranker.reindex(index=self.close.index, columns=self.close.columns).where(self.pool)
        return ranked_roster(ranked, n)

    def portfolio(self, gate: pd.Series, ranker: pd.DataFrame, n: int,
                  cost: float = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
        # Sub-ten-name variants are concentration diagnostics, not portfolios
        # satisfying the live ten-percent name cap.
        daily, trades = simulate_roster(self.open, self.close, self.selected(ranker, n),
            gate=gate, n=n, round_trip_bp=cost, max_weight=max(.1, 1/n))
        daily["entry_date"] = daily.index
        daily.index = pd.DatetimeIndex(daily.exit_date, name="date")
        return daily, trades

    def basket(self, gate: pd.Series, ranker: pd.DataFrame, n: int) -> pd.Series:
        return self.portfolio(gate, ranker, n)[0]["return"]


# -------------------------------------------------------------------- main
def main(evaluation_date: str | None = None) -> None:
    from overnight_backtest import load_config
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    open_, close, spy, tickers = load(evaluation_date)
    sig = Signals(open_, close, spy)
    gates, rankers = sig.gates(), sig.rankers()
    periods = reporting_periods(close.index[1:], cfg)
    comparison_periods = {k: periods[k] for k in ("2023-24", "2025")}
    if "continuation" in periods:
        comparison_periods["continuation"] = periods["continuation"]
    ungated, _ = sig.portfolio(gates["always on"], sig.persistence, HEADLINE["n"])
    summary = {"universe": len(tickers), "pool": POOL,
        "overnight_sessions_in_sample": len(close)-1,
        "sessions_with_signal": int(ungated.intended_names.ne("").sum()),
        "evaluation_date": str(close.index.max().date()),
        "accounting": "Official-session calendar indexed by next-session valuation date, including zero-return cash days; zero cash interest; actual notional buy/sell costs; pending exits retained and all new entries suspended until liquidation.",
        "assignment_cost": "20 bp per side = 40 bp round trip; entry costs reserved before sizing",
        "breadth_note": "n<10 is a concentration diagnostic exceeding the live 10% name cap; not a compliant executable portfolio"}

    def comparison_row(frame, period, bounds):
        sub = frame.loc[bounds[0]:bounds[1]]
        active = sub.loc[sub.active, "return"]
        stats = describe(sub["return"])
        return {"period": period, "nights": int(sub.selected_count.gt(0).sum()),
            "calendar_sessions": len(sub), "gross_bp": float(active.mean()*1e4),
            "t": stats.get("t"), "sharpe": stats.get("sharpe"), "max_dd": stats.get("dd")}

    rows = []
    for n in (1, 2, 3, 5, 8, 10, 15, 20):
        for rt in (0, 6, 9, 13.5, 20, 40):
            book, _ = sig.portfolio(gates["always on"], sig.momentum, n, rt)
            for period, bounds in comparison_periods.items():
                sub = book.loc[bounds[0]:bounds[1]]
                s = describe(sub["return"])
                rows.append({"names": n, "round_trip_bp": rt, "period": period,
                    "total": s.get("total"), "bp": float(sub.loc[sub.active, "return"].mean()*1e4),
                    "sharpe": s.get("sharpe"), "max_dd": s.get("dd"),
                    "live_name_cap_compliant": n >= 10})
    pd.DataFrame(rows).to_csv(OUT / "breadth_cost.csv", index=False)

    rows = []
    for gname, gate in gates.items():
        for rname, ranker in rankers.items():
            for n in (1, 3, 5, 10):
                books = {rt: sig.portfolio(gate, ranker, n, rt)[0] for rt in (0, 6, 9, 20, 40)}
                for period, bounds in comparison_periods.items():
                    row = comparison_row(books[0], period, bounds)
                    if not row["nights"]:
                        continue
                    row.update({"gate": gname, "ranker": rname, "names": n,
                                "live_name_cap_compliant": n >= 10})
                    for rt in (6, 9, 20, 40):
                        row[f"net{rt}_pct"] = ((1+books[rt].loc[bounds[0]:bounds[1], "return"]).prod()-1)*100
                    rows.append(row)
    grid = pd.DataFrame(rows)
    grid.to_csv(OUT / "search_grid.csv", index=False)
    cells = len(grid.groupby(["gate", "ranker", "names"]))
    wide = grid.pivot_table(index=["gate", "ranker", "names"], columns="period", values="net9_pct")
    survivors = wide[(wide.get("2025", np.nan) > 0) & (wide.get("2023-24", np.nan) > 0)]
    summary["search"] = {"cells": cells, "positive_both_periods_at_9bp": len(survivors),
        "bonferroni_t_threshold_5pct": round(abs(_inv_norm(0.025 / cells)), 2),
        "interpretation": "Exploratory sensitivity; overlapping cells and wider prior search preclude an independent confirmation claim."}

    g, r, n = HEADLINE["gate"], HEADLINE["ranker"], HEADLINE["n"]
    books = {rt: sig.portfolio(gates[g], rankers[r], n, rt) for rt in (0, 6, 9, 20, 40)}
    raw = books[0][0]
    first_active = raw.index[raw.active][0]
    historical = raw.loc[first_active:cfg["evaluation_end"]]
    daily = raw.loc[first_active:].rename(columns={"return": "gross"}).copy()
    for rt in (6, 9, 20, 40):
        daily[f"net{rt}"] = books[rt][0]["return"].reindex(daily.index)
    daily.to_csv(OUT / "headline_daily.csv", date_format="%Y-%m-%d")
    books[0][1].to_csv(OUT / "headline_trades.csv", index=False, date_format="%Y-%m-%d")
    detail = {}
    for period, bounds in periods.items():
        sub = daily.loc[bounds[0]:bounds[1]]
        if sub.empty:
            detail[period] = {"n": 0, "traded_nights": 0}
            continue
        active = sub.loc[sub.active, "gross"]
        stats = describe(sub.gross)
        d = {**stats, "calendar_sessions": len(sub), "traded_nights": int(sub.selected_count.gt(0).sum()),
            "active_nights": int(sub.active.sum()), "gross_bp_per_active_night": float(active.mean()*1e4),
            "trade_t": newey_west_t(active.to_numpy()),
            "pending_exit_sessions": int(sub.pending_exits.ne("").sum()),
            "blocked_entry_sessions": int(sub.new_entries_blocked.sum())}
        years = (pd.Timestamp(sub.exit_date.iloc[-1])-pd.Timestamp(sub.entry_date.iloc[0])).days / 365.25
        d["calendar_span_years"] = years
        for rt in (6, 9, 20, 40):
            net = describe(sub[f"net{rt}"])
            d[f"net{rt}_pct"] = net.get("total", 0)*100
            d[f"net{rt}_sharpe"] = net.get("sharpe")
            d[f"net{rt}_dd_pct"] = net.get("dd", 0)*100
            d[f"net{rt}_annualised_pct"] = ((1+sub[f"net{rt}"]).prod()**(1/years)-1)*100 if years else None
        detail[period] = _clean(d)
    detail["combined"]["sessions_with_signal"] = int(ungated.loc[:cfg["evaluation_end"], "intended_names"].ne("").sum())
    detail["combined"]["share_of_sessions_traded"] = detail["combined"]["traded_nights"] / detail["combined"]["sessions_with_signal"]
    summary["headline"] = {"specification": HEADLINE, **detail}

    # Compare every annualized statistic on exactly the same official sessions.
    # Missing benchmark observations stay missing and invalidate that period's
    # benchmark profile; they never suppress stock trades or become fake zeros.
    h = daily.loc[:cfg["evaluation_end"]]
    official_spy = spy.reindex(close.index)
    bh = official_spy.close.shift(-1) / official_spy.close - 1
    on = official_spy.open.shift(-1) / official_spy.close - 1
    common = pd.DataFrame(index=h.index)
    for rt in (6, 9, 40):
        common[f"Strategy, net {rt} bp round trip"] = h[f"net{rt}"]
    common["SPY buy and hold, same calendar span"] = pd.Series(bh.reindex(pd.DatetimeIndex(h.entry_date)).to_numpy(), index=h.index)
    common["SPY overnight, same traded nights"] = pd.Series(on.reindex(pd.DatetimeIndex(h.entry_date)).to_numpy(), index=h.index).where(h.selected_count.gt(0), 0.0)
    common.to_csv(OUT / "benchmark_daily.csv")
    years = detail["combined"]["calendar_span_years"]
    bench = []
    for label, returns in common.items():
        complete = bool(returns.notna().all())
        stats = describe(returns) if complete else {}
        total = stats.get("total")
        bench.append({"series": label, "observations": int(returns.notna().sum()),
            "calendar_sessions": len(returns), "coverage_complete": complete,
            "total_pct": total*100 if total is not None else None,
            "annualised_pct": ((1+total)**(1/years)-1)*100 if total is not None else None,
            "sharpe": stats.get("sharpe"), "max_drawdown_pct": stats.get("dd", np.nan)*100})
    pd.DataFrame(bench).to_csv(OUT / "benchmarks.csv", index=False)
    summary["benchmarks"] = {"span": [str(pd.Timestamp(h.entry_date.iloc[0]).date()), str(pd.Timestamp(h.exit_date.iloc[-1]).date())],
        "years": years, "rows": bench, "cash_interest_rate": 0,
        "note": "All strategies use common official sessions, with zero on inactive cash days. Benchmarks gross of costs; stock returns exclude cash dividends."}

    checks, fam, thr = {}, [], []
    for k in (3, 5, 8, 10, 15, 20):
        gross, _ = sig.portfolio(gates[g], rankers[r], k)
        net, _ = sig.portfolio(gates[g], rankers[r], k, 9)
        for period, bounds in comparison_periods.items():
            row = comparison_row(gross, period, bounds)
            row.update({"names": k, "net9_pct": ((1+net.loc[bounds[0]:bounds[1], "return"]).prod()-1)*100,
                        "live_name_cap_compliant": k >= 10})
            fam.append(row)
    pd.DataFrame(fam).to_csv(OUT / "breadth_consistency.csv", index=False)
    checks["breadth_consistency"] = "Exploratory overlapping concentration diagnostics; n<10 exceeds the live 10% name cap."
    for q in (.30, .40, .50, .60, .70):
        gate = sig.gate(sig.dispersion.shift(1), quantile=q)
        gross, _ = sig.portfolio(gate, rankers[r], n)
        net, _ = sig.portfolio(gate, rankers[r], n, 9)
        for period, bounds in comparison_periods.items():
            row = comparison_row(gross, period, bounds)
            row.update({"gate_quantile": q,
                        "net9_pct": ((1+net.loc[bounds[0]:bounds[1], "return"]).prod()-1)*100})
            thr.append(row)
    pd.DataFrame(thr).to_csv(OUT / "gate_sensitivity.csv", index=False)
    conc = {}
    for period, bounds in comparison_periods.items():
        sub = daily.loc[bounds[0]:bounds[1]]
        best = sub.loc[sub.active].sort_values("gross", ascending=False).index
        conc[period] = {"nights": int(sub.selected_count.gt(0).sum()),
            "net9_all_pct": ((1+sub.net9).prod()-1)*100,
            "net9_ex_best5_pct": ((1+sub.net9.drop(best[:5])).prod()-1)*100,
            "net9_ex_best10_pct": ((1+sub.net9.drop(best[:10])).prod()-1)*100}
    checks["concentration"] = conc
    monthly = h.net9.groupby(h.index.to_period("M")).apply(lambda x: ((1+x).prod()-1)*100)
    monthly.index = monthly.index.astype(str)
    monthly.to_csv(OUT / "monthly_net9.csv", header=["net9_pct"])
    checks["months_positive"] = f"{int((monthly > 0).sum())} of {len(monthly)}"
    evaluation = daily.loc[cfg["evaluation_start"]:cfg["evaluation_end"], "net9"]
    if len(evaluation):
        boot = block_bootstrap(evaluation)
        checks["bootstrap_2025_net9"] = {"point_pct": ((1+evaluation).prod()-1)*100,
            "ci95_pct": [float(np.percentile(boot, 2.5)*100), float(np.percentile(boot, 97.5)*100)],
            "probability_negative": float((boot < 0).mean()),
            "method": "10-session circular block bootstrap, common calendar including inactive days; descriptive after selection"}
    summary["adversarial_checks"] = checks
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    figure()
    print(json.dumps(summary, indent=2, default=float))
    print(f"\nwritten to {OUT}")


# ------------------------------------------------------------------ figure
def figure() -> None:
    """Rebuild Figure 1 of the research report from results/rev6/.

    Left: the gated roster under four cost assumptions. Right: gross edge by
    breadth in both periods, against the 9 bp round-trip line. Written to
    results/rev6/fig1_strategy.png so every visual in the report is
    reproducible by `python run.py` rather than pasted in by hand.
    """
    import os, tempfile
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "etoro_mpl_cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False,
                         "axes.spines.right": False, "axes.grid": True,
                         "grid.color": "#E6E9EE", "grid.linewidth": .8,
                         "axes.edgecolor": "#AEB5C0", "font.size": 9.5})
    INK, NAVY, TEAL = "#141A22", "#20517E", "#2E7D6E"
    RUST, SAND, GREY = "#A8392B", "#C7912F", "#7C8592"
    pct = FuncFormatter(lambda v, _: f"{v * 100:.0f}%")

    daily = pd.read_csv(OUT / "headline_daily.csv", parse_dates=[0], index_col=0).loc[:EVAL[1]]
    d = daily["gross"]
    fam = pd.read_csv(OUT / "breadth_consistency.csv").rename(columns={"names": "n"})

    fig, ax = plt.subplots(1, 2, figsize=(11.4, 4.0), gridspec_kw={"width_ratios": [1.4, 1]})

    for cost, colr, lab, lw in [(0, GREY, "gross", 1.5),
                                (6, TEAL, "net @ 6 bp round trip", 2.2),
                                (9, NAVY, "net @ 9 bp round trip", 2.2),
                                (40, RUST, "net @ 40 bp round trip (assignment)", 1.8)]:
        r = d if cost == 0 else daily[f"net{cost}"]
        ax[0].plot(r.index, (1 + r).cumprod() - 1, color=colr, lw=lw, label=lab)
    ax[0].axhline(0, color=INK, lw=.9)
    ax[0].axvline(pd.Timestamp("2025-01-01"), color=SAND, lw=1.2, ls="--")
    ax[0].text(pd.Timestamp("2025-01-08"), .69, "2025 evaluation", fontsize=8, color="#8a6412")
    ax[0].text(pd.Timestamp("2024-05-05"), .69, "development", fontsize=8, color=GREY)
    ax[0].annotate("Nov 2024", xy=(pd.Timestamp("2024-11-20"), .075),
                   xytext=(pd.Timestamp("2024-06-10"), .20), fontsize=7.8, color=RUST,
                   arrowprops=dict(arrowstyle="->", color=RUST, lw=.9))
    ax[0].annotate("Oct 2025", xy=(pd.Timestamp("2025-10-25"), .145),
                   xytext=(pd.Timestamp("2025-06-20"), .015), fontsize=7.8, color=RUST,
                   arrowprops=dict(arrowstyle="->", color=RUST, lw=.9))
    ax[0].text(pd.Timestamp("2024-04-10"), -.20,
               "two months carry most of the result - see section 8",
               fontsize=7.8, color=RUST, style="italic")
    ax[0].set_ylim(-.60, .76)
    ax[0].yaxis.set_major_formatter(pct)
    ax[0].legend(frameon=False, fontsize=8.2, loc="upper left", bbox_to_anchor=(0.0, .93))
    ax[0].set_title(f"Dispersion-gated overnight roster, {int(daily.selected_count.gt(0).sum())} entries / "
                    f"{len(daily)} sessions", loc="left", fontsize=11, weight="bold", color=INK)
    ax[0].tick_params(axis="x", labelsize=8)

    w = .36
    ns = sorted(fam.n.unique())
    x = np.arange(len(ns))
    for k, (per, colr) in enumerate([("2023-24", GREY), ("2025", NAVY)]):
        v = [fam[(fam.n == nn) & (fam.period == per)].gross_bp.iloc[0] for nn in ns]
        ax[1].bar(x + (k - .5) * w, v, w, color=colr, label=per, zorder=3)
        for xi, vi in zip(x + (k - .5) * w, v):
            ax[1].text(xi, vi + .5, f"{vi:.0f}", ha="center", fontsize=7.6, color=INK)
    ax[1].axhline(9, color=RUST, lw=1.5, ls="--", zorder=4)
    ax[1].text(len(ns) - .45, 9.9, "9 bp round-trip cost", fontsize=8, color=RUST, ha="right")
    ax[1].set_xticks(x, [str(nn) for nn in ns])
    ax[1].set_xlabel("names held", fontsize=8.5)
    ax[1].set_ylabel("gross edge, bp per night", fontsize=8.5)
    ax[1].set_ylim(0, max(29, fam.gross_bp.max()+4))
    ax[1].legend(frameon=False, fontsize=8.4, loc="upper right")
    ax[1].set_title("Exploratory breadth sensitivity", loc="left",
                    fontsize=11, weight="bold", color=INK)
    ax[1].text(.5, -.19, "n < 10 exceeds the live 10% name cap", fontsize=7.8,
               color=GREY, style="italic", ha="center", transform=ax[1].transAxes)
    fig.tight_layout()
    fig.savefig(OUT / "fig1_strategy.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def summary_nights() -> int:
    """Sessions on which the mechanical roster exists, read back from summary.json."""
    return int(json.loads((OUT / "summary.json").read_text())["sessions_with_signal"])


def _clean(d):
    return {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in d.items()} \
        if isinstance(d, dict) else d


def _inv_norm(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation)."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    rr = q * q
    return (((((a[0]*rr+a[1])*rr+a[2])*rr+a[3])*rr+a[4])*rr+a[5])*q / \
           (((((b[0]*rr+b[1])*rr+b[2])*rr+b[3])*rr+b[4])*rr+1)


if __name__ == "__main__":
    main()
