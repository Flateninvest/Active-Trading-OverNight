"""Synthetic safety and accounting checks; never market/backtest evidence."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from active_trading.earnings import (  # noqa: E402
    EarningsPlanningError, build_shadow_plan, schedule_earnings_event,
    synthetic_demo_packet,
)


def uncapped_packet():
    packet = synthetic_demo_packet()
    packet["account"].update(equity_usd="10000", uncommitted_buying_power_usd="10000", cost_reserve_usd="0")
    packet["frozen_allocation"]["equity_usd"] = "10000"
    packet["frozen_allocation"]["pool_ceiling_usd"] = "2000"
    return packet


def amounts(plan):
    return {row["ticker"]: Decimal(row["proposed_notional_usd"]) for row in plan["proposals"]}


def one_event(packet):
    packet["events"] = packet["events"][:1]
    packet["combined_review"]["earnings_reviewed_event_ids"] = ["SYNTH_A"]
    packet["frozen_allocation"]["convictions"] = {"SYNTH_A": "HIGH"}
    return packet


class EarningsAllocationTests(unittest.TestCase):
    def test_weighting_name_clip_floor_and_cash_are_reproducible(self):
        plan = build_shadow_plan(uncapped_packet())
        self.assertEqual(amounts(plan), {"SYNTHA": Decimal("800.00"), "SYNTHB": Decimal("666.66"), "SYNTHC": Decimal("333.33")})
        self.assertEqual(plan["earnings_allocation_usd"], "1799.99")
        self.assertEqual(plan["unallocated_earnings_budget_usd"], "200.01")
        self.assertEqual(plan, build_shadow_plan(uncapped_packet()))

    def test_combined_gross_cost_reserve_is_applied_before_weights(self):
        plan = build_shadow_plan(synthetic_demo_packet())
        self.assertEqual(plan["allocation_pool_usd"], "1490.00")
        self.assertEqual(amounts(plan), {"SYNTHA": Decimal("500.00"), "SYNTHB": Decimal("496.66"), "SYNTHC": Decimal("248.33")})
        self.assertLessEqual(Decimal(plan["combined_gross_with_proposals_and_reserved_costs_usd"]), Decimal("1500"))

    def test_caps_can_flatten_conviction_without_redistribution(self):
        packet = synthetic_demo_packet()
        packet["account"]["cost_reserve_usd"] = "0"
        packet["frozen_allocation"]["pool_ceiling_usd"] = "1500"
        plan = build_shadow_plan(packet)
        self.assertTrue(plan["caps_flatten_conviction_ordering"])
        self.assertEqual(amounts(plan), {"SYNTHA": Decimal("500"), "SYNTHB": Decimal("500"), "SYNTHC": Decimal("250")})

    def test_failing_review_keeps_its_frozen_share_cash(self):
        packet = uncapped_packet()
        before = amounts(build_shadow_plan(packet))
        packet["events"][0]["review"]["ta_pass"] = False
        after = build_shadow_plan(packet)
        self.assertEqual(amounts(after), {"SYNTHB": before["SYNTHB"], "SYNTHC": before["SYNTHC"]})
        self.assertEqual(len(after["blocked_events"]), 1)

    def test_risk_downgrade_lowers_only_its_numerator(self):
        packet = uncapped_packet()
        packet["events"][0]["risk_review_conviction"] = "CAUTIOUS"
        self.assertEqual(amounts(build_shadow_plan(packet)), {"SYNTHA": Decimal("333.33"), "SYNTHB": Decimal("666.66"), "SYNTHC": Decimal("333.33")})

    def test_risk_exclusion_keeps_denominator(self):
        packet = uncapped_packet()
        packet["events"][0]["risk_review_conviction"] = "EXCLUDE"
        self.assertEqual(amounts(build_shadow_plan(packet)), {"SYNTHB": Decimal("666.66"), "SYNTHC": Decimal("333.33")})

    def test_risk_cannot_raise_conviction(self):
        packet = uncapped_packet()
        packet["events"][2]["risk_review_conviction"] = "HIGH"
        plan = build_shadow_plan(packet)
        self.assertNotIn("SYNTHC", amounts(plan))
        self.assertIn("never raise", plan["blocked_events"][0]["reason"])

    def test_refresh_cannot_grow_pool_or_nav_name_cap(self):
        packet = uncapped_packet()
        packet["frozen_allocation"].update(pool_ceiling_usd="1200", equity_usd="4000")
        first = amounts(build_shadow_plan(packet))
        packet["account"].update(equity_usd="100000", uncommitted_buying_power_usd="100000")
        self.assertEqual(first, amounts(build_shadow_plan(packet)))
        self.assertEqual(first["SYNTHA"], Decimal("400"))

    def test_refresh_ceilings_prevent_growth_after_cash_capacity_increases(self):
        packet = uncapped_packet()
        packet["account"]["uncommitted_buying_power_usd"] = "1000"
        first = build_shadow_plan(packet)
        packet["prior_proposed_ceiling_usd_by_event_id"] = first["refresh_ceiling_usd_by_event_id"]
        packet["account"]["uncommitted_buying_power_usd"] = "10000"
        self.assertEqual(amounts(first), amounts(build_shadow_plan(packet)))

    def test_refresh_ceilings_prevent_growth_after_ordinary_proposal_removed(self):
        packet = synthetic_demo_packet()
        packet["events"] = packet["events"][:2]
        packet["combined_review"]["earnings_reviewed_event_ids"] = ["SYNTH_A", "SYNTH_B"]
        packet["frozen_allocation"]["convictions"].pop("SYNTH_C")
        packet["combined_review"]["ordinary_reviewed_tickers"] = ["ORDINARY"]
        packet["account"]["ordinary_proposals"] = [{"ticker": "ORDINARY", "notional_usd": "500", "sleeve": "ORDINARY"}]
        first = build_shadow_plan(packet)
        packet["prior_proposed_ceiling_usd_by_event_id"] = first["refresh_ceiling_usd_by_event_id"]
        packet["account"]["ordinary_proposals"] = []
        self.assertEqual(amounts(first), amounts(build_shadow_plan(packet)))

    def test_rejected_event_zero_refresh_ceiling_cannot_reappear(self):
        packet = uncapped_packet()
        packet["events"][0]["review"]["ta_pass"] = False
        first = build_shadow_plan(packet)
        packet["prior_proposed_ceiling_usd_by_event_id"] = first["refresh_ceiling_usd_by_event_id"]
        packet["events"][0]["review"]["ta_pass"] = True
        self.assertEqual(amounts(first), amounts(build_shadow_plan(packet)))

    def test_impossible_frozen_pool_or_increased_prior_ceiling_is_refused(self):
        packet = synthetic_demo_packet()
        packet["frozen_allocation"]["pool_ceiling_usd"] = "1500.01"
        with self.assertRaisesRegex(EarningsPlanningError, "frozen NAV gross"):
            build_shadow_plan(packet)
        packet = uncapped_packet()
        packet["prior_proposed_ceiling_usd_by_event_id"] = {"SYNTH_A": "800.01", "SYNTH_B": "666.66", "SYNTH_C": "333.33"}
        with self.assertRaisesRegex(EarningsPlanningError, "original frozen"):
            build_shadow_plan(packet)

    def test_original_conviction_cannot_change_in_refresh(self):
        packet = uncapped_packet()
        packet["events"][0]["conviction"] = "CAUTIOUS"
        with self.assertRaisesRegex(EarningsPlanningError, "frozen conviction"):
            build_shadow_plan(packet)

    def test_sleeve_budget_cannot_change_without_new_frozen_plan(self):
        packet = uncapped_packet()
        packet["earnings_budget_usd"] = "1000"
        with self.assertRaisesRegex(EarningsPlanningError, "frozen ceiling"):
            build_shadow_plan(packet)

    def test_requested_budget_is_ceiling_not_added_capital(self):
        packet = uncapped_packet()
        packet["earnings_budget_usd"] = "999999"
        plan = build_shadow_plan(packet)
        self.assertEqual(plan["earnings_budget_ceiling_usd"], "2000.00")
        self.assertEqual(plan["whole_book_gross_limit_usd"], "3000.00")

    def test_holdings_and_pending_block_second_purchase_and_count_exposure(self):
        for field in ("holdings", "pending_entries"):
            with self.subTest(field=field):
                packet = uncapped_packet()
                packet["account"][field] = [{"ticker": "SYNTHA", "notional_usd": "1000", "sleeve": "EARNINGS"}]
                plan = build_shadow_plan(packet)
                self.assertNotIn("SYNTHA", amounts(plan))
                self.assertEqual(plan["whole_book_gross_before_usd"], "1000.00")

    def test_ordinary_proposal_uses_same_review_and_gross_slots(self):
        packet = one_event(uncapped_packet())
        packet["combined_review"]["ordinary_reviewed_tickers"] = ["ORDINARY"]
        packet["account"]["ordinary_proposals"] = [{"ticker": "ORDINARY", "notional_usd": "1000", "sleeve": "ORDINARY"}]
        packet["account"]["holdings"] = [{"ticker": "EXISTING", "notional_usd": "1500", "sleeve": "OTHER"}]
        plan = build_shadow_plan(packet)
        self.assertEqual(plan["allocation_pool_usd"], "500.00")
        self.assertEqual(amounts(plan)["SYNTHA"], Decimal("500"))

    def test_ordinary_proposal_cannot_exceed_shared_name_cap(self):
        packet = one_event(uncapped_packet())
        packet["combined_review"]["ordinary_reviewed_tickers"] = ["ORDINARY"]
        packet["account"]["ordinary_proposals"] = [{"ticker": "ORDINARY", "notional_usd": "1000.01", "sleeve": "ORDINARY"}]
        with self.assertRaisesRegex(EarningsPlanningError, "10% NAV/name"):
            build_shadow_plan(packet)

    def test_existing_positions_leave_only_available_slot_without_redistribution(self):
        packet = uncapped_packet()
        packet["account"]["holdings"] = [{"ticker": "HELDONE", "notional_usd": "10", "sleeve": "OTHER"}, {"ticker": "HELDTWO", "notional_usd": "10", "sleeve": "OTHER"}]
        plan = build_shadow_plan(packet)
        self.assertEqual(amounts(plan), {"SYNTHA": Decimal("800")})
        self.assertEqual(len(plan["blocked_events"]), 2)

    def test_shared_buying_power_and_cash_cost_reserves(self):
        packet = uncapped_packet()
        packet["account"].update(uncommitted_buying_power_usd="110", cash_reserve_usd="100", cost_reserve_usd="10")
        plan = build_shadow_plan(packet)
        self.assertEqual(plan["proposals"], [])
        self.assertEqual(plan["earnings_allocation_usd"], "0.00")

    def test_existing_earnings_held_and_pending_use_sleeve_ceiling(self):
        for field in ("holdings", "pending_entries"):
            with self.subTest(field=field):
                packet = one_event(uncapped_packet())
                packet["account"].update(equity_usd="100000", uncommitted_buying_power_usd="100000")
                packet["account"][field] = [{"ticker": "ALREADY", "notional_usd": "1500", "sleeve": "EARNINGS"}]
                plan = build_shadow_plan(packet)
                self.assertEqual(plan["remaining_earnings_budget_usd"], "500.00")
                self.assertEqual(amounts(plan), {"SYNTHA": Decimal("500")})
                self.assertEqual(plan["unallocated_earnings_budget_usd"], "0.00")

    def test_unknown_sleeve_classification_is_refused(self):
        packet = uncapped_packet()
        packet["account"]["holdings"] = [{"ticker": "UNKNOWN", "notional_usd": "10"}]
        with self.assertRaisesRegex(EarningsPlanningError, "sleeve classification"):
            build_shadow_plan(packet)

    def test_unreconciled_incomplete_unresolved_or_stale_account_blocks(self):
        for field, value in (("state_reconciled", False), ("exposure_complete", "true"),
                             ("unresolved_orders_or_exits", True), ("unresolved_orders_or_exits", 0),
                             ("snapshot_at", "2026-10-07T19:53:59Z")):
            with self.subTest(field=field, value=value):
                packet = uncapped_packet()
                packet["account"][field] = value
                with self.assertRaises(EarningsPlanningError):
                    build_shadow_plan(packet)

    def test_single_name_does_not_consume_other_names_shares(self):
        packet = one_event(uncapped_packet())
        self.assertEqual(amounts(build_shadow_plan(packet)), {"SYNTHA": Decimal("800")})

    def test_no_fractional_support_omits_units(self):
        packet = one_event(uncapped_packet())
        packet["events"][0]["review"]["fractional_units_supported"] = False
        row = build_shadow_plan(packet)["proposals"][0]
        self.assertNotIn("indicative_fractional_units_at_ask", row)
        self.assertTrue(row["units_provisional"])

    def test_shadow_and_product_boundaries_cannot_be_enabled_by_inputs(self):
        packet = uncapped_packet()
        packet.update(broker_writes=True, approval_required=False, options=True)
        plan = build_shadow_plan(packet)
        self.assertFalse(plan["broker_writes"])
        self.assertFalse(plan["execution_approved"])
        self.assertTrue(plan["approval_required"])
        for row in plan["proposals"]:
            self.assertEqual(row["product"], "UNDERLYING_CASH_X1_LONG_ONLY")
            self.assertFalse(row["options"])
            self.assertFalse(row["cfds"])
            self.assertFalse(row["shorts"])
        packet["mode"] = "DEMO"
        with self.assertRaisesRegex(EarningsPlanningError, "only SHADOW"):
            build_shadow_plan(packet)

    def test_duplicate_event_or_ticker_is_refused(self):
        for field in ("event_id", "ticker"):
            with self.subTest(field=field):
                packet = uncapped_packet()
                packet["events"][1][field] = packet["events"][0][field]
                with self.assertRaisesRegex(EarningsPlanningError, "duplicate earnings"):
                    build_shadow_plan(packet)

    def test_maximum_three_combined_review_priorities(self):
        packet = uncapped_packet()
        packet["combined_review"]["ordinary_reviewed_tickers"] = ["FOURTH"]
        with self.assertRaisesRegex(EarningsPlanningError, "at most three"):
            build_shadow_plan(packet)

    def test_global_factual_flags_are_strict_booleans(self):
        for field in ("calendar_complete_and_verified",):
            for value in ("true", 1, None, False):
                with self.subTest(field=field, value=value):
                    packet = uncapped_packet()
                    packet[field] = value
                    with self.assertRaises(EarningsPlanningError):
                        build_shadow_plan(packet)
        packet = uncapped_packet()
        packet["account"]["costs_complete"] = "true"
        with self.assertRaises(EarningsPlanningError):
            build_shadow_plan(packet)

    def test_nonfinite_negative_and_boolean_money_is_refused(self):
        for value in ("NaN", "Infinity", "-0.01", True, None):
            with self.subTest(value=value):
                packet = uncapped_packet()
                packet["account"]["equity_usd"] = value
                with self.assertRaises(EarningsPlanningError):
                    build_shadow_plan(packet)

    def test_unknown_or_high_governing_risk_score_blocks(self):
        packet = uncapped_packet()
        packet["account"]["account_risk_score"] = None
        with self.assertRaises(EarningsPlanningError):
            build_shadow_plan(packet)
        packet["account"]["account_risk_score"] = 5
        self.assertEqual(build_shadow_plan(packet)["proposals"], [])

    def test_pre_freeze_receipt_and_publication_chronology(self):
        for field, value in (("received_at", "2026-10-07T07:00:00Z"), ("published_at", "2026-10-05T07:00:00Z")):
            with self.subTest(field=field):
                packet = uncapped_packet()
                packet["source_receipts"][0][field] = value
                with self.assertRaises(EarningsPlanningError):
                    build_shadow_plan(packet)

    def test_wrong_freeze_timezone_or_new_unregistered_event_is_refused(self):
        packet = uncapped_packet()
        packet["combined_review"]["morning_freeze_at"] = "2026-10-07T08:15:00Z"
        with self.assertRaisesRegex(EarningsPlanningError, "08:15"):
            build_shadow_plan(packet)
        packet = uncapped_packet()
        packet["combined_review"]["earnings_reviewed_event_ids"] = ["SYNTH_A", "SYNTH_B"]
        packet["frozen_allocation"]["convictions"].pop("SYNTH_C")
        with self.assertRaisesRegex(EarningsPlanningError, "exactly match"):
            build_shadow_plan(packet)


class EarningsFinalReviewTests(unittest.TestCase):
    def check_block(self, field, value, reason):
        packet = one_event(uncapped_packet())
        packet["events"][0]["review"][field] = value
        plan = build_shadow_plan(packet)
        self.assertEqual(plan["proposals"], [])
        self.assertIn(reason, plan["blocked_events"][0]["reason"])

    def test_each_required_factual_gate_blocks_when_missing_or_false(self):
        for field in ("issuer_window_rechecked", "ta_pass", "news_no_conflict", "risk_pass", "costs_known", "underlying_cash_x1_eligible"):
            for value in (None, False, "true"):
                with self.subTest(field=field, value=value):
                    self.check_block(field, value, "explicit true")

    def test_high_beta_requires_additional_risk_review(self):
        packet = one_event(uncapped_packet())
        packet["events"][0]["high_beta_review_required"] = True
        packet["events"][0]["review"]["enhanced_risk_review_pass"] = False
        self.assertEqual(build_shadow_plan(packet)["proposals"], [])

    def test_review_is_event_day_current_and_not_future(self):
        for value in ("2026-10-06T19:55:00Z", "2026-10-07T19:29:59Z", "2026-10-07T19:55:01Z", "2026-10-07T19:55:00"):
            with self.subTest(value=value):
                self.check_block("reviewed_at", value, "review")

    def test_future_and_stale_quotes_block(self):
        self.check_block("quote_at", "2026-10-07T19:55:01Z", "future evidence")
        self.check_block("quote_at", "2026-10-07T19:53:59Z", "older than 60")
        self.check_block("quote_type", "DELAYED", "REALTIME")

    def test_spread_and_monday_reference_boundaries(self):
        self.check_block("bid", "99", "20 basis points")
        self.check_block("ask", "98", "crossed")
        self.check_block("monday_reference_close", "97", "+/-2%")
        self.check_block("monday_reference_date", "2026-09-28", "current-week Monday")
        self.check_block("monday_reference_verified_at", "2026-10-07T19:56:00Z", "future evidence")
        self.check_block("monday_reference_verified_at", "2026-10-05T18:00:00Z", "future evidence")

    def test_ta_history_and_finite_prices(self):
        self.check_block("completed_daily_bars", 59, "60 completed")
        self.check_block("completed_daily_bars", "60.5", "60 completed")
        self.check_block("ask", "NaN", "finite")


class EarningsCalendarTests(unittest.TestCase):
    def setUp(self):
        self.packet = synthetic_demo_packet()
        self.event = self.packet["events"][0]

    def schedule(self):
        return schedule_earnings_event(self.event, self.packet["sessions"], now=self.packet["as_of"])

    def test_amc_maps_to_event_close_then_next_open(self):
        result = self.schedule()
        self.assertEqual(result["entry_session_date"], "2026-10-07")
        self.assertEqual(result["exit_session_date"], "2026-10-08")
        self.assertEqual(result["entry_target_paris"], "2026-10-07T21:55:00+02:00")
        self.assertEqual(result["exit_open_paris"], "2026-10-08T15:30:00+02:00")

    def test_bmo_maps_to_previous_session_close(self):
        for field in ("sheet_earnings_date", "issuer_earnings_date"):
            self.event[field] = "2026-10-08"
        for field in ("sheet_release_window", "issuer_release_window"):
            self.event[field] = "BMO"
        self.event["issuer_release_at"] = "2026-10-08T12:00:00Z"
        self.assertEqual(self.schedule()["entry_session_date"], "2026-10-07")

    def test_preparation_can_precede_event_day(self):
        self.packet["as_of"] = "2026-10-05T07:00:00Z"
        self.event["issuer_verified_at"] = "2026-10-05T06:55:00Z"
        self.assertEqual(self.schedule()["entry_session_date"], "2026-10-07")

    def test_unconfirmed_call_time_is_not_release_evidence(self):
        self.event.update(issuer_timing_confirmed=False, earnings_call_at="2026-10-07T21:00:00Z")
        with self.assertRaisesRegex(EarningsPlanningError, "explicit true"):
            self.schedule()

    def test_sheet_issuer_date_or_window_conflict_blocks(self):
        for field, value in (("issuer_earnings_date", "2026-10-08"), ("issuer_release_window", "BMO")):
            with self.subTest(field=field):
                event = deepcopy(self.event)
                event[field] = value
                with self.assertRaisesRegex(EarningsPlanningError, "conflict"):
                    schedule_earnings_event(event, self.packet["sessions"], now=self.packet["as_of"])

    def test_release_outside_interval_or_already_released_blocks(self):
        for release in ("2026-10-07T20:00:00Z", "2026-10-08T13:30:00Z", "2026-10-07T18:00:00Z"):
            with self.subTest(release=release):
                self.event["issuer_release_at"] = release
                with self.assertRaisesRegex(EarningsPlanningError, "outside"):
                    self.schedule()
        self.event.pop("issuer_release_at")
        self.event["release_status"] = "RELEASED"
        with self.assertRaisesRegex(EarningsPlanningError, "NOT_RELEASED"):
            self.schedule()

    def test_future_verification_naive_time_or_past_entry_blocks(self):
        self.event["issuer_verified_at"] = "2026-10-07T19:55:01Z"
        with self.assertRaisesRegex(EarningsPlanningError, "future evidence"):
            self.schedule()
        self.event["issuer_verified_at"] = "2026-10-07T19:50:00"
        with self.assertRaisesRegex(EarningsPlanningError, "timezone-aware"):
            self.schedule()
        self.event["issuer_verified_at"] = "2026-10-07T19:50:00Z"
        self.packet["as_of"] = "2026-10-07T19:59:00Z"
        with self.assertRaisesRegex(EarningsPlanningError, "cutoff has passed"):
            self.schedule()

    def test_weekend_holiday_and_missing_calendar_blocks(self):
        self.packet["sessions"][2] = {"session_date": "2026-10-09", "exchange_timezone": "America/New_York",
                                      "open_at": "2026-10-09T13:30:00Z", "close_at": "2026-10-09T20:00:00Z"}
        with self.assertRaisesRegex(EarningsPlanningError, "holiday bridge"):
            self.schedule()
        self.packet["sessions"] = self.packet["sessions"][:2]
        with self.assertRaisesRegex(EarningsPlanningError, "both event entry"):
            self.schedule()

    def test_monday_and_friday_entries_remain_excluded(self):
        for day, next_day in (("2026-10-05", "2026-10-06"), ("2026-10-09", "2026-10-12")):
            with self.subTest(day=day):
                event = deepcopy(self.event)
                event.update(sheet_earnings_date=day, issuer_earnings_date=day, issuer_verified_at="2026-10-01T12:00:00Z")
                sessions = [{"session_date": d, "exchange_timezone": "America/New_York", "open_at": d + "T13:30:00Z", "close_at": d + "T20:00:00Z"} for d in (day, next_day)]
                with self.assertRaisesRegex(EarningsPlanningError, "Tuesday-Thursday"):
                    schedule_earnings_event(event, sessions, now="2026-10-01T13:00:00Z")

    def test_dst_mismatch_uses_iana_conversion(self):
        event = deepcopy(self.event)
        event.update(sheet_earnings_date="2026-10-28", issuer_earnings_date="2026-10-28", issuer_verified_at="2026-10-28T18:00:00Z")
        sessions = [{"session_date": d, "exchange_timezone": "America/New_York", "open_at": d + "T13:30:00Z", "close_at": d + "T20:00:00Z"} for d in ("2026-10-28", "2026-10-29")]
        result = schedule_earnings_event(event, sessions, now="2026-10-28T19:55:00Z")
        self.assertEqual(result["entry_target_paris"], "2026-10-28T20:55:00+01:00")
        self.assertEqual(result["exit_open_paris"], "2026-10-29T14:30:00+01:00")

    def test_supplied_early_close_changes_target_not_hold_rule(self):
        # Deliberately invented early close: software fixture, not an NYSE claim.
        self.packet["sessions"][1]["close_at"] = "2026-10-07T17:00:00Z"
        self.packet["as_of"] = "2026-10-07T16:50:00Z"
        self.event["issuer_verified_at"] = "2026-10-07T16:45:00Z"
        result = self.schedule()
        self.assertEqual(result["entry_target_at"], "2026-10-07T16:55:00+00:00")
        self.assertEqual(result["exit_open_at"], "2026-10-08T13:30:00+00:00")

    def test_calendar_duplicates_wrong_timezone_and_naive_times_block(self):
        for change in ("duplicate", "timezone", "naive"):
            with self.subTest(change=change):
                sessions = deepcopy(self.packet["sessions"])
                if change == "duplicate":
                    sessions[1] = deepcopy(sessions[0])
                elif change == "timezone":
                    sessions[1]["exchange_timezone"] = "EST"
                else:
                    sessions[1]["close_at"] = "2026-10-07T20:00:00"
                with self.assertRaises(EarningsPlanningError):
                    schedule_earnings_event(self.event, sessions, now=self.packet["as_of"])


class EarningsCliTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "earnings_plan.py"), *args],
                              cwd=ROOT, capture_output=True, text=True)

    def test_demo_is_explicitly_synthetic_and_never_approved(self):
        completed = self.cli("--demo")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["fixture_kind"], "SYNTHETIC_OPERATIONAL_FIXTURE")
        self.assertFalse(output["plan"]["broker_writes"])
        self.assertFalse(output["plan"]["profitability_evidence"])
        self.assertFalse(output["plan"]["execution_approved"])

    def test_private_input_requires_external_output_and_no_overwrite(self):
        # Outside Git, and independent of the portable runner's in-Git tempdir.
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as folder:
            self.assertEqual(Path(folder).resolve().parent, ROOT.parent.resolve())
            input_path = Path(folder) / "private-input.json"
            output_path = Path(folder) / "private-plan.json"
            input_path.write_text(json.dumps(synthetic_demo_packet()), encoding="utf-8")
            self.assertEqual(self.cli("--input", str(input_path)).returncode, 2)
            self.assertEqual(self.cli("--input", str(input_path), "--output", str(output_path)).returncode, 0)
            self.assertFalse(json.loads(output_path.read_text())["broker_writes"])
            self.assertEqual(self.cli("--input", str(input_path), "--output", str(output_path)).returncode, 2)

    def test_git_worktree_output_is_refused(self):
        completed = self.cli("--demo", "--output", str(ROOT / "private-plan.json"))
        self.assertEqual(completed.returncode, 2)
        self.assertFalse((ROOT / "private-plan.json").exists())


if __name__ == "__main__":
    unittest.main()
