"""Data-free weekly, research, earnings and shadow-control checks. No orders."""
from pathlib import Path
import json
import hashlib
from datetime import datetime, timezone
import os
import platform
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "legacy" / "weekly-paper"

def main():
    for path in (ROOT / "spec").glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    temporary = ROOT / ".runtime" / "portable"
    temporary.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(temporary)
    os.environ["TEMP"] = os.environ["TMP"] = str(temporary)
    sys.path.insert(0, str(LEGACY))
    sys.path.insert(0, str(ROOT / "src"))
    weekly_suite = unittest.defaultTestLoader.discover(str(LEGACY / "tests"), pattern="test_rev12_*.py")
    # Independent loaders avoid retaining the first suite's discovery root.
    research_suite = unittest.TestLoader().discover(str(ROOT / "tests"), pattern="test_research_protocol.py")
    earnings_suite = unittest.TestLoader().discover(str(ROOT / "tests"), pattern="test_earnings.py")
    shadow_suites = [unittest.TestLoader().discover(str(ROOT / "tests"), pattern=pattern) for pattern in (
        "test_review.py", "test_accounting.py", "test_operations_ledger.py", "test_shadow_workflow.py")]
    weekly_count, research_count = weekly_suite.countTestCases(), research_suite.countTestCases()
    earnings_count = earnings_suite.countTestCases()
    shadow_counts = [suite.countTestCases() for suite in shadow_suites]
    if weekly_count == 0 or research_count == 0 or earnings_count == 0 or any(count == 0 for count in shadow_counts):
        raise RuntimeError("Portable test suite is missing; refusing an empty successful run")
    suite = unittest.TestSuite([weekly_suite, research_suite, earnings_suite, *shadow_suites])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    with tempfile.TemporaryDirectory(dir=temporary) as demo_dir:
        completed = subprocess.run([sys.executable, "-m", "weekly_strategy.cli", "demo", "--output", demo_dir],
            cwd=LEGACY, check=True, capture_output=True, text=True)
        print(completed.stdout.strip())
        comparison = json.loads((Path(demo_dir) / "Synthetic_Demonstration_Comparison.json").read_text())
        if comparison["profitability_evidence"] is not False:
            raise ValueError("Demonstration must remain explicitly synthetic")
    with tempfile.TemporaryDirectory(dir=temporary) as protocol_dir:
        protocol_demo = subprocess.run([sys.executable, str(ROOT / "scripts" / "research_loop.py"),
            "demo", "--output", protocol_dir], cwd=ROOT, check=True, capture_output=True, text=True)
        summary = json.loads(protocol_demo.stdout)
        if summary.get("status") != "SYNTHETIC_OPERATIONAL_FIXTURE" or summary.get("fixture_guard_checks_passed") is not True:
            raise ValueError("Research protocol demonstration did not complete its fixture checks")
        for flag in ("profitability_evidence", "broker_writes", "report_ready_for_genuine_research",
                     "genuine_owner_approval_verified", "actual_committed_code_verified"):
            if summary.get(flag) is not False:
                raise ValueError("Research protocol demo must remain explicitly synthetic: " + flag)
        print(protocol_demo.stdout.strip())
    # The CLI keeps even generated earnings packets outside the Git checkout.
    with tempfile.TemporaryDirectory(prefix="earnings-check-", dir=ROOT.parent) as earnings_dir:
        earnings_output = Path(earnings_dir) / "synthetic-earnings-plan.json"
        earnings_demo = subprocess.run([sys.executable, str(ROOT / "scripts" / "earnings_plan.py"),
            "--demo", "--output", str(earnings_output)], cwd=ROOT, check=True, capture_output=True, text=True)
        print(earnings_demo.stdout.strip())
        # CLI output is an explicitly synthetic prepared packet and plan, never a fill.
        earnings_record = json.loads(earnings_output.read_text(encoding="utf-8"))
        earnings_plan = earnings_record.get("plan", earnings_record)
        if earnings_plan.get("mode") != "SHADOW" or earnings_plan.get("broker_writes") is not False:
            raise ValueError("Earnings demonstration must remain SHADOW with no broker writes")
    shadow_demo = subprocess.run([sys.executable, str(ROOT / "scripts" / "shadow_workflow.py"), "--demo"],
        cwd=ROOT, check=True, capture_output=True, text=True)
    shadow_summary = json.loads(shadow_demo.stdout)
    if (shadow_summary.get("status") != "SYNTHETIC_OPERATIONAL_FIXTURE"
            or shadow_summary.get("broker_writes") is not False
            or shadow_summary.get("profitability_evidence") is not False
            or not all(shadow_summary.get("checks", {}).values())):
        raise ValueError("Shadow controls demonstration must remain fictional and pass its checks")
    print(shadow_demo.stdout.strip())
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    committed = False
    if revision.returncode == 0:
        source_paths = ["scripts", "src", "tests", "examples", "legacy", "spec", ".github/workflows"]
        changed = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *source_paths], cwd=ROOT)
        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", *source_paths],
            cwd=ROOT, capture_output=True, text=True)
        committed = changed.returncode == 0 and untracked.returncode == 0 and not untracked.stdout.strip()
    record = {"status":"PASSED", "tested_at_utc":datetime.now(timezone.utc).isoformat(),
        "python_version":platform.python_version(), "tests_run":result.testsRun,
        "legacy_weekly_tests_run":weekly_count, "research_protocol_tests_run":research_count,
        "earnings_tests_run":earnings_count, "earnings_demo":"SYNTHETIC_OPERATIONAL_FIXTURE",
        "shadow_review_tests_run":shadow_counts[0], "trade_accounting_tests_run":shadow_counts[1],
        "order_memory_tests_run":shadow_counts[2], "shadow_integration_tests_run":shadow_counts[3],
        "shadow_controls_demo":"SYNTHETIC_OPERATIONAL_FIXTURE",
        "failures":len(result.failures), "errors":len(result.errors),
        "demo":"SYNTHETIC_OPERATIONAL_FIXTURE", "broker_writes":False,
        "research_protocol_demo":"SYNTHETIC_OPERATIONAL_FIXTURE",
        "daily_runtime_validated":False, "private_data_required":False,
        "independent_reviewer_service_deployed":False, "broker_producers_authenticated":False,
        "commit":revision.stdout.strip() if committed else None,
        "source_state":"COMMITTED" if committed else "WORKTREE_NOT_COMMITTED",
        "runner_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (ROOT / "docs" / "portable-check-result.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
