"""Accounting and continuation regressions independent of historical profits."""
import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overnight_execution import simulate_roster
from overnight_backtest import build_daily_and_trades


class OvernightExecution(unittest.TestCase):
    def setUp(self):
        self.dates = pd.bdate_range("2025-12-29", periods=6)
        self.close = pd.DataFrame(100.0, index=self.dates, columns=list("ABCDEFGHIJ"))
        self.open = self.close.copy()
        self.roster = pd.DataFrame(True, index=self.dates, columns=self.close.columns)

    def test_missing_exit_is_carried_and_blocks_new_entries(self):
        self.open.loc[self.dates[1], "A"] = np.nan
        self.close.loc[self.dates[1], "A"] = np.nan
        self.open.loc[self.dates[2], "A"] = 110.0
        daily, trades = simulate_roster(self.open, self.close, self.roster)
        self.assertEqual(daily.iloc[0].selected_count, 10)
        self.assertEqual(daily.iloc[0].pending_exits, "A")
        self.assertEqual(daily.iloc[1].selected_count, 0)
        self.assertTrue(daily.iloc[1].new_entries_blocked)
        self.assertEqual(daily.iloc[2].selected_count, 10)
        self.assertAlmostEqual(daily.iloc[0]["return"], 0)
        self.assertAlmostEqual(daily.iloc[1]["return"], .01)
        delayed = trades[(trades.ticker == "A") & (trades.entry_date == self.dates[0])].iloc[0]
        self.assertEqual(delayed.exit_date, self.dates[2])
        self.assertTrue(delayed.delayed_exit)
        self.assertTrue((daily.entry_gross <= 1+1e-10).all())
        self.assertTrue((trades.entry_weight <= .1+1e-10).all())

    def test_future_missing_exit_cannot_change_current_roster(self):
        clean, _ = simulate_roster(self.open, self.close, self.roster)
        self.open.loc[self.dates[1], "A"] = np.nan
        dirty, _ = simulate_roster(self.open, self.close, self.roster)
        self.assertEqual(clean.iloc[0].selected_names, dirty.iloc[0].selected_names)
        self.assertEqual(clean.iloc[0].selected_count, dirty.iloc[0].selected_count)

    def test_unavailable_entry_leaves_cash_without_reweighting(self):
        self.close.loc[self.dates[0], "A"] = np.nan
        daily, trades = simulate_roster(self.open, self.close, self.roster)
        self.assertEqual(daily.iloc[0].selected_count, 9)
        self.assertEqual(daily.iloc[0].unavailable_entries, "A")
        self.assertAlmostEqual(daily.iloc[0].cash_weight_after_entry, .1)
        self.assertAlmostEqual(daily.iloc[0].entry_gross, .9)
        self.assertTrue((trades.entry_weight <= .1+1e-10).all())

    def test_costs_are_per_side_and_cash_sessions_cost_nothing(self):
        gate = pd.Series(False, index=self.dates)
        gate.iloc[0] = True
        daily, _ = simulate_roster(self.open, self.close, self.roster, gate, round_trip_bp=40)
        # Full round trip costs 20 bp on each actual traded notional. Entry
        # sizing reserves the buy fee, preserving a nonnegative cash balance.
        self.assertAlmostEqual(daily.iloc[0]["return"], (1-.002)/(1+.002)-1)
        self.assertTrue(np.allclose(daily.iloc[1:]["return"], 0))
        self.assertTrue((daily.cash_weight_after_entry >= -1e-10).all())

    def test_unresolved_terminal_holding_is_reported_not_sold(self):
        self.open.loc[self.dates[1]:, "A"] = np.nan
        daily, trades = simulate_roster(self.open, self.close, self.roster)
        self.assertEqual(daily.iloc[-1].pending_exits, "A")
        self.assertEqual(int((trades.status == "open").sum()), 1)
        unresolved = trades[trades.status == "open"].iloc[0]
        self.assertTrue(pd.isna(unresolved.exit_date))
        self.assertTrue(pd.isna(unresolved.exit_open))

    def test_continuation_trades_do_not_require_extended_spy(self):
        spy = pd.DataFrame({"open": 100., "close": 100.}, index=self.dates[:3])
        cfg = {"momentum_lookback_days": 1, "signal_lag_days": 1,
               "top_n": 10, "transaction_cost_bps_per_side": 20}
        daily, trades = build_daily_and_trades(self.open, self.close, spy, cfg)
        later = daily[daily.index.year == 2026]
        self.assertGreater(len(later), 0)
        self.assertTrue((later.selected_count == 10).all())
        self.assertTrue(later.spy_overnight_gross.isna().all())
        self.assertTrue(later.basket_overnight_gross.notna().all())

    def test_appended_prices_do_not_restate_completed_calendar_year(self):
        cfg = {"momentum_lookback_days": 1, "signal_lag_days": 1,
               "top_n": 10, "transaction_cost_bps_per_side": 20}
        dates = pd.bdate_range("2025-12-22", periods=12)
        close = pd.DataFrame(100., index=dates, columns=self.close.columns)
        cutoff = dates <= pd.Timestamp("2025-12-31")
        spy = pd.DataFrame({"open": 100., "close": 100.}, index=dates[cutoff])
        base, _ = build_daily_and_trades(close.loc[cutoff], close.loc[cutoff], spy, cfg)
        changed = close.copy()
        changed.loc[changed.index.year == 2026] *= 1.1
        extended, _ = build_daily_and_trades(changed, close, spy, cfg)
        pd.testing.assert_frame_equal(base.loc[:"2025-12-31"], extended.loc[:"2025-12-31"])


if __name__ == "__main__":
    unittest.main()
