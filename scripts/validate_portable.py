"""Data-free weekly comparison checks. Never places broker orders."""
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
    suite = unittest.defaultTestLoader.discover(str(LEGACY / "tests"), pattern="test_rev12_*.py")
    if suite.countTestCases() == 0:
        raise RuntimeError("Portable test suite is missing; refusing an empty successful run")
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
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    committed = False
    if revision.returncode == 0:
        changed = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "scripts", "legacy", "spec"], cwd=ROOT)
        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "scripts", "legacy", "spec"],
            cwd=ROOT, capture_output=True, text=True)
        committed = changed.returncode == 0 and untracked.returncode == 0 and not untracked.stdout.strip()
    record = {"status":"PASSED", "tested_at_utc":datetime.now(timezone.utc).isoformat(),
        "python_version":platform.python_version(), "tests_run":result.testsRun,
        "failures":len(result.failures), "errors":len(result.errors),
        "demo":"SYNTHETIC_OPERATIONAL_FIXTURE", "broker_writes":False,
        "daily_runtime_validated":False, "private_data_required":False,
        "commit":revision.stdout.strip() if committed else None,
        "source_state":"COMMITTED" if committed else "WORKTREE_NOT_COMMITTED",
        "runner_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (ROOT / "docs" / "portable-check-result.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
