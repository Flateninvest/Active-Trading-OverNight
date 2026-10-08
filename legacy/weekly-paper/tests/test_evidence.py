import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flow_layer import conviction_score, daily_premium_panel, qualifying_mask


class EvidenceTests(unittest.TestCase):
    def test_filter_inclusive_dte_and_strict_open_interest(self):
        rows = pd.DataFrame({
            "Date": pd.to_datetime(["2025-01-02"] * 7),
            "Side": ["Near Ask"] * 6 + ["On Bid"],
            "Premium": [100000, 100000, 99999, 100000, 100000, 100000, 100000],
            "Quantity": [11, 11, 11, 10, 11, 11, 11],
            "Open Interest": [10] * 7,
            "DTE": [180, 730, 180, 180, 179, 731, 180],
            "Sentiment": ["BULLISH", "BEARISH"] + ["BULLISH"] * 5,
        })
        self.assertEqual(qualifying_mask(rows).tolist(), [True, True, False, False, False, False, False])

    def test_same_day_and_future_flow_cannot_affect_entry_score(self):
        dates = pd.bdate_range("2025-01-02", periods=35)
        cutoff = dates[25]
        volume = pd.DataFrame(1e8, index=dates, columns=["A"])
        initial = pd.DataFrame({"Date": [dates[22]], "Symbol": ["A"], "signed_premium": [100000.0]})
        polluted = pd.concat([initial, pd.DataFrame({
            "Date": [cutoff, dates[28]], "Symbol": ["A", "A"], "signed_premium": [1e9, -1e9]
        })], ignore_index=True)
        before = conviction_score(daily_premium_panel(initial, dates, ["A"]), volume, 5)
        after = conviction_score(daily_premium_panel(polluted, dates, ["A"]), volume, 5)
        pd.testing.assert_frame_equal(before.loc[:cutoff], after.loc[:cutoff])
        self.assertNotEqual(before.loc[dates[26], "A"], after.loc[dates[26], "A"])


if __name__ == "__main__":
    unittest.main()
