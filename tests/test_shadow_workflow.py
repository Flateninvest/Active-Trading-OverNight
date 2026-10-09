"""Integration and private report CLI checks using fictional facts only."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.shadow_workflow import run_demo


class ShadowWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo = run_demo()

    def test_all_three_components_work_together_and_remain_fictional(self):
        self.assertTrue(all(self.demo["checks"].values()))
        self.assertFalse(self.demo["broker_writes"])
        self.assertFalse(self.demo["profitability_evidence"])
        self.assertFalse(self.demo["genuine_independent_reviewer_deployed"])
        self.assertEqual(self.demo["partial_accounting"]["remaining_quantity"], "3")
        result = self.demo["final_accounting"]
        self.assertEqual(result["net_pnl_status"], "FINAL")
        self.assertEqual(Decimal(result["realized_gross_pnl_usd"]), Decimal("3.80"))
        self.assertEqual(Decimal(result["final_net_pnl_usd"]), Decimal("2.80"))
        self.assertFalse(result["spread_diagnostic"]["deducted_from_pnl"])

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "trade_report.py"), *args], cwd=ROOT, capture_output=True, text=True)

    def test_private_report_cli_refuses_git_paths_and_overwriting(self):
        with tempfile.TemporaryDirectory(prefix="private-report-test-", dir=ROOT.parent) as folder:
            source, output = Path(folder) / "input.json", Path(folder) / "report.json"
            source.write_text(json.dumps(self.demo["normalized_final_accounting_packet"]), encoding="utf-8")
            result = self.cli("--input", str(source), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("fictional-shadow-account", result.stdout)
            self.assertEqual(json.loads(output.read_text())["net_pnl_status"], "FINAL")
            self.assertEqual(self.cli("--input", str(source), "--output", str(output)).returncode, 2)
            self.assertEqual(self.cli("--input", str(source), "--output", str(ROOT / "bad-report.json")).returncode, 2)
            self.assertFalse((ROOT / "bad-report.json").exists())

    def test_private_report_errors_do_not_echo_sensitive_record(self):
        with tempfile.TemporaryDirectory(prefix="private-report-test-", dir=ROOT.parent) as folder:
            source, output = Path(folder) / "input.json", Path(folder) / "report.json"
            packet = deepcopy(self.demo["normalized_final_accounting_packet"])
            packet["fills"][0]["account_id"] = "DO_NOT_ECHO_PRIVATE_IDENTIFIER"
            source.write_text(json.dumps(packet), encoding="utf-8")
            result = self.cli("--input", str(source), "--output", str(output))
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("DO_NOT_ECHO_PRIVATE_IDENTIFIER", result.stdout + result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__": unittest.main()
