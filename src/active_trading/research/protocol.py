"""Offline checks for the workshop research loop, using a provisional format.

This module is not a backtester, broker adapter, approval authenticator, or file
access boundary. An owner approval needs external verification. Local hash chains
need protected external tail anchors to reveal wholesale rewrite/truncation.
The ledger lock serializes cooperating writers; it is not an operating-system
security boundary. Private inputs and ledger files belong outside tracked Git.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Callable


class ProtocolError(ValueError):
    """A research-protocol requirement was not met."""


SCHEMA_STATUS = "PROVISIONAL_NOT_WORKSHOP_VALIDATED"
GENESIS_HASH = "0" * 64
COST_FIELDS = ("commission_bps", "entry_spread_bps", "exit_spread_bps",
               "slippage_bps", "fx_bps", "financing_bps", "tax_bps")
INCLUSION_POLICY = "ALL_ATTEMPTS_INCLUDING_CASH_MISSED_FAILED_UNKNOWN"


def _fail(message):
    raise ProtocolError(message)


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        _fail(f"{label} must be a nonempty string")
    return value.strip()


def _research_text(value, label):
    value = _text(value, label)
    if re.search(r"\b(?:UNSET|UNKNOWN|TBD)\b|TO\s+BE\s+DETERMINED", value, flags=re.IGNORECASE):
        _fail(f"{label} contains unresolved research metadata")
    return value


def _mapping(value, label):
    if not isinstance(value, dict):
        _fail(f"{label} must be an object")
    return value


def _digest(value, label, length=64):
    if not isinstance(value, str) or not re.fullmatch(rf"[0-9a-f]{{{length}}}", value):
        _fail(f"{label} must be a lowercase {length}-character hexadecimal identity")
    if value == "0" * length:
        _fail(f"{label} cannot be an unset zero identity")
    return value


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        _fail(f"{label} must be a finite nonnegative number")
    return value


def _timestamp(value, label):
    try:
        result = datetime.fromisoformat(_text(value, label).replace("Z", "+00:00"))
    except (ValueError, TypeError) as error:
        raise ProtocolError(f"{label} must be an ISO timestamp") from error
    if result.tzinfo is None or result.utcoffset() is None:
        _fail(f"{label} must include its timezone")
    return result.astimezone(timezone.utc)


def _now(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            _fail("now must have a timezone")
        return value.astimezone(timezone.utc)
    return _timestamp(value, "now")


def _span(value, label):
    value = _mapping(value, label)
    try:
        start = date.fromisoformat(value["start"])
        end = date.fromisoformat(value["end"])
    except (KeyError, ValueError, TypeError) as error:
        raise ProtocolError(f"{label} requires ISO start/end dates") from error
    if start > end:
        _fail(f"{label} starts after it ends")
    return start, end


def canonical_hash(value):
    """SHA256 of deterministic JSON, rejecting non-finite values."""
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ProtocolError("Value is not finite JSON") from error
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path):
    """Hash actual local file bytes; no file contents are published or printed."""
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except (OSError, TypeError) as error:
        raise ProtocolError("A required artifact file is unavailable") from error
    return digest.hexdigest()


def dataset_hashes(plan):
    return {item["id"]: item["sha256"] for item in plan["datasets"]}


def validate_plan(plan):
    """Validate a frozen research plan, retaining genuinely unresolved periods."""
    plan = _mapping(plan, "plan")
    if plan.get("schema_status") != SCHEMA_STATUS or plan.get("mode") != "SHADOW_RESEARCH":
        _fail("Only the provisional SHADOW_RESEARCH protocol is supported")
    if plan.get("data_kind") not in ("GENUINE", "SYNTHETIC"):
        _fail("data_kind must be GENUINE or SYNTHETIC")
    hypothesis = _mapping(plan.get("hypothesis"), "hypothesis")
    statement = _research_text(hypothesis.get("statement"), "hypothesis.statement")
    # A deliberate, simple writing convention: one sentence and one terminal mark.
    if len(re.findall(r"[.!?](?:\s|$)", statement)) != 1 or statement[-1] not in ".!?":
        _fail("Hypothesis must be one sentence with a terminal punctuation mark")
    _research_text(hypothesis.get("economic_reason"), "hypothesis.economic_reason")
    _research_text(hypothesis.get("falsifier"), "hypothesis.falsifier")
    _digest(plan.get("code_commit"), "code_commit", 40)
    _digest(plan.get("config_sha256"), "config_sha256")
    datasets = plan.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        _fail("At least one frozen dataset identity is required")
    seen = set()
    for item in datasets:
        item = _mapping(item, "dataset")
        identity = _text(item.get("id"), "dataset.id")
        if identity in seen:
            _fail("Dataset IDs must be unique")
        seen.add(identity)
        _digest(item.get("sha256"), "dataset.sha256")
        _timestamp(item.get("frozen_at"), "dataset.frozen_at")
    costs = _mapping(plan.get("costs"), "costs")
    if costs.get("model") != "EXPLICIT_BPS":
        _fail("A predeclared EXPLICIT_BPS cost model is required")
    _research_text(costs.get("basis"), "costs.basis")
    for field in COST_FIELDS:
        _number(costs.get(field), f"costs.{field}")
    comparator = _mapping(plan.get("comparator"), "comparator")
    for field in ("id", "description", "selection_reason"):
        _text(comparator.get(field), f"comparator.{field}")
    _digest(comparator.get("config_sha256"), "comparator.config_sha256")
    if comparator.get("same_data_and_cost_model") is not True or comparator.get("inclusion_policy") != INCLUSION_POLICY:
        _fail("Comparator must share the frozen data/cost model and account for all attempts")
    dimensions = plan.get("ablation_dimensions")
    baseline = _mapping(plan.get("baseline_settings"), "baseline_settings")
    if not isinstance(dimensions, list) or not dimensions or any(not isinstance(d, str) for d in dimensions) or len(set(dimensions)) != len(dimensions):
        _fail("Ablation dimensions must be a nonempty unique list")
    for dimension in dimensions:
        _text(dimension, "ablation dimension")
        if dimension not in baseline:
            _fail("Every ablation dimension needs a frozen baseline setting")
    canonical_hash(baseline)
    ablation_comparator = _mapping(plan.get("ablation_comparator"), "ablation_comparator")
    _text(ablation_comparator.get("id"), "ablation_comparator.id")
    if ablation_comparator.get("config_sha256") != plan["config_sha256"] or ablation_comparator.get("settings_sha256") != canonical_hash(baseline):
        _fail("Ablation comparator must identify the exact frozen full-model configuration and settings")
    evaluation = _mapping(plan.get("evaluation"), "evaluation")
    unresolved = []
    spans = {}
    for field in ("train", "validation", "holdout", "forward_extension"):
        value = evaluation.get(field)
        if value == "UNSET":
            unresolved.append(field)
        else:
            spans[field] = _span(value, f"evaluation.{field}")
    # Chronology is strict and inclusive boundaries must not overlap.
    ordered = [spans[name] for name in ("train", "validation", "holdout", "forward_extension") if name in spans]
    if any(left[1] >= right[0] for left, right in zip(ordered, ordered[1:])):
        _fail("Training, validation, holdout and extension must be strictly chronological")
    year = evaluation.get("disclosed_holdout_year")
    if year == "UNSET":
        unresolved.append("disclosed_holdout_year")
    elif isinstance(year, bool) or not isinstance(year, int) or not 1900 <= year <= 9999:
        _fail("disclosed_holdout_year must be an explicit year or UNSET")
    elif "holdout" in spans and (spans["holdout"][0].year != year or spans["holdout"][1].year != year):
        _fail("The disclosed year must match the complete holdout period")
    folds = evaluation.get("walk_forward")
    if folds == "UNSET":
        unresolved.append("walk_forward")
    elif not isinstance(folds, list) or not folds:
        _fail("walk_forward must be predeclared nonempty folds or UNSET")
    else:
        previous_test_end = None
        for fold in folds:
            fold = _mapping(fold, "walk_forward fold")
            train = _span(fold.get("train"), "fold.train")
            test = _span(fold.get("test"), "fold.test")
            if train[1] >= test[0] or (previous_test_end is not None and previous_test_end >= test[0]):
                _fail("Walk-forward folds must train before disjoint chronological tests")
            if "train" in spans and train[0] < spans["train"][0]:
                _fail("Fold training starts before the frozen training range")
            if "validation" in spans and test[0] < spans["validation"][0]:
                _fail("Fold tests start before validation")
            if "forward_extension" in spans and test[1] > spans["forward_extension"][1]:
                _fail("Fold tests extend beyond the declared evaluation range")
            previous_test_end = test[1]
    previously_seen = evaluation.get("holdout_previously_observed")
    if not isinstance(previously_seen, bool):
        _fail("The holdout's prior-observation status must be explicit")
    prior_observation = evaluation.get("holdout_prior_observation_at")
    if previously_seen:
        _timestamp(prior_observation, "holdout_prior_observation_at")
        unresolved.append("HOLDOUT_ALREADY_OBSERVED")
    elif prior_observation != "UNSET":
        _fail("An observation timestamp cannot be hidden behind an unobserved flag")
    reporting = _mapping(plan.get("reporting"), "reporting")
    names = reporting.get("headline_metrics")
    tolerances = _mapping(reporting.get("metric_tolerances"), "metric_tolerances")
    if not isinstance(names, list) or not names or any(not isinstance(n, str) for n in names) or len(set(names)) != len(names):
        _fail("Headline metrics must be a nonempty unique predeclared list")
    if set(names) != set(tolerances):
        _fail("Every headline metric needs exactly one predeclared tolerance")
    for name in names:
        _text(name, "headline metric")
        _number(tolerances[name], f"metric tolerance {name}")
    if reporting.get("include_all_trials") is not True:
        _fail("Reporting must retain the full uncensored trial count")
    return {"plan_hash": canonical_hash(plan), "holdout_ready": not unresolved, "unresolved": unresolved}


def validate_ablation(plan, comparator_id, changes):
    """Enforce one declared intervention against the declared comparator."""
    validate_plan(plan)
    if comparator_id != plan["ablation_comparator"]["id"]:
        _fail("Ablation uses the wrong frozen full-model comparator")
    changes = _mapping(changes, "changes")
    if len(changes) != 1:
        _fail("An ablation must change exactly one predeclared dimension")
    dimension, change = next(iter(changes.items()))
    change = _mapping(change, "ablation change")
    if dimension not in plan["ablation_dimensions"] or set(change) != {"from", "to"}:
        _fail("Ablation must declare from/to values for an allowed dimension")
    if change["from"] != plan["baseline_settings"][dimension]:
        _fail("Ablation from-value differs from the frozen baseline")
    if canonical_hash(change["from"]) == canonical_hash(change["to"]):
        _fail("An ablation must actually change its declared dimension")


def _validate_events(events):
    previous = GENESIS_HASH
    previous_time = None
    trials, results, hashes = {}, {}, set()
    for sequence, event in enumerate(events, 1):
        _mapping(event, "ledger event")
        if type(event.get("sequence")) is not int or event["sequence"] != sequence or event.get("previous_hash") != previous:
            _fail("Ledger sequence or hash chain is broken")
        payload = {key: value for key, value in event.items() if key != "event_hash"}
        if event.get("event_hash") != canonical_hash(payload):
            _fail("Ledger event bytes no longer match their hash")
        timestamp = _timestamp(event.get("timestamp"), "event.timestamp")
        if previous_time is not None and timestamp < previous_time:
            _fail("Ledger event timestamps must not go backwards")
        previous_time = timestamp
        kind = event.get("type")
        if kind == "TRIAL_PLANNED":
            trial_id = _text(event.get("trial_id"), "trial_id")
            if trial_id in trials:
                _fail("A trial ID cannot be planned twice")
            trials[trial_id] = event
            _digest(event.get("plan_hash"), "trial.plan_hash")
            _digest(event.get("code_commit"), "trial.code_commit", 40)
            _digest(event.get("config_sha256"), "trial.config_sha256")
            if event.get("kind") not in ("BASELINE", "ABLATION", "VARIANT") or event.get("evaluation_stage") not in ("VALIDATION", "HOLDOUT", "FORWARD_EXTENSION"):
                _fail("Trial kind and evaluation stage must be explicit")
        elif kind == "TRIAL_RESULT":
            trial_id = event.get("trial_id")
            if trial_id not in trials or trial_id in results:
                _fail("Each result requires a unique previously planned trial")
            if event.get("status") not in ("SUCCEEDED", "FAILED", "REJECTED", "ABORTED") or not isinstance(event.get("viewed"), bool):
                _fail("Result status and viewed/not-viewed state must be explicit")
            if event["status"] == "SUCCEEDED":
                _digest(event.get("results_sha256"), "results_sha256")
            results[trial_id] = event
        elif kind == "RESULT_ACCESSED":
            result = results.get(event.get("trial_id"))
            if result is None or event.get("result_event_hash") != result["event_hash"]:
                _fail("Result access must reference a previously logged result")
        elif kind == "CORRECTION":
            if event.get("target_event_hash") not in hashes:
                _fail("A correction must link an existing event")
            _text(event.get("reason"), "correction.reason")
            _mapping(event.get("replacement"), "correction.replacement")
        elif kind in ("OWNER_APPROVAL_RECORDED", "HOLDOUT_OPENED"):
            _digest(event.get("plan_hash"), "holdout.plan_hash")
            _digest(event.get("approval_hash"), "holdout.approval_hash")
            if kind == "HOLDOUT_OPENED":
                _mapping(event.get("dataset_hashes"), "holdout.dataset_hashes")
                if not any(e["type"] == "OWNER_APPROVAL_RECORDED" and e["approval_hash"] == event["approval_hash"] and e["plan_hash"] == event["plan_hash"] and e.get("approved_at") == event.get("approved_at") for e in events[:sequence - 1]):
                    _fail("Holdout open requires a preceding recorded approval")
                if _timestamp(event.get("approved_at"), "approved_at") >= timestamp:
                    _fail("Approval must strictly predate first holdout opening")
        else:
            _fail("Unknown ledger event type")
        previous = event["event_hash"]
        hashes.add(previous)
    return events


def read_ledger(path, expected_tail_hash=None):
    """Read and validate a ledger; a trusted tail anchor detects truncation."""
    path = Path(path)
    try:
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    except (OSError, json.JSONDecodeError) as error:
        raise ProtocolError("Ledger is unavailable or contains an incomplete/invalid event") from error
    _validate_events(events)
    if expected_tail_hash is not None and expected_tail_hash != (events[-1]["event_hash"] if events else GENESIS_HASH):
        _fail("Ledger tail differs from the protected external anchor")
    return events


@contextmanager
def _ledger_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ProtocolError("Ledger is locked; do not remove a stale lock without operator review") from error
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink()


def _append_locked(path, events, additions, timestamp):
    fresh = list(events)
    for event in additions:
        if any(key in event for key in ("sequence", "previous_hash", "event_hash", "timestamp")):
            _fail("Ledger envelope fields are assigned by the writer")
        envelope = dict(event, sequence=len(fresh) + 1,
                        previous_hash=fresh[-1]["event_hash"] if fresh else GENESIS_HASH,
                        timestamp=timestamp.isoformat())
        envelope["event_hash"] = canonical_hash(envelope)
        fresh.append(envelope)
    _validate_events(fresh)
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            for event in fresh:
                handle.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
    return fresh[-len(additions):]


def append_event(path, event, now=None):
    """Serialize and atomically replace the local ledger without rewriting events."""
    event = _mapping(event, "event")
    if event.get("type") in ("TRIAL_PLANNED", "OWNER_APPROVAL_RECORDED", "HOLDOUT_OPENED"):
        _fail("Privileged events require record_trial or open_holdout so their gates cannot be bypassed")
    with _ledger_lock(path):
        return _append_locked(path, read_ledger(path), [event], _now(now))[0]


def trial_count(events):
    """Count all planned attempts, including missing, failed and rejected results."""
    return sum(event.get("type") == "TRIAL_PLANNED" for event in events)


def record_trial(path, plan, trial_id, kind, changes, comparator_id, now=None, evaluation_stage="VALIDATION"):
    """Reserve a trial identity before running code or accessing its result."""
    validated = validate_plan(plan)
    _text(trial_id, "trial_id")
    changes = _mapping(changes, "changes")
    if kind == "ABLATION":
        validate_ablation(plan, comparator_id, changes)
    elif kind == "BASELINE":
        if changes:
            _fail("Baseline trials cannot hide changed settings")
    elif kind != "VARIANT":
        _fail("Trial kind must be BASELINE, ABLATION or VARIANT")
    if kind != "ABLATION" and comparator_id != plan["comparator"]["id"]:
        _fail("Economic comparison trial must use the frozen economic comparator")
    if evaluation_stage not in ("VALIDATION", "HOLDOUT", "FORWARD_EXTENSION"):
        _fail("Unknown evaluation stage")
    with _ledger_lock(path):
        events = read_ledger(path)
        if evaluation_stage == "VALIDATION" and any(e["type"] == "HOLDOUT_OPENED" and e["plan_hash"] == validated["plan_hash"] for e in events):
            _fail("The holdout is already exposed; new validation tuning of this plan is prohibited")
        if evaluation_stage != "VALIDATION":
            if kind != "BASELINE" or changes:
                _fail("Frozen holdout/extension evaluation cannot tune or ablate the plan")
            if not any(e["type"] == "HOLDOUT_OPENED" and e["plan_hash"] == validated["plan_hash"] for e in events):
                _fail("Holdout/extension trial requires prior approved opening for the exact plan")
        event = {"type": "TRIAL_PLANNED", "trial_id": trial_id, "plan_hash": validated["plan_hash"],
                 "code_commit": plan["code_commit"], "config_sha256": plan["config_sha256"],
                 "dataset_hashes": dataset_hashes(plan), "kind": kind, "changes": changes,
                 "comparator_id": comparator_id, "evaluation_stage": evaluation_stage}
        return _append_locked(path, events, [event], _now(now))[0]


def validate_preregistration(plan, approval, events, now=None):
    """Validate approval metadata. This does not authenticate the named owner."""
    validated = validate_plan(plan)
    if not validated["holdout_ready"]:
        _fail("Fresh holdout opening is blocked by unresolved or previously seen inputs")
    approval = _mapping(approval, "approval")
    if approval.get("status") not in ("OWNER_APPROVAL_RECORDED", "SIMULATED_APPROVAL"):
        _fail("A recorded owner approval is required")
    if plan["data_kind"] == "GENUINE" and approval["status"] == "SIMULATED_APPROVAL":
        _fail("Simulated approval cannot open genuine holdout data")
    _text(approval.get("owner_id"), "approval.owner_id")
    _text(approval.get("external_evidence"), "approval.external_evidence")
    for key, expected in (("plan_hash", validated["plan_hash"]), ("code_commit", plan["code_commit"]),
                          ("config_sha256", plan["config_sha256"]), ("dataset_hashes", dataset_hashes(plan))):
        if approval.get(key) != expected:
            _fail(f"Approval {key} is stale or bound to different inputs")
    approved_at = _timestamp(approval.get("approved_at"), "approved_at")
    if approved_at >= _now(now):
        _fail("Approval must strictly predate the first holdout opening")
    if any(_timestamp(d["frozen_at"], "frozen_at") > approved_at for d in plan["datasets"]):
        _fail("Data identity must be frozen before owner preregistration approval")
    _validate_events(events)
    for event in events:
        if event["type"] == "HOLDOUT_OPENED" and set(event["dataset_hashes"].values()) & set(dataset_hashes(plan).values()):
            _fail("These data were already opened; they cannot be presented as a fresh holdout")
    return {"approval_hash": canonical_hash(approval), "status": "OWNER_APPROVAL_METADATA_CHECKED"}


def open_holdout(path, plan, approval, external_approval_verifier, now=None):
    """Record externally checked approval and first opening atomically.

    No dataset file is opened by this function. Operators must enforce actual
    data access separately. The callback must verify owner evidence externally;
    an always-true callback is acceptable only in a clearly synthetic fixture.
    """
    timestamp = _now(now)
    if not callable(external_approval_verifier) or external_approval_verifier(approval) is not True:
        _fail("External approval evidence has not been verified")
    with _ledger_lock(path):
        events = read_ledger(path)
        validated = validate_preregistration(plan, approval, events, timestamp)
        common = {"plan_hash": canonical_hash(plan), "approval_hash": validated["approval_hash"],
                  "approval_status": approval["status"], "approved_at": approval["approved_at"],
                  "data_kind": plan["data_kind"]}
        additions = [dict(common, type="OWNER_APPROVAL_RECORDED"),
                     dict(common, type="HOLDOUT_OPENED", dataset_hashes=dataset_hashes(plan))]
        return _append_locked(path, events, additions, timestamp)[-1]


def _committed_repository(repository_path, revision):
    if repository_path is None:
        return False
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository_path, check=True,
                              capture_output=True, text=True).stdout.strip()
        changed = subprocess.run(["git", "diff", "--quiet", revision, "--"], cwd=repository_path)
        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
                                  cwd=repository_path, check=True, capture_output=True, text=True)
        return head == revision and changed.returncode == 0 and not untracked.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return False


def _validate_report_trial(plan, trial, events):
    """Replay the semantic gates, independently of a ledger's valid hash chain."""
    expected = {"plan_hash": canonical_hash(plan), "code_commit": plan["code_commit"],
                "config_sha256": plan["config_sha256"], "dataset_hashes": dataset_hashes(plan)}
    if any(trial.get(key) != value for key, value in expected.items()):
        _fail("Reported trial identities differ from the exact frozen plan")
    changes = _mapping(trial.get("changes"), "trial.changes")
    kind = trial.get("kind")
    if kind == "ABLATION":
        validate_ablation(plan, trial.get("comparator_id"), changes)
    elif kind == "BASELINE":
        if changes or trial.get("comparator_id") != plan["comparator"]["id"]:
            _fail("Reported baseline hides changed settings or the wrong economic comparator")
    elif kind == "VARIANT":
        if trial.get("comparator_id") != plan["comparator"]["id"]:
            _fail("Reported variant uses the wrong economic comparator")
    else:
        _fail("Reported trial has an invalid kind")
    stage = trial.get("evaluation_stage")
    same_plan_opens = [e for e in events if e["type"] == "HOLDOUT_OPENED" and e["plan_hash"] == expected["plan_hash"]]
    preceding_opens = [e for e in same_plan_opens if e["sequence"] < trial["sequence"]]
    if stage == "VALIDATION":
        if preceding_opens:
            _fail("Validation trial was reserved after its holdout had been exposed")
        return
    if stage not in ("HOLDOUT", "FORWARD_EXTENSION") or kind != "BASELINE" or changes:
        _fail("Held-out evaluation must use the frozen baseline without tuning")
    if not validate_plan(plan)["holdout_ready"]:
        _fail("Held-out trial uses unresolved or previously observed research data")
    opening = next((e for e in preceding_opens if e.get("dataset_hashes") == expected["dataset_hashes"]), None)
    if opening is None or _timestamp(opening["timestamp"], "holdout.timestamp") > _timestamp(trial["timestamp"], "trial.timestamp"):
        _fail("Held-out trial must be reserved after the exact approved opening")
    if opening.get("data_kind") != plan["data_kind"]:
        _fail("Held-out opening changed the genuine/synthetic data designation")
    status = opening.get("approval_status")
    if status not in ("OWNER_APPROVAL_RECORDED", "SIMULATED_APPROVAL") or (plan["data_kind"] == "GENUINE" and status != "OWNER_APPROVAL_RECORDED"):
        _fail("Held-out trial lacks valid owner preregistration metadata for its data mode")
    approval = next((e for e in events if e["type"] == "OWNER_APPROVAL_RECORDED"
                     and e["sequence"] < opening["sequence"] and e["plan_hash"] == expected["plan_hash"]
                     and e["approval_hash"] == opening["approval_hash"]), None)
    if approval is None or any(approval.get(key) != opening.get(key) for key in ("approval_status", "approved_at", "data_kind")):
        _fail("Held-out opening is not bound to the exact preceding owner approval record")
    approved_at = _timestamp(opening.get("approved_at"), "approved_at")
    if approved_at >= _timestamp(opening["timestamp"], "opened_at"):
        _fail("Owner preregistration must strictly predate first holdout opening")
    if any(_timestamp(d["frozen_at"], "frozen_at") > approved_at for d in plan["datasets"]):
        _fail("Held-out trial data identities were not frozen before owner approval")
    if any(e["type"] == "CORRECTION" and e["target_event_hash"] in {opening["event_hash"], approval["event_hash"]} for e in events):
        _fail("Corrected preregistration evidence cannot authorize this report")


