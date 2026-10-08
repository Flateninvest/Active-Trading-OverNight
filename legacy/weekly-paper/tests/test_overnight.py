import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overnight_backtest import calculate_momentum, close_to_open_return, select_top_names


class OvernightTests(unittest.TestCase):
    def test_momentum_is_lagged_before_close_entry(self):
        dates = pd.date_range("2025-01-01", periods=5, freq="B")
        close = pd.DataFrame({"A": [10.0, 11.0, 12.0, 15.0, 30.0]}, index=dates)
        momentum = calculate_momentum(close, lookback=2, lag=1)
        self.assertAlmostEqual(momentum.loc[dates[3], "A"], 0.2)
        self.assertNotAlmostEqual(momentum.loc[dates[3], "A"], 15.0 / 11.0 - 1.0)

    def test_top_names_are_deterministic(self):
        signal = pd.Series({"A": 0.1, "B": 0.4, "C": 0.2})
        close = pd.Series({"A": 10.0, "B": 20.0, "C": 30.0})
        self.assertEqual(select_top_names(signal, close, 2), ["B", "C"])

    def test_close_to_open_return(self):
        entry = pd.Series({"A": 100.0})
        exit_ = pd.Series({"A": 101.0})
        self.assertAlmostEqual(close_to_open_return(entry, exit_)["A"], 0.01)


if __name__ == "__main__":
    unittest.main()
