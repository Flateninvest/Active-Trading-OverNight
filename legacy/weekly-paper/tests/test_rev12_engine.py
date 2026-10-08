import copy
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from weekly_strategy.calendar import LOCAL, aware, entry_allowed, is_session, schedule, session
from weekly_strategy.engine import WeeklyEngine
from weekly_strategy.evaluation import evaluate
from weekly_strategy.fixtures import synthetic_market, synthetic_selection
from weekly_strategy.cli import main

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "rev12_config.json").read_text())
DECISION = "2026-10-06T19:30:00+00:00"
ENTRY = "2026-10-06T19:55:00+00:00"
PREOPEN = "2026-10-07T13:25:00+00:00"
OPEN = "2026-10-07T13:30:00+00:00"


class CalendarTests(unittest.TestCase):
    def test_normal_and_october_dst_mismatch(self):
        normal = schedule("2026-10-06", CONFIG)
        mismatch = schedule("2026-10-27", CONFIG)
        self.assertIn("21:55", normal["local"]["entry"])
        self.assertIn("15:30", normal["local"]["regular_exit"])
        self.assertIn("20:55", mismatch["local"]["entry"])
        self.assertIn("14:30", mismatch["local"]["regular_exit"])

    def test_march_dst_mismatch(self):
        opening, _ = session("2026-03-10")
        self.assertEqual(opening.astimezone(LOCAL).hour, 14)

    def test_holidays_early_closes_and_2028_new_year_exception(self):
        self.assertFalse(is_session(date(2026, 11, 26)))
        self.assertEqual(session("2026-11-27")[1].astimezone(LOCAL).hour, 19)
        self.assertEqual(session("2026-12-24")[1].astimezone(LOCAL).hour, 19)
        self.assertTrue(is_session(date(2027, 12, 31)))
        self.assertEqual(session("2027-07-02")[1].astimezone(LOCAL).hour, 22)
        self.assertEqual(session("2028-07-03")[1].astimezone(LOCAL).hour, 19)

    def test_friday_weekend_and_holiday_bridging_excluded(self):
        for day in (date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 10),
                    date(2026, 11, 25), date(2026, 12, 24)):
            self.assertFalse(entry_allowed(day), day)
        self.assertTrue(entry_allowed(date(2026, 10, 6)))

    def test_unsupported_calendar_and_naive_timestamp_fail(self):
        with self.assertRaises(ValueError):
            session("2029-01-02")
        with self.assertRaises(ValueError):
            aware("2026-10-06T19:55:00")