def verify_report(plan, events, artifact, reproduced, *, artifact_paths,
                  commit_verifier=None, regeneration_verifier=None, repository_path=None, now=None):
    """Permit an owner-review report only after byte-level reproduction checks.

    External verifiers attest the actual committed code and regeneration run;
    narrative flags alone cannot do so. This validates supplied evidence and
    local bytes, not the economic validity of a model or trusted execution.
    """
    validated = validate_plan(plan)
    _validate_events(events)
    artifact = _mapping(artifact, "report artifact")
    reproduced = _mapping(reproduced, "reproduction record")
    paths = _mapping(artifact_paths, "artifact_paths")
    identities = {"code_commit": plan["code_commit"], "config_sha256": plan["config_sha256"],
                  "dataset_hashes": dataset_hashes(plan)}
    if artifact.get("plan_hash") != validated["plan_hash"]:
        _fail("Report is bound to a different frozen plan")
    for record in (artifact, reproduced):
        if record.get("source_state") != "COMMITTED":
            _fail("Reports require exact committed source, not uncommitted worktree claims")
        for key, expected in identities.items():
            if record.get(key) != expected:
                _fail(f"Reproduction {key} differs from frozen identity")
    committed = commit_verifier(plan["code_commit"]) if callable(commit_verifier) else _committed_repository(repository_path, plan["code_commit"])
    if committed is not True:
        _fail("The exact clean committed code has not been independently checked")
    if file_sha256(paths.get("config")) != plan["config_sha256"]:
        _fail("Configuration file bytes differ from the frozen configuration")
    data_paths = _mapping(paths.get("datasets"), "dataset artifact paths")
    if set(data_paths) != set(dataset_hashes(plan)):
        _fail("Actual artifact files are required for every frozen dataset")
    for identity, expected in dataset_hashes(plan).items():
        if file_sha256(data_paths[identity]) != expected:
            _fail("Dataset file bytes differ from the frozen identity")
    result_hash = _digest(artifact.get("results_sha256"), "report.results_sha256")
    if reproduced.get("results_sha256") != result_hash:
        _fail("Regenerated results identity differs from the reported result")
    if file_sha256(paths.get("results")) != result_hash or file_sha256(paths.get("reproduced_results")) != result_hash:
        _fail("Results file bytes were not exactly regenerated")
    regenerated_at = _timestamp(reproduced.get("regenerated_at"), "regenerated_at")
    if regenerated_at > _now(now):
        _fail("Regeneration timestamp is in the future relative to report verification")
    _text(reproduced.get("run_command"), "run_command")
    if not callable(regeneration_verifier) or regeneration_verifier(reproduced) is not True:
        _fail("The actual regeneration command has not been independently verified")
    tail = events[-1]["event_hash"] if events else GENESIS_HASH
    if artifact.get("ledger_tail_hash") != tail or artifact.get("trial_count") != trial_count(events):
        _fail("Report trial count or ledger tail omits recorded attempts")
    trial_id = artifact.get("trial_id")
    trial = next((e for e in events if e["type"] == "TRIAL_PLANNED" and e["trial_id"] == trial_id), None)
    result = next((e for e in events if e["type"] == "TRIAL_RESULT" and e["trial_id"] == trial_id), None)
    if trial is None or trial["plan_hash"] != validated["plan_hash"] or result is None or result["status"] != "SUCCEEDED" or result.get("results_sha256") != result_hash:
        _fail("Reported result must belong to a successfully logged trial of this plan")
    _validate_report_trial(plan, trial, events)
    if regenerated_at < _timestamp(result["timestamp"], "successful result timestamp"):
        _fail("Headline must be regenerated after the successful result was logged")
    stage = artifact.get("evaluation_stage")
    if stage != trial["evaluation_stage"]:
        _fail("Report must disclose its trial's actual evaluation stage")
    affected_hashes = {trial["event_hash"], result["event_hash"]}
    if any(e["type"] == "CORRECTION" and e["target_event_hash"] in affected_hashes for e in events):
        _fail("Corrected trial evidence requires a new linked trial and regeneration")
    try:
        result_data = json.loads(Path(paths["results"]).read_text(encoding="utf-8"))
        regenerated_data = json.loads(Path(paths["reproduced_results"]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProtocolError("Results must be valid JSON artifacts") from error
    for data in (result_data, regenerated_data):
        _mapping(data, "results file")
        if data.get("data_kind") != plan["data_kind"]:
            _fail("Results must explicitly preserve their genuine or synthetic data designation")
        if plan["data_kind"] == "SYNTHETIC" and data.get("profitability_evidence") is True:
            _fail("Synthetic result files cannot claim profitability evidence")
    metrics = _mapping(result_data.get("metrics"), "result metrics")
    regenerated_metrics = _mapping(regenerated_data.get("metrics"), "regenerated metrics")
    headline = _mapping(artifact.get("headline_metrics"), "headline metrics")
    names = plan["reporting"]["headline_metrics"]
    if set(headline) != set(names):
        _fail("Headline must use every and only the predeclared metric")
    for name in names:
        if name not in metrics or name not in regenerated_metrics:
            _fail("A reported metric is absent from regenerated results")
        for value in (headline[name], metrics[name], regenerated_metrics[name]):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                _fail("Headline metrics must be finite numeric values")
        tolerance = plan["reporting"]["metric_tolerances"][name]
        if abs(headline[name] - metrics[name]) > tolerance or abs(headline[name] - regenerated_metrics[name]) > tolerance:
            _fail("Narrative headline differs from newly regenerated numbers")
    return {"ready": True, "status": "VERIFIED_FOR_OWNER_REVIEW", "plan_hash": validated["plan_hash"],
            "trial_count": trial_count(events), "evaluation_stage": stage,
            "data_kind": plan["data_kind"], "profitability_evidence": False,
            "economic_validity_established": False}
