"""Tests for the Rev 6 gated overnight strategy.

Three things worth testing that the earlier suite did not cover:
  1. no signal uses information from after its own date (leakage)
  2. no gate fires before it has the required history (causality)
  3. the fixed supplied equity universe is retained without membership filtering
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overnight_strategy_v6 import MIN_HIST, Signals, load, newey_west_t


class SignalCausality(unittest.TestCase):
    """Corrupt every price after a cutoff; signals dated on or before it must not move."""

    @classmethod
    def setUpClass(cls):
        cls.open_, cls.close, cls.spy, _ = load()
        cls.cutoff = cls.close.index[400]

    def test_signals_ignore_future_prices(self):
        clean = Signals(self.open_, self.close, self.spy)
        rng = np.random.default_rng(0)
        future = self.close.index > self.cutoff
        o2, c2 = self.open_.copy(), self.close.copy()
        noise = rng.uniform(2.0, 5.0, size=(future.sum(), c2.shape[1]))
        o2.loc[future, :] = o2.loc[future, :].to_numpy() * noise
        c2.loc[future, :] = c2.loc[future, :].to_numpy() * noise
        dirty = Signals(o2, c2, self.spy)

        for name in ("momentum", "persistence", "hit_rate"):
            a = getattr(clean, name).loc[:self.cutoff]
            b = getattr(dirty, name).loc[:self.cutoff]
            pd.testing.assert_frame_equal(a, b, check_exact=False, atol=1e-12,
                                          obj=f"{name} leaked future information")
        pd.testing.assert_series_equal(clean.dispersion.loc[:self.cutoff],
                                       dirty.dispersion.loc[:self.cutoff],
                                       check_exact=False, atol=1e-12)

    def test_gate_silent_until_history_exists(self):
        s = Signals(self.open_, self.close, self.spy)
        gate = s.gate(s.dispersion.shift(1))
        # the threshold needs MIN_HIST observations and the series itself needs
        # MOM_LOOKBACK before it is defined at all, so the gate must be False early
        self.assertFalse(bool(gate.iloc[:MIN_HIST].any()),
                         "gate fired before it had the required history")

    def test_entry_signal_is_lagged_one_session(self):
        s = Signals(self.open_, self.close, self.spy)
        t = self.close.index[300]
        prior = self.close.index[299]
        ticker = self.close.columns[0]
        expected = self.close.at[prior, ticker] / self.close.iloc[299 - 60][ticker] - 1.0
        self.assertAlmostEqual(s.momentum.at[t, ticker], expected, places=10)


class UniverseAndSelection(unittest.TestCase):
    def test_all_supplied_equities_are_retained(self):
        open_, close, spy, tickers = load()
        universe = pd.read_csv(Path(__file__).resolve().parents[1] / "data/official/universe.csv")
        supplied = set(universe.loc[universe.category.eq("equity"), "ticker"])
        self.assertEqual(len(supplied), 200)
        self.assertEqual(set(tickers), supplied)
        self.assertEqual(set(close.columns), supplied)

    def test_selected_roster_cannot_use_future_exit_availability(self):
        open_, close, spy, _ = load()
        cutoff = close.index[400]
        clean = Signals(open_, close, spy)
        changed_open = open_.copy()
        changed_open.loc[changed_open.index > cutoff] = np.nan
        changed = Signals(changed_open, close, spy)
        pd.testing.assert_frame_equal(clean.selected(clean.persistence, 10).loc[:cutoff],
                                       changed.selected(changed.persistence, 10).loc[:cutoff])


class Inference(unittest.TestCase):
    def test_newey_west_matches_ols_t_when_series_is_iid(self):
        rng = np.random.default_rng(3)
        x = rng.normal(0.001, 0.01, 4000)
        plain = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
        self.assertAlmostEqual(newey_west_t(x), plain, delta=0.15)

    def test_newey_west_is_more_conservative_under_persistence(self):
        rng = np.random.default_rng(4)
        e = rng.normal(0, 0.01, 4000)
        x = np.zeros(4000)
        for i in range(1, 4000):
            x[i] = 0.6 * x[i - 1] + e[i]
        x += 0.001
        plain = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
        self.assertLess(abs(newey_west_t(x)), abs(plain))


if __name__ == "__main__":
    unittest.main()
