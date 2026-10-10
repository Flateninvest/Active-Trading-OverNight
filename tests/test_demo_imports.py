"""External DEMO import checks with invented fills, never actual broker history."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from active_trading.reporting import AccountingError, build_trade_report, import_demo_trade

OWNER = {"account_id": "FICTIONAL_DEMO", "strategy_id": "FICTIONAL_STRATEGY",
         "instrument_id": "FICTIONAL_STOCK", "position_id": "FICTIONAL_POSITION"}


def source(*, preview=False):
    return {"schema": "EXTERNAL_DEMO_TRADE_v1", "mode": "DEMO", "currency": "USD",
        "source_record_id": "receipt-1", "source": "INVENTED_EXTERNAL_DEMO_NOT_BROKER_HISTORY",
        "observed_at": "2026-10-08T19:55:01Z", "ownership": dict(OWNER),
        "fill_status": "PREVIEW" if preview else "FINAL", "history_finalized": False,
        "fill": {"fill_id": "buy-1", "side": "BUY", "quantity": "2", "price": "100",
                 "filled_at": "2026-10-08T19:55:00Z", "sequence": 1}}


def closed_packet():
    first = import_demo_trade(source())
    exit_record = source()
    exit_record.update(source_record_id="receipt-2", observed_at="2026-10-09T13:30:01Z")
    exit_record["fill"].update(fill_id="sell-1", side="SELL", price="101",
                               filled_at="2026-10-09T13:30:00Z", sequence=2)
    exit_record["reconciliation"] = {**OWNER, "mode": "DEMO", "source": "INVENTED_COMPLETE_SNAPSHOT",
        "observed_at": "2026-10-09T13:30:01Z", "complete": True,
        "position_quantity": "0", "pending_order_count": 0}
    return import_demo_trade(exit_record, previous_packet=first)


class DemoImportTests(unittest.TestCase):
    def test_preview_price_does_not_become_a_fill_or_fee(self):
        packet = import_demo_trade(source(preview=True))
        self.assertEqual(packet["fills"], [])
        self.assertEqual(packet["fee_records"], [])
        report = build_trade_report(packet)
        self.assertEqual(report["position_status"], "NO_FILLS")
        self.assertIsNone(report["final_net_pnl_usd"])

    def test_final_fill_without_final_history_has_unknown_fees(self):
        packet = import_demo_trade(source())
        self.assertEqual(len(packet["fills"]), 1)
        self.assertEqual(packet["fee_records"][0]["status"], "UNKNOWN")
        self.assertIsNone(packet["fee_records"][0]["amount"])
        self.assertFalse(build_trade_report(packet)["fee_coverage_complete"])

    def test_provisional_zero_fee_is_not_final_zero_fee(self):
        record = source()
        record["fees"] = {"status": "KNOWN", "amount": "0", "complete": True,
                          "observed_at": record["observed_at"]}
        packet = import_demo_trade(record)
        self.assertEqual(packet["fee_records"][0]["status"], "UNKNOWN")

    def test_final_history_without_explicit_fee_coverage_stays_unknown(self):
        record = source()
        record["history_finalized"] = True
        self.assertEqual(import_demo_trade(record)["fee_records"][0]["status"], "UNKNOWN")

    def test_sourced_final_zero_charge_is_valid(self):
        record = source()
        record.update(history_finalized=True, fees={"status": "KNOWN", "amount": "0",
            "complete": True, "observed_at": record["observed_at"]})
        self.assertEqual(import_demo_trade(record)["fee_records"][0]["amount"], "0")

    def test_same_source_replay_is_idempotent_and_exact_bytes_are_hashed(self):
        record = source()
        raw = json.dumps(record, indent=2).encode("utf-8")
        packet = import_demo_trade(record, source_bytes=raw)
        self.assertEqual(packet["import_history"][0]["source_bytes_sha256"], hashlib.sha256(raw).hexdigest())
        replay = import_demo_trade(record, previous_packet=packet, source_bytes=raw)
        self.assertEqual(replay, packet)

    def test_conflicting_source_id_is_rejected(self):
        record = source()
        packet = import_demo_trade(record)
        record["fill"]["price"] = "102"
        with self.assertRaises(AccountingError):
            import_demo_trade(record, previous_packet=packet)

    def test_conflicting_final_fill_id_is_rejected_under_new_source_id(self):
        record = source()
        packet = import_demo_trade(record)
        record.update(source_record_id="receipt-new", observed_at="2026-10-08T19:55:02Z")
        record["fill"]["quantity"] = "3"
        with self.assertRaises(AccountingError):
            import_demo_trade(record, previous_packet=packet)

    def test_final_fee_history_appends_correction_without_rewriting_unknown(self):
        record = source()
        packet = import_demo_trade(record)
        original = deepcopy(packet)
        record.update(source_record_id="receipt-final-history", observed_at="2026-10-08T19:56:00Z",
            history_finalized=True, fees={"status": "KNOWN", "amount": "0.2", "complete": True,
                                         "observed_at": "2026-10-08T19:56:00Z"})
        updated = import_demo_trade(record, previous_packet=packet)
        self.assertEqual(packet, original)
        self.assertEqual(len(updated["fills"]), 1)
        self.assertEqual(len(updated["fee_records"]), 2)
        self.assertEqual(updated["fee_records"][0]["status"], "UNKNOWN")
        self.assertEqual(updated["fee_records"][1]["supersedes_cost_id"], updated["fee_records"][0]["cost_id"])
        self.assertTrue(build_trade_report(updated)["fee_coverage_complete"])

    def test_externally_closed_trade_still_has_unknown_net_until_fees_arrive(self):
        report = build_trade_report(closed_packet())
        self.assertTrue(report["closed"])
        self.assertEqual(report["realized_gross_pnl_usd"], "2")
        self.assertIsNone(report["final_net_pnl_usd"])
        self.assertEqual(report["net_pnl_status"], "NOT_FINAL")

    def test_external_override_is_excluded_from_strategy_equity_by_default(self):
        packet = import_demo_trade(source())
        report = build_trade_report(packet)
        self.assertTrue(report["strategy_scope"]["external_override"])
        self.assertFalse(report["strategy_scope"]["include_in_strategy_equity"])
        record = source()
        record["include_in_strategy_equity"] = True
        with self.assertRaises(AccountingError):
            import_demo_trade(record)

    def test_equity_scope_cannot_change_on_subsequent_import(self):
        packet = import_demo_trade(source())
        record = source()
        record.update(source_record_id="receipt-2", external_override=False, include_in_strategy_equity=True)
        with self.assertRaises(AccountingError):
            import_demo_trade(record, previous_packet=packet)

    def test_live_or_other_currency_never_imported(self):
        for key, value in (("mode", "LIVE"), ("currency", "EUR")):
            with self.subTest(key=key):
                record = source()
                record[key] = value
                with self.assertRaises(AccountingError):
                    import_demo_trade(record)

    def test_source_bytes_must_match_record(self):
        with self.assertRaises(AccountingError):
            import_demo_trade(source(), source_bytes=b'{}')

    def test_final_fill_cannot_hide_different_mode_currency_or_account(self):
        for key, value in (("mode", "LIVE"), ("currency", "EUR"), ("account_id", "OTHER_ACCOUNT")):
            with self.subTest(key=key):
                record = source()
                record["fill"][key] = value
                with self.assertRaises(AccountingError):
                    import_demo_trade(record)

    def test_preview_cannot_manufacture_closed_reconciliation(self):
        record = source(preview=True)
        record["reconciliation"] = {**OWNER, "mode": "DEMO", "source": "INVENTED",
            "observed_at": record["observed_at"], "complete": True,
            "position_quantity": "0", "pending_order_count": 0}
        packet = import_demo_trade(record)
        self.assertNotIn("reconciliation", packet)
        self.assertFalse(build_trade_report(packet)["closed"])

    def test_import_does_not_change_source_or_previous_input(self):
        record = source()
        original = deepcopy(record)
        import_demo_trade(record)
        self.assertEqual(record, original)

    def test_private_cli_import_keeps_normalized_packet_and_never_overwrites(self):
        with tempfile.TemporaryDirectory(prefix="demo-import-", dir=ROOT.parent) as folder:
            input_path, output = Path(folder) / "input.json", Path(folder) / "output.json"
            input_path.write_text(json.dumps(source()), encoding="utf-8")
            command = [sys.executable, str(ROOT / "scripts" / "trade_report.py"), "--import-demo",
                       "--input", str(input_path), "--output", str(output)]
            result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            saved = json.loads(output.read_text())
            self.assertEqual(saved["mode"], "DEMO")
            self.assertEqual(saved["normalized_accounting_packet"]["fee_records"][0]["status"], "UNKNOWN")
            self.assertNotIn(OWNER["account_id"], result.stdout)
            self.assertEqual(subprocess.run(command, cwd=ROOT, text=True, capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
