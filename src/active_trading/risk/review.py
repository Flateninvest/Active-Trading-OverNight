"""Exact-proposal reviewer attestations and deterministic SHADOW entry checks.

Reviewer keys are trusted service configuration, never part of an input packet.
HMAC authenticates an attestation's origin/integrity, not its financial truth.
Separate processes/credentials and authenticated data producers are deployment
requirements. A PASS here authorizes only recording a shadow intent.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import re


class ReviewError(ValueError):
    """A supplied proposal cannot advance to shadow intent recording."""


CHECKS = ("source_quality", "thesis", "ta", "calendar_events", "costs_liquidity",
          "ownership_account", "risk_exposure")


def canonical_hash(value):
    try:
        body = json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise ReviewError("Packet must contain finite JSON values") from exc
    return hashlib.sha256(body).hexdigest()


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ReviewError(label + " is required")
    return value


def _number(value, label, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ReviewError(label + " must be numeric")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ReviewError(label + " must be numeric") from exc
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise ReviewError(label + " must be finite and nonnegative/positive")
    return result


def _time(value, label):
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ReviewError(label + " must be an ISO timestamp") from exc
    else:
        raise ReviewError(label + " must be an ISO timestamp")
    if result.tzinfo is None or result.utcoffset() is None:
        raise ReviewError(label + " must include its timezone")
    return result.astimezone(timezone.utc)


def _mapping(value, label):
    if not isinstance(value, dict):
        raise ReviewError(label + " must be an object")
    return value


def _fresh(record, now, max_age, label):
    _text(record.get("source"), label + " source")
    observed = _time(record.get("observed_at"), label + " observed_at")
    if not now - timedelta(seconds=max_age) <= observed <= now:
        raise ReviewError(label + " is stale or future dated")
    return observed


def sign_review(review, key):
    """Reviewer-side utility. Never expose the key to the proposing agent."""
    if not isinstance(key, bytes) or len(key) < 32:
        raise ReviewError("Reviewer key must contain at least 32 secret bytes")
    unsigned = {k: v for k, v in review.items() if k != "signature"}
    result = dict(unsigned)
    result["signature"] = hmac.new(key, canonical_hash(unsigned).encode("ascii"),
                                   hashlib.sha256).hexdigest()
    return result


def review_proposal(proposal, review, policy, *, reviewer_keys, now):
    """Validate a signed critic packet and current deterministic entry policy.

    The caller owns trusted policy/key loading. Source authenticity, model
    invocation, actor credential isolation and any capital approvals are outside
    this offline function. It refuses both real and broker-demo execution.
    """
    proposal = _mapping(proposal, "proposal")
    review = _mapping(review, "review")
    policy = _mapping(policy, "policy")
    current = _time(now, "now")
    if (policy.get("default_mode") != "SHADOW" or policy.get("live_orders_enabled") is not False
            or policy.get("demo_orders_enabled") is not False or proposal.get("mode") != "SHADOW"):
        raise ReviewError("Only non-order-writing SHADOW mode is supported")
    if proposal.get("strategy_id") != policy.get("strategy_id"):
        raise ReviewError("Strategy differs from trusted policy")
    digest = canonical_hash(proposal)
    if proposal.get("spec_hash") != canonical_hash(policy):
        raise ReviewError("Proposal specification is stale or different")
    for field in ("proposal_id", "account_id", "instrument_id", "analyst_id", "sleeve"):
        _text(proposal.get(field), field)
    if proposal["sleeve"] not in policy["selection"]["sleeves"]:
        raise ReviewError("Unknown qualification sleeve")
    if not re.fullmatch(r"[0-9a-f]{40}", proposal.get("code_commit", "")):
        raise ReviewError("Exact source commit is required")
    inputs = proposal.get("input_hashes")
    if not isinstance(inputs, list) or not inputs or any(
            not isinstance(x, str) or not re.fullmatch(r"[0-9a-f]{64}", x) for x in inputs):
        raise ReviewError("Frozen input hashes are required")
    for field in ("calendar_hash", "frozen_register_hash"):
        if not re.fullmatch(r"[0-9a-f]{64}", proposal.get(field, "")):
            raise ReviewError(field + " is required")
    if (proposal.get("side") != "BUY" or proposal.get("product") != "UNDERLYING_REAL"
            or proposal.get("leverage") != 1 or isinstance(proposal.get("leverage"), bool)):
        raise ReviewError("Only long cash/X1 underlying entries are permitted")
    if proposal.get("currency") != "USD":
        raise ReviewError("USD-only control needs explicit FX support for any other currency")
    if proposal.get("in_frozen_register") is not True:
        raise ReviewError("Entry is not in the entry-day frozen register")
    if proposal.get("protected_or_unrelated_position") is not False:
        raise ReviewError("Ownership exception or unrelated position is unresolved")

    # Reviewer authentication and exact binding precede interpretation of PASS.
    reviewer_id = _text(review.get("reviewer_id"), "reviewer_id")
    if reviewer_id == proposal["analyst_id"]:
        raise ReviewError("Analyst cannot approve its own research review")
    if not isinstance(reviewer_keys, dict) or reviewer_id not in reviewer_keys:
        raise ReviewError("Reviewer is not in trusted service configuration")
    expected_signature = sign_review(review, reviewer_keys[reviewer_id])["signature"]
    signature = review.get("signature")
    if not isinstance(signature, str) or not hmac.compare_digest(signature, expected_signature):
        raise ReviewError("Reviewer signature is missing or invalid")
    if (review.get("schema") != "DOUBLE_REVIEW_v1" or review.get("mode") != "SHADOW"
            or review.get("proposal_digest") != digest or review.get("decision") != "PASS"):
        raise ReviewError("Reviewer packet is rejected or bound to a different proposal")
    _text(review.get("review_id"), "review_id")
    reviewed = _time(review.get("reviewed_at"), "reviewed_at")
    valid_until = _time(review.get("valid_until"), "valid_until")
    if not reviewed <= current < valid_until:
        raise ReviewError("Reviewer attestation is expired or future dated")
    required = list(CHECKS)
    if not isinstance(proposal.get("high_beta_or_volatile"), bool):
        raise ReviewError("Volatility review classification is required")
    if proposal["high_beta_or_volatile"]:
        required.append("enhanced_volatility")
    verdicts = _mapping(review.get("checks"), "review checks")
    for check in required:
        verdict = _mapping(verdicts.get(check), check)
        evidence = verdict.get("evidence")
        if (verdict.get("status") != "PASS" or not isinstance(evidence, list) or not evidence
                or any(not isinstance(x, str) or not x.strip() for x in evidence)):
            raise ReviewError(check + " requires PASS and traceable evidence")

    risk = policy["risk"]
    age = int(risk["maximum_quote_age_seconds"])
    quote = _mapping(proposal.get("quote"), "quote")
    quote_time = _fresh(quote, current, age, "quote")
    bid = _number(quote.get("bid"), "bid", positive=True)
    ask = _number(quote.get("ask"), "ask", positive=True)
    if bid > ask:
        raise ReviewError("Crossed quote")
    spread = (ask - bid) / ((ask + bid) / 2) * 10000
    if spread > _number(risk["maximum_spread_bps"], "spread cap"):
        raise ReviewError("Spread exceeds common entry cap")
    if reviewed < quote_time:
        raise ReviewError("Reviewer predates the bound quote snapshot")
    quantity = _number(proposal.get("quantity"), "quantity", positive=True)
    limit = _number(proposal.get("entry_price_limit"), "entry price limit", positive=True)
    if limit < ask:
        raise ReviewError("Passive/unfillable price variant is outside the primary shadow route")
    costs = _mapping(proposal.get("costs"), "costs")
    if costs.get("status") != "KNOWN" or costs.get("per_instrument") is not True:
        raise ReviewError("Explicit per-instrument entry cost model is required; no default fee")
    _text(costs.get("source"), "cost source")
    if costs.get("instrument_id") != proposal["instrument_id"]:
        raise ReviewError("Costs belong to another instrument")
    if not re.fullmatch(r"[0-9a-f]{64}", costs.get("model_hash", "")):
        raise ReviewError("Frozen per-instrument cost identity is required")
    reserve = _number(proposal.get("entry_cost_reserve_usd"), "cost reserve")
    if reserve < _number(costs.get("estimated_total_usd"), "estimated costs"):
        raise ReviewError("Reserved capital omits the supplied cost estimate")
    notional = quantity * limit + reserve
    if _number(proposal.get("approved_notional_usd"), "approved notional") != notional:
        raise ReviewError("Quantity, price ceiling and cost reserve do not match notional")
    snapshot = _mapping(proposal.get("account_snapshot"), "account snapshot")
    snapshot_time = _fresh(snapshot, current, age, "account snapshot")
    if reviewed < snapshot_time or snapshot.get("reconciled") is not True:
        raise ReviewError("Reviewer must check a current reconciled account snapshot")
    if snapshot.get("account_id") != proposal["account_id"] or snapshot.get("mode") != "SHADOW":
        raise ReviewError("Account snapshot belongs to another account/mode")
    nav = _number(snapshot.get("nav_usd"), "NAV", positive=True)
    if _number(proposal.get("nav_usd"), "proposal NAV", positive=True) != nav:
        raise ReviewError("Proposal NAV differs from account snapshot")
    score = _number(snapshot.get("broker_risk_score"), "broker risk score")
    if score > 10 or score >= _number(risk["pause_new_entries_at_score"], "risk pause"):
        raise ReviewError("Account risk score pauses new entries")
    exposures = snapshot.get("exposures")
    if not isinstance(exposures, list):
        raise ReviewError("Current plus pending strategy exposures are required")
    total = Decimal("0")
    instruments = set()
    for item in exposures:
        item = _mapping(item, "exposure")
        instrument = _text(item.get("instrument_id"), "exposure instrument")
        amount = _number(item.get("reserved_usd"), "exposure amount", positive=True)
        total += amount
        instruments.add(instrument)
    if proposal["instrument_id"] in instruments:
        raise ReviewError("Instrument already held or pending in either sleeve")
    if len(instruments) >= int(risk["maximum_positions"]):
        raise ReviewError("Combined position cap reached")
    if notional > nav * _number(risk["maximum_name_weight"], "name cap"):
        raise ReviewError("Entry exceeds the shared per-name capital cap")
    if total + notional > nav * _number(risk["maximum_gross_weight_including_pending"], "gross cap"):
        raise ReviewError("Entry exceeds combined held/pending capital cap")
    if notional > _number(snapshot.get("available_cash_usd"), "available cash"):
        raise ReviewError("Entry is not fully cash funded")
    reference = _mapping(proposal.get("monday_reference"), "Monday reference")
    _text(reference.get("source"), "Monday reference source")
    try:
        entry_day = datetime.fromisoformat(proposal["entry_session"]).date()
        reference_day = datetime.fromisoformat(reference["date"]).date()
    except (ValueError, KeyError, TypeError) as exc:
        raise ReviewError("Entry/reference session dates are required") from exc
    if (reference_day.weekday() != 0 or (entry_day - reference_day).days not in
            range(0, int(risk["reference_max_age_calendar_days"]) + 1)
            or entry_day.isocalendar()[:2] != reference_day.isocalendar()[:2]):
        raise ReviewError("A valid current-week Monday reference is required")
    close = _number(reference.get("close"), "Monday close", positive=True)
    band = _number(risk["monday_reference_ask_band_fraction"], "reference band")
    if abs(ask / close - 1) > band or abs(limit / close - 1) > band:
        raise ReviewError("Ask/price ceiling violates the Monday reference band")
    start = _time(proposal.get("entry_not_before"), "entry_not_before")
    cutoff = _time(proposal.get("entry_cutoff"), "entry_cutoff")
    if not start <= current < cutoff or valid_until > cutoff:
        raise ReviewError("Entry is outside its bounded validity window")
    if reviewed < start:
        raise ReviewError("Final review precedes the preclose review window")
    return {"decision": "PASS", "mode": "SHADOW", "reviewed": True,
            "boundary_verified": True, "proposal_digest": digest,
            "review_id": review["review_id"], "spec_hash": proposal["spec_hash"],
            "checked_at": current.isoformat(), "valid_until": valid_until.isoformat(),
            "capital_approval": False, "broker_writes": False,
            "scope": "SIGNED_REVIEW_AND_SUPPLIED_PACKET_POLICY_CHECKS_ONLY"}


def authorization_verifier(review, policy, reviewer_keys):
    """Trusted backend closure: recompute checks; do not trust a client PASS."""
    def verify(proposal, authorization, now):
        try:
            expected = review_proposal(proposal, review, policy, reviewer_keys=reviewer_keys, now=now)
            return all(authorization.get(k) == expected[k] for k in (
                "proposal_digest", "review_id", "spec_hash", "decision", "mode", "reviewed",
                "boundary_verified", "valid_until", "capital_approval", "broker_writes"))
        except (ReviewError, TypeError, KeyError):
            return False
    return verify
