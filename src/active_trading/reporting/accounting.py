"""Deterministic accounting for one exactly owned SHADOW or DEMO position.

Inputs are normalized private records, not authenticated broker evidence. This
module performs no I/O, order submission, approval, tax or currency conversion.
Actual fill prices already incorporate execution spread. The optional midpoint
comparison is diagnostic and is never deducted from fill-based PnL again.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import json
from typing import Any


class AccountingError(ValueError):
    """Invalid, conflicting or unsupported normalized accounting evidence."""


OWNERSHIP_KEYS = ("account_id", "strategy_id", "instrument_id", "position_id")
ZERO = Decimal("0")


def _object(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise AccountingError(f"{label}: object required")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AccountingError(f"{label}: nonempty text required")
    return value


def _boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise AccountingError(f"{label}: explicit boolean required")
    return value


def _integer(value: Any, label: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0):
        raise AccountingError(f"{label}: {'positive' if positive else 'nonnegative'} integer required")
    return value


def _number(value: Any, label: str, *, positive: bool = False) -> Decimal:
    # Binary floats can silently change broker quantities. JSON producers should
    # normalize decimals to strings, preserving the precision of the source.
    if type(value) not in (str, int):
        raise AccountingError(f"{label}: decimal string or integer required; floats unsupported")
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise AccountingError(f"{label}: invalid decimal") from exc
    if not number.is_finite() or number < ZERO or (positive and number == ZERO):
        raise AccountingError(f"{label}: finite {'positive' if positive else 'nonnegative'} decimal required")
    digits = number.as_tuple()
    if len(digits.digits) > 40 or abs(digits.exponent) > 30:
        raise AccountingError(f"{label}: unsupported numeric precision or exponent")
    return number


def _time(value: Any, label: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(_text(value, label).replace("Z", "+00:00"))
    except ValueError as exc:
        raise AccountingError(f"{label}: ISO timestamp required") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise AccountingError(f"{label}: timezone-aware timestamp required")
    return stamp.astimezone(timezone.utc)


def _amount(number: Decimal | None) -> str | None:
    if number is None:
        return None
    if number == ZERO:
        return "0"
    value = format(number, "f")
    return value.rstrip("0").rstrip(".") if "." in value else value


def _identity(record: dict, ownership: dict, mode: str, label: str) -> None:
    if record.get("mode") != mode:
        raise AccountingError(f"{label}: mode mismatch; SHADOW and DEMO must remain separate")
    for key in OWNERSHIP_KEYS:
        if record.get(key) != ownership[key]:
            raise AccountingError(f"{label}: exact {key} ownership mismatch")


def _usd(record: dict, label: str) -> None:
    if record.get("currency") != "USD":
        raise AccountingError(f"{label}: USD required; currency conversion is not implemented")


def _deduplicate(records: Any, id_key: str, label: str) -> tuple[list[dict], int]:
    if not isinstance(records, list):
        raise AccountingError(f"{label}: array required")
    unique: dict[str, tuple[str, dict]] = {}
    duplicates = 0
    for value in records:
        record = _object(value, label)
        record_id = _text(record.get(id_key), f"{label}.{id_key}")
        try:
            fingerprint = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise AccountingError(f"{label}: JSON-compatible normalized records required") from exc
        if record_id in unique:
            if fingerprint != unique[record_id][0]:
                raise AccountingError(f"{label}: conflicting replay of {id_key} {record_id}")
            duplicates += 1
        else:
            unique[record_id] = (fingerprint, record)
    return [item[1] for item in unique.values()], duplicates


def _fills(packet: dict, ownership: dict, mode: str, as_of: datetime) -> tuple[list[dict], int]:
    unique, duplicate_count = _deduplicate(packet.get("fills"), "fill_id", "fills")
    normalized = []
    sequences = set()
    for fill in unique:
        _identity(fill, ownership, mode, "fill")
        _usd(fill, "fill")
        side = fill.get("side")
        if side not in ("BUY", "SELL"):
            raise AccountingError("fill.side: BUY or SELL required")
        stamp = _time(fill.get("filled_at"), "fill.filled_at")
        if stamp > as_of:
            raise AccountingError("fill: cannot use a fill from after report as_of")
        sequence = _integer(fill.get("sequence"), "fill.sequence", positive=True)
        if sequence in sequences:
            raise AccountingError("fill.sequence: duplicate ordering sequence")
        sequences.add(sequence)
        normalized.append({"raw": fill, "id": fill["fill_id"], "side": side,
            "time": stamp, "sequence": sequence,
            "quantity": _number(fill.get("quantity"), "fill.quantity", positive=True),
            "price": _number(fill.get("price"), "fill.price", positive=True)})
    # Never use alphabetical fill IDs or caller array order to decide cost basis.
    normalized.sort(key=lambda fill: (fill["time"], fill["sequence"]))
    return normalized, duplicate_count


def _fees(packet: dict, fills: list[dict], ownership: dict, mode: str,
          as_of: datetime) -> tuple[dict[str, dict], list[str], int]:
    unique, duplicate_count = _deduplicate(packet.get("fee_records", []), "cost_id", "fee_records")
    by_fill = {fill["id"]: fill for fill in fills}
    costs = {}
    for record in unique:
        _identity(record, ownership, mode, "fee_record")
        _usd(record, "fee_record")
        fill_id = _text(record.get("fill_id"), "fee_record.fill_id")
        if fill_id not in by_fill:
            raise AccountingError("fee_record: refers to a fill outside this report")
        source = _text(record.get("source"), "fee_record.source")
        observed = _time(record.get("observed_at"), "fee_record.observed_at")
        if observed > as_of or observed < by_fill[fill_id]["time"]:
            raise AccountingError("fee_record: observed_at must be between fill and report as_of")
        status = record.get("status")
        if status not in ("KNOWN", "UNKNOWN"):
            raise AccountingError("fee_record.status: KNOWN or UNKNOWN required")
        complete = _boolean(record.get("complete", False), "fee_record.complete")
        if status == "UNKNOWN":
            if record.get("amount") is not None or complete:
                raise AccountingError("fee_record: UNKNOWN cannot carry an amount or complete=true")
            amount = None
        else:
            amount = _number(record.get("amount"), "fee_record.amount")
        previous = record.get("supersedes_cost_id")
        if previous is not None:
            previous = _text(previous, "fee_record.supersedes_cost_id")
        costs[record["cost_id"]] = {"id": record["cost_id"], "fill_id": fill_id,
            "time": observed, "source": source, "status": status,
            "complete": complete, "amount": amount, "previous": previous}
    child = {}
    roots = {}
    for cost in costs.values():
        previous = cost["previous"]
        if previous is None:
            if cost["fill_id"] in roots:
                raise AccountingError("fee_record: multiple fee roots for one fill; append a superseding correction")
            roots[cost["fill_id"]] = cost["id"]
            continue
        if previous not in costs:
            raise AccountingError("fee_record: superseded record missing from immutable history")
        prior = costs[previous]
        if prior["fill_id"] != cost["fill_id"] or prior["time"] >= cost["time"]:
            raise AccountingError("fee_record: correction must follow the same fill's earlier record")
        if previous in child:
            raise AccountingError("fee_record: branched correction history")
        child[previous] = cost["id"]
    active = {}
    for fill_id, root in roots.items():
        current = root
        while current in child:
            current = child[current]
        active[fill_id] = costs[current]
    # Strictly increasing timestamps prevent cycles; every chain must have a root.
    if len(active) != len({cost["fill_id"] for cost in costs.values()}):
        raise AccountingError("fee_record: incomplete correction chain")
    history = sorted(costs, key=lambda cost_id: (costs[cost_id]["time"], cost_id))
    return active, history, duplicate_count


def _spread(fill: dict) -> tuple[Decimal | None, str]:
    benchmark = fill["raw"].get("benchmark")
    if benchmark is None:
        return None, "MISSING_BENCHMARK"
    benchmark = _object(benchmark, "fill.benchmark")
    _text(benchmark.get("source"), "fill.benchmark.source")
    _usd(benchmark, "fill.benchmark")
    mid = _number(benchmark.get("mid_price"), "fill.benchmark.mid_price", positive=True)
    observed = _time(benchmark.get("observed_at"), "fill.benchmark.observed_at")
    age = (fill["time"] - observed).total_seconds()
    if age < 0:
        return None, "BENCHMARK_AFTER_FILL"
    if age > 60:
        return None, "STALE_BENCHMARK"
    adverse_per_share = fill["price"] - mid if fill["side"] == "BUY" else mid - fill["price"]
    return adverse_per_share * fill["quantity"], "AVAILABLE"


def _reconciliation(value: Any, ownership: dict, mode: str, as_of: datetime,
                    latest_fill: datetime | None, remaining: Decimal) -> dict:
    if value is None:
        return {"status": "MISSING", "source": None, "observed_at": None,
                "quantity_matches": False, "pending_order_count": None, "complete": False}
    record = _object(value, "reconciliation")
    _identity(record, ownership, mode, "reconciliation")
    source = _text(record.get("source"), "reconciliation.source")
    observed = _time(record.get("observed_at"), "reconciliation.observed_at")
    supplied_complete = _boolean(record.get("complete"), "reconciliation.complete")
    quantity = _number(record.get("position_quantity"), "reconciliation.position_quantity")
    pending = _integer(record.get("pending_order_count"), "reconciliation.pending_order_count")
    status = "MATCHED"
    if observed > as_of:
        status = "AFTER_REPORT_AS_OF"
    elif latest_fill is not None and observed < latest_fill:
        status = "PREDATES_LATEST_FILL"
    elif (as_of - observed).total_seconds() > 60:
        status = "STALE_RECONCILIATION"
    elif not supplied_complete:
        status = "INCOMPLETE"
    elif quantity != remaining:
        status = "QUANTITY_MISMATCH"
    elif pending:
        status = "PENDING_ORDERS"
    return {"status": status, "source": source, "observed_at": observed.isoformat(),
        "position_quantity": _amount(quantity), "quantity_matches": quantity == remaining,
        "pending_order_count": pending, "complete": status == "MATCHED",
        "authentication": "CALLER_SUPPLIED_NOT_VERIFIED_BY_ACCOUNTING"}


def _mark(packet: dict, ownership: dict, mode: str, as_of: datetime,
          latest_fill: datetime | None, remaining: Decimal, basis: Decimal) -> dict:
    value = packet.get("mark")
    if value is None:
        if remaining == ZERO:
            return {"status": "NO_REMAINING_SHARES", "unrealized_gross_pnl_usd": "0",
                    "market_value_usd": "0", "price": None, "observed_at": None}
        return {"status": "MISSING", "unrealized_gross_pnl_usd": None,
                "market_value_usd": None, "price": None, "observed_at": None}
    record = _object(value, "mark")
    _identity(record, ownership, mode, "mark")
    _usd(record, "mark")
    source = _text(record.get("source"), "mark.source")
    price = _number(record.get("price"), "mark.price", positive=True)
    stamp = _time(record.get("observed_at"), "mark.observed_at")
    if remaining == ZERO:
        return {"status": "NO_REMAINING_SHARES", "unrealized_gross_pnl_usd": "0",
                "market_value_usd": "0", "price": _amount(price),
                "observed_at": stamp.isoformat(), "source": source}
    age = (as_of - stamp).total_seconds()
    status = "AVAILABLE"
    if age < 0:
        status = "AFTER_REPORT_AS_OF"
    elif latest_fill is not None and stamp < latest_fill:
        status = "PREDATES_LATEST_FILL"
    elif age > 60:
        status = "STALE_MARK"
    valid = status == "AVAILABLE"
    return {"status": status, "price": _amount(price), "observed_at": stamp.isoformat(),
        "source": source, "market_value_usd": _amount(remaining * price) if valid else None,
        "unrealized_gross_pnl_usd": _amount(remaining * price - basis) if valid else None}


def _modeled_costs(packet: dict, as_of: datetime) -> dict | None:
    value = packet.get("modeled_live_costs")
    if value is None:
        return None
    record = _object(value, "modeled_live_costs")
    _usd(record, "modeled_live_costs")
    source = _text(record.get("source"), "modeled_live_costs.source")
    observed = _time(record.get("observed_at"), "modeled_live_costs.observed_at")
    if observed > as_of:
        raise AccountingError("modeled_live_costs: future estimate cannot be used")
    amount = _number(record.get("estimated_total_cost"), "modeled_live_costs.estimated_total_cost")
    includes_spread = _boolean(record.get("includes_spread"), "modeled_live_costs.includes_spread")
    return {"estimated_total_cost_usd": _amount(amount), "source": source,
        "observed_at": observed.isoformat(), "includes_spread": includes_spread,
        "classification": "HYPOTHETICAL_LIVE_COST_NOT_OBSERVED_FEE",
        "deducted_from_observed_pnl": False}


def build_trade_report(packet: dict) -> dict:
    """Return JSON-safe accounting for one owned position without modifying input.

    Every fill has a unique immutable fill_id and integer sequence. Replaying an
    identical record is idempotent; conflicting payloads fail. Fees are one
    aggregate charge record per fill, optionally corrected by append-only
    supersedes chains. Missing or incomplete fee coverage never becomes zero.
    Decimal strings retain source precision; arithmetic uses 50-digit precision.
    Mode LIVE is forbidden. A matched caller reconciliation is not authenticated
    here and cannot itself authorize execution, publication or account adoption.
    """
    packet = _object(packet, "packet")
    if packet.get("corporate_actions") or packet.get("other_cash_movements"):
        raise AccountingError("corporate actions and other cash movements require a supported accounting adapter")
    mode = packet.get("mode")
    if mode not in ("SHADOW", "DEMO"):
        raise AccountingError("mode: only SHADOW or DEMO accounting permitted; LIVE forbidden")
    ownership_value = _object(packet.get("ownership"), "ownership")
    ownership = {key: _text(ownership_value.get(key), "ownership." + key) for key in OWNERSHIP_KEYS}
    strategy_scope = packet.get("strategy_scope")
    if strategy_scope is not None:
        strategy_scope = dict(_object(strategy_scope, "strategy_scope"))
        override = _boolean(strategy_scope.get("external_override"), "strategy_scope.external_override")
        include = _boolean(strategy_scope.get("include_in_strategy_equity"), "strategy_scope.include_in_strategy_equity")
        if override and include:
            raise AccountingError("external override must be excluded from strategy equity")
    as_of = _time(packet.get("as_of"), "as_of")
    fills, duplicate_fills = _fills(packet, ownership, mode, as_of)
    fee_by_fill, fee_history, duplicate_costs = _fees(packet, fills, ownership, mode, as_of)
    with localcontext() as context:
        context.prec = 50
        remaining = basis = realized = bought = sold = buy_notional = sell_notional = ZERO
        known_fees = remaining_known_entry_fees = realized_known_fees = ZERO
        entry_fees_complete = all_fees_complete = True
        spread_total = ZERO
        spread_complete = True
        spread_rows = []
        closed_once = False
        all_active_costs = []
        for fill in fills:
            quantity, price = fill["quantity"], fill["price"]
            cost = fee_by_fill.get(fill["id"])
            cost_complete = bool(cost and cost["status"] == "KNOWN" and cost["complete"])
            all_fees_complete = all_fees_complete and cost_complete
            fee = cost["amount"] if cost and cost["amount"] is not None else ZERO
            known_fees += fee
            all_active_costs.append({"fill_id": fill["id"], "cost_id": cost["id"] if cost else None,
                "status": cost["status"] if cost else "MISSING", "complete": cost_complete,
                "known_amount_usd": _amount(cost["amount"]) if cost else None})
            if fill["side"] == "BUY":
                if closed_once:
                    raise AccountingError("fill: cannot reopen a closed position_id; use a new exact position")
                remaining += quantity
                bought += quantity
                basis += quantity * price
                buy_notional += quantity * price
                remaining_known_entry_fees += fee
                entry_fees_complete = entry_fees_complete and cost_complete
            else:
                if quantity > remaining:
                    raise AccountingError("fill: sell exceeds previously bought remaining shares")
                fraction = quantity / remaining
                # Exact final subtraction avoids rounding leaving phantom shares/basis.
                removed_basis = basis if quantity == remaining else basis * fraction
                removed_fees = remaining_known_entry_fees if quantity == remaining else remaining_known_entry_fees * fraction
                proceeds = quantity * price
                realized += proceeds - removed_basis
                realized_known_fees += removed_fees + fee
                remaining -= quantity
                basis -= removed_basis
                remaining_known_entry_fees -= removed_fees
                sold += quantity
                sell_notional += proceeds
                if remaining == ZERO:
                    closed_once = True
            spread, reason = _spread(fill)
            spread_complete = spread_complete and spread is not None
            if spread is not None:
                spread_total += spread
            spread_rows.append({"fill_id": fill["id"], "status": reason,
                                "adverse_midpoint_difference_usd": _amount(spread)})
        latest = fills[-1]["time"] if fills else None
        reconciliation = _reconciliation(packet.get("reconciliation"), ownership, mode, as_of, latest, remaining)
        mark = _mark(packet, ownership, mode, as_of, latest, remaining, basis)
        if not fills:
            position_status = "NO_FILLS"
        elif remaining > ZERO:
            position_status = "OPEN_RECONCILED" if reconciliation["complete"] else "OPEN_UNRECONCILED"
        else:
            position_status = "CLOSED_RECONCILED" if reconciliation["complete"] else "FLAT_UNRECONCILED"
        # Complete costs and independently supplied matching state are both needed
        # for final trade PnL. Open-position realized PnL remains provisional.
        final = bool(fills) and all_fees_complete and position_status == "CLOSED_RECONCILED"
        realized_net = realized - realized_known_fees if all_fees_complete and fills else None
        unrealized_gross = mark["unrealized_gross_pnl_usd"]
        unrealized_after_entry_fees = (Decimal(unrealized_gross) - remaining_known_entry_fees
            if unrealized_gross is not None and entry_fees_complete else None)
        return {"schema_version": "TRADE_ACCOUNTING_v1", "mode": mode, "ownership": ownership,
            "strategy_scope": strategy_scope,
            "as_of": as_of.isoformat(), "currency": "USD", "broker_writes": False,
            "evidence_authentication": "CALLER_SUPPLIED_NOT_VERIFIED_BY_ACCOUNTING",
            "accounting_method": "WEIGHTED_AVERAGE_FILL_PRICE_NOT_TAX_ACCOUNTING",
            "pnl_scope": "POSITION_FILL_PNL_AND_EXPLICIT_CHARGES_NOT_WHOLE_ACCOUNT_EQUITY",
            "fill_count": len(fills), "duplicate_fill_replays_removed": duplicate_fills,
            "duplicate_cost_replays_removed": duplicate_costs, "bought_quantity": _amount(bought),
            "sold_quantity": _amount(sold), "remaining_quantity": _amount(remaining),
            "buy_notional_usd": _amount(buy_notional), "sell_notional_usd": _amount(sell_notional),
            "remaining_fill_cost_basis_usd": _amount(basis),
            "average_remaining_fill_price_usd": _amount(basis / remaining) if remaining else None,
            "realized_gross_pnl_usd": _amount(realized),
            "known_observed_fees_usd": _amount(known_fees),
            "observed_fees_usd": _amount(known_fees) if all_fees_complete and fills else None,
            "fee_coverage_complete": bool(fills) and all_fees_complete,
            "known_realized_fee_component_usd": _amount(realized_known_fees),
            "known_remaining_entry_fee_component_usd": _amount(remaining_known_entry_fees),
            "remaining_basis_including_entry_fees_usd": _amount(basis + remaining_known_entry_fees)
                if entry_fees_complete and fills else None,
            "realized_net_pnl_usd": _amount(realized_net),
            "net_pnl_status": "FINAL" if final else "NOT_FINAL",
            "final_net_pnl_usd": _amount(realized_net) if final else None,
            "unrealized": mark,
            "unrealized_after_known_entry_fees_usd": _amount(unrealized_after_entry_fees),
            "future_exit_fees_included_in_unrealized": False,
            "position_status": position_status, "closed": position_status == "CLOSED_RECONCILED",
            "reconciliation": reconciliation, "active_fee_records": all_active_costs,
            "fee_history_cost_ids": fee_history,
            "spread_diagnostic": {"adverse_midpoint_difference_usd": _amount(spread_total)
                if spread_complete and fills else None, "complete": bool(fills) and spread_complete,
                "per_fill": spread_rows, "deducted_from_pnl": False,
                "interpretation": "FILL_MINUS_CONTEMPORANEOUS_MID_NOT_A_SEPARATE_CHARGE"},
            "modeled_live_costs": _modeled_costs(packet, as_of)}
