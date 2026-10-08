"""Offline protocol gates using invented fixtures; no market or profit evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from active_trading.research.protocol import (  # noqa: E402
    ProtocolError,
    append_event,
    canonical_hash,
    open_holdout,
    read_ledger,
    record_trial,
    trial_count,
    validate_ablation,
    validate_plan,
    validate_preregistration,
    verify_report,
)


def fixture_plan():
    plan = {
        "schema_status": "PROVISIONAL_NOT_WORKSHOP_VALIDATED",
        "mode": "SHADOW_RESEARCH",
        "data_kind": "SYNTHETIC",
        "hypothesis": {
            "statement": "Delayed bullish flow predicts positive next-opening net returns.",
            "economic_reason": "Slow diffusion of information is a testable conjecture.",
            "falsifier": "Net excess return versus the comparator is non-positive.",
        },
        "code_commit": "a" * 40,
        "config_sha256": "b" * 64,
        "datasets": [
            {"id": "prices", "sha256": "c" * 64,
             "frozen_at": "2025-01-01T00:00:00Z"},
        ],
        "costs": {
            "model": "EXPLICIT_BPS",
            "basis": "Invented test fixture, never calibrated market costs.",
            "commission_bps": 0,
            "entry_spread_bps": 1,
            "exit_spread_bps": 1,
            "slippage_bps": 1,
            "fx_bps": 0,
            "financing_bps": 0,
            "tax_bps": 0,
        },
        "comparator": {
            "id": "cash",
            "config_sha256": "d" * 64,
            "description": "Same eligible nights including cash and unsuccessful attempts.",
            "selection_reason": "Measures incremental signal with the same costs and data.",
            "same_data_and_cost_model": True,
            "inclusion_policy": "ALL_ATTEMPTS_INCLUDING_CASH_MISSED_FAILED_UNKNOWN",
        },
        "evaluation": {
            "train": {"start": "2020-01-01", "end": "2022-12-31"},
            "validation": {"start": "2023-01-01", "end": "2023-12-31"},
            "holdout": {"start": "2024-01-01", "end": "2024-12-31"},
            "disclosed_holdout_year": 2024,
            "walk_forward": [{
                "train": {"start": "2020-01-01", "end": "2022-12-31"},
                "test": {"start": "2023-01-01", "end": "2023-12-31"},
            }],
            "forward_extension": {"start": "2025-01-01", "end": "2025-12-31"},
            "holdout_previously_observed": False,
            "holdout_prior_observation_at": "UNSET",
        },
        "ablation_dimensions": ["flow", "hidden_angles", "ta", "execution"],
        "baseline_settings": {"flow": True, "hidden_angles": True, "ta": True,
                              "execution": "PRIMARY_NEXT_OPEN"},
        "reporting": {
            "headline_metrics": ["net_excess_return"],
            "metric_tolerances": {"net_excess_return": 0},
            "include_all_trials": True,
        },
    }
    plan["ablation_comparator"] = {
        "id": "full_model", "config_sha256": plan["config_sha256"],
        "settings_sha256": canonical_hash(plan["baseline_settings"]),
    }
    return plan


def fixture_approval(plan, status="SIMULATED_APPROVAL"):
    return {
        "status": status,
        "owner_id": "fixture-owner",
        "approved_at": "2025-01-02T12:00:00Z",
        "plan_hash": canonical_hash(plan),
        "code_commit": plan["code_commit"],
        "config_sha256": plan["config_sha256"],
        "dataset_hashes": {row["id"]: row["sha256"] for row in plan["datasets"]},
        "external_evidence": "synthetic-owner-receipt-reference",
    }


def fixture_directory():
    # Keep ephemeral files in the ignored workspace on restricted Windows hosts.
    directory = ROOT / ".runtime" / "research-protocol-tests"
    directory.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=directory)


def adversarial_rechain(events):
    """Model a local-file attacker; a hash chain alone is not authentication."""
    events = deepcopy(events)
    previous = "0" * 64
    for sequence, event in enumerate(events, 1):
        event.update(sequence=sequence, previous_hash=previous)
        event.pop("event_hash", None)
        event["event_hash"] = canonical_hash(event)
        previous = event["event_hash"]
    return events


class PlanGates(unittest.TestCase):
    def test_complete_synthetic_metadata_is_ready_but_not_economic_evidence(self):
        result = validate_plan(fixture_plan())
        self.assertTrue(result["holdout_ready"])
        self.assertEqual(result["plan_hash"], canonical_hash(fixture_plan()))

    def test_missing_frozen_identity_is_rejected(self):
        for field in ("id", "sha256", "frozen_at"):
            with self.subTest(field=field):
                plan = fixture_plan()
                del plan["datasets"][0][field]
                with self.assertRaises(ProtocolError):
                    validate_plan(plan)

    def test_missing_cost_coverage_and_negative_costs_are_rejected(self):
        for field in ("commission_bps", "entry_spread_bps", "exit_spread_bps",
                      "slippage_bps", "fx_bps", "financing_bps", "tax_bps"):
            with self.subTest(field=field):
                plan = fixture_plan()
                del plan["costs"][field]
                with self.assertRaises(ProtocolError):
                    validate_plan(plan)
        plan = fixture_plan()
        plan["costs"]["slippage_bps"] = -1
        with self.assertRaises(ProtocolError):
            validate_plan(plan)

    def test_comparator_must_be_declared_and_use_equal_data_and_costs(self):
        plan = fixture_plan()
        del plan["comparator"]
        with self.assertRaises(ProtocolError):
            validate_plan(plan)
        plan = fixture_plan()
        plan["comparator"]["same_data_and_cost_model"] = False
        with self.assertRaises(ProtocolError):
            validate_plan(plan)

    def test_chronological_overlap_or_backward_fold_is_rejected(self):
        mutations = [
            lambda p: p["evaluation"]["validation"].update(start="2022-12-31"),
            lambda p: p["evaluation"]["holdout"].update(start="2023-12-31"),
            lambda p: p["evaluation"]["walk_forward"][0]["test"].update(start="2022-01-01"),
            lambda p: p["evaluation"]["forward_extension"].update(start="2024-12-31"),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                plan = fixture_plan()
                mutation(plan)
                with self.assertRaises(ProtocolError):
                    validate_plan(plan)

    def test_disclosed_year_must_match_holdout(self):
        plan = fixture_plan()
        plan["evaluation"]["disclosed_holdout_year"] = 2023
        with self.assertRaises(ProtocolError):
            validate_plan(plan)

    def test_unset_periods_are_visible_and_block_holdout_readiness(self):
        plan = fixture_plan()
        for field in ("holdout", "disclosed_holdout_year", "walk_forward", "forward_extension"):
            plan["evaluation"][field] = "UNSET"
        result = validate_plan(plan)
        self.assertFalse(result["holdout_ready"])
        self.assertTrue(result["unresolved"])

    def test_only_one_declared_real_change_is_an_ablation(self):
        plan = fixture_plan()
        validate_ablation(plan, "full_model", {"flow": {"from": True, "to": False}})
        invalid = [
            {},
            {"flow": {"from": True, "to": True}},
            {"flow": {"from": "invented-comparator-setting", "to": False}},
            {"flow": {"from": True, "to": False}, "ta": {"from": True, "to": False}},
            {"undeclared_factor": {"from": True, "to": False}},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ProtocolError):
                validate_ablation(plan, "full_model", changes)

    def test_economic_cash_control_is_not_the_full_model_ablation_comparator(self):
        with self.assertRaises(ProtocolError):
            validate_ablation(fixture_plan(), "cash", {"flow": {"from": True, "to": False}})

    def test_ablation_comparator_is_bound_to_frozen_config_and_settings(self):
        for field in ("config_sha256", "settings_sha256"):
            with self.subTest(field=field):
                plan = fixture_plan()
                plan["ablation_comparator"][field] = "f" * 64
                with self.assertRaises(ProtocolError):
                    validate_plan(plan)

    def test_placeholder_hypothesis_falsifier_and_cost_basis_are_not_research(self):
        mutations = [
            lambda p: p["hypothesis"].update(statement="UNKNOWN"),
            lambda p: p["hypothesis"].update(economic_reason="TBD"),
            lambda p: p["hypothesis"].update(falsifier="UNSET"),
            lambda p: p["costs"].update(basis="UNSET"),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                plan = fixture_plan()
                mutation(plan)
                with self.assertRaises(ProtocolError):
                    validate_plan(plan)


class LedgerAndHoldoutGates(unittest.TestCase):
    def setUp(self):
        self.temporary = fixture_directory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "trials.jsonl"
        self.plan = fixture_plan()

    def start_trial(self, trial_id="trial-A", kind="BASELINE", changes=None):
        comparator = "full_model" if kind == "ABLATION" else "cash"
        return record_trial(self.path, self.plan, trial_id, kind, changes or {}, comparator,
                            now="2025-01-01T12:00:00Z")

    def test_every_failed_aborted_and_unviewed_attempt_counts(self):
        statuses = ["FAILED", "ABORTED", "REJECTED", "SUCCEEDED"]
        for index, status in enumerate(statuses):
            trial_id = f"trial-{index}"
            self.start_trial(trial_id)
            event = {"type": "TRIAL_RESULT", "trial_id": trial_id,
                     "status": status, "viewed": False}
            if status == "SUCCEEDED":
                event["results_sha256"] = "e" * 64
            append_event(self.path, event, now="2025-01-01T12:00:00Z")
        self.assertEqual(trial_count(read_ledger(self.path)), len(statuses))

    def test_duplicate_trial_ids_are_rejected(self):
        self.start_trial()
        with self.assertRaises(ProtocolError):
            self.start_trial()
        self.assertEqual(trial_count(read_ledger(self.path)), 1)

    def test_result_without_a_started_trial_is_rejected(self):
        with self.assertRaises(ProtocolError):
            append_event(self.path, {"type": "TRIAL_RESULT", "trial_id": "not-started",
                                    "status": "FAILED", "viewed": False})

    def test_public_append_cannot_bypass_reservation_or_owner_approval_gates(self):
        source = Path(self.temporary.name) / "valid-source-ledger.jsonl"
        record_trial(source, self.plan, "complete-identity", "BASELINE", {}, "cash",
                     now="2025-01-01T12:00:00Z")
        open_holdout(source, self.plan, fixture_approval(self.plan), lambda *_: True,
                     now="2025-01-03T12:00:00Z")
        events = read_ledger(source)
        for event in events:
            # Replay a complete valid payload so malformed fields cannot mask a bypass.
            payload = {key: value for key, value in event.items()
                       if key not in {"sequence", "previous_hash", "event_hash", "timestamp"}}
            path = source if event["type"] == "HOLDOUT_OPENED" else self.path
            with self.subTest(kind=event["type"]), self.assertRaises(ProtocolError):
                append_event(path, payload, now="2025-01-04T12:00:00Z")
        self.assertEqual(read_ledger(self.path), [])
        self.assertEqual(read_ledger(source), events)

    def test_ablation_gate_prevents_logging_a_mislabeled_trial(self):
        with self.assertRaises(ProtocolError):
            self.start_trial(kind="ABLATION", changes={
                "flow": {"from": True, "to": False},
                "ta": {"from": True, "to": False},
            })
        self.assertEqual(trial_count(read_ledger(self.path)), 0)

    def test_corrections_preserve_the_original_and_trial_count(self):
        original = self.start_trial()
        append_event(self.path, {"type": "CORRECTION", "target_event_hash": original["event_hash"],
                                "reason": "Invented fixture label correction",
                                "replacement": {"note": "synthetic label"}})
        events = read_ledger(self.path)
        self.assertEqual(trial_count(events), 1)
        self.assertEqual(events[0], original)

    def test_tampered_history_is_rejected(self):
        self.start_trial()
        text = self.path.read_text(encoding="utf-8")
        self.path.write_text(text.replace("trial-A", "tampered-A"), encoding="utf-8")
        with self.assertRaises(ProtocolError):
            read_ledger(self.path)

    def test_deleting_an_interior_event_breaks_the_chain(self):
        self.start_trial("trial-A")
        self.start_trial("trial-B")
        self.start_trial("trial-C")
        lines = self.path.read_text(encoding="utf-8").splitlines(keepends=True)
        self.path.write_text("".join([lines[0], *lines[2:]]), encoding="utf-8")
        with self.assertRaises(ProtocolError):
            read_ledger(self.path)

    def test_truncation_is_rejected_against_a_retained_external_anchor(self):
        self.start_trial("trial-A")
        self.start_trial("trial-B")
        anchor = read_ledger(self.path)[-1]["event_hash"]
        lines = self.path.read_text(encoding="utf-8").splitlines(keepends=True)
        self.path.write_text("".join(lines[:-1]), encoding="utf-8")
        with self.assertRaises(ProtocolError):
            read_ledger(self.path, expected_tail_hash=anchor)

    def test_approval_is_invalid_after_config_code_or_dataset_changes(self):
        approval = fixture_approval(self.plan)
        mutations = [
            lambda p: p.update(config_sha256="f" * 64),
            lambda p: p.update(code_commit="f" * 40),
            lambda p: p["datasets"][0].update(sha256="f" * 64),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                plan = deepcopy(self.plan)
                mutation(plan)
                with self.assertRaises(ProtocolError):
                    validate_preregistration(plan, approval, [], now="2025-01-03T12:00:00Z")

    def test_holdout_requires_approval_before_it_is_opened(self):
        approval = fixture_approval(self.plan)
        with self.assertRaises(ProtocolError):
            open_holdout(self.path, self.plan, approval, lambda *_: True,
                         now="2025-01-02T11:00:00Z")
        self.assertEqual(read_ledger(self.path), [])

    def test_externally_verified_synthetic_approval_can_open_once(self):
        approval = fixture_approval(self.plan)
        receipt = deepcopy(approval)
        event = open_holdout(self.path, self.plan, approval,
                             lambda supplied: supplied == receipt,
                             now="2025-01-03T12:00:00Z")
        self.assertEqual(event["type"], "HOLDOUT_OPENED")
        with self.assertRaises(ProtocolError):
            open_holdout(self.path, self.plan, approval, lambda *_: True,
                         now="2025-01-04T12:00:00Z")

    def test_synthetic_approval_cannot_open_genuine_data(self):
        self.plan["data_kind"] = "GENUINE"
        approval = fixture_approval(self.plan)
        with self.assertRaises(ProtocolError):
            open_holdout(self.path, self.plan, approval, lambda *_: True,
                         now="2025-01-03T12:00:00Z")

    def test_genuine_owner_receipt_requires_external_verification(self):
        self.plan["data_kind"] = "GENUINE"
        approval = fixture_approval(self.plan, "OWNER_APPROVAL_RECORDED")
        with self.assertRaises(ProtocolError):
            open_holdout(self.path, self.plan, approval, lambda *_: False,
                         now="2025-01-03T12:00:00Z")
        event = open_holdout(self.path, self.plan, approval,
                             lambda supplied: supplied == approval,
                             now="2025-01-03T12:00:00Z")
        self.assertEqual(event["type"], "HOLDOUT_OPENED")

    def test_previously_observed_holdout_is_not_fresh(self):
        self.plan["evaluation"]["holdout_previously_observed"] = True
        self.plan["evaluation"]["holdout_prior_observation_at"] = "2025-01-01T12:00:00Z"
        with self.assertRaises(ProtocolError):
            open_holdout(self.path, self.plan, fixture_approval(self.plan), lambda *_: True,
                         now="2025-01-03T12:00:00Z")

    def test_unset_dates_cannot_be_opened_by_owner_approval(self):
        self.plan["evaluation"]["holdout"] = "UNSET"
        self.plan["evaluation"]["disclosed_holdout_year"] = "UNSET"
        with self.assertRaises(ProtocolError):
            open_holdout(self.path, self.plan, fixture_approval(self.plan), lambda *_: True,
                         now="2025-01-03T12:00:00Z")

    def test_holdout_trial_cannot_start_before_the_opening_gate(self):
        with self.assertRaises(ProtocolError):
            record_trial(self.path, self.plan, "premature-holdout", "BASELINE", {}, "cash",
                         now="2025-01-03T12:00:00Z", evaluation_stage="HOLDOUT")

    def test_frozen_baseline_can_be_evaluated_but_not_tuned_on_holdout(self):
        open_holdout(self.path, self.plan, fixture_approval(self.plan), lambda *_: True,
                     now="2025-01-03T12:00:00Z")
        record_trial(self.path, self.plan, "frozen-holdout", "BASELINE", {}, "cash",
                     now="2025-01-03T12:01:00Z", evaluation_stage="HOLDOUT")
        with self.assertRaises(ProtocolError):
            record_trial(self.path, self.plan, "tuned-holdout", "ABLATION",
                         {"flow": {"from": True, "to": False}}, "full_model",
                         now="2025-01-03T12:02:00Z", evaluation_stage="HOLDOUT")

    def test_validation_label_cannot_allow_tuning_after_holdout_opening(self):
        open_holdout(self.path, self.plan, fixture_approval(self.plan), lambda *_: True,
                     now="2025-01-03T12:00:00Z")
        with self.assertRaises(ProtocolError):
            record_trial(self.path, self.plan, "post-open-tuning", "VARIANT",
                         {"flow": {"from": True, "to": False}}, "cash",
                         now="2025-01-03T12:02:00Z", evaluation_stage="VALIDATION")


class ReportGates(unittest.TestCase):
    def setUp(self):
        self.temporary = fixture_directory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.plan = fixture_plan()
        config = root / "config.json"
        dataset = root / "synthetic-input.json"
        results = root / "results.json"
        regenerated = root / "regenerated-results.json"
        config.write_text(json.dumps({"synthetic": True, "flow": True}), encoding="utf-8")
        dataset.write_text(json.dumps({"synthetic": True, "observations": [1, 2, 3]}), encoding="utf-8")
        results.write_text(json.dumps({"data_kind": "SYNTHETIC",
                                       "metrics": {"net_excess_return": 0.01}}), encoding="utf-8")
        regenerated.write_bytes(results.read_bytes())
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        self.plan["config_sha256"] = digest(config)
        self.plan["ablation_comparator"]["config_sha256"] = digest(config)
        self.plan["datasets"][0]["sha256"] = digest(dataset)
        ledger = root / "trials.jsonl"
        record_trial(ledger, self.plan, "synthetic-baseline", "BASELINE", {}, "cash",
                     now="2025-01-01T12:00:00Z")
        append_event(ledger, {"type": "TRIAL_RESULT", "trial_id": "synthetic-baseline",
                              "status": "SUCCEEDED", "viewed": False,
                              "results_sha256": digest(results)}, now="2025-01-01T12:00:00Z")
        self.events = read_ledger(ledger)
        dataset_hashes = {"prices": digest(dataset)}
        self.artifact = {
            "plan_hash": canonical_hash(self.plan), "code_commit": self.plan["code_commit"],
            "config_sha256": digest(config), "dataset_hashes": dataset_hashes,
            "results_sha256": digest(results), "ledger_tail_hash": self.events[-1]["event_hash"],
            "trial_id": "synthetic-baseline", "trial_count": 1,
            "evaluation_stage": "VALIDATION",
            "headline_metrics": {"net_excess_return": 0.01}, "source_state": "COMMITTED",
        }
        self.reproduced = {
            "code_commit": self.plan["code_commit"], "config_sha256": digest(config),
            "dataset_hashes": dataset_hashes, "results_sha256": digest(results),
            "source_state": "COMMITTED", "regenerated_at": "2025-01-03T12:00:00Z",
            "run_command": "synthetic fixture regeneration, externally attested in this test",
        }
        self.paths = {"config": config, "datasets": {"prices": dataset},
                      "results": results, "reproduced_results": regenerated}

    def verify(self, **kwargs):
        options = {"artifact_paths": self.paths,
                   "commit_verifier": lambda revision: revision == self.plan["code_commit"],
                   "regeneration_verifier": lambda receipt: receipt == self.reproduced,
                   "now": "2025-01-04T12:00:00Z"}
        options.update(kwargs)
        return verify_report(self.plan, self.events, self.artifact, self.reproduced, **options)

    def test_matching_synthetic_files_and_external_receipts_are_reviewable(self):
        result = self.verify()
        self.assertTrue(result["ready"])
        self.assertEqual(result["status"], "VERIFIED_FOR_OWNER_REVIEW")
        self.assertEqual(result["trial_count"], 1)

    def test_noncommitted_source_cannot_support_headline(self):
        for target in (self.artifact, self.reproduced):
            original = target["source_state"]
            target["source_state"] = "WORKTREE_NOT_COMMITTED"
            with self.assertRaises(ProtocolError):
                self.verify()
            target["source_state"] = original

    def test_declaring_committed_is_not_a_commit_verification(self):
        with self.assertRaises(ProtocolError):
            self.verify(commit_verifier=lambda *_: False)
        with self.assertRaises(ProtocolError):
            self.verify(commit_verifier=None)

    def test_regeneration_cannot_be_self_asserted_without_external_check(self):
        with self.assertRaises(ProtocolError):
            self.verify(regeneration_verifier=None)
        with self.assertRaises(ProtocolError):
            self.verify(regeneration_verifier=lambda *_: False)

    def test_headline_must_match_the_regenerated_numeric_artifact(self):
        self.artifact["headline_metrics"]["net_excess_return"] = 0.99
        with self.assertRaises(ProtocolError):
            self.verify()

    def test_changed_result_bytes_are_rejected_even_when_metadata_still_matches(self):
        self.paths["reproduced_results"].write_text(
            json.dumps({"metrics": {"net_excess_return": 0.99}}), encoding="utf-8")
        with self.assertRaises(ProtocolError):
            self.verify()

    def test_changed_input_or_configuration_bytes_invalidate_report(self):
        for path in (self.paths["config"], self.paths["datasets"]["prices"]):
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                with self.assertRaises(ProtocolError):
                    self.verify()
                path.write_bytes(original)

    def test_report_cannot_hide_unviewed_failed_trials(self):
        root = Path(self.temporary.name)
        ledger = root / "trials.jsonl"
        record_trial(ledger, self.plan, "unviewed-failure", "BASELINE", {}, "cash",
                     now="2025-01-02T12:00:00Z")
        append_event(ledger, {"type": "TRIAL_RESULT", "trial_id": "unviewed-failure",
                              "status": "FAILED", "viewed": False}, now="2025-01-02T12:00:00Z")
        self.events = read_ledger(ledger)
        self.artifact["ledger_tail_hash"] = self.events[-1]["event_hash"]
        with self.assertRaises(ProtocolError):
            self.verify()

    def test_result_must_trace_to_a_successful_logged_trial(self):
        self.artifact["trial_id"] = "unlogged-winner"
        with self.assertRaises(ProtocolError):
            self.verify()

    def test_validation_result_cannot_be_relabeled_as_holdout_evidence(self):
        self.artifact["evaluation_stage"] = "HOLDOUT"
        with self.assertRaises(ProtocolError):
            self.verify()

    def test_rechained_trial_identity_and_ablation_bypasses_are_rejected(self):
        original = deepcopy(self.events)
        mutations = [
            lambda trial: trial.update(code_commit="f" * 40),
            lambda trial: trial.update(config_sha256="f" * 64),
            lambda trial: trial.update(dataset_hashes={"prices": "f" * 64}),
            lambda trial: trial.update(comparator_id="cherry-picked-winner"),
            lambda trial: trial.update(changes={"flow": {"from": True, "to": False}}),
            lambda trial: trial.update(kind="ABLATION", comparator_id="full_model", changes={
                "flow": {"from": True, "to": False}, "ta": {"from": True, "to": False}}),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                events = deepcopy(original)
                mutation(events[0])
                self.events = adversarial_rechain(events)
                self.artifact["ledger_tail_hash"] = self.events[-1]["event_hash"]
                with self.assertRaises(ProtocolError):
                    self.verify()

    def test_regeneration_receipt_cannot_predate_success_or_claim_the_future(self):
        for timestamp in ("2024-01-01T12:00:00Z", "2099-01-01T12:00:00Z"):
            with self.subTest(timestamp=timestamp):
                self.reproduced["regenerated_at"] = timestamp
                with self.assertRaises(ProtocolError):
                    self.verify()

    def holdout_report_fixture(self):
        ledger = Path(self.temporary.name) / "holdout.jsonl"
        open_holdout(ledger, self.plan, fixture_approval(self.plan), lambda *_: True,
                     now="2025-01-03T12:00:00Z")
        record_trial(ledger, self.plan, "held-out-baseline", "BASELINE", {}, "cash",
                     now="2025-01-03T12:01:00Z", evaluation_stage="HOLDOUT")
        append_event(ledger, {"type": "TRIAL_RESULT", "trial_id": "held-out-baseline",
                              "status": "SUCCEEDED", "viewed": False,
                              "results_sha256": self.artifact["results_sha256"]},
                     now="2025-01-03T12:02:00Z")
        self.events = read_ledger(ledger)
        self.artifact.update(trial_id="held-out-baseline", evaluation_stage="HOLDOUT",
                             ledger_tail_hash=self.events[-1]["event_hash"])
        self.reproduced["regenerated_at"] = "2025-01-03T12:03:00Z"

    def test_rechained_holdout_trial_reserved_before_opening_is_rejected(self):
        self.holdout_report_fixture()
        trial = self.events[2]
        trial["timestamp"] = "2025-01-03T11:59:00Z"
        self.events = adversarial_rechain([trial, *self.events[:2], self.events[3]])
        self.artifact["ledger_tail_hash"] = self.events[-1]["event_hash"]
        with self.assertRaises(ProtocolError):
            self.verify()

    def test_rechained_simulated_approval_cannot_become_genuine_holdout_evidence(self):
        self.holdout_report_fixture()
        self.plan["data_kind"] = "GENUINE"
        plan_hash = canonical_hash(self.plan)
        for event in self.events:
            if "plan_hash" in event:
                event["plan_hash"] = plan_hash
            if "data_kind" in event:
                event["data_kind"] = "GENUINE"
        # All bytes are invented, even though this adversarial metadata claims GENUINE.
        data = {"data_kind": "GENUINE", "metrics": {"net_excess_return": 0.01}}
        self.paths["results"].write_text(json.dumps(data), encoding="utf-8")
        self.paths["reproduced_results"].write_bytes(self.paths["results"].read_bytes())
        result_hash = hashlib.sha256(self.paths["results"].read_bytes()).hexdigest()
        self.events[-1]["results_sha256"] = result_hash
        self.events = adversarial_rechain(self.events)
        self.artifact.update(plan_hash=plan_hash, results_sha256=result_hash,
                             ledger_tail_hash=self.events[-1]["event_hash"])
        self.reproduced["results_sha256"] = result_hash
        with self.assertRaises(ProtocolError):
            self.verify()


if __name__ == "__main__":
    unittest.main()
