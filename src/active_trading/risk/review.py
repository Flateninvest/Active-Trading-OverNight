"""Exact-proposal reviewer attestations and offline SHADOW/DEMO entry checks.

Reviewer keys are trusted service configuration, never part of an input packet.
HMAC authenticates an attestation's origin/integrity, not its financial truth.
Separate processes/credentials and authenticated data producers are deployment
requirements. A PASS allows recording an offline DEMO/SHADOW intent only.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import re
from zoneinfo import ZoneInfo

from active_trading.policy import PolicyError, capital_limits


class ReviewError(ValueError):
    """A supplied proposal cannot advance to offline intent recording."""


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


def _signed_number(value, label):
    if isinstance(value, bool):
        raise ReviewError(label + " must be finite numeric")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ReviewError(label + " must be finite numeric") from exc
    if not number.is_finite():
        raise ReviewError(label + " must be finite numeric")
    return number


def _technical_and_stress(proposal, policy, current):
    """Check supplied sourced TA/stress facts, not vendor-data authenticity."""
    technical = _mapping(proposal.get("technical_analysis"), "technical analysis")
    instrument = proposal.get("instrument_id")
    if instrument is not None and technical.get("instrument_id") != instrument:
        raise ReviewError("Technical analysis belongs to another instrument")
    _text(technical.get("source"), "technical analysis source")
    observed = _time(technical.get("observed_at"), "technical analysis observed_at")
    try:
        entry = datetime.fromisoformat(proposal["entry_session"]).date()
        session = datetime.fromisoformat(technical["as_of_session"]).date()
    except (ValueError, KeyError, TypeError) as exc:
        raise ReviewError("Completed TA session is required") from exc
    if observed > current or not session < entry or (entry - session).days > 4:
        raise ReviewError("Technical analysis must use recent completed sessions without future information")
    count = technical.get("completed_daily_bars")
    if isinstance(count, bool) or not isinstance(count, int) or count < policy["ta"]["minimum_completed_daily_bars"]:
        raise ReviewError("Insufficient completed daily bars for technical analysis")
    for field in ("sma20", "sma50", "atr14", "close", "support", "resistance"):
        _number(technical.get(field), field, positive=True)
    rsi = _number(technical.get("wilder_rsi14"), "Wilder RSI14")
    if rsi > 100 or _number(technical["support"], "support") > _number(technical["resistance"], "resistance"):
        raise ReviewError("Invalid RSI or support/resistance range")
    beta = _signed_number(technical.get("beta"), "beta")
    stress = _mapping(proposal.get("stress_sizing"), "stress sizing")
    if instrument is not None and stress.get("instrument_id") != instrument:
        raise ReviewError("Stress history belongs to another instrument")
    _text(stress.get("source"), "stress source")
    if _time(stress.get("observed_at"), "stress observed_at") > current or stress.get("complete") is not True:
        raise ReviewError("Complete nonfuture stress inputs are required")
    gaps = stress.get("overnight_gaps")
    gap_count = policy["risk"]["stress_gap_sessions"]
    if isinstance(gap_count, bool) or not isinstance(gap_count, int) or gap_count <= 0:
        raise ReviewError("Positive integer stress-gap sample policy required")
    if not isinstance(gaps, list) or len(gaps) != gap_count:
        raise ReviewError(f"Exactly the last {gap_count} completed overnight gaps are required")
    dates = []
    for gap in gaps:
        gap = _mapping(gap, "overnight gap")
        try:
            day = datetime.fromisoformat(gap["session"]).date()
        except (ValueError, KeyError, TypeError) as exc:
            raise ReviewError("Overnight gap session is required") from exc
        if day > session:
            raise ReviewError("Stress gap is later than the completed TA session")
        dates.append(day)
        _signed_number(gap.get("gap_fraction"), "overnight gap fraction")
    if dates != sorted(set(dates)) or dates[-1] != session:
        raise ReviewError("Stress gaps need 60 unique chronological sessions ending with the TA session")
    if proposal["sleeve"] == "EARNINGS_OVERNIGHT":
        releases = stress.get("earnings_releases")
        release_count = policy["risk"]["earnings_stress_confirmed_releases"]
        if isinstance(release_count, bool) or not isinstance(release_count, int) or release_count <= 0:
            raise ReviewError("Positive integer earnings sample policy required")
        if not isinstance(releases, list) or len(releases) != release_count:
            raise ReviewError("Last eight confirmed earnings release gaps are required")
        identifiers, times = set(), []
        for release in releases:
            release = _mapping(release, "earnings release")
            identifier = _text(release.get("release_id"), "earnings release id")
            release_time = _time(release.get("release_at"), "earnings release time")
            if (identifier in identifiers or release.get("issuer_confirmed") is not True
                    or release_time > current):
                raise ReviewError("Earnings stress history must be unique, confirmed and nonfuture")
            _text(release.get("source"), "earnings history source")
            _signed_number(release.get("overnight_gap_fraction"), "earnings gap fraction")
            identifiers.add(identifier)
            times.append(release_time)
        if times != sorted(set(times)):
            raise ReviewError("Earnings releases must be chronological with unique release timestamps")
    risk = policy["risk"]
    volatility_quote = _mapping(proposal.get("quote", {}), "volatility quote")
    volatility_price = volatility_quote.get("ask", technical["close"])
    return (beta >= _number(risk["enhanced_review_beta_threshold"], "enhanced beta threshold")
            or _number(technical["atr14"], "ATR14") / _number(volatility_price, "volatility review price", positive=True)
            >= _number(risk["enhanced_review_atr_fraction"], "enhanced ATR threshold"))


def _stress_loss(proposal):
    technical, stress = proposal["technical_analysis"], proposal["stress_sizing"]
    fraction = _stress_fraction(technical, stress, proposal["sleeve"])
    return (_number(proposal["quantity"], "quantity") * _number(proposal["entry_price_limit"], "entry limit")
            * fraction + _number(proposal["costs"]["estimated_total_usd"], "estimated round-trip costs"))


def _stress_fraction(technical, stress, sleeve):
    fraction = max(2 * _number(technical["atr14"], "ATR14") / _number(technical["close"], "close"),
                   max(abs(_signed_number(row["gap_fraction"], "overnight gap"))
                       for row in stress["overnight_gaps"]))
    if sleeve == "EARNINGS_OVERNIGHT":
        fraction = max(fraction, max(abs(_signed_number(row["overnight_gap_fraction"], "earnings gap"))
                                     for row in stress["earnings_releases"]))
    return fraction


def stress_loss_fraction(policy, technical, stress, entry_session, now, sleeve, *, instrument_id=None):
    """Public allocation helper; costs must be added to dollar stress loss."""
    proposal = {"technical_analysis": technical, "stress_sizing": stress,
                "entry_session": entry_session, "sleeve": sleeve, "instrument_id": instrument_id}
    _technical_and_stress(proposal, policy, _time(now, "now"))
    return _stress_fraction(technical, stress, sleeve)


def _check_risk_state(proposal, policy, current, limits):
    state = _mapping(proposal.get("strategy_risk_state"), "strategy risk state")
    _fresh(state, current, int(policy["risk"]["maximum_quote_age_seconds"]), "strategy risk state")
    if (state.get("schema") != "STRATEGY_RISK_STATE_v1" or state.get("complete") is not True
            or state.get("account_id") != proposal["account_id"]
            or state.get("strategy_id") != proposal["strategy_id"] or state.get("mode") != "DEMO"
            or _number(state.get("strategy_allocation_usd"), "risk-state allocation")
            != _number(policy["risk"]["strategy_allocation_usd"], "policy allocation")):
        raise ReviewError("Strategy risk state must match this demo account, strategy and allocation")
    if proposal.get("entry_session") is not None and state.get("night_id") != proposal["entry_session"]:
        raise ReviewError("Strategy risk state belongs to another entry night")
    equity = _number(state.get("equity_usd"), "strategy equity")
    hwm = _number(state.get("cash_flow_adjusted_high_water_mark_usd"), "high-water mark")
    baseline = _number(state.get("night_start_equity_usd"), "night starting equity")
    cash_flow = _signed_number(state.get("night_cash_flow_usd"), "night cash flow")
    if hwm < equity:
        raise ReviewError("Strategy high-water mark cannot be below current equity")
    if not isinstance(state.get("drawdown_pause_latched"), bool):
        raise ReviewError("Drawdown pause state is required")
    if not isinstance(state.get("night_loss_pause_latched"), bool):
        raise ReviewError("Night-loss pause state is required")
    if state["night_loss_pause_latched"] or max(Decimal(0), baseline + cash_flow - equity) >= limits["night_loss_limit"]:
        raise ReviewError("Single-night loss pauses new entries")
    if state["drawdown_pause_latched"] or hwm - equity >= limits["drawdown_limit"]:
        raise ReviewError("Drawdown pause requires controlled owner review before resuming")


def validate_strategy_risk_state(proposal, policy, now, *, limits=None):
    """Common entry gate on supplied risk state; not an authenticated producer."""
    if limits is None:
        try:
            limits = capital_limits(policy, proposal.get("nav_usd"))
        except PolicyError as exc:
            raise ReviewError(str(exc)) from exc
    _check_risk_state(proposal, policy, _time(now, "now"), limits)


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
    this offline function. DEMO validation never performs order writes.
    """
    proposal = _mapping(proposal, "proposal")
    review = _mapping(review, "review")
    policy = _mapping(policy, "policy")
    current = _time(now, "now")
    mode = proposal.get("mode")
    if (policy.get("default_mode") not in ("SHADOW", "DEMO")
            or policy.get("live_orders_enabled") is not False or mode not in ("SHADOW", "DEMO")):
        raise ReviewError("Only offline SHADOW and demo-account DEMO modes are supported")
    if mode == "DEMO" and policy.get("demo_orders_enabled") is not True:
        raise ReviewError("DEMO is not enabled in the owner policy")
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
    if (review.get("schema") != "DOUBLE_REVIEW_v1" or review.get("mode") != mode
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
    enhanced = proposal["high_beta_or_volatile"]
    if mode == "DEMO":
        enhanced = _technical_and_stress(proposal, policy, reviewed) or enhanced
    if enhanced:
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
    if mode == "DEMO" and costs.get("coverage") != "ROUND_TRIP":
        raise ReviewError("DEMO stress sizing requires an explicit round-trip cost estimate")
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
    if snapshot.get("account_id") != proposal["account_id"] or snapshot.get("mode") != mode:
        raise ReviewError("Account snapshot belongs to another account/mode")
    if mode == "DEMO" and snapshot.get("account_environment") != "DEMO":
        raise ReviewError("DEMO requires an explicitly identified demo account")
    if mode == "DEMO" and (snapshot.get("risk_score_account_environment") not in (None, "DEMO")
            or snapshot.get("risk_score_account_id", proposal["account_id"]) != proposal["account_id"]
            or "real_account_risk_score" in snapshot):
        raise ReviewError("Real or unrelated account risk score cannot govern DEMO")
    nav = _number(snapshot.get("nav_usd"), "NAV", positive=True)
    if _number(proposal.get("nav_usd"), "proposal NAV", positive=True) != nav:
        raise ReviewError("Proposal NAV differs from account snapshot")
    switches = _mapping(risk.get("account_risk_score_gate_by_mode"), "risk-score policy switches")
    if not isinstance(switches.get(mode), bool):
        raise ReviewError("An explicit account risk-score switch is required for this mode")
    if switches[mode]:
        score = _number(snapshot.get("broker_risk_score"), "broker risk score")
        if score > 10 or score >= _number(risk["pause_new_entries_at_score"], "risk pause"):
            raise ReviewError("Account risk score pauses new entries")
    try:
        limits = capital_limits(policy, nav)
    except PolicyError as exc:
        raise ReviewError(str(exc)) from exc
    if mode == "DEMO":
        _check_risk_state(proposal, policy, current, limits)
        if _time(proposal["strategy_risk_state"]["observed_at"], "risk-state timestamp") > reviewed:
            raise ReviewError("Reviewer predates the strategy risk state")
        if _stress_loss(proposal) > limits["position_risk_budget"]:
            raise ReviewError("Stress loss including costs exceeds the per-position overnight risk budget")
    exposures = snapshot.get("exposures")
    if not isinstance(exposures, list):
        raise ReviewError("Current plus pending strategy exposures are required")
    total = Decimal("0")
    instruments = {}
    name_cap = limits["name_cap"]
    for item in exposures:
        item = _mapping(item, "exposure")
        instrument = _text(item.get("instrument_id"), "exposure instrument")
        amount = _number(item.get("reserved_usd"), "exposure amount", positive=True)
        total += amount
        instruments[instrument] = instruments.get(instrument, Decimal("0")) + amount
    if any(amount > name_cap for amount in instruments.values()):
        raise ReviewError("Existing held/pending instrument exceeds the shared per-name capital cap")
    if proposal["instrument_id"] in instruments:
        raise ReviewError("Instrument already held or pending in either sleeve")
    if len(instruments) >= limits["maximum_positions"]:
        raise ReviewError("Combined position cap reached")
    if notional > name_cap:
        raise ReviewError("Entry exceeds the shared per-name capital cap")
    if total + notional > limits["gross_cap"]:
        raise ReviewError("Entry exceeds combined held/pending capital cap")
    if notional > _number(snapshot.get("available_cash_usd"), "available cash"):
        raise ReviewError("Entry is not fully cash funded")
    reference = _mapping(proposal.get("monday_reference"), "Monday reference")
    _text(reference.get("source"), "Monday reference source")
    if mode == "DEMO" and reference.get("official_close") is not True:
        raise ReviewError("DEMO requires the official Monday closing reference")
    try:
        entry_day = datetime.fromisoformat(proposal["entry_session"]).date()
        reference_day = datetime.fromisoformat(reference["date"]).date()
    except (ValueError, KeyError, TypeError) as exc:
        raise ReviewError("Entry/reference session dates are required") from exc
    names = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    if names[entry_day.weekday()] not in policy["schedule"]["entry_weekdays"]:
        raise ReviewError("Entry weekday is not permitted by the strategy policy")
    if current.astimezone(ZoneInfo(policy["schedule"]["exchange_timezone"])).date() != entry_day:
        raise ReviewError("Review timestamp differs from the entry session")
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
    return {"decision": "PASS", "mode": mode, "reviewed": True,
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
