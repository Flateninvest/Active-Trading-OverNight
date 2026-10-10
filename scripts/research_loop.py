"""Offline provisional research-loop checks; never connects to a broker."""
from pathlib import Path
import argparse
from datetime import datetime, timedelta, timezone
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from active_trading.research.protocol import (  # noqa: E402
    ProtocolError, SCHEMA_STATUS, INCLUSION_POLICY, COST_FIELDS, append_event,
    canonical_hash, dataset_hashes, file_sha256, open_holdout, read_ledger,
    record_trial, trial_count, validate_plan, verify_report,
)
from active_trading.jsonio import load_json


def _write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _read(path):
    return load_json(path)


def _synthetic_reproduce(dataset, config, output):
    """Arithmetic fixture only: deterministic invented returns, never market data."""
    data = _read(dataset)
    settings = _read(config)
    if data.get("data_kind") != "SYNTHETIC" or settings.get("data_kind") != "SYNTHETIC":
        raise ProtocolError("The demonstration generator accepts explicitly synthetic inputs only")
    returns = data["invented_overnight_returns"]
    cost = sum(settings["costs"][name] for name in COST_FIELDS) / 10000
    _write(output, {"data_kind": "SYNTHETIC", "profitability_evidence": False,
                    "metrics": {"net_excess_return": sum(returns) / len(returns) - cost}})


