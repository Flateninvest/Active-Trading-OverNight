import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run import apply_no_trade_buffer, ar1_s_score, backtest
from data_quality import calendar_short_rates, load_price_frame


class CoreTests(unittest.TestCase):
    def test_ar1_recovers_fast_mean_reversion(self):
        rng = np.random.default_rng(7)
        etf = rng.normal(0, 0.01, 60)
        residual_level = np.zeros(61)
        for i in range(60):
            residual_level[i + 1] = 0.85 * residual_level[i] + rng.normal(0, 0.004)
        residual_return = np.diff(residual_level)
        stock = 1.2 * etf + residual_return
        mean, sigma, beta = ar1_s_score(stock, etf, 30)
        self.assertTrue(np.isfinite(mean))
        self.assertGreater(sigma, 0)
        self.assertAlmostEqual(beta, 1.2, delta=0.20)

    def test_no_trade_buffer_ignores_small_change_but_closes(self):
        target = pd.DataFrame({"A": [0.01, 0.011, 0.013, 0.0]})
        actual = apply_no_trade_buffer(target, 0.0025)
        self.assertEqual(actual["A"].tolist(), [0.01, 0.01, 0.013, 0.0])

    def test_positions_are_lagged_before_return(self):
        dates = pd.date_range("2025-01-01", periods=3, freq="D")
        weights = pd.DataFrame({"A": [1.0, 1.0, 1.0]}, index=dates)
        close = pd.DataFrame({"A": [100.0, 110.0, 121.0]}, index=dates)
        sofr = pd.Series(0.0, index=dates)
        result = backtest(weights, close, sofr, 0.0)
        self.assertEqual(result.loc[dates[0], "gross_return"], 0.0)
        self.assertEqual(result.loc[dates[1], "gross_return"], 0.0)
        self.assertAlmostEqual(result.loc[dates[2], "gross_return"], 0.10)

    def test_calendar_financing_includes_each_weekend_rate(self):
        dates = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
        calendar = pd.date_range(dates[0], dates[-1], freq="D")
        sofr = pd.Series([4., 5., 6., 7., 8.], index=calendar)
        weights = pd.DataFrame({"A": [-.5, -.5, -.5]}, index=dates)
        close = pd.DataFrame({"A": [100., 100., 100.]}, index=dates)
        result = backtest(weights, close, sofr, 0.)
        self.assertAlmostEqual(result.loc[dates[-1], "short_financing"], .5 * (5.5 + 6.5 + 7.5) / 100 / 360)
        self.assertEqual(result.loc[dates[1], "short_financing"], 0.)

    def test_missing_rate_is_not_silently_zero(self):
        dates = pd.to_datetime(["2025-01-03", "2025-01-06"])
        with self.assertRaisesRegex(ValueError, "SOFR does not cover"):
            calendar_short_rates(dates, pd.Series([4.], index=dates[1:]))

    def test_missing_quote_defers_entry(self):
        dates = pd.date_range("2025-01-01", periods=4, freq="D")
        weights = pd.DataFrame({"A": [1., 1., 1., 1.]}, index=dates)
        close = pd.DataFrame({"A": [100., np.nan, 110., 121.]}, index=dates)
        result = backtest(weights, close, pd.Series(0., index=dates), 0.)
        self.assertEqual(result.loc[dates[1], "unavailable_orders"], 1)
        self.assertEqual(result.loc[dates[1], "turnover"], 0.)
        self.assertEqual(result.loc[dates[2], "gross_return"], 0.)
        self.assertAlmostEqual(result.loc[dates[3], "gross_return"], .1)

    def test_missing_quote_retains_holding_and_catches_up_before_exit(self):
        dates = pd.date_range("2025-01-01", periods=4, freq="D")
        weights = pd.DataFrame({"A": [1., 0., 0., 0.]}, index=dates)
        close = pd.DataFrame({"A": [100., 100., np.nan, 120.]}, index=dates)
        result = backtest(weights, close, pd.Series(0., index=dates), 0.)
        self.assertEqual(result.loc[dates[2], "stale_positions"], 1)
        self.assertEqual(result.loc[dates[2], "turnover"], 0.)
        self.assertAlmostEqual(result.loc[dates[3], "gross_return"], .2)
        self.assertAlmostEqual(result.loc[dates[3], "turnover"], 1.2)
        self.assertEqual(result.attrs["executed_weights"].loc[dates[3], "A"], 0.)

    def test_drift_trade_and_post_fee_target_reconcile(self):
        dates = pd.date_range("2025-01-01", periods=3, freq="D")
        weights = pd.DataFrame({"A": [.5, .5, .5]}, index=dates)
        close = pd.DataFrame({"A": [100., 100., 110.]}, index=dates)
        fee = .002
        result = backtest(weights, close, pd.Series(0., index=dates), fee * 1e4)
        self.assertAlmostEqual(result.loc[dates[1], "equity"], 1 / (1 + .5 * fee))
        expected_growth = (1.05 - .55 * fee) / (1 - .5 * fee)
        self.assertAlmostEqual(1 + result.loc[dates[2], "net_return"], expected_growth)
        self.assertGreater(result.loc[dates[2], "turnover"], .024)
        np.testing.assert_allclose(result.attrs["executed_weights"].iloc[1:, 0], .5)
        np.testing.assert_allclose(result["net_return"], result["gross_return"] - result["transaction_cost"] - result["short_financing"], atol=1e-12)
        np.testing.assert_allclose(result["equity"], (1 + result["net_return"]).cumprod())

    def test_buffer_preserves_gross_limit(self):
        target = pd.DataFrame({"A": [.4, .6], "B": [.3, .2], "C": [.3, .2]})
        self.assertGreater(float(apply_no_trade_buffer(target, .15).abs().sum(axis=1).max()), 1.)
        actual = apply_no_trade_buffer(target, .15, gross_cap=1.)
        self.assertLessEqual(float(actual.abs().sum(axis=1).max()), 1.)


