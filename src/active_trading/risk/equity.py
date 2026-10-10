"""Offline bid-marked DEMO strategy equity and cash-flow-adjusted pause state.

The service supplying scoped cash, positions, flows, calendar and prior state must be
authenticated and persist the result outside Git. This pure helper cannot prove
those facts or stop an operator discarding its history. Calendar chronology
checks do not authenticate the actual exchange calendar.
"""
from datetime import date, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from active_trading.policy import PolicyError, capital_limits
from .review import ReviewError, _fresh, _mapping, _number, _signed_number, _text, _time


def build_strategy_risk_state(policy, packet, now, *, prior_state=None, owner_review_verifier=None):
    """Mark owned strategy positions at bid; latch drawdown until verified review.

    ``cash_flow_usd`` is the signed net strategy deposit/withdrawal since the
    previous observation (since strategy inception for the first observation).
    Cash must exclude all non-strategy trade cash movements, including overrides.
    Owner review is an opaque receipt verified by caller-controlled code, never a
    boolean supplied by an analyst. This function performs no broker writes.
    """
    packet = _mapping(packet, "equity packet")
    current = _time(now, "now")
    age = int(policy["risk"]["maximum_quote_age_seconds"])
    observed = _fresh(packet, current, age, "equity packet")
    if (packet.get("mode") != "DEMO" or packet.get("account_environment") != "DEMO"
            or packet.get("strategy_id") != policy["strategy_id"] or packet.get("complete") is not True
            or packet.get("cash_excludes_non_strategy_trades") is not True):
        raise ReviewError("Complete, segregated DEMO strategy cash/positions are required")
    account = _text(packet.get("account_id"), "equity account")
    night = _text(packet.get("night_id"), "night id")
    session = _mapping(packet.get("night_session"), "calendar-bound night session")
    try:
        night_day = date.fromisoformat(night)
    except ValueError as exc:
        raise ReviewError("Night id must be an exchange session date") from exc
    exchange_zone = ZoneInfo(policy["schedule"]["exchange_timezone"])
    opened = _time(session.get("open_at"), "night session open")
    close = _time(session.get("close_at"), "night session close")
    if (opened.astimezone(exchange_zone).date() != night_day
            or opened.astimezone(exchange_zone).time() != time(9, 30)
            or close.astimezone(exchange_zone).date() != night_day or close <= opened):
        raise ReviewError("Night calendar requires a 09:30 exchange opening and a later same-session close")
    calendar_context = dict(session, session_date=night, open_at=opened.isoformat(), close_at=close.isoformat())
    if (session.get("session_date") != night or night_day.weekday() > 4
            or observed < close - timedelta(minutes=policy["schedule"]["review_minutes_before_regular_close"])):
        raise ReviewError("Night state must begin at the calendar session's preclose review boundary")
    try:
        limits = capital_limits(policy, packet.get("account_balance_usd"))
    except PolicyError as exc:
        raise ReviewError(str(exc)) from exc
    allocation = _number(policy["risk"]["strategy_allocation_usd"], "strategy allocation", positive=True)
    equity = _number(packet.get("cash_usd"), "strategy cash")
    flow = _signed_number(packet.get("cash_flow_usd"), "strategy cash flow")
    positions = packet.get("positions")
    if not isinstance(positions, list):
        raise ReviewError("Complete owned position list is required")
    seen, excluded = set(), []
    for row in positions:
        row = _mapping(row, "equity position")
        position = _text(row.get("position_id"), "position id")
        if position in seen or row.get("account_id") != account or row.get("mode") != "DEMO":
            raise ReviewError("Position identity must be unique and belong to this demo account")
        seen.add(position)
        if row.get("strategy_included") is False:
            _text(row.get("exclusion_reason"), "non-strategy exclusion reason")
            excluded.append(position)
            continue
        if row.get("strategy_included") is not True or row.get("strategy_id") != policy["strategy_id"]:
            raise ReviewError("Included position must be explicitly strategy owned")
        _fresh(row, observed, age, "position bid")
        equity += _number(row.get("quantity"), "owned quantity", positive=True) * _number(
            row.get("bid"), "position bid", positive=True)
    prior_hwm, prior_equity = allocation, allocation
    prior_latch, night_latch = False, False
    night_start, night_flow = allocation, flow
    if prior_state is not None:
        prior = _mapping(prior_state, "prior strategy state")
        if (prior.get("schema") != "STRATEGY_RISK_STATE_v1" or prior.get("mode") != "DEMO"
                or prior.get("account_id") != account or prior.get("strategy_id") != policy["strategy_id"]
                or _number(prior.get("strategy_allocation_usd"), "prior allocation") != allocation
                or _time(prior.get("observed_at"), "prior observed_at") >= observed):
            raise ReviewError("Prior risk state must match this strategy/account and precede this observation")
        prior_equity = _number(prior.get("equity_usd"), "prior strategy equity")
        prior_hwm = _number(prior.get("cash_flow_adjusted_high_water_mark_usd"), "prior high-water mark")
        if prior_hwm < prior_equity or not isinstance(prior.get("drawdown_pause_latched"), bool):
            raise ReviewError("Invalid prior high-water mark or drawdown pause")
        prior_latch = prior["drawdown_pause_latched"]
        if prior.get("night_id") != night:
            try:
                previous_night = date.fromisoformat(prior["night_id"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ReviewError("Prior night must be an exchange session date") from exc
            if (night_day <= previous_night
                    or observed.astimezone(ZoneInfo(policy["schedule"]["exchange_timezone"])).date() != night_day):
                raise ReviewError("Night-loss pause can reset only at a later calendar session's review boundary")
        night_start = prior_equity
        if prior.get("night_id") == night:
            if prior.get("night_session") != calendar_context:
                raise ReviewError("The same night's calendar context cannot change across observations")
            night_start = _number(prior.get("night_start_equity_usd"), "night starting equity")
            night_flow += _signed_number(prior.get("night_cash_flow_usd"), "prior night cash flow")
            if not isinstance(prior.get("night_loss_pause_latched"), bool):
                raise ReviewError("Prior night-loss pause state is required")
            night_latch = prior["night_loss_pause_latched"]
    hwm = max(equity, prior_hwm + flow)
    drawdown = hwm - equity
    night_loss = max(Decimal(0), night_start + night_flow - equity)
    drawdown_latch = prior_latch or drawdown >= limits["drawdown_limit"]
    resumed = False
    if prior_latch and packet.get("owner_review_receipt") is not None:
        if drawdown >= limits["drawdown_limit"]:
            raise ReviewError("Cannot resume while the drawdown limit is still breached")
        if not callable(owner_review_verifier) or owner_review_verifier(
                packet["owner_review_receipt"], prior_state, current) is not True:
            raise ReviewError("Drawdown resumption needs externally verified owner review")
        drawdown_latch, resumed = False, True
    night_latch = night_latch or night_loss >= limits["night_loss_limit"]
    return {"schema": "STRATEGY_RISK_STATE_v1", "mode": "DEMO", "account_id": account,
            "strategy_id": policy["strategy_id"], "source": packet["source"],
            "observed_at": observed.isoformat(), "complete": True, "night_id": night,
            "night_session": calendar_context,
            "strategy_allocation_usd": str(allocation), "equity_usd": str(equity),
            "cash_flow_adjusted_high_water_mark_usd": str(hwm),
            "night_start_equity_usd": str(night_start), "night_cash_flow_usd": str(night_flow),
            "night_loss_usd": str(night_loss), "drawdown_usd": str(drawdown),
            "night_loss_pause_latched": night_latch, "drawdown_pause_latched": drawdown_latch,
            "owner_review_verified_for_resumption": resumed, "excluded_position_ids": excluded,
            "new_entries_paused": night_latch or drawdown_latch, "broker_writes": False,
            "scope": "SUPPLIED_STRATEGY_CASH_POSITIONS_FLOWS_AND_PRIOR_STATE_ONLY"}