def demo(output):
    """Exercise guards with invented data and visibly simulated verifier seams."""
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ProtocolError("Use a new or empty demonstration directory to preserve prior attempts")
    output.mkdir(parents=True, exist_ok=True)
    config_path, dataset_path = output / "synthetic_config.json", output / "synthetic_data.json"
    result_path, reproduction_path = output / "synthetic_results.json", output / "synthetic_regenerated_results.json"
    ledger_path = output / "synthetic_trials.jsonl"
    costs = {name: 0 for name in COST_FIELDS}
    costs.update(entry_spread_bps=1, exit_spread_bps=1, slippage_bps=1,
                 model="EXPLICIT_BPS", basis="Invented fixture costs; not empirically calibrated")
    _write(config_path, {"data_kind": "SYNTHETIC", "costs": costs})
    _write(dataset_path, {"data_kind": "SYNTHETIC", "invented_overnight_returns": [0.002, -0.001, 0.003]})
    timestamp = datetime.now(timezone.utc)
    plan = {
        "schema_status": SCHEMA_STATUS, "mode": "SHADOW_RESEARCH", "data_kind": "SYNTHETIC",
        "hypothesis": {
            "statement": "Delayed bullish flow predicts positive next-opening excess return after costs.",
            "economic_reason": "Illustrative information diffusion hypothesis, not an observed market fact",
            "falsifier": "Non-positive net excess return against the frozen cash comparator"},
        "code_commit": "a" * 40,  # Explicitly fictitious identity, never an actual Git commit claim.
        "config_sha256": file_sha256(config_path),
        "datasets": [{"id": "synthetic_prices", "sha256": file_sha256(dataset_path),
                      "frozen_at": (timestamp - timedelta(seconds=5)).isoformat()}],
        "costs": costs,
        "comparator": {"id": "cash", "config_sha256": canonical_hash({"synthetic_cash_return": 0}),
                       "description": "Cash fixture on every invented eligible night",
                       "selection_reason": "Tests net incremental returns with declared cash/missed attempts",
                       "same_data_and_cost_model": True, "inclusion_policy": INCLUSION_POLICY},
        "evaluation": {
            "train": {"start": "2020-01-01", "end": "2022-12-31"},
            "validation": {"start": "2023-01-01", "end": "2023-12-31"},
            "holdout": {"start": "2024-01-01", "end": "2024-12-31"},
            "disclosed_holdout_year": 2024,
            "walk_forward": [{"train": {"start": "2020-01-01", "end": "2022-12-31"},
                              "test": {"start": "2023-01-01", "end": "2023-12-31"}}],
            "forward_extension": {"start": "2025-01-01", "end": "2025-12-31"},
            "holdout_previously_observed": False, "holdout_prior_observation_at": "UNSET"},
        "ablation_dimensions": ["flow", "hidden_angles", "ta", "execution"],
        "baseline_settings": {"flow": True, "hidden_angles": True, "ta": True, "execution": "PRIMARY_NEXT_OPEN"},
        "reporting": {"headline_metrics": ["net_excess_return"],
                      "metric_tolerances": {"net_excess_return": 0}, "include_all_trials": True}}
    plan["ablation_comparator"] = {
        "id": "frozen_full_model", "config_sha256": plan["config_sha256"],
        "settings_sha256": canonical_hash(plan["baseline_settings"])}
    # These dates are fixture boundaries, not the actual disclosed workshop year.
    _write(output / "synthetic_plan.json", plan)
    validate_plan(plan)
    record_trial(ledger_path, plan, "fixture-failed-not-viewed", "VARIANT",
                 {"flow": {"from": True, "to": "intentionally_bad_fixture"}}, "cash")
    append_event(ledger_path, {"type": "TRIAL_RESULT", "trial_id": "fixture-failed-not-viewed",
                              "status": "FAILED", "viewed": False, "reason": "Synthetic failed run preserved"})
    approval = {"status": "SIMULATED_APPROVAL", "owner_id": "SYNTHETIC_FIXTURE_OWNER",
                "approved_at": (timestamp - timedelta(seconds=2)).isoformat(),
                "plan_hash": canonical_hash(plan), "code_commit": plan["code_commit"],
                "config_sha256": plan["config_sha256"], "dataset_hashes": dataset_hashes(plan),
                "external_evidence": "SIMULATED_FIXTURE_ONLY_NO_AUTHENTICATED_OWNER"}
    open_holdout(ledger_path, plan, approval, lambda _: True)
    record_trial(ledger_path, plan, "fixture-frozen-holdout", "BASELINE", {}, "cash", evaluation_stage="HOLDOUT")
    first_command = [sys.executable, str(Path(__file__).resolve()), "_synthetic-reproduce",
                     "--dataset", str(dataset_path), "--config", str(config_path), "--output", str(result_path)]
    subprocess.run(first_command, check=True, capture_output=True, text=True)
    append_event(ledger_path, {"type": "TRIAL_RESULT", "trial_id": "fixture-frozen-holdout",
                              "status": "SUCCEEDED", "viewed": False, "results_sha256": file_sha256(result_path)})
    result_event = read_ledger(ledger_path)[-1]
    append_event(ledger_path, {"type": "RESULT_ACCESSED", "trial_id": "fixture-frozen-holdout",
                              "result_event_hash": result_event["event_hash"]})
    second_command = first_command[:-1] + [str(reproduction_path)]
    regenerated = subprocess.run(second_command, check=True, capture_output=True, text=True)
    events = read_ledger(ledger_path)
    artifact = {
        "plan_hash": canonical_hash(plan), "code_commit": plan["code_commit"],
        "config_sha256": plan["config_sha256"], "dataset_hashes": dataset_hashes(plan),
        "results_sha256": file_sha256(result_path), "ledger_tail_hash": events[-1]["event_hash"],
        "trial_id": "fixture-frozen-holdout", "trial_count": trial_count(events),
        "headline_metrics": _read(result_path)["metrics"], "source_state": "COMMITTED",
        "evaluation_stage": "HOLDOUT"}
    reproduction = {
        "code_commit": plan["code_commit"], "config_sha256": plan["config_sha256"],
        "dataset_hashes": dataset_hashes(plan), "results_sha256": file_sha256(reproduction_path),
        "source_state": "COMMITTED", "regenerated_at": datetime.now(timezone.utc).isoformat(),
        "run_command": json.dumps(second_command)}
    checked = verify_report(
        plan, events, artifact, reproduction,
        artifact_paths={"config": config_path, "datasets": {"synthetic_prices": dataset_path},
                        "results": result_path, "reproduced_results": reproduction_path},
        commit_verifier=lambda _: True,  # Simulated seam only; never used for genuine evidence.
        regeneration_verifier=lambda _: regenerated.returncode == 0)
    summary = {
        "status": "SYNTHETIC_OPERATIONAL_FIXTURE", "profitability_evidence": False,
        "broker_writes": False, "daily_backtester_implemented": False,
        "genuine_owner_approval_verified": False, "actual_committed_code_verified": False,
        "simulated_verifier_seams": True, "report_ready_for_genuine_research": False,
        "fixture_guard_checks_passed": checked["ready"], "trial_count": checked["trial_count"],
        "ledger_tail_hash": events[-1]["event_hash"]}
    _write(output / "synthetic_demo_summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate a frozen provisional research plan")
    validate.add_argument("--plan", required=True, type=Path)
    ledger = commands.add_parser("ledger", help="Check the chain and full count of all reserved attempts")
    ledger.add_argument("--path", required=True, type=Path)
    ledger.add_argument("--expected-tail-hash")
    demonstrate = commands.add_parser("demo", help="Run clearly synthetic fixtures without broker access")
    demonstrate.add_argument("--output", required=True, type=Path)
    generate = commands.add_parser("_synthetic-reproduce", help=argparse.SUPPRESS)
    for name in ("dataset", "config", "output"):
        generate.add_argument("--" + name, required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "validate":
            result = validate_plan(_read(arguments.plan))
            result["status"] = "PLAN_CHECKED" if result["holdout_ready"] else "DRAFT_NOT_READY_FOR_HOLDOUT"
        elif arguments.command == "ledger":
            events = read_ledger(arguments.path, arguments.expected_tail_hash)
            result = {"status": "CHAIN_CHECKED", "trial_count": trial_count(events),
                      "external_tail_anchor_supplied": arguments.expected_tail_hash is not None,
                      "event_count": len(events)}
        elif arguments.command == "demo":
            result = demo(arguments.output)
        else:
            _synthetic_reproduce(arguments.dataset, arguments.config, arguments.output)
            return 0
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ProtocolError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
