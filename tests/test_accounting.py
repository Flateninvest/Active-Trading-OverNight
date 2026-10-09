"""Synthetic economic and ownership checks; no real fills or profitability evidence."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from active_trading.reporting import AccountingError, build_trade_report  # noqa: E402


OWNER = {"account_id": "SYNTHETIC_DEMO_ACCOUNT", "strategy_id": "SYNTHETIC_OVERNIGHT",
         "instrument_id": "SYNTHETIC_INSTRUMENT", "position_id": "SYNTHETIC_POSITION"}


def fill(fill_id, side, quantity, price, stamp, sequence, *, mode="DEMO"):
    return {**OWNER, "mode": mode, "fill_id": fill_id, "side": side,
            "quantity": quantity, "price": price, "currency": "USD", "filled_at": stamp,
            "sequence": sequence}


def fee(fill_id, amount="0", *, mode="DEMO", **updates):
    record = {**OWNER, "mode": mode, "cost_id": "FEE_" + fill_id, "fill_id": fill_id,
        "status": "KNOWN", "complete": True, "amount": amount, "currency": "USD",
        "source": "SYNTHETIC_AGGREGATE_BROKER_CHARGES", "observed_at": "2026-10-07T13:30:01Z"}
    record.update(updates)
    return record


def packet(*, partial=False):
    fills = [fill("ENTRY", "BUY", "10", "50", "2026-10-06T19:55:00Z", 1),
        fill("EXIT", "SELL", "4" if partial else "10", "51", "2026-10-07T13:30:00Z", 2)]
    return {"mode": "DEMO", "ownership": dict(OWNER), "as_of": "2026-10-07T13:30:05Z",
        "fills": fills, "fee_records": [fee("ENTRY", "1"), fee("EXIT", "0.5")],
        "reconciliation": {**OWNER, "mode": "DEMO", "observed_at": "2026-10-07T13:30:04Z",
            "source": "SYNTHETIC_COMPLETE_POSITION_AND_OPEN_ORDERS_SNAPSHOT", "complete": True,
            "position_quantity": "6" if partial else "0", "pending_order_count": 0}}


class TradeAccountingTests(unittest.TestCase):
    def test_full_reconciled_exit_has_fill_profit_less_sourced_fees(self):
        result = build_trade_report(packet())
        self.assertEqual(result["realized_gross_pnl_usd"], "10")
        self.assertEqual(result["observed_fees_usd"], "1.5")
        self.assertEqual(result["final_net_pnl_usd"], "8.5")
        self.assertEqual(result["remaining_quantity"], "0")
        self.assertEqual(result["remaining_fill_cost_basis_usd"], "0")
        self.assertEqual(result["position_status"], "CLOSED_RECONCILED")
        self.assertEqual(result["net_pnl_status"], "FINAL")
        self.assertFalse(result["broker_writes"])

    def test_partial_exit_retains_basis_allocates_entry_fees_and_is_not_closed(self):
        result = build_trade_report(packet(partial=True))
        self.assertEqual(result["remaining_quantity"], "6")
        self.assertEqual(result["remaining_fill_cost_basis_usd"], "300")
        self.assertEqual(result["known_remaining_entry_fee_component_usd"], "0.6")
        self.assertEqual(result["known_realized_fee_component_usd"], "0.9")
        self.assertEqual(result["realized_gross_pnl_usd"], "4")
        self.assertEqual(result["realized_net_pnl_usd"], "3.1")
        self.assertEqual(result["remaining_basis_including_entry_fees_usd"], "300.6")
        self.assertEqual(result["net_pnl_status"], "NOT_FINAL")
        self.assertIsNone(result["final_net_pnl_usd"])
        self.assertFalse(result["closed"])

    def test_decimal_fractional_shares_close_without_phantom_residuals(self):
        value = packet()
        value["fills"] = [fill("A", "BUY", "0.3", "10.10", "2026-10-06T19:55:00Z", 1),
            fill("B", "SELL", "0.1", "10.20", "2026-10-07T13:30:00Z", 2),
            fill("C", "SELL", "0.2", "10.30", "2026-10-07T13:30:00Z", 3)]
        value["fee_records"] = [fee(name, "0.01") for name in ("A", "B", "C")]
        result = build_trade_report(value)
        self.assertEqual(result["remaining_quantity"], "0")
        self.assertEqual(result["remaining_fill_cost_basis_usd"], "0")
        self.assertEqual(result["known_remaining_entry_fee_component_usd"], "0")
        self.assertEqual(Decimal(result["realized_gross_pnl_usd"]), Decimal("0.05"))
        self.assertEqual(Decimal(result["final_net_pnl_usd"]), Decimal("0.02"))

    def test_multiple_entry_prices_use_weighted_cost_basis(self):
        value = packet(partial=True)
        value["fills"].insert(1, fill("ADD", "BUY", "10", "60", "2026-10-06T19:56:00Z", 3))
        value["fee_records"].append(fee("ADD", "1"))
        value["reconciliation"]["position_quantity"] = "16"
        result = build_trade_report(value)
        self.assertEqual(result["average_remaining_fill_price_usd"], "55")
        self.assertEqual(result["remaining_fill_cost_basis_usd"], "880")
        self.assertEqual(result["realized_gross_pnl_usd"], "-16")

    def test_missing_fee_is_unknown_and_not_implicitly_zero(self):
        value = packet()
        value["fee_records"] = value["fee_records"][:1]
        result = build_trade_report(value)
        self.assertEqual(result["realized_gross_pnl_usd"], "10")
        self.assertEqual(result["known_observed_fees_usd"], "1")
        self.assertIsNone(result["observed_fees_usd"])
        self.assertIsNone(result["realized_net_pnl_usd"])
        self.assertIsNone(result["final_net_pnl_usd"])
        self.assertEqual(result["net_pnl_status"], "NOT_FINAL")
        self.assertEqual(result["active_fee_records"][1]["status"], "MISSING")

    def test_explicit_unknown_fee_is_not_zero(self):
        value = packet()
        value["fee_records"][0].update(status="UNKNOWN", amount=None, complete=False)
        result = build_trade_report(value)
        self.assertIsNone(result["final_net_pnl_usd"])
        self.assertIsNone(result["remaining_basis_including_entry_fees_usd"])
        self.assertEqual(result["known_observed_fees_usd"], "0.5")

    def test_sourced_explicit_zero_fees_are_known(self):
        value = packet()
        for record in value["fee_records"]:
            record["amount"] = "0"
        result = build_trade_report(value)
        self.assertEqual(result["observed_fees_usd"], "0")
        self.assertEqual(result["final_net_pnl_usd"], "10")

    def test_known_partial_or_unattested_charges_are_not_final(self):
        value = packet()
        value["fee_records"][0]["complete"] = False
        result = build_trade_report(value)
        self.assertIsNone(result["final_net_pnl_usd"])
        self.assertEqual(result["known_observed_fees_usd"], "1.5")
        del value["fee_records"][0]["complete"]
        self.assertEqual(build_trade_report(value)["net_pnl_status"], "NOT_FINAL")

    def test_zero_fee_requires_nonempty_source(self):
        value = packet()
        value["fee_records"][0].update(amount="0", source="")
        with self.assertRaises(AccountingError):
            build_trade_report(value)

    def test_identical_duplicate_fill_and_cost_replays_do_not_change_economics(self):
        value = packet()
        original = build_trade_report(value)
        value["fills"].append(deepcopy(value["fills"][0]))
        value["fee_records"].append(deepcopy(value["fee_records"][0]))
        result = build_trade_report(value)
        self.assertEqual(result["final_net_pnl_usd"], original["final_net_pnl_usd"])
        self.assertEqual(result["fill_count"], 2)
        self.assertEqual(result["duplicate_fill_replays_removed"], 1)
        self.assertEqual(result["duplicate_cost_replays_removed"], 1)

    def test_conflicting_fill_or_fee_replay_is_rejected(self):
        for records_key, changed_key, changed_value in (("fills", "price", "51"),
                ("fee_records", "amount", "9")):
            with self.subTest(records_key=records_key):
                value = packet()
                conflict = deepcopy(value[records_key][0])
                conflict[changed_key] = changed_value
                value[records_key].append(conflict)
                with self.assertRaisesRegex(AccountingError, "conflicting replay"):
                    build_trade_report(value)

    def test_fee_correction_preserves_history_and_replaces_not_adds(self):
        value = packet()
        value["fee_records"][0].update(status="UNKNOWN", amount=None, complete=False)
        value["fee_records"].append(fee("ENTRY", "2", cost_id="FEE_ENTRY_FINAL",
            supersedes_cost_id="FEE_ENTRY", observed_at="2026-10-07T13:30:02Z"))
        result = build_trade_report(value)
        self.assertEqual(result["fee_history_cost_ids"], ["FEE_ENTRY", "FEE_EXIT", "FEE_ENTRY_FINAL"])
        self.assertEqual(result["observed_fees_usd"], "2.5")
        self.assertEqual(result["final_net_pnl_usd"], "7.5")

    def test_fee_corrections_require_nonbranching_same_fill_later_history(self):
        cases = ("missing", "other_fill", "same_time", "branch", "root")
        for case in cases:
            with self.subTest(case=case):
                value = packet()
                correction = fee("ENTRY", "2", cost_id="CORRECTION", supersedes_cost_id="FEE_ENTRY",
                    observed_at="2026-10-07T13:30:02Z")
                if case == "missing":
                    correction["supersedes_cost_id"] = "NO_SUCH_COST"
                elif case == "other_fill":
                    correction["fill_id"] = "EXIT"
                elif case == "same_time":
                    correction["observed_at"] = "2026-10-07T13:30:01Z"
                elif case == "branch":
                    value["fee_records"].append({**correction, "cost_id": "SECOND_CORRECTION"})
                else:
                    del correction["supersedes_cost_id"]
                value["fee_records"].append(correction)
                with self.assertRaises(AccountingError):
                    build_trade_report(value)

    def test_oversell_or_sell_before_buy_is_rejected(self):
        for mutation in ("oversell", "first_sell"):
            with self.subTest(mutation=mutation):
                value = packet()
                if mutation == "oversell":
                    value["fills"][1]["quantity"] = "10.0000000001"
                else:
                    value["fills"][0]["side"] = "SELL"
                with self.assertRaises(AccountingError):
                    build_trade_report(value)

    def test_closed_position_id_cannot_be_reopened(self):
        value = packet()
        value["fills"].append(fill("REOPEN", "BUY", "1", "52", "2026-10-07T13:30:01Z", 3))
        value["fee_records"].append(fee("REOPEN"))
        with self.assertRaisesRegex(AccountingError, "cannot reopen"):
            build_trade_report(value)

    def test_input_order_and_alphabetical_ids_do_not_control_chronology(self):
        value = packet()
        for record in value["fills"]:
            record["filled_at"] = "2026-10-07T13:30:00Z"
        value["fills"][0]["fill_id"] = "Z_BUY"
        value["fills"][1]["fill_id"] = "A_SELL"
        value["fee_records"] = [fee("Z_BUY", "1"), fee("A_SELL", "0.5")]
        value["fills"].reverse()
        self.assertEqual(build_trade_report(value)["final_net_pnl_usd"], "8.5")

    def test_missing_or_duplicate_sequence_cannot_ambiguously_reorder(self):
        for mutation in ("missing", "duplicate"):
            value = packet()
            if mutation == "missing":
                del value["fills"][0]["sequence"]
            else:
                value["fills"][1]["sequence"] = 1
            with self.subTest(mutation=mutation), self.assertRaises(AccountingError):
                build_trade_report(value)

    def test_every_ownership_field_and_mode_is_exact_on_fills_costs_recon(self):
        for record_type in ("fill", "cost", "reconciliation"):
            for field in (*OWNER, "mode"):
                with self.subTest(record_type=record_type, field=field):
                    value = packet()
                    record = (value["fills"][0] if record_type == "fill" else
                        value["fee_records"][0] if record_type == "cost" else value["reconciliation"])
                    record[field] = "ANOTHER_ID"
                    with self.assertRaises(AccountingError):
                        build_trade_report(value)

    def test_live_is_forbidden_and_shadow_cannot_mix_demo(self):
        value = packet()
        value["mode"] = "LIVE"
        with self.assertRaisesRegex(AccountingError, "LIVE forbidden"):
            build_trade_report(value)
        value["mode"] = "SHADOW"
        with self.assertRaises(AccountingError):
            build_trade_report(value)
        for record in value["fills"] + value["fee_records"] + [value["reconciliation"]]:
            record["mode"] = "SHADOW"
        self.assertEqual(build_trade_report(value)["mode"], "SHADOW")

    def test_cross_currency_fill_fee_mark_or_live_estimate_is_rejected(self):
        for field in ("fill", "fee", "mark", "estimate"):
            value = packet(partial=True)
            if field == "fill":
                value["fills"][0]["currency"] = "NOK"
            elif field == "fee":
                value["fee_records"][0]["currency"] = "NOK"
            elif field == "mark":
                value["mark"] = {**OWNER, "mode": "DEMO", "price": "52", "currency": "NOK",
                    "source": "SYNTHETIC", "observed_at": value["as_of"]}
            else:
                value["modeled_live_costs"] = {"currency": "NOK", "estimated_total_cost": "1",
                    "source": "SYNTHETIC", "observed_at": value["as_of"], "includes_spread": True}
            with self.subTest(field=field), self.assertRaises(AccountingError):
                build_trade_report(value)

    def test_invalid_numbers_and_naive_or_future_timestamps_are_rejected(self):
        for bad in (True, 1.0, "NaN", "Infinity", "-1", "0", "1e999"):
            with self.subTest(number=bad):
                value = packet()
                value["fills"][0]["quantity"] = bad
                with self.assertRaises(AccountingError):
                    build_trade_report(value)
        for bad in ("2026-10-07T13:30:00", "2026-10-08T13:30:00Z"):
            value = packet()
            value["fills"][1]["filled_at"] = bad
            with self.subTest(time=bad), self.assertRaises(AccountingError):
                build_trade_report(value)

    def test_fill_only_history_is_not_reconciliation_and_not_closed(self):
        value = packet()
        del value["reconciliation"]
        result = build_trade_report(value)
        self.assertEqual(result["position_status"], "FLAT_UNRECONCILED")
        self.assertFalse(result["closed"])
        self.assertIsNone(result["final_net_pnl_usd"])

    def test_stale_incomplete_mismatched_pending_or_future_recon_cannot_close(self):
        cases = ({"observed_at": "2026-10-06T19:56:00Z"},
                 {"complete": False}, {"position_quantity": "1"},
                 {"pending_order_count": 1}, {"observed_at": "2026-10-07T13:30:06Z"})
        for changes in cases:
            with self.subTest(changes=changes):
                value = packet()
                value["reconciliation"].update(changes)
                result = build_trade_report(value)
                self.assertFalse(result["closed"])
                self.assertEqual(result["net_pnl_status"], "NOT_FINAL")
        value = packet()
        value["as_of"] = "2026-10-07T13:35:00Z"
        result = build_trade_report(value)
        self.assertEqual(result["reconciliation"]["status"], "STALE_RECONCILIATION")
        self.assertFalse(result["closed"])

    def test_no_fills_is_no_trade_even_if_empty_snapshot_matches(self):
        value = packet()
        value.update(fills=[], fee_records=[])
        result = build_trade_report(value)
        self.assertEqual(result["position_status"], "NO_FILLS")
        self.assertFalse(result["closed"])
        self.assertIsNone(result["final_net_pnl_usd"])

    def test_unrealized_requires_fresh_owned_mark_and_is_separate_from_realized(self):
        value = packet(partial=True)
        value["mark"] = {**OWNER, "mode": "DEMO", "currency": "USD", "price": "52",
            "source": "SYNTHETIC_QUOTE", "observed_at": "2026-10-07T13:30:03Z"}
        result = build_trade_report(value)
        self.assertEqual(result["unrealized"]["unrealized_gross_pnl_usd"], "12")
        self.assertEqual(result["unrealized_after_known_entry_fees_usd"], "11.4")
        self.assertEqual(result["realized_net_pnl_usd"], "3.1")
        self.assertFalse(result["future_exit_fees_included_in_unrealized"])
        value["mark"]["position_id"] = "UNRELATED"
        with self.assertRaises(AccountingError):
            build_trade_report(value)

    def test_absent_stale_future_or_predating_mark_stays_unknown(self):
        value = packet(partial=True)
        self.assertIsNone(build_trade_report(value)["unrealized"]["unrealized_gross_pnl_usd"])
        for stamp in ("2026-10-07T13:00:00Z", "2026-10-07T13:30:06Z", "2026-10-06T19:55:01Z"):
            value["mark"] = {**OWNER, "mode": "DEMO", "currency": "USD", "price": "52",
                "source": "SYNTHETIC_QUOTE", "observed_at": stamp}
            with self.subTest(stamp=stamp):
                self.assertIsNone(build_trade_report(value)["unrealized"]["unrealized_gross_pnl_usd"])

    def test_supplied_foreign_mark_is_not_ignored_even_for_flat_position(self):
        value = packet()
        value["mark"] = {**OWNER, "mode": "DEMO", "currency": "NOK", "price": "52",
            "source": "SYNTHETIC_QUOTE", "observed_at": value["as_of"]}
        with self.assertRaises(AccountingError):
            build_trade_report(value)
        value["mark"].update(currency="USD", position_id="UNRELATED")
        with self.assertRaises(AccountingError):
            build_trade_report(value)

    def test_spread_diagnostic_never_deducts_from_actual_fill_profit_twice(self):
        value = packet()
        for fill_record, midpoint in zip(value["fills"], ("49.9", "51.1")):
            fill_record["benchmark"] = {"currency": "USD", "mid_price": midpoint,
                "observed_at": fill_record["filled_at"], "source": "SYNTHETIC_QUOTE"}
        result = build_trade_report(value)
        self.assertEqual(result["spread_diagnostic"]["adverse_midpoint_difference_usd"], "2")
        self.assertFalse(result["spread_diagnostic"]["deducted_from_pnl"])
        self.assertEqual(result["final_net_pnl_usd"], "8.5")

    def test_missing_stale_or_postfill_benchmark_is_unknown_not_zero(self):
        value = packet()
        result = build_trade_report(value)
        self.assertIsNone(result["spread_diagnostic"]["adverse_midpoint_difference_usd"])
        for observed in ("2026-10-06T19:50:00Z", "2026-10-06T19:55:01Z"):
            value["fills"][0]["benchmark"] = {"currency": "USD", "mid_price": "50",
                "observed_at": observed, "source": "SYNTHETIC_QUOTE"}
            with self.subTest(observed=observed):
                self.assertFalse(build_trade_report(value)["spread_diagnostic"]["complete"])

    def test_modeled_live_costs_remain_separate_from_demo_observed_costs(self):
        value = packet()
        value["modeled_live_costs"] = {"currency": "USD", "estimated_total_cost": "99",
            "source": "SYNTHETIC_UNCALIBRATED_LIVE_MODEL", "observed_at": value["as_of"],
            "includes_spread": True}
        result = build_trade_report(value)
        self.assertEqual(result["final_net_pnl_usd"], "8.5")
        self.assertEqual(result["modeled_live_costs"]["estimated_total_cost_usd"], "99")
        self.assertFalse(result["modeled_live_costs"]["deducted_from_observed_pnl"])

    def test_unknown_fee_cannot_carry_amount_or_claim_completeness(self):
        for changes in ({"amount": "0", "complete": False}, {"amount": None, "complete": True}):
            value = packet()
            value["fee_records"][0].update(status="UNKNOWN", **changes)
            with self.subTest(changes=changes), self.assertRaises(AccountingError):
                build_trade_report(value)

    def test_fee_cannot_reference_foreign_fill_or_precede_actual_fill(self):
        for changes in ({"fill_id": "FOREIGN_FILL"}, {"observed_at": "2026-10-06T19:00:00Z"}):
            value = packet()
            value["fee_records"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(AccountingError):
                build_trade_report(value)

    def test_corporate_actions_or_other_cashflows_cannot_be_silently_ignored(self):
        for field in ("corporate_actions", "other_cash_movements"):
            value = packet()
            value[field] = [{"synthetic": True}]
            with self.subTest(field=field), self.assertRaisesRegex(AccountingError, "supported accounting adapter"):
                build_trade_report(value)

    def test_report_does_not_mutate_inputs_and_is_reproducible(self):
        value = packet()
        original = deepcopy(value)
        self.assertEqual(build_trade_report(value), build_trade_report(value))
        self.assertEqual(value, original)


if __name__ == "__main__":
    unittest.main()
