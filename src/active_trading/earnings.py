"""Offline, deterministic earnings scheduling and DEMO/SHADOW allocation.

Consumes privately prepared factual JSON. This is not a PDF parser, calendar
service, TA calculator, issuer/source verifier, approval authority or broker.
Caller attestations are checked for consistency, never authenticated here.
All dollar allocations are proposals, not orders, fills or performance evidence.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
import re
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from active_trading.policy import capital_limits, load_policy, PolicyError
from active_trading.risk.review import (ReviewError, canonical_hash, stress_loss_fraction,
                                        validate_strategy_risk_state)


class EarningsPlanningError(ValueError):
    """Missing, contradictory or out-of-policy prepared input."""


NY = ZoneInfo("America/New_York")
PARIS = ZoneInfo("Europe/Paris")
CENT = Decimal("0.01")


def _mapping(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise EarningsPlanningError(f"{label}: expected an object")
    return value


def _array(value: Any, label: str) -> list:
    if not isinstance(value, list):
        raise EarningsPlanningError(f"{label}: expected an array")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EarningsPlanningError(f"{label}: nonempty text required")
    return value.strip()


def _true(value: Any, label: str) -> None:
    if type(value) is not bool or not value:
        raise EarningsPlanningError(f"{label}: explicit true factual verdict required")


def _boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise EarningsPlanningError(f"{label}: expected a boolean")
    return value


def _false(value: Any, label: str) -> None:
    if type(value) is not bool or value:
        raise EarningsPlanningError(f"{label}: explicit false factual verdict required")


def _number(value: Any, label: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or value is None or not isinstance(value, (int, float, str, Decimal)):
        raise EarningsPlanningError(f"{label}: finite nonnegative number required")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise EarningsPlanningError(f"{label}: invalid number") from exc
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise EarningsPlanningError(f"{label}: finite {'positive' if positive else 'nonnegative'} number required")
    return result


def _timestamp(value: Any, label: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(_text(value, label).replace("Z", "+00:00"))
        except ValueError as exc:
            raise EarningsPlanningError(f"{label}: invalid ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EarningsPlanningError(f"{label}: timezone-aware timestamp required")
    return parsed.astimezone(timezone.utc)


def _date(value: Any, label: str) -> date:
    try:
        return date.fromisoformat(_text(value, label))
    except ValueError as exc:
        raise EarningsPlanningError(f"{label}: ISO calendar date required") from exc


def _not_future(value: Any, label: str, latest: datetime) -> datetime:
    parsed = _timestamp(value, label)
    if parsed > latest:
        raise EarningsPlanningError(f"{label}: future evidence is unavailable")
    return parsed


def _ticker(value: Any) -> str:
    ticker = _text(value, "ticker").upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,11}", ticker):
        raise EarningsPlanningError("ticker: unsupported normalized stock symbol")
    return ticker


def _money(value: Decimal) -> str:
    return str(value.quantize(CENT, rounding=ROUND_DOWN))


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _sessions(values: Any) -> list[dict]:
    result = []
    for raw in _array(values, "sessions"):
        session = _mapping(raw, "session")
        if session.get("exchange_timezone") != "America/New_York":
            raise EarningsPlanningError("session: explicit America/New_York IANA timezone required")
        day = _date(session.get("session_date"), "session_date")
        opened = _timestamp(session.get("open_at"), "open_at")
        closed = _timestamp(session.get("close_at"), "close_at")
        if day.weekday() >= 5 or opened >= closed:
            raise EarningsPlanningError("session: invalid regular-session date or interval")
        if opened.astimezone(NY).date() != day or closed.astimezone(NY).date() != day:
            raise EarningsPlanningError("session: UTC timestamps conflict with the exchange date")
        if result and (day <= result[-1]["day"] or opened <= result[-1]["close"]):
            raise EarningsPlanningError("sessions: must be unique and chronological")
        result.append({"day": day, "open": opened, "close": closed})
    if len(result) < 2:
        raise EarningsPlanningError("sessions: at least entry and next opening are required")
    return result


def schedule_earnings_event(event: dict, sessions: list[dict], *, now: str | datetime, policy=None) -> dict:
    """Prepare one AMC/BMO hold from supplied, externally verified sessions.

    Future eligible entry days are allowed for preparation. Final readiness and
    allocation require build_shadow_plan and same-day final-review evidence.
    No inference from an earnings-call time or an unconfirmed calendar is made.
    """
    event = _mapping(event, "event")
    policy = load_policy() if policy is None else policy
    current = _timestamp(now, "now")
    calendar = _sessions(sessions)
    event_id = _text(event.get("event_id"), "event_id")
    ticker = _ticker(event.get("ticker"))
    sheet_day = _date(event.get("sheet_earnings_date"), "sheet_earnings_date")
    issuer_day = _date(event.get("issuer_earnings_date"), "issuer_earnings_date")
    sheet_window = event.get("sheet_release_window")
    window = event.get("issuer_release_window")
    if sheet_day != issuer_day or sheet_window != window:
        raise EarningsPlanningError("material sheet/issuer date or release-window conflict; updated frozen plan required")
    if window not in ("AMC", "BMO"):
        raise EarningsPlanningError("issuer release window: confirmed AMC or BMO required; call time is insufficient")
    _true(event.get("issuer_timing_confirmed"), "issuer_timing_confirmed")
    issuer_url = urlsplit(_text(event.get("issuer_source_url"), "issuer_source_url"))
    if issuer_url.scheme != "https" or not issuer_url.netloc or issuer_url.username or issuer_url.password:
        raise EarningsPlanningError("issuer_source_url: HTTPS issuer evidence URL required")
    verified = _not_future(event.get("issuer_verified_at"), "issuer_verified_at", current)
    if event.get("release_status") != "NOT_RELEASED":
        raise EarningsPlanningError("release_status: must be explicitly NOT_RELEASED")
    matching = next((i for i, row in enumerate(calendar) if row["day"] == issuer_day), None)
    if matching is None:
        raise EarningsPlanningError("issuer event date is absent from the verified session calendar")
    entry_index = matching if window == "AMC" else matching - 1
    exit_index = matching + 1 if window == "AMC" else matching
    if entry_index < 0 or exit_index >= len(calendar):
        raise EarningsPlanningError("calendar does not contain both event entry and following opening")
    entry, exit_session = calendar[entry_index], calendar[exit_index]
    if ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[entry["day"].weekday()] not in policy["schedule"]["entry_weekdays"]:
        raise EarningsPlanningError("entry weekday is outside the existing Tuesday-Thursday mandate")
    if exit_session["day"] != entry["day"] + timedelta(days=1):
        raise EarningsPlanningError("weekend/full-holiday bridge is prohibited")
    cutoff = entry["close"] - timedelta(minutes=policy["schedule"]["cutoff_minutes_before_regular_close"])
    if current >= cutoff:
        raise EarningsPlanningError("entry cutoff has passed; no retrospective entry")
    if verified >= exit_session["open"]:
        raise EarningsPlanningError("issuer verification occurred after the event hold window")
    release_at = event.get("issuer_release_at")
    if release_at is not None:
        release = _timestamp(release_at, "issuer_release_at")
        if not entry["close"] < release < exit_session["open"]:
            raise EarningsPlanningError("exact earnings release is outside close-to-next-open interval")
        if release <= current:
            raise EarningsPlanningError("earnings release has already occurred")
        if release.astimezone(NY).date() != issuer_day:
            raise EarningsPlanningError("exact release timestamp conflicts with issuer release date")
    return {
        "event_id": event_id, "ticker": ticker, "release_window": window,
        "earnings_date": issuer_day.isoformat(), "entry_session_date": entry["day"].isoformat(),
        "exit_session_date": exit_session["day"].isoformat(),
        "review_start_at": _iso(entry["close"] - timedelta(minutes=policy["schedule"]["review_minutes_before_regular_close"])),
        "entry_target_at": _iso(entry["close"] - timedelta(minutes=policy["schedule"]["entry_minutes_before_regular_close"])),
        "entry_cutoff_at": _iso(cutoff), "entry_close_at": _iso(entry["close"]),
        "exit_open_at": _iso(exit_session["open"]),
        "entry_target_paris": (entry["close"] - timedelta(minutes=policy["schedule"]["entry_minutes_before_regular_close"])).astimezone(PARIS).isoformat(),
        "exit_open_paris": exit_session["open"].astimezone(PARIS).isoformat(),
        "mode": "SHADOW", "broker_writes": False, "approval_required": True,
        "calendar_authenticated_by_helper": False,
    }


def _exposures(raw: Any, label: str, *, unique: bool = False) -> tuple[Decimal, set[str], Decimal]:
    total = Decimal(0)
    earnings_total = Decimal(0)
    tickers: set[str] = set()
    for value in _array(raw, label):
        row = _mapping(value, label)
        ticker = _ticker(row.get("ticker"))
        amount = _number(row.get("notional_usd"), f"{label}.notional_usd")
        sleeve = row.get("sleeve")
        if sleeve not in ("ORDINARY", "EARNINGS", "OTHER"):
            raise EarningsPlanningError(f"{label}: explicit ORDINARY/EARNINGS/OTHER sleeve classification required")
        if unique and sleeve != "ORDINARY":
            raise EarningsPlanningError("ordinary_proposals: only ORDINARY sleeve proposals belong in this field")
        if unique and ticker in tickers:
            raise EarningsPlanningError(f"{label}: duplicate ticker proposal")
        total += amount
        if sleeve == "EARNINGS":
            earnings_total += amount
        if amount > 0:
            tickers.add(ticker)
    return total, tickers, earnings_total


def _review_event(event: dict, schedule: dict, current: datetime, policy: dict) -> tuple[int, Decimal, bool]:
    weights = dict(policy["earnings"]["conviction_weights"], EXCLUDE=0)
    review = _mapping(event.get("review"), "review")
    reviewed_at = _not_future(review.get("reviewed_at"), "reviewed_at", current)
    start = _timestamp(schedule["review_start_at"], "review_start_at")
    cutoff = _timestamp(schedule["entry_cutoff_at"], "entry_cutoff_at")
    if not start <= reviewed_at <= current < cutoff:
        raise EarningsPlanningError("final review must be current, on the event entry day, inside close-minus-30 to cutoff")
    for field in ("issuer_window_rechecked", "ta_pass", "news_no_conflict", "risk_pass", "costs_known",
                  "underlying_cash_x1_eligible"):
        _true(review.get(field), "review." + field)
    rechecked = _not_future(review.get("issuer_rechecked_at"), "issuer_rechecked_at", reviewed_at)
    if rechecked < start:
        raise EarningsPlanningError("issuer release window was not rechecked during final review")
    bars = _number(review.get("completed_daily_bars"), "completed_daily_bars")
    if bars != bars.to_integral_value() or bars < policy["ta"]["minimum_completed_daily_bars"]:
        raise EarningsPlanningError("TA requires at least 60 completed daily bars")
    high_beta = _boolean(event.get("high_beta_review_required"), "high_beta_review_required")
    if high_beta:
        _true(review.get("enhanced_risk_review_pass"), "enhanced_risk_review_pass")
    conviction = event.get("conviction")
    risk_conviction = event.get("risk_review_conviction")
    if conviction not in policy["earnings"]["conviction_weights"] or not isinstance(risk_conviction, str) or risk_conviction not in weights:
        raise EarningsPlanningError("explicit categorical conviction and independent risk conviction required")
    if weights[risk_conviction] > weights[conviction]:
        raise EarningsPlanningError("risk review may lower conviction or exclude, never raise it")
    if risk_conviction == "EXCLUDE":
        raise EarningsPlanningError("independent risk review excluded this event")
    quote_at = _not_future(review.get("quote_at"), "quote_at", reviewed_at)
    if review.get("quote_type") != "REALTIME":
        raise EarningsPlanningError("quote_type: explicit REALTIME quote required")
    if (current - quote_at).total_seconds() > policy["risk"]["maximum_quote_age_seconds"]:
        raise EarningsPlanningError("quote is older than 60 seconds at proposal time")
    bid = _number(review.get("bid"), "bid", positive=True)
    ask = _number(review.get("ask"), "ask", positive=True)
    if ask < bid:
        raise EarningsPlanningError("crossed quote")
    if (ask - bid) / ((ask + bid) / 2) * 10000 > Decimal(str(policy["risk"]["maximum_spread_bps"])):
        raise EarningsPlanningError("spread exceeds 20 basis points")
    entry_day = _date(schedule["entry_session_date"], "entry_session_date")
    monday_day = _date(review.get("monday_reference_date"), "monday_reference_date")
    expected_monday = entry_day - timedelta(days=entry_day.weekday())
    if monday_day != expected_monday or not 0 <= (entry_day - monday_day).days <= policy["risk"]["reference_max_age_calendar_days"]:
        raise EarningsPlanningError("current-week Monday reference within four calendar days is required")
    monday_verified = _not_future(review.get("monday_reference_verified_at"), "monday_reference_verified_at", reviewed_at)
    monday_closed = _not_future(review.get("monday_reference_close_at"), "monday_reference_close_at", monday_verified)
    if monday_closed.astimezone(NY).date() != monday_day:
        raise EarningsPlanningError("Monday close timestamp conflicts with its reference date")
    monday = _number(review.get("monday_reference_close"), "monday_reference_close", positive=True)
    if abs(ask / monday - 1) > Decimal(str(policy["risk"]["monday_reference_ask_band_fraction"])):
        raise EarningsPlanningError("ask is outside the existing +/-2% Monday-reference band")
    fractional = _boolean(review.get("fractional_units_supported"), "fractional_units_supported")
    return weights[risk_conviction], ask, fractional


def build_shadow_plan(packet: dict, *, policy=None) -> dict:
    """Validate final facts and create cost-reserved conviction-weighted proposals.

    The $2,000 sleeve ceiling and 40% sleeve/name cap are proposed earnings
    policy, not statistically optimal settings. Allocation-based name/gross
    gross and three-position caps still govern the combined book. Weights are
    categorical ranks, never calibrated profit probabilities. The final pool is
    reduced to current capacity before weights and name caps. Its frozen ceiling,
    NAV cap and original weight denominator prevent redistribution after removal.
    """
    packet = _mapping(packet, "packet")
    policy = load_policy() if policy is None else policy
    mode = packet.get("mode", policy["default_mode"])
    if mode not in ("SHADOW", "DEMO"):
        raise EarningsPlanningError("only SHADOW or DEMO planning is supported; LIVE is rejected")
    if policy.get("live_orders_enabled") is not False or (mode == "DEMO" and policy.get("demo_orders_enabled") is not True):
        raise EarningsPlanningError("DEMO-only owner policy is required; LIVE is rejected")
    weights = dict(policy["earnings"]["conviction_weights"], EXCLUDE=0)
    earnings_name_fraction = Decimal(str(policy["earnings"]["maximum_fraction_of_earnings_ceiling_per_name"]))
    current = _timestamp(packet.get("as_of"), "as_of")
    _true(packet.get("calendar_complete_and_verified"), "calendar_complete_and_verified")
    _sessions(packet.get("sessions"))
    budget = min(_number(packet.get("earnings_budget_usd", policy["earnings"]["illustrative_budget_usd"]), "earnings_budget_usd"), Decimal(str(policy["earnings"]["illustrative_budget_usd"])))
    review_register = _mapping(packet.get("combined_review"), "combined_review")
    _true(review_register.get("daily_candidates_frozen"), "daily_candidates_frozen")
    _true(review_register.get("earnings_register_frozen"), "earnings_register_frozen")
    entry_day = _date(review_register.get("session_date"), "combined_review.session_date")
    freeze = _not_future(review_register.get("morning_freeze_at"), "morning_freeze_at", current)
    freeze_local = freeze.astimezone(PARIS)
    freeze_clock = time.fromisoformat(policy["selection"]["freeze_time"])
    if freeze_local.date() != entry_day or freeze_local.time().replace(tzinfo=None) != freeze_clock:
        raise EarningsPlanningError("morning_freeze_at must identify " + policy["selection"]["freeze_time"] + " Europe/Paris on the entry session date")
    ordinary = [_ticker(t) for t in _array(review_register.get("ordinary_reviewed_tickers"), "ordinary_reviewed_tickers")]
    registered_ids = [_text(v, "earnings_reviewed_event_id") for v in _array(review_register.get("earnings_reviewed_event_ids"), "earnings_reviewed_event_ids")]
    if len(set(ordinary)) != len(ordinary) or len(set(registered_ids)) != len(registered_ids):
        raise EarningsPlanningError("combined review register contains duplicate priorities")
    if len(ordinary) + len(registered_ids) > policy["selection"]["max_review_priorities"]:
        raise EarningsPlanningError("at most three ordinary and earnings priorities may be reviewed together")
    frozen = _mapping(packet.get("frozen_allocation"), "frozen_allocation")
    if _not_future(frozen.get("frozen_at"), "frozen_allocation.frozen_at", current) != freeze:
        raise EarningsPlanningError("allocation identities must be frozen at the same morning freeze")
    frozen_pool = _number(frozen.get("pool_ceiling_usd"), "frozen_allocation.pool_ceiling_usd")
    frozen_equity = _number(frozen.get("equity_usd"), "frozen_allocation.equity_usd", positive=True)
    try:
        frozen_limits = capital_limits(policy, frozen_equity)
    except PolicyError as exc:
        raise EarningsPlanningError(str(exc)) from exc
    frozen_budget = _number(frozen.get("earnings_budget_ceiling_usd"), "frozen_allocation.earnings_budget_ceiling_usd")
    if frozen_budget != budget:
        raise EarningsPlanningError("earnings budget differs from its frozen ceiling; a new reviewed plan is required")
    if frozen_pool > budget:
        raise EarningsPlanningError("frozen allocation pool exceeds the earnings budget ceiling")
    if frozen_pool > frozen_limits["gross_cap"]:
        raise EarningsPlanningError("frozen allocation pool exceeds the frozen NAV gross cap")
    frozen_convictions = _mapping(frozen.get("convictions"), "frozen_allocation.convictions")
    if set(frozen_convictions) != set(registered_ids) or any(value not in ("HIGH", "STANDARD", "CAUTIOUS") for value in frozen_convictions.values()):
        raise EarningsPlanningError("frozen convictions must exactly cover every registered earnings priority")
    frozen_weight_total = sum(weights[value] for value in frozen_convictions.values())
    original_stake_ceilings = {
        event_id: min(frozen_pool * weights[value] / frozen_weight_total,
                      frozen_limits["name_cap"], frozen_budget * earnings_name_fraction)
        for event_id, value in frozen_convictions.items()
    }
    previous_ceilings = packet.get("prior_proposed_ceiling_usd_by_event_id")
    if previous_ceilings is not None:
        previous_ceilings = _mapping(previous_ceilings, "prior_proposed_ceiling_usd_by_event_id")
        if set(previous_ceilings) != set(registered_ids):
            raise EarningsPlanningError("prior proposal ceilings must exactly cover the frozen event register")
        previous_ceilings = {event_id: _number(value, "prior proposal ceiling") for event_id, value in previous_ceilings.items()}
        if any(amount > original_stake_ceilings[event_id] for event_id, amount in previous_ceilings.items()):
            raise EarningsPlanningError("prior proposal ceiling exceeds its original frozen stake ceiling")
    sources = {}
    for raw in _array(packet.get("source_receipts"), "source_receipts"):
        row = _mapping(raw, "source receipt")
        digest = _text(row.get("source_sha256"), "source_sha256")
        if not re.fullmatch(r"[a-f0-9]{64}", digest) or digest in sources:
            raise EarningsPlanningError("source_sha256: unique lowercase SHA-256 identity required")
        received = _not_future(row.get("received_at"), "source.received_at", freeze)
        published = _not_future(row.get("published_at"), "source.published_at", received)
        sources[digest] = {"published_at": _iso(published), "received_at": _iso(received)}
    account = _mapping(packet.get("account"), "account")
    _true(account.get("costs_complete"), "account.costs_complete")
    _true(account.get("state_reconciled"), "account.state_reconciled")
    _true(account.get("exposure_complete"), "account.exposure_complete")
    _false(account.get("unresolved_orders_or_exits"), "account.unresolved_orders_or_exits")
    snapshot_at = _not_future(account.get("snapshot_at"), "account.snapshot_at", current)
    if (current - snapshot_at).total_seconds() > 60:
        raise EarningsPlanningError("account snapshot is older than 60 seconds")
    equity = _number(account.get("equity_usd"), "equity_usd", positive=True)
    try:
        limits = capital_limits(policy, equity)
    except PolicyError as exc:
        raise EarningsPlanningError(str(exc)) from exc
    if mode == "DEMO":
        if account.get("mode") != "DEMO" or account.get("account_environment") != "DEMO":
            raise EarningsPlanningError("DEMO planning requires a scoped DEMO account snapshot")
        if packet.get("spec_hash") != canonical_hash(policy):
            raise EarningsPlanningError("DEMO packet must bind the effective policy hash")
        try:
            validate_strategy_risk_state({"account_id": _text(account.get("account_id"), "account_id"),
                "strategy_id": policy["strategy_id"], "nav_usd": equity,
                "entry_session": entry_day.isoformat(),
                "strategy_risk_state": packet.get("strategy_risk_state")}, policy, current, limits=limits)
        except ReviewError as exc:
            raise EarningsPlanningError(str(exc)) from exc
    buying_power = _number(account.get("uncommitted_buying_power_usd"), "uncommitted_buying_power_usd")
    cash_reserve = _number(account.get("cash_reserve_usd"), "cash_reserve_usd")
    costs = _number(account.get("cost_reserve_usd"), "cost_reserve_usd")
    score_gate = policy["risk"]["account_risk_score_gate_by_mode"][mode]
    if (account.get("risk_score_account_environment") not in (None, mode)
            or "real_account_risk_score" in account or (mode == "DEMO" and
            account.get("risk_score_account_id", account.get("account_id")) != account.get("account_id"))):
        raise EarningsPlanningError("Real-account risk scores cannot govern this strategy")
    score = _number(account.get("account_risk_score"), "account_risk_score") if score_gate else None
    if score_gate and score > 10:
        raise EarningsPlanningError("account_risk_score: expected eToro score from 0 to 10")
    holdings, held_names, earnings_held = _exposures(account.get("holdings"), "holdings")
    pending, pending_names, earnings_pending = _exposures(account.get("pending_entries"), "pending_entries")
    ordinary_amount, ordinary_names, _ = _exposures(account.get("ordinary_proposals"), "ordinary_proposals", unique=True)
    name_exposures = {}
    for row in account["holdings"] + account["pending_entries"]:
        ticker = _ticker(row.get("ticker"))
        name_exposures[ticker] = name_exposures.get(ticker, Decimal(0)) + _number(row["notional_usd"], "exposure")
    if any(amount > limits["name_cap"] for amount in name_exposures.values()):
        raise EarningsPlanningError("existing held/pending instrument exceeds the allocation-based name cap")
    if any(_number(row["notional_usd"], "ordinary_proposals.notional_usd") > limits["name_cap"]
           for row in account["ordinary_proposals"]):
        raise EarningsPlanningError("ordinary proposal exceeds the allocation-based name cap")
    if not ordinary_names.issubset(set(ordinary)):
        raise EarningsPlanningError("ordinary proposals must be in the combined frozen review register")
    if ordinary_names & (held_names | pending_names):
        raise EarningsPlanningError("ordinary proposal duplicates an existing holding or pending entry")
    events = []
    ids: set[str] = set()
    names: set[str] = set()
    for raw in _array(packet.get("events"), "events"):
        event = _mapping(raw, "event")
        event_id = _text(event.get("event_id"), "event_id")
        ticker = _ticker(event.get("ticker"))
        if event_id in ids or ticker in names:
            raise EarningsPlanningError("duplicate earnings event or ticker; combine evidence without a second purchase")
        ids.add(event_id)
        names.add(ticker)
        events.append(dict(event, event_id=event_id, ticker=ticker))
    if ids != set(registered_ids):
        raise EarningsPlanningError("events must exactly match the frozen earnings review priorities")
    if any(event.get("conviction") != frozen_convictions[event["event_id"]] for event in events):
        raise EarningsPlanningError("event conviction differs from its frozen conviction; a new reviewed plan is required")
    occupied_names = held_names | pending_names | ordinary_names
    remaining_slots = max(0, limits["maximum_positions"] - len(occupied_names))
    gross_before = holdings + pending + ordinary_amount
    shared_capacity = max(Decimal(0), min(limits["gross_cap"] - gross_before - costs,
                                           buying_power - cash_reserve - costs))
    earnings_used = earnings_held + earnings_pending
    remaining_earnings_budget = max(Decimal(0), budget - earnings_used)
    allocation_pool = min(remaining_earnings_budget, frozen_pool, shared_capacity)
    blocked = []
    eligible = []
    for event in events:
        event_id, ticker = event["event_id"], _ticker(event["ticker"])
        try:
            if score_gate and score >= Decimal(str(policy["risk"]["pause_new_entries_at_score"])):
                raise EarningsPlanningError("governing account risk score is at least 5; pause new entries")
            if ticker in occupied_names:
                raise EarningsPlanningError("ticker already held, pending or proposed in the combined book; no second purchase")
            if event.get("source_sha256") not in sources:
                raise EarningsPlanningError("event source identity lacks a pre-freeze receipt")
            schedule = schedule_earnings_event(event, packet["sessions"], now=current, policy=policy)
            if schedule["entry_session_date"] != entry_day.isoformat():
                raise EarningsPlanningError("event does not belong to the current frozen entry session")
            weight, ask, fractional = _review_event(event, schedule, current, policy)
            stress_fraction, event_cost = None, Decimal(0)
            if mode == "DEMO":
                try:
                    technical = _mapping(event.get("technical_analysis"), "technical analysis")
                    stress_fraction = stress_loss_fraction(policy, technical, event.get("stress_sizing"),
                        schedule["entry_session_date"], event["review"]["reviewed_at"], "EARNINGS_OVERNIGHT",
                        instrument_id=_text(event.get("instrument_id"), "event instrument_id"))
                    enhanced = (Decimal(str(technical["beta"])) >= Decimal(str(policy["risk"]["enhanced_review_beta_threshold"]))
                                or Decimal(str(technical["atr14"])) / ask >= Decimal(str(policy["risk"]["enhanced_review_atr_fraction"])))
                    if enhanced:
                        _true(event["review"].get("enhanced_risk_review_pass"), "enhanced_risk_review_pass")
                    event_costs = _mapping(event.get("costs"), "event costs")
                    if (event_costs.get("status") != "KNOWN" or event_costs.get("coverage") != "ROUND_TRIP"
                            or event_costs.get("per_instrument") is not True):
                        raise EarningsPlanningError("known per-instrument ROUND_TRIP cost estimate required")
                    _text(event_costs.get("source"), "cost source")
                    if not re.fullmatch(r"[0-9a-f]{64}", event_costs.get("model_hash", "")):
                        raise EarningsPlanningError("frozen cost model hash required")
                    if event_costs.get("instrument_id") != _text(event.get("instrument_id"), "event instrument_id"):
                        raise EarningsPlanningError("costs belong to another instrument")
                    event_cost = _number(event_costs.get("estimated_total_usd"), "event round-trip costs")
                except ReviewError as exc:
                    raise EarningsPlanningError(str(exc)) from exc
            eligible.append({"event": event, "schedule": schedule, "weight": weight,
                             "ask": ask, "fractional": fractional, "stress_fraction": stress_fraction,
                             "event_cost": event_cost})
        except EarningsPlanningError as exc:
            blocked.append({"event_id": event_id, "ticker": ticker, "reason": str(exc)})
    eligible.sort(key=lambda row: (-row["weight"], row["event"]["event_id"]))
    selected = eligible[:remaining_slots]
    for row in eligible[remaining_slots:]:
        blocked.append({"event_id": row["event"]["event_id"], "ticker": row["event"]["ticker"],
                        "reason": "no remaining combined-book position slot"})
    # Rejected and excluded events keep their original shares in this denominator.
    # Removing a failed event must never increase the surviving event's allocation.
    total_weight = frozen_weight_total
    name_cap = min(limits["name_cap"], frozen_limits["name_cap"], budget * earnings_name_fraction)
    for row in selected:
        row["weighted_amount"] = allocation_pool * row["weight"] / total_weight
        row["name_clipped_amount"] = min(row["weighted_amount"], name_cap)
        if previous_ceilings is not None and mode == "SHADOW":
            row["name_clipped_amount"] = min(row["name_clipped_amount"], previous_ceilings[row["event"]["event_id"]])
    proposals = []
    for row in selected:
        amount = row["name_clipped_amount"].quantize(CENT, rounding=ROUND_DOWN)
        if mode == "DEMO":
            amount = min(max(Decimal(0), amount - row["event_cost"]),
                         max(Decimal(0), limits["position_risk_budget"] - row["event_cost"]) / row["stress_fraction"])
            if previous_ceilings is not None:
                amount = min(amount, previous_ceilings[row["event"]["event_id"]])
            amount = amount.quantize(CENT, rounding=ROUND_DOWN)
        if amount <= 0:
            blocked.append({"event_id": row["event"]["event_id"], "ticker": row["event"]["ticker"],
                            "reason": "zero available allocation after shared caps, cash and cost reservations"})
            continue
        proposal = dict(row["schedule"])
        proposal.update({"proposal_status": mode + "_REVIEWED_FACTS_NOT_APPROVED", "mode": mode,
                         "product": "UNDERLYING_CASH_X1_LONG_ONLY", "leverage": 1,
                         "options": False, "cfds": False, "shorts": False,
                         "source_sha256": row["event"]["source_sha256"],
                         "conviction": row["event"]["conviction"],
                         "risk_review_conviction": row["event"]["risk_review_conviction"],
                         "categorical_weight": row["weight"],
                         "frozen_weight_denominator": total_weight,
                         "stake_ceiling_usd": _money(original_stake_ceilings[row["event"]["event_id"]]),
                         "unclipped_weighted_usd": _money(row["weighted_amount"]),
                         "name_clipped_usd": _money(row["name_clipped_amount"]),
                         "proposed_notional_usd": _money(amount),
                         "units_provisional": True})
        if mode == "DEMO":
            proposal.update(instrument_id=row["event"]["instrument_id"],
                            reserved_round_trip_costs_usd=str(row["event_cost"]),
                            stress_loss_fraction=str(row["stress_fraction"]),
                            stress_loss_usd=str(amount * row["stress_fraction"] + row["event_cost"]))
        if row["fractional"]:
            proposal["indicative_fractional_units_at_ask"] = str((amount / row["ask"]).quantize(Decimal("0.000001"), rounding=ROUND_DOWN))
        proposals.append(proposal)
    allocated = sum((Decimal(row["proposed_notional_usd"]) for row in proposals), Decimal(0))
    event_costs_reserved = sum((Decimal(row.get("reserved_round_trip_costs_usd", "0")) for row in proposals), Decimal(0))
    flattened = any(a["categorical_weight"] != b["categorical_weight"] and
                    a["proposed_notional_usd"] == b["proposed_notional_usd"]
                    for i, a in enumerate(proposals) for b in proposals[i + 1:])
    return {
        "status": mode + "_PROPOSALS_ONLY", "mode": mode, "as_of": _iso(current),
        "broker_writes": False, "approval_required": True, "execution_approved": False,
        "authenticated_source_or_review": False, "profitability_evidence": False,
        "loss_drawdown_mandate_verified": False,
        "earnings_budget_ceiling_usd": _money(budget), "earnings_allocation_usd": _money(allocated),
        "earnings_used_and_reserved_usd": _money(earnings_used),
        "remaining_earnings_budget_usd": _money(remaining_earnings_budget),
        "allocation_pool_usd": _money(allocation_pool), "frozen_pool_ceiling_usd": _money(frozen_pool),
        "unallocated_earnings_budget_usd": _money(remaining_earnings_budget - allocated - event_costs_reserved),
        "whole_book_gross_before_usd": _money(gross_before),
        "reserved_costs_usd": _money(costs + event_costs_reserved), "remaining_shared_capacity_usd": _money(shared_capacity),
        "earnings_reserved_costs_usd": str(event_costs_reserved),
        "combined_gross_with_proposals_and_reserved_costs_usd": _money(gross_before + allocated + costs + event_costs_reserved),
        "whole_book_gross_limit_usd": _money(limits["gross_cap"]),
        "capital_basis_usd": _money(limits["basis"]), "requires_common_entry_review": True,
        "caps_flatten_conviction_ordering": flattened,
        "cap_explanation": ("Different conviction ranks have equal dollars because name/shared caps bind; clipped dollars stay cash."
                            if flattened else "Caps can reduce conviction-weighted dollars; clipped dollars stay cash and are never redistributed."),
        "proposals": proposals, "blocked_events": blocked,
        "refresh_ceiling_usd_by_event_id": {
            event_id: next((row["proposed_notional_usd"] for row in proposals if row["event_id"] == event_id), "0.00")
            for event_id in registered_ids
        },
        "limitations": [
            "Prepared source/calendar/TA/risk facts are caller attestations, not authenticated by this helper.",
            "This helper does not read PDFs, calculate TA, fetch quotes, verify issuer websites or execute orders.",
            "Uncommitted buying power must already exclude pending entries and ordinary proposals; costs are reserved once here.",
            "Dollar amounts and any units are provisional; broker fractional-unit and settlement eligibility remain separate prerequisites.",
            "The requested $2,000 ceiling, 3/2/1 conviction weights and 40% sleeve cap are proposed policy, not optimal parameters.",
            "Frozen pool must be the actual feasible policy-time pool after all shared reservations; this factual attestation is not authenticated here.",
            "On every refresh, caller must preserve and pass refresh_ceiling_usd_by_event_id as prior_proposed_ceiling_usd_by_event_id; no durable runtime state is enforced here.",
            "Risk PASS and this prepared plan are not human/platform/broker approval; source authenticity and mandate approval are outside this helper.",
        ],
    }


def synthetic_demo_packet() -> dict:
    """Invented inputs for software checks. These are not securities or prices."""
    digest = "a" * 64
    packet = {
        "fixture_kind": "SYNTHETIC_OPERATIONAL_FIXTURE", "mode": "SHADOW",
        "as_of": "2026-10-07T19:55:00Z", "earnings_budget_usd": "2000",
        "calendar_complete_and_verified": True,
        "sessions": [
            {"session_date": day, "exchange_timezone": "America/New_York",
             "open_at": day + "T13:30:00Z", "close_at": day + "T20:00:00Z"}
            for day in ("2026-10-06", "2026-10-07", "2026-10-08")],
        "source_receipts": [{"source_sha256": digest, "published_at": "2026-10-05T06:00:00Z",
                             "received_at": "2026-10-05T06:05:00Z"}],
        "combined_review": {"session_date": "2026-10-07", "morning_freeze_at": "2026-10-07T07:00:00Z",
                            "ordinary_reviewed_tickers": [], "earnings_reviewed_event_ids": ["SYNTH_A", "SYNTH_B", "SYNTH_C"],
                            "daily_candidates_frozen": True, "earnings_register_frozen": True},
        "frozen_allocation": {"frozen_at": "2026-10-07T07:00:00Z", "pool_ceiling_usd": "1490", "equity_usd": "5000",
                              "earnings_budget_ceiling_usd": "2000",
                              "convictions": {"SYNTH_A": "HIGH", "SYNTH_B": "STANDARD", "SYNTH_C": "CAUTIOUS"}},
        "account": {"equity_usd": "5000", "uncommitted_buying_power_usd": "5000",
                    "cash_reserve_usd": "100", "cost_reserve_usd": "10", "costs_complete": True,
                    "state_reconciled": True, "exposure_complete": True, "unresolved_orders_or_exits": False,
                    "snapshot_at": "2026-10-07T19:55:00Z",
                    "account_risk_score": 3, "holdings": [], "pending_entries": [], "ordinary_proposals": []},
        "events": [],
    }
    for letter, conviction in zip("ABC", ("HIGH", "STANDARD", "CAUTIOUS")):
        packet["events"].append({
            "event_id": "SYNTH_" + letter, "ticker": "SYNTH" + letter,
            "source_sha256": digest, "sheet_earnings_date": "2026-10-07", "sheet_release_window": "AMC",
            "issuer_earnings_date": "2026-10-07", "issuer_release_window": "AMC",
            "issuer_timing_confirmed": True, "issuer_source_url": "https://issuer.example/earnings",
            "issuer_verified_at": "2026-10-07T19:50:00Z", "release_status": "NOT_RELEASED",
            "conviction": conviction, "risk_review_conviction": conviction, "high_beta_review_required": False,
            "review": {"reviewed_at": "2026-10-07T19:55:00Z", "issuer_rechecked_at": "2026-10-07T19:54:00Z",
                       "issuer_window_rechecked": True, "ta_pass": True, "completed_daily_bars": 120,
                       "news_no_conflict": True, "risk_pass": True, "costs_known": True,
                       "underlying_cash_x1_eligible": True, "quote_type": "REALTIME",
                       "quote_at": "2026-10-07T19:54:50Z", "bid": "99.90", "ask": "100",
                       "monday_reference_date": "2026-10-05", "monday_reference_close": "100",
                       "monday_reference_close_at": "2026-10-05T20:00:00Z",
                       "monday_reference_verified_at": "2026-10-06T06:00:00Z",
                       "fractional_units_supported": True, "enhanced_risk_review_pass": True},
        })
    return packet
