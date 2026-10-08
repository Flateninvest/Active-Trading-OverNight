"""Independent ledger checks using hand-calculated trading cash flows."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overnight_execution import simulate_roster
from overnight_backtest import build_daily_and_trades, build_metrics


class IndependentOvernightAudit(unittest.TestCase):
    def fixture(self):
        dates = pd.bdate_range("2025-12-29", periods=5)
        close = pd.DataFrame(100., index=dates, columns=list("ABCDEFGHIJ"))
        return dates, close.copy(), close, pd.DataFrame(True, index=dates, columns=close.columns)

    def test_ten_percent_cap_is_also_met_after_entry_fees(self):
        dates, open_, close, roster = self.fixture()
        for missing in (0, 1, 4):
            quotes = close.copy()
            quotes.iloc[0, :missing] = np.nan
            daily, trades = simulate_roster(open_, quotes, roster, round_trip_bp=40.)
            first = daily.iloc[0]
            nav_after_entry = first.entry_gross + first.cash_weight_after_entry
            entered = trades.loc[trades.entry_date.eq(dates[0])]
            post_fee_weights = entered.entry_weight / nav_after_entry
            self.assertTrue(post_fee_weights.le(.1 + 1e-12).all())
            self.assertGreaterEqual(first.cash_weight_after_entry, -1e-12)
            if missing == 0:
                np.testing.assert_allclose(post_fee_weights, .1)
            else:
                self.assertTrue(post_fee_weights.lt(.1).all())

    def test_price_drift_and_both_fees_match_cash_proceeds(self):
        dates, open_, close, roster = self.fixture()
        open_.iloc[1] = np.linspace(90., 130., 10)
        gate = pd.Series(False, index=dates)
        gate.iloc[0] = True
        side = .002
        daily, trades = simulate_roster(open_, close, roster, gate=gate, round_trip_bp=40.)
        invested = 1. / (1. + side)
        proceeds = invested * open_.iloc[1].mean() / 100.
        self.assertAlmostEqual(daily.iloc[0].equity, proceeds * (1. - side))
        self.assertAlmostEqual(daily.iloc[0].cost_return, side * (invested + proceeds))
        self.assertAlmostEqual(daily.iloc[0].sell_turnover, proceeds)
        self.assertEqual(len(trades), 10)
        np.testing.assert_allclose(daily.iloc[1:]["return"], 0.)

    def test_delayed_mark_and_final_exit_reconcile_across_periods(self):
        dates, open_, close, roster = self.fixture()
        gate = pd.Series(False, index=dates)
        gate.iloc[0] = True
        open_.loc[dates[1], "A"] = np.nan
        close.loc[dates[1], "A"] = 120.
        open_.loc[dates[2], "A"] = 110.
        side = .002
        daily, trades = simulate_roster(open_, close, roster, gate=gate, round_trip_bp=40.)
        per_name = .1 / (1 + side)
        after_nine_exits = 9 * per_name * (1 - side)
        self.assertAlmostEqual(daily.iloc[0].equity, after_nine_exits + 1.2 * per_name)
        self.assertAlmostEqual(daily.iloc[1].equity, after_nine_exits + 1.1 * per_name * (1 - side))
        self.assertLess(daily.iloc[1]["return"], 0.)
        self.assertEqual(daily.iloc[1].selected_count, 0)
        self.assertAlmostEqual(daily.iloc[1].cost_return, side * 1.1 * per_name / daily.iloc[0].equity)
        np.testing.assert_allclose((1 + daily["return"]).cumprod(), daily.equity)
        delayed = trades.loc[trades.ticker.eq("A")].iloc[0]
        self.assertAlmostEqual(delayed.overnight_return_net, 1.1 * (1 - side) / (1 + side) - 1)

    def test_new_year_exit_belongs_to_continuation_and_missing_benchmark_is_unknown(self):
        dates, open_, close, roster = self.fixture()
        open_.loc[dates[3]] = 120.
        spy = pd.DataFrame({"open": 100., "close": 100.}, index=dates[:3])
        cfg = {"momentum_lookback_days": 1, "signal_lag_days": 1, "top_n": 10,
               "transaction_cost_bps_per_side": 20., "development_start": "2023-01-01",
               "development_end": "2024-12-31", "evaluation_start": "2025-01-01",
               "evaluation_end": "2025-12-31"}
        daily, _ = build_daily_and_trades(open_, close, spy, cfg)
        self.assertEqual(daily.iloc[0].entry_date, pd.Timestamp("2025-12-31"))
        self.assertEqual(daily.index[0].year, 2026)
        self.assertAlmostEqual(daily.iloc[0].basket_overnight_gross, .2)
        metrics = build_metrics(daily, cfg)
        fixed_2025 = metrics.loc[(metrics.period == "evaluation_2025") & (metrics.strategy == "top10_overnight_gross")].iloc[0]
        self.assertEqual(fixed_2025.observations, 0)
        continuation = metrics.loc[(metrics.period == "continuation") & (metrics.strategy == "spy_overnight_gross")].iloc[0]
        self.assertFalse(continuation.coverage_complete)
        self.assertTrue(pd.isna(continuation.total_return))


if __name__ == "__main__":
    unittest.main()
