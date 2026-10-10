"""Synthetic owner DEMO-policy, stress-sizing and strategy-equity regressions."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from active_trading.policy import PolicyError, capital_limits, load_policy
from active_trading.risk.equity import build_strategy_risk_state
from active_trading.risk.review import (ReviewError, canonical_hash, review_proposal,
                                        sign_review, stress_loss_fraction)
from test_review import KEY, fixture


def equity_packet(policy, **changes):
    packet = {"mode": "DEMO", "account_environment": "DEMO", "account_id": "fictional-shadow-account",
              "strategy_id": policy["strategy_id"], "source": "SYNTHETIC_SCOPED_STRATEGY_BOOK",
              "observed_at": "2026-10-08T19:55:00Z", "complete": True,
              "cash_excludes_non_strategy_trades": True, "night_id": "2026-10-08",
              "night_session": {"session_date": "2026-10-08", "open_at": "2026-10-08T13:30:00Z", "close_at": "2026-10-08T20:00:00Z"},
              "cash_usd": "10000", "cash_flow_usd": "0", "account_balance_usd": "141000",
              "positions": []}
    packet.update(changes)
    return packet


def demo_fixture():
    packet, policy = fixture()
    p = packet["proposal"]
    p["mode"] = packet["review"]["mode"] = "DEMO"
    p["nav_usd"] = "141000"
    p["account_snapshot"].update(mode="DEMO", account_environment="DEMO", nav_usd="141000",
                                 available_cash_usd="141000")
    p["account_snapshot"].pop("broker_risk_score")
    p["monday_reference"]["official_close"] = True
    p["costs"]["coverage"] = "ROUND_TRIP"
    p["technical_analysis"] = {"source": "SYNTHETIC_NOT_MARKET_DATA", "instrument_id": p["instrument_id"], "observed_at": packet["now"],
        "as_of_session": "2026-10-07", "completed_daily_bars": 120, "sma20": "99", "sma50": "98",
        "wilder_rsi14": "55", "atr14": "1", "close": "100", "support": "90", "resistance": "110", "beta": "1"}
    sessions, day = [], date(2026, 10, 7)
    while len(sessions) < 60:
        if day.weekday() < 5:
            sessions.append(day.isoformat())
        day -= timedelta(days=1)
    p["stress_sizing"] = {"source": "SYNTHETIC_NOT_MARKET_DATA", "instrument_id": p["instrument_id"], "observed_at": packet["now"],
                          "complete": True, "overnight_gaps": [
                              {"session": day, "gap_fraction": "0.01"} for day in reversed(sessions)]}
    p["strategy_risk_state"] = build_strategy_risk_state(policy, equity_packet(policy), packet["now"])
    p["spec_hash"] = canonical_hash(policy)
    packet["review"]["proposal_digest"] = canonical_hash(p)
    packet["review"] = sign_review(packet["review"], KEY)
    return packet, policy


class AllocationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()

    def test_large_demo_balance_does_not_expand_strategy_caps(self):
        self.assertEqual(capital_limits(self.policy, "141000"), {
            "basis": Decimal("10000"), "maximum_positions": 3, "name_cap": Decimal("1000"),
            "gross_cap": Decimal("3000"), "position_risk_budget": Decimal("25"),
            "night_loss_limit": Decimal("100"), "drawdown_limit": Decimal("500")})

    def test_smaller_account_reduces_all_dollar_limits(self):
        limits = capital_limits(self.policy, "4000")
        self.assertEqual([limits[k] for k in ("basis", "name_cap", "gross_cap", "position_risk_budget",
                                               "night_loss_limit", "drawdown_limit")],
                         [Decimal(x) for x in ("4000", "400", "1200", "10", "40", "200")])

    def test_caps_are_read_from_policy(self):
        self.policy["risk"].update(strategy_allocation_usd=8000, maximum_positions=2,
                                   maximum_name_weight=.08, maximum_gross_weight_including_pending=.2)
        limits = capital_limits(self.policy, "100000")
        self.assertEqual((limits["name_cap"], limits["gross_cap"], limits["maximum_positions"]),
                         (Decimal("640"), Decimal("1600"), 2))

    def test_incomplete_or_invalid_policy_fails_closed(self):
        for field, value in (("strategy_allocation_usd", None), ("maximum_positions", True),
                             ("maximum_name_weight", "NaN"), ("drawdown_fraction", 2)):
            policy = deepcopy(self.policy)
            policy["risk"][field] = value
            with self.subTest(field=field), self.assertRaises(PolicyError):
                capital_limits(policy, 100000)

    def test_policy_loader_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            path = Path(directory) / "policy.json"
            path.write_text('{"risk":{},"risk":{}}')
            with self.assertRaises(ValueError): load_policy(path)


class DemoReviewTests(unittest.TestCase):
    def setUp(self):
        self.packet, self.policy = demo_fixture()

    def resign(self):
        self.packet["proposal"]["spec_hash"] = canonical_hash(self.policy)
        self.packet["review"]["proposal_digest"] = canonical_hash(self.packet["proposal"])
        self.packet["review"] = sign_review(self.packet["review"], KEY)

    def check(self):
        return review_proposal(self.packet["proposal"], self.packet["review"], self.policy,
                               reviewer_keys={"fictional-reviewer": KEY}, now=self.packet["now"])

    def test_demo_supported_without_account_risk_score_and_no_writer(self):
        result = self.check()
        self.assertEqual(result["mode"], "DEMO")
        self.assertFalse(result["broker_writes"])
        self.assertFalse(result["capital_approval"])

    def test_9005_entry_on_100k_account_fails_allocation_name_cap(self):
        p = self.packet["proposal"]
        p.update(nav_usd="100000", quantity="90", approved_notional_usd="9005", entry_cost_reserve_usd="0.5")
        p["account_snapshot"]["nav_usd"] = "100000"
        p["costs"]["estimated_total_usd"] = "0.5"
        p["technical_analysis"]["atr14"] = "0.01"
        for gap in p["stress_sizing"]["overnight_gaps"]: gap["gap_fraction"] = "0.001"
        self.resign()
        with self.assertRaisesRegex(ReviewError, "per-name capital cap"): self.check()

    def test_real_account_score_and_live_account_never_used(self):
        for field, value in (("real_account_risk_score", "1"), ("risk_score_account_environment", "LIVE"),
                             ("risk_score_account_id", "different-account"), ("account_environment", "LIVE")):
            self.packet, self.policy = demo_fixture()
            self.packet["proposal"]["account_snapshot"][field] = value
            self.resign()
            with self.subTest(field=field), self.assertRaises(ReviewError): self.check()

    def test_score_switch_is_policy_controlled(self):
        self.packet["proposal"]["account_snapshot"]["broker_risk_score"] = "10"
        self.resign()
        self.assertEqual(self.check()["decision"], "PASS")
        self.policy["risk"]["account_risk_score_gate_by_mode"]["DEMO"] = True
        self.resign()
        with self.assertRaisesRegex(ReviewError, "risk score"): self.check()

    def test_weekday_checked_even_for_signed_shadow_proposal(self):
        for day, monday in (("2026-10-05", "2026-10-05"), ("2026-10-09", "2026-10-05")):
            self.packet, self.policy = fixture()
            p = self.packet["proposal"]
            p["entry_session"], p["monday_reference"]["date"] = day, monday
            self.resign()
            with self.subTest(day=day), self.assertRaisesRegex(ReviewError, "weekday"): self.check()

    def test_signed_session_cannot_differ_from_review_day(self):
        self.packet["proposal"]["entry_session"] = "2026-10-07"
        self.resign()
        with self.assertRaises(ReviewError): self.check()

    def test_demo_requires_official_monday_reference(self):
        self.packet["proposal"]["monday_reference"].pop("official_close")
        self.resign()
        with self.assertRaisesRegex(ReviewError, "official Monday"): self.check()

    def test_automatic_high_beta_and_atr_require_enhanced_check(self):
        for field, value in (("beta", "1.5"), ("atr14", "4.01")):
            self.packet, self.policy = demo_fixture()
            self.packet["proposal"]["technical_analysis"][field] = value
            self.resign()
            with self.subTest(field=field), self.assertRaisesRegex(ReviewError, "enhanced_volatility"):
                self.check()
            self.packet["review"]["checks"]["enhanced_volatility"] = {
                "status": "PASS", "evidence": ["SYNTHETIC_ENHANCED_REVIEW"]}
            # ATR stress still applies after enhanced review, so use one share.
            self.packet["proposal"].update(quantity="1", approved_notional_usd="101.05")
            self.resign()
            self.assertEqual(self.check()["decision"], "PASS")

    def test_atr_enhanced_gate_uses_current_entry_ask(self):
        p = self.packet["proposal"]
        p["technical_analysis"]["atr14"] = "3.9"
        p["quote"].update(bid="94.95", ask="95")
        p["monday_reference"]["close"] = "95"
        p.update(quantity="1", entry_price_limit="95", approved_notional_usd="96")
        self.resign()
        with self.assertRaisesRegex(ReviewError, "enhanced_volatility"): self.check()

    def test_ta_and_stress_are_bound_to_the_proposed_instrument(self):
        for field in ("technical_analysis", "stress_sizing"):
            self.packet, self.policy = demo_fixture()
            self.packet["proposal"][field]["instrument_id"] = "other-company"
            self.resign()
            with self.subTest(field=field), self.assertRaisesRegex(ReviewError, "another instrument"):
                self.check()

    def test_history_sample_counts_are_read_from_policy(self):
        p = self.packet["proposal"]
        self.policy["risk"]["stress_gap_sessions"] = 2
        p["stress_sizing"]["overnight_gaps"] = p["stress_sizing"]["overnight_gaps"][-2:]
        self.resign()
        self.assertEqual(self.check()["decision"], "PASS")

    def test_incomplete_ta_and_stress_history_fail(self):
        for change in ("bars", "gaps", "duplicate", "future", "unconfirmed"):
            self.packet, self.policy = demo_fixture()
            p = self.packet["proposal"]
            if change == "bars": p["technical_analysis"]["completed_daily_bars"] = 59
            if change == "gaps": p["stress_sizing"]["overnight_gaps"].pop()
            if change == "duplicate": p["stress_sizing"]["overnight_gaps"][0] = deepcopy(p["stress_sizing"]["overnight_gaps"][1])
            if change == "future": p["stress_sizing"]["overnight_gaps"][-1]["session"] = "2026-10-09"
            if change == "unconfirmed": p["stress_sizing"]["complete"] = False
            self.resign()
            with self.subTest(change=change), self.assertRaises(ReviewError): self.check()

    def test_larger_gap_and_costs_define_risk_budget(self):
        p = self.packet["proposal"]
        p["stress_sizing"]["overnight_gaps"][-1]["gap_fraction"] = "-0.06"
        self.resign()
        # 400.2 * .06 + 1 = 25.012, greater than the $25 budget.
        with self.assertRaisesRegex(ReviewError, "Stress loss"): self.check()
        p["costs"]["estimated_total_usd"] = "0.98"
        self.resign()
        self.assertEqual(self.check()["decision"], "PASS")

    def test_risk_budget_boundary_and_round_trip_cost_coverage(self):
        p = self.packet["proposal"]
        p.update(quantity="1", entry_cost_reserve_usd="4.99", approved_notional_usd="105.04")
        p["costs"]["estimated_total_usd"] = "4.99"
        p["stress_sizing"]["overnight_gaps"][-1]["gap_fraction"] = ".2"
        self.resign()
        self.assertEqual(self.check()["decision"], "PASS")  # 100.05 * .2 + 4.99 = 25.
        p.update(entry_cost_reserve_usd="5", approved_notional_usd="105.05")
        p["costs"]["estimated_total_usd"] = "5"
        self.resign()
        with self.assertRaisesRegex(ReviewError, "Stress loss"): self.check()
        p["costs"]["coverage"] = "ENTRY_ONLY"
        self.resign()
        with self.assertRaisesRegex(ReviewError, "round-trip"): self.check()

    def test_earnings_requires_last_eight_confirmed_release_gaps(self):
        p = self.packet["proposal"]
        p["sleeve"] = "EARNINGS_OVERNIGHT"
        self.resign()
        with self.assertRaisesRegex(ReviewError, "eight confirmed"): self.check()
        p["stress_sizing"]["earnings_releases"] = [
            {"release_id": f"SYNTHETIC_{year}_{month}", "release_at": f"{year}-{month:02d}-01T20:05:00Z",
             "issuer_confirmed": True, "source": "SYNTHETIC_ISSUER", "overnight_gap_fraction": ".03"}
            for year in (2024, 2025) for month in (1, 4, 7, 10)]
        self.resign()
        self.assertEqual(self.check()["decision"], "PASS")
        p["stress_sizing"]["earnings_releases"][-1]["overnight_gap_fraction"] = "-.1"
        self.resign()
        with self.assertRaisesRegex(ReviewError, "Stress loss"): self.check()
        p["stress_sizing"]["earnings_releases"][-1]["issuer_confirmed"] = False
        self.resign()
        with self.assertRaisesRegex(ReviewError, "confirmed"): self.check()

    def test_new_entries_pause_at_night_loss_or_drawdown_or_latched_pause(self):
        for change in ("night", "drawdown", "latched", "night_latched", "other-account", "stale"):
            self.packet, self.policy = demo_fixture()
            state = self.packet["proposal"]["strategy_risk_state"]
            if change == "night": state["equity_usd"] = "9900"
            if change == "drawdown": state["cash_flow_adjusted_high_water_mark_usd"] = "10500"
            if change == "latched": state["drawdown_pause_latched"] = True
            if change == "night_latched": state["night_loss_pause_latched"] = True
            if change == "other-account": state["account_id"] = "other"
            if change == "stale": state["observed_at"] = "2026-10-08T19:53:00Z"
            self.resign()
            with self.subTest(change=change), self.assertRaises(ReviewError): self.check()

    def test_public_stress_helper_returns_fraction_without_deducting_costs(self):
        p = self.packet["proposal"]
        self.assertEqual(stress_loss_fraction(self.policy, p["technical_analysis"], p["stress_sizing"],
                         p["entry_session"], self.packet["now"], p["sleeve"]), Decimal(".02"))


class StrategyEquityTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()
        self.packet = equity_packet(self.policy)

    def state(self, **kwargs):
        return build_strategy_risk_state(self.policy, self.packet, self.packet["observed_at"], **kwargs)

    def advance(self, **changes):
        self.packet["observed_at"] = "2026-10-08T19:55:01Z"
        self.packet.update(changes)

    def test_start_at_allocation_and_mark_owned_positions_at_bid(self):
        self.packet["cash_usd"] = "9600"
        self.packet["positions"] = [{"position_id": "SYNTHETIC_POS", "account_id": self.packet["account_id"],
            "mode": "DEMO", "strategy_id": self.policy["strategy_id"], "strategy_included": True,
            "source": "SYNTHETIC_BID", "observed_at": self.packet["observed_at"], "quantity": "4", "bid": "99.9"}]
        state = self.state()
        self.assertEqual(Decimal(state["equity_usd"]), Decimal("9999.6"))
        self.assertEqual(Decimal(state["cash_flow_adjusted_high_water_mark_usd"]), Decimal("10000"))

    def test_exclude_override_positions_and_require_segregated_cash(self):
        self.packet["positions"] = [{"position_id": "SYNTHETIC_OKTA_OVERRIDE", "account_id": self.packet["account_id"],
            "mode": "DEMO", "strategy_included": False, "exclusion_reason": "OWNER_NON_STRATEGY_OVERRIDE",
            "quantity": "100", "bid": "999"}]
        state = self.state()
        self.assertEqual(Decimal(state["equity_usd"]), Decimal("10000"))
        self.assertEqual(state["excluded_position_ids"], ["SYNTHETIC_OKTA_OVERRIDE"])
        self.packet["cash_excludes_non_strategy_trades"] = False
        with self.assertRaises(ReviewError): self.state()

    def test_deposit_and_withdrawal_adjust_hwm_and_night_loss(self):
        prior = self.state()
        self.advance(cash_usd="10950", cash_flow_usd="1000")
        state = self.state(prior_state=prior)
        self.assertEqual(Decimal(state["drawdown_usd"]), Decimal("50"))
        self.assertEqual(Decimal(state["night_loss_usd"]), Decimal("50"))
        self.packet["observed_at"] = "2026-10-08T19:55:02Z"
        self.packet.update(cash_usd="9950", cash_flow_usd="-1000")
        state = self.state(prior_state=state)
        self.assertEqual(Decimal(state["cash_flow_adjusted_high_water_mark_usd"]), Decimal("10000"))
        self.assertEqual(Decimal(state["night_loss_usd"]), Decimal("50"))

    def test_night_pause_latches_until_next_night(self):
        self.packet["cash_usd"] = "9900"
        prior = self.state()
        self.assertTrue(prior["night_loss_pause_latched"])
        self.advance(cash_usd="10000")
        prior = self.state(prior_state=prior)
        self.assertTrue(prior["night_loss_pause_latched"])
        self.packet["observed_at"] = "2026-10-09T19:55:00Z"
        self.packet["night_id"] = "2026-10-09"
        self.packet["night_session"] = {"session_date": "2026-10-09", "open_at": "2026-10-09T13:30:00Z", "close_at": "2026-10-09T20:00:00Z"}
        self.assertFalse(self.state(prior_state=prior)["night_loss_pause_latched"])

    def test_night_pause_cannot_reset_with_an_arbitrary_id_or_before_next_review(self):
        self.packet["cash_usd"] = "9900"
        prior = self.state()
        self.advance(night_id="RESET_SAME_NIGHT")
        with self.assertRaises(ReviewError): self.state(prior_state=prior)
        self.packet.update(night_id="2026-10-09", observed_at="2026-10-09T13:30:00Z",
                           night_session={"session_date": "2026-10-09", "open_at": "2026-10-09T13:30:00Z", "close_at": "2026-10-09T20:00:00Z"})
        with self.assertRaisesRegex(ReviewError, "preclose review boundary"):
            self.state(prior_state=prior)

    def test_opening_cannot_be_forged_as_next_night_close(self):
        self.packet["cash_usd"] = "9900"
        prior = self.state()
        self.packet.update(night_id="2026-10-09", observed_at="2026-10-09T13:30:00Z",
                           night_session={"session_date": "2026-10-09", "open_at": "2026-10-09T13:30:00Z",
                                          "close_at": "2026-10-09T13:30:00Z"})
        with self.assertRaisesRegex(ReviewError, "later same-session close"):
            self.state(prior_state=prior)

    def test_same_night_calendar_context_cannot_change(self):
        prior = self.state()
        self.advance()
        self.packet["night_session"]["close_at"] = "2026-10-08T17:00:00Z"
        with self.assertRaisesRegex(ReviewError, "calendar context cannot change"):
            self.state(prior_state=prior)

    def test_calendar_opening_date_and_time_must_match_regular_session(self):
        for opened in ("2026-10-08T13:29:00Z", "2026-10-07T13:30:00Z"):
            self.packet = equity_packet(self.policy)
            self.packet["night_session"]["open_at"] = opened
            with self.subTest(opened=opened), self.assertRaisesRegex(ReviewError, "09:30 exchange opening"):
                self.state()

    def test_early_close_uses_its_supplied_review_boundary(self):
        # Invented calendar event, not a claim about this actual exchange date.
        self.packet["night_session"]["close_at"] = "2026-10-08T17:00:00Z"
        self.packet["observed_at"] = "2026-10-08T16:29:59Z"
        with self.assertRaisesRegex(ReviewError, "preclose review boundary"): self.state()
        self.packet["observed_at"] = "2026-10-08T16:30:00Z"
        self.assertEqual(self.state()["night_session"]["close_at"], "2026-10-08T17:00:00+00:00")

    def test_drawdown_pause_requires_controlled_owner_verifier(self):
        self.packet["cash_usd"] = "9500"
        prior = self.state()
        self.assertTrue(prior["drawdown_pause_latched"])
        self.advance(cash_usd="10000")
        self.assertTrue(self.state(prior_state=prior)["drawdown_pause_latched"])
        self.packet["owner_review_receipt"] = {"approved": True}
        with self.assertRaisesRegex(ReviewError, "externally verified"): self.state(prior_state=prior)
        with self.assertRaises(ReviewError): self.state(prior_state=prior, owner_review_verifier=lambda *args: False)
        state = self.state(prior_state=prior, owner_review_verifier=lambda receipt, state, now: receipt == {"approved": True})
        self.assertFalse(state["drawdown_pause_latched"])
        self.assertTrue(state["owner_review_verified_for_resumption"])

    def test_no_resume_while_drawdown_still_breached(self):
        self.packet["cash_usd"] = "9500"
        prior = self.state()
        self.advance(owner_review_receipt="SYNTHETIC_OWNER_RECEIPT")
        with self.assertRaisesRegex(ReviewError, "still breached"):
            self.state(prior_state=prior, owner_review_verifier=lambda *args: True)

    def test_stale_bid_and_mismatched_prior_scope_fail_closed(self):
        prior = self.state()
        self.advance()
        prior["account_id"] = "other"
        with self.assertRaises(ReviewError): self.state(prior_state=prior)
        self.packet["positions"] = [{"position_id": "SYNTHETIC_POS", "account_id": self.packet["account_id"],
            "mode": "DEMO", "strategy_id": self.policy["strategy_id"], "strategy_included": True,
            "source": "SYNTHETIC_BID", "observed_at": "2026-10-08T19:50:00Z", "quantity": "1", "bid": "100"}]
        with self.assertRaisesRegex(ReviewError, "stale"): self.state()


if __name__ == "__main__": unittest.main()