class EngineTests(unittest.TestCase):
    def setUp(self):
        # Deliberately place temp artifacts in the repository's writable root.
        tmp_root = ROOT / "results" / "test_temporary"
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=tmp_root)
        self.path = Path(self.temp.name) / "state.sqlite"
        self.config = copy.deepcopy(CONFIG)
        self.engine = WeeklyEngine(self.path, self.config)
        self.selection = synthetic_selection(overlay=False)

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def enter(self, selection=None, decision_market=None, entry_market=None):
        self.engine.load_selection(selection or self.selection)
        self.engine.tick(DECISION, decision_market or synthetic_market(DECISION))
        return self.engine.tick(ENTRY, entry_market or synthetic_market(ENTRY))

    def test_universe_is_immutable_and_duplicate_packet_idempotent(self):
        first = self.engine.load_selection(self.selection)
        self.assertEqual(first, self.engine.load_selection(self.selection))
        changed = copy.deepcopy(self.selection)
        changed["candidates"].append({**changed["candidates"][0], "ticker": "NEW"})
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.engine.load_selection(changed)

    def test_availability_after_selection_cutoff_rejected(self):
        self.selection["candidates"][0]["source_available_at"] = "2026-10-06T07:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "after the selection cutoff"):
            self.engine.load_selection(self.selection)

    def test_selection_future_and_missing_availability_fail_closed(self):
        self.selection["selection_cutoff"] = "2026-10-06T20:00:00+00:00"
        result = self.enter()
        self.assertEqual(result["orders"], [])
        self.assertIn("selection_not_yet_available", result["events"][0]["payload"])

    def test_expired_0dte_and_expiry_on_entry_day_do_not_support_next_open(self):
        for candidate in self.selection["candidates"]:
            candidate["supporting_expiries"] = ["2026-10-05", "2026-10-06"]
        result = self.enter()
        self.assertEqual(result["orders"], [])
        self.assertIn("expired_without", result["events"][0]["payload"])

    def test_expired_evidence_requires_explicit_continuing_thesis(self):
        for candidate in self.selection["candidates"]:
            candidate["supporting_expiries"] = ["2026-10-05"]
            candidate["continuing_thesis"] = True
            candidate["continuing_thesis_evidence"] = "Explicit synthetic approved continuing business thesis"
        self.assertEqual(self.enter()["open_strategy_positions"], 3)

    def test_last_eligible_night_enforced(self):
        for candidate in self.selection["candidates"]:
            candidate["last_eligible_entry"] = "2026-10-06"
        self.engine.load_selection(self.selection)
        at = "2026-10-07T19:30:00+00:00"
        self.engine.tick(at, synthetic_market(at))
        at = "2026-10-07T19:55:00+00:00"
        self.assertEqual(self.engine.tick(at, synthetic_market(at))["orders"], [])

    def test_restart_and_repeated_ticks_do_not_duplicate_buys_or_sells(self):
        self.enter()
        self.engine.close()
        self.engine = WeeklyEngine(self.path, self.config)
        for _ in range(3):
            self.engine.tick(ENTRY, synthetic_market(ENTRY))
        self.assertEqual(len(self.engine.report()["orders"]), 3)
        self.engine.tick(OPEN, synthetic_market(OPEN, "OPEN"))
        self.engine.tick(OPEN, synthetic_market(OPEN, "OPEN"))
        self.assertEqual(len(self.engine.report()["orders"]), 6)
        self.assertEqual(self.engine.report()["open_strategy_positions"], 0)

    def test_scheduler_cannot_invent_a_missed_daily_decision(self):
        self.engine.load_selection(self.selection)
        result = self.engine.tick(ENTRY, synthetic_market(ENTRY))
        self.assertEqual(result["orders"], [])
        self.assertIn("missing_prior_daily_decision", result["events"][0]["payload"])

    def test_late_entry_outside_window_skipped(self):
        self.engine.load_selection(self.selection)
        self.engine.tick(DECISION, synthetic_market(DECISION))
        late = "2026-10-06T20:00:00+00:00"
        self.assertEqual(self.engine.tick(late, synthetic_market(late))["orders"], [])

    def test_stale_delayed_missing_and_future_quotes_skip(self):
        bad = synthetic_market(DECISION)
        bad["quotes"]["AAPL"]["as_of"] = "2026-10-06T19:28:59+00:00"
        bad["quotes"]["GOOG"]["realtime"] = False
        bad["quotes"].pop("MU")
        self.assertEqual(self.enter(decision_market=bad)["orders"], [])

    def test_future_quote_timestamp_rejected(self):
        bad = synthetic_market(DECISION)
        for quote in bad["quotes"].values():
            quote["as_of"] = "2026-10-06T19:30:01+00:00"
        self.assertEqual(self.enter(decision_market=bad)["orders"], [])

    def test_frozen_daily_decision_can_remove_not_add(self):
        bad = synthetic_market(DECISION)
        bad["quotes"].pop("MU")
        result = self.enter(decision_market=bad)
        self.assertEqual({o["ticker"] for o in result["orders"]}, {"AAPL", "GOOG"})

    def test_spread_price_band_and_settlement_checks(self):
        bad = synthetic_market(DECISION)
        bad["quotes"]["AAPL"]["bid"] = 99.0
        bad["quotes"]["GOOG"]["ask"] = 210.0
        bad["quotes"]["GOOG"]["bid"] = 209.99
        bad["quotes"]["MU"]["settlement_type"] = "CFD"
        self.assertEqual(self.enter(decision_market=bad)["orders"], [])

    def test_risk_missing_cash_and_incomplete_costs_skip(self):
        bad = synthetic_market(DECISION)
        bad["costs"].pop("fx_usd")
        self.assertEqual(self.enter(decision_market=bad)["orders"], [])

    def test_account_pause_at_five_before_entry(self):
        bad = synthetic_market(ENTRY)
        bad["account"]["risk_score"] = 5
        self.assertEqual(self.enter(entry_market=bad)["orders"], [])

    def test_exact_broker_identifier_required(self):
        for candidate in self.selection["candidates"]:
            candidate["instrument_id"] = None
        self.assertEqual(self.enter()["orders"], [])

    def test_size_caps_cash_and_no_slot_replacement(self):
        extra = {**self.selection["candidates"][0], "ticker": "EXTRA", "instrument_id": "SYNTHETIC-EXTRA", "rank": 4}
        self.selection["candidates"].append(extra)
        decision = synthetic_market(DECISION)
        decision["quotes"]["EXTRA"] = {**decision["quotes"]["AAPL"], "instrument_id": "SYNTHETIC-EXTRA"}
        entry = synthetic_market(ENTRY)
        entry["quotes"]["EXTRA"] = {**entry["quotes"]["AAPL"], "instrument_id": "SYNTHETIC-EXTRA"}
        entry["order_scenarios"] = {"BUY:AAPL:ENTRY": {"status": "REJECTED"}}
        result = self.enter(decision_market=decision, entry_market=entry)
        result = self.engine.tick(ENTRY, entry)
        self.assertEqual(len(result["orders"]), 3)
        self.assertNotIn("EXTRA", {o["ticker"] for o in result["orders"]})
        self.assertGreaterEqual(result["cash_usd"], 3500.0)
        for order in result["orders"]:
            payload = json.loads(order["payload"])
            self.assertLessEqual(order["quantity"] * payload["reference_price"], 500.0)

    def test_acknowledgement_and_unknown_are_not_fills(self):
        bad = synthetic_market(ENTRY)
        bad["order_scenarios"] = {"BUY": {"status": "ACK"}}
        result = self.enter(entry_market=bad)
        self.assertEqual(result["positions"], [])
        self.assertEqual(result["fills"], [])
        self.assertEqual(result["cash_usd"], 5000.0)
        self.assertEqual(result["pending_orders"], 3)

    def test_inconsistent_acknowledgement_with_quantity_is_not_booked(self):
        bad = synthetic_market(ENTRY)
        bad["order_scenarios"] = {"BUY": {"status": "ACK", "fill_fraction": 1.0}}
        result = self.enter(entry_market=bad)
        self.assertEqual(result["positions"], [])
        self.assertEqual(result["fills"], [])
        self.assertTrue(all(o["status"] == "UNKNOWN" for o in result["orders"]))

    def test_adverse_buy_fill_above_ioc_limit_rejects_without_breaching_caps(self):
        bad = synthetic_market(ENTRY)
        bad["order_scenarios"] = {"BUY:AAPL:ENTRY": {"fill_price": 200.0}}
        result = self.enter(entry_market=bad)
        order = next(o for o in result["orders"] if o["ticker"] == "AAPL")
        self.assertEqual(order["status"], "REJECTED")
        self.assertEqual(order["accounted_quantity"], 0.0)
        self.assertGreaterEqual(result["cash_usd"], 4000.0)

    def test_wrong_strategy_position_id_in_sell_result_is_rejected(self):
        self.enter()
        opening = synthetic_market(OPEN, "OPEN")
        opening["order_scenarios"] = {"SELL": {"status": "ACK"}}
        self.engine.tick(OPEN, opening)
        sells = [o for o in self.engine.report()["orders"] if o["action"] == "SELL"]
        first = sells[0]
        corrupt = self.engine.broker.order_status(first["client_id"])
        corrupt.update({"status": "FILLED", "filled_quantity": first["quantity"],
                        "position_id": sells[1]["position_id"]})
        self.engine.broker.set_result(first["client_id"], corrupt)
        self.engine.db.commit()
        result = self.engine.tick(OPEN, opening)
        self.assertEqual(result["open_strategy_positions"], 3)
        self.assertFalse(any(f["action"] == "SELL" for f in result["fills"]))

    def test_unproven_actual_selection_and_stock_identity_flags_block(self):
        for candidate in self.selection["candidates"]:
            candidate["selection_source_availability_proven"] = False
            candidate["stock_identifier_verified"] = False
        self.assertEqual(self.enter()["orders"], [])

    def test_explicit_flow_only_comparison_does_not_invent_accepted_research(self):
        self.engine.close()
        self.config.update({"research_overlay_enabled": False, "evaluation_variant": "weekly_flow_only"})
        self.engine = WeeklyEngine(self.path.parent / "flow_only.sqlite", self.config)
        for candidate in self.selection["candidates"]:
            candidate["thesis_active"] = False
            candidate["flow_gate_pass"] = True
        self.assertEqual(self.enter()["open_strategy_positions"], 3)

    def test_thesis_invalidation_is_recorded_even_when_risk_common_gate_blocks(self):
        decision = synthetic_market(DECISION)
        decision["invalidated_candidates"] = ["MU"]
        decision["account"]["risk_score"] = 5
        self.enter(decision_market=decision)
        at = "2026-10-07T19:30:00+00:00"
        self.engine.tick(at, synthetic_market(at))
        at = "2026-10-07T19:55:00+00:00"
        result = self.engine.tick(at, synthetic_market(at))
        self.assertNotIn("MU", {o["ticker"] for o in result["orders"]})
        self.assertEqual([i["ticker"] for i in result["invalidations"]], ["MU"])

    def test_unknown_order_blocks_later_entries_and_no_blind_retry(self):
        bad = synthetic_market(ENTRY)
        bad["order_scenarios"] = {"BUY": {"status": "UNKNOWN"}}
        self.enter(entry_market=bad)
        at = "2026-10-07T19:30:00+00:00"
        self.engine.tick(at, synthetic_market(at))
        at = "2026-10-07T19:55:00+00:00"
        result = self.engine.tick(at, synthetic_market(at))
        self.assertEqual(len(result["orders"]), 3)
        self.assertEqual(result["positions"], [])

    def test_partial_entry_reconciled_and_remaining_cancelled(self):
        bad = synthetic_market(ENTRY)
        bad["order_scenarios"] = {"BUY": {"status": "PARTIAL", "fill_fraction": .5}}
        result = self.enter(entry_market=bad)
        self.assertEqual(result["open_strategy_positions"], 3)
        self.assertAlmostEqual(result["cash_usd"], 4250.0, places=3)
        result = self.engine.tick(OPEN, synthetic_market(OPEN, "OPEN"))
        self.assertEqual(result["open_strategy_positions"], 0)
        self.assertTrue(all(o["status"] == "CANCELLED" for o in result["orders"] if o["action"] == "BUY"))

    def test_preopen_partial_fill_fallback_sells_exact_remaining_once(self):
        self.engine.close()
        self.config["exit_mode"] = "B"
        self.engine = WeeklyEngine(self.path.parent / "mode_b.sqlite", self.config)
        self.enter()
        original_qty = {p["position_id"]: p["quantity"] for p in self.engine.report()["positions"]}
        pre = synthetic_market(PREOPEN, "PREOPEN")
        pre["order_scenarios"] = {"SELL": {"status": "PARTIAL", "fill_fraction": .4}}
        self.engine.tick(PREOPEN, pre)
        result = self.engine.tick(OPEN, synthetic_market(OPEN, "OPEN"))
        self.engine.tick(OPEN, synthetic_market(OPEN, "OPEN"))
        self.assertEqual(result["open_strategy_positions"], 0)
        for order in result["orders"]:
            if order["phase"] == "OPEN":
                self.assertAlmostEqual(order["quantity"], original_qty[order["position_id"]] * .6)
        self.assertEqual(len([o for o in result["orders"] if o["phase"] == "OPEN"]), 3)

    def test_failed_preopen_quote_falls_back_without_duplicate(self):
        self.engine.close()
        self.config["exit_mode"] = "B"
        self.engine = WeeklyEngine(self.path.parent / "mode_b.sqlite", self.config)
        self.enter()
        pre = synthetic_market(PREOPEN, "PREOPEN")
        for q in pre["quotes"].values():
            q["same_position_preopen_close_verified"] = False
        self.engine.tick(PREOPEN, pre)
        result = self.engine.tick(OPEN, synthetic_market(OPEN, "OPEN"))
        self.assertEqual(result["open_strategy_positions"], 0)
        self.assertFalse(any(o["phase"] == "PREOPEN" for o in result["orders"]))
        self.assertEqual(sum(e["kind"] == "PREOPEN_FALLBACK_TO_REGULAR_OPEN" for e in result["events"]), 3)

    def test_unknown_preopen_cancel_prevents_duplicate_fallback(self):
        self.engine.close()
        self.config["exit_mode"] = "B"
        self.engine = WeeklyEngine(self.path.parent / "mode_b.sqlite", self.config)
        self.enter()
        pre = synthetic_market(PREOPEN, "PREOPEN")
        pre["order_scenarios"] = {"SELL": {"status": "UNKNOWN", "cancel_confirmed": False}}
        self.engine.tick(PREOPEN, pre)
        result = self.engine.tick(OPEN, synthetic_market(OPEN, "OPEN"))
        self.assertFalse(any(o["phase"] == "OPEN" for o in result["orders"]))
        self.assertEqual(result["open_strategy_positions"], 3)

    def test_closes_only_strategy_owned_position_ids_preserving_core(self):
        self.enter()
        core_values = ["SYNTHETIC-CORE-PLTR", "PLTR", "SYNTHETIC-PLTR", "CORE", 100., 10.,
                       "2026-10-06", OPEN, PREOPEN, "A", 0., 0., 0.]
        self.engine.db.execute("INSERT INTO positions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", core_values)
        self.engine.db.commit()
        result = self.engine.tick(OPEN, synthetic_market(OPEN, "OPEN"))
        core = next(p for p in result["positions"] if p["position_id"] == "SYNTHETIC-CORE-PLTR")
        self.assertEqual(core["quantity"], 100.)
        self.assertTrue(all(o["position_id"] != core["position_id"] for o in result["orders"] if o["action"] == "SELL"))

    def test_no_double_spread_or_fee_accounting(self):
        entry = synthetic_market(ENTRY)
        entry["costs"]["other_usd"] = .10
        self.enter(entry_market=entry)
        opening = synthetic_market(OPEN, "OPEN")
        opening["costs"]["other_usd"] = .20
        result = self.engine.tick(OPEN, opening)
        self.engine.tick(OPEN, opening)
        expected_gross = sum(p["realized_gross"] for p in result["positions"])
        self.assertAlmostEqual(result["recorded_cost_usd"], .90)
        self.assertAlmostEqual(result["net_realized_pnl_usd"], expected_gross - .90)
        self.assertAlmostEqual(result["cash_usd"] - 5000., result["net_realized_pnl_usd"])

    def test_same_stock_can_reenter_next_eligible_night(self):
        self.enter()
        self.engine.tick(OPEN, synthetic_market(OPEN, "OPEN"))
        decision = "2026-10-07T19:30:00+00:00"
        entry = "2026-10-07T19:55:00+00:00"
        self.engine.tick(decision, synthetic_market(decision))
        result = self.engine.tick(entry, synthetic_market(entry))
        buys = [o for o in result["orders"] if o["action"] == "BUY"]
        self.assertEqual(len(buys), 6)
        self.assertEqual({o["session_date"] for o in buys}, {"2026-10-06", "2026-10-07"})

    def test_explicit_thesis_invalidation_persists_across_restart_and_missing_flag(self):
        decision = synthetic_market(DECISION)
        decision["invalidated_candidates"] = ["MU"]
        self.enter(decision_market=decision)
        self.engine.tick(OPEN, synthetic_market(OPEN, "OPEN"))
        self.engine.close()
        self.engine = WeeklyEngine(self.path, self.config)
        at = "2026-10-07T19:30:00+00:00"
        self.engine.tick(at, synthetic_market(at))
        at = "2026-10-07T19:55:00+00:00"
        result = self.engine.tick(at, synthetic_market(at))
        self.assertNotIn("MU", {o["ticker"] for o in result["orders"]})
        self.assertEqual([i["ticker"] for i in result["invalidations"]], ["MU"])

    def test_live_mode_outer_limits_and_changed_restart_config_disabled(self):
        for changes in ({"mode": "live"}, {"live_enabled": True}, {"maximum_name_weight": .15}, {"outer_limits_enabled": True}):
            with self.assertRaises((ValueError, PermissionError)):
                WeeklyEngine(self.path.parent / "other.sqlite", {**CONFIG, **changes})
        with self.assertRaisesRegex(ValueError, "Configuration changed"):
            WeeklyEngine(self.path, {**CONFIG, "maximum_spread_bps": 25})

    def test_exposure_matched_spy_and_zero_yield_cash(self):
        self.enter()
        result = self.engine.tick(OPEN, synthetic_market(OPEN, "OPEN"))
        metrics = evaluate(result, 5000., {"2026-10-06": .01})
        invested = sum(t["invested_usd"] for t in metrics["trades"])
        self.assertAlmostEqual(metrics["spy_matched_exposure_gross_usd"], invested * .01)
        self.assertAlmostEqual(metrics["nights"][0]["cash_weight"], 1 - invested / 5000.)
        self.assertEqual(metrics["independent_nights"], 1)
        self.assertEqual(metrics["weeks"], 1)

    def test_cash_skipped_nights_retained_and_unresolved_equity_null(self):
        bad = synthetic_market(DECISION)
        bad["account"]["risk_score"] = 5
        result = self.enter(decision_market=bad)
        metrics = evaluate(result, 5000., {})
        self.assertEqual(metrics["cash_or_skipped_nights"], 1)
        self.assertEqual(metrics["nights"][0]["cash_weight"], 1.)
        self.assertEqual(metrics["return_on_total_strategy_equity"], 0.)
        self.assertEqual(metrics["spy_matched_exposure_gross_usd"], 0.)

    def test_open_position_or_unknown_order_does_not_report_complete_equity(self):
        result = self.enter()
        metrics = evaluate(result, 5000., {"2026-10-06": .001})
        self.assertIsNone(metrics["return_on_total_strategy_equity"])
        self.assertIsNone(metrics["drawdown_on_completed_nights"])
        self.assertIsNone(metrics["net_pnl_usd"])
        self.assertIsNone(metrics["nights"][0]["cash_weight"])
        self.assertIsNone(metrics["nights"][0]["return_on_invested"])

    def test_core_holding_pnl_fees_and_open_units_are_excluded_from_strategy_metrics(self):
        self.enter()
        self.engine.tick(OPEN, synthetic_market(OPEN, "OPEN"))
        before = self.engine.report()
        core_values = ["SYNTHETIC-CORE-RKLB", "RKLB", "SYNTHETIC-RKLB", "CORE", 100., 10.,
                       "2026-10-06", OPEN, PREOPEN, "A", 777., 99999., 555.]
        self.engine.db.execute("INSERT INTO positions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", core_values)
        self.engine.db.commit()
        after = self.engine.report()
        self.assertEqual(before["gross_realized_pnl_usd"], after["gross_realized_pnl_usd"])
        self.assertEqual(before["recorded_cost_usd"], after["recorded_cost_usd"])
        self.assertEqual(evaluate(before), evaluate(after))

    def test_known_entry_cost_recorded_while_open_and_unknown_exit_cost_nulls_net(self):
        entry = synthetic_market(ENTRY)
        entry["costs"]["other_usd"] = .10
        result = self.enter(entry_market=entry)
        metrics = evaluate(result)
        self.assertAlmostEqual(metrics["recorded_trading_cost_usd"], .30)
        opening = synthetic_market(OPEN, "OPEN")
        opening["costs"] = None
        result = self.engine.tick(OPEN, opening)
        self.assertFalse(result["costs_complete"])
        self.assertIsNone(result["net_realized_pnl_usd"])
        metrics = evaluate(result)
        self.assertIsNone(metrics["net_pnl_usd"])
        self.assertIsNone(metrics["trading_cost_usd"])

    def test_scheduler_one_tick_command_is_persistent_and_idempotent(self):
        folder = self.path.parent
        (folder / "selection.json").write_text(json.dumps(self.selection))
        (folder / "market.json").write_text(json.dumps(synthetic_market(DECISION)))
        args = ["scheduler", "--selection", str(folder / "selection.json"), "--market", str(folder / "market.json"),
                "--database", str(folder / "scheduler.sqlite"), "--report", str(folder / "report.json"),
                "--log", str(folder / "scheduler.log"), "--at", DECISION, "--max-ticks", "1"]
        main(args)
        main(args)
        report = json.loads((folder / "report.json").read_text())
        self.assertEqual(sum(e["kind"] == "DAILY_DECISION" for e in report["events"]), 1)
        self.assertEqual(report["orders"], [])


if __name__ == "__main__":
    unittest.main()
