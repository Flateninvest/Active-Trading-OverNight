"""Prepare an offline earnings shadow plan from private normalized JSON.

Examples:
  python scripts/earnings_plan.py --demo
  python scripts/earnings_plan.py --input PRIVATE.json --output OUTSIDE_REPO.json

--demo prints invented inputs and their plan. It never submits broker orders.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from active_trading.earnings import (  # noqa: E402
    EarningsPlanningError, build_shadow_plan, synthetic_demo_packet,
)
from active_trading.jsonio import loads_json


def _private_path(path: str, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise EarningsPlanningError(f"{label} must be outside the repository; private inputs/state are not Git content")
    return resolved


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="Private normalized JSON outside the repository")
    source.add_argument("--demo", action="store_true", help="Invented data only; prints schema example and shadow plan")
    parser.add_argument("--output", help="New result JSON outside the repository; existing files are not overwritten")
    args = parser.parse_args(argv)
    try:
        if not args.demo and not args.output:
            raise EarningsPlanningError("private --input requires --output outside the repository; avoid printing private state")
        if args.demo:
            packet = synthetic_demo_packet()
            input_bytes = json.dumps(packet, sort_keys=True, allow_nan=False).encode("utf-8")
        else:
            input_path = _private_path(args.input, "input")
            input_bytes = input_path.read_bytes()
            packet = loads_json(input_bytes)
        plan = build_shadow_plan(packet)
        plan["identities"] = {"input_bytes_sha256": hashlib.sha256(input_bytes).hexdigest(),
                              "planner_source_sha256": hashlib.sha256((ROOT / "src" / "active_trading" / "earnings.py").read_bytes()).hexdigest(),
                              "commit_verified": False,
                              "specification_status": "PROVISIONAL_NOT_WORKSHOP_VALIDATED"}
        output = {"fixture_kind": "SYNTHETIC_OPERATIONAL_FIXTURE", "input": packet, "plan": plan} if args.demo else plan
        serialized = json.dumps(output, indent=2, allow_nan=False) + "\n"
        if args.output:
            output_path = _private_path(args.output, "output")
            if not output_path.parent.is_dir():
                raise EarningsPlanningError("output parent directory must already exist")
            with output_path.open("x", encoding="utf-8") as handle:
                handle.write(serialized)
            print(json.dumps({"status": plan["status"], "broker_writes": False,
                              "proposed_count": len(plan["proposals"]), "blocked_count": len(plan["blocked_events"])}))
        else:
            print(serialized, end="")
        return 0
    except (EarningsPlanningError, OSError, ValueError, TypeError) as exc:
        # Do not echo private records, account values or paths on error.
        print(json.dumps({"status": "REFUSED", "broker_writes": False,
                          "error_type": type(exc).__name__,
                          "reason": str(exc) if isinstance(exc, EarningsPlanningError) else "Input/output could not be processed"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