class CorporateActionTests(unittest.TestCase):
    def load_fixture(self, closes, factor=10., ticker="TEST"):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            prices = pd.DataFrame({"date": ["2025-01-02", "2025-01-03"],
                                   "open": closes, "close": closes, "volume": [100., 1000.]})
            prices.to_csv(folder / "TEST.csv", index=False)
            actions = pd.DataFrame([{ "ticker": ticker, "ex_date": "2025-01-03",
                                     "action": "split", "factor": factor,
                                     "source_url": "https://example.com/verified-test-fixture"}])
            actions.to_csv(folder / "actions.csv", index=False)
            result = load_price_frame(folder / "TEST.csv", actions_path=folder / "actions.csv")
            raw = pd.read_csv(folder / "TEST.csv")
            return result, raw

    def test_split_adjustment_preserves_economic_return_and_dollar_volume(self):
        result, raw = self.load_fixture([100., 11.])
        self.assertAlmostEqual(result["close"].iloc[1] / result["close"].iloc[0] - 1, .1)
        self.assertEqual(result["volume"].iloc[0], 1000.)
        self.assertEqual(raw["close"].iloc[0], 100.)
        np.testing.assert_allclose(result["close"] * result["volume"], raw["close"] * raw["volume"])

    def test_already_adjusted_prices_are_unchanged(self):
        result, raw = self.load_fixture([10., 11.])
        np.testing.assert_allclose(result["close"], raw["close"])
        np.testing.assert_allclose(result["volume"], raw["volume"])
        self.assertEqual(result.attrs["corporate_action_audit"][0]["status"], "already_adjusted")

    def test_unexplained_split_sized_move_stops_run(self):
        with self.assertRaisesRegex(ValueError, "unexplained"):
            self.load_fixture([100., 50.], ticker="ANOTHER")


if __name__ == "__main__":
    unittest.main()
