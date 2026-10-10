"""Normalize private, externally executed DEMO evidence for accounting only.

This does not adopt a position into the operating ledger or authorize an order.
PREVIEW prices remain observations, never fills. Every import retains its source
identity; identical replays are idempotent and conflicting replays fail closed.
"""
from copy import deepcopy
import hashlib
import json

from active_trading.jsonio import loads_json
from .accounting import (AccountingError, OWNERSHIP_KEYS, _boolean, _integer,
                         _number, _object, _text, _time, build_trade_report)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def import_demo_trade(record, *, previous_packet=None, source_bytes=None):
    """Append one normalized external DEMO observation to a private packet.

    Required envelope: schema EXTERNAL_DEMO_TRADE_v1, mode DEMO,
    source_record_id, source, observed_at, ownership and fill_status PREVIEW or
    FINAL. FINAL requires a fill with immutable fill_id, side, decimal-string
    quantity/price, filled_at and positive sequence. Explicit fees become KNOWN
    only with history_finalized=true and fees.complete=true. Otherwise fees
    stay UNKNOWN, including a final fill whose final charge history is missing.

    source_bytes, when supplied, must decode to exactly this record. The receipt
    records its byte hash separately from the canonical record hash. External
    overrides default to excluded from strategy equity and remain so on replay.
    """
    record = _object(record, "external_demo_record")
    if record.get("schema") != "EXTERNAL_DEMO_TRADE_v1" or record.get("mode") != "DEMO":
        raise AccountingError("import: EXTERNAL_DEMO_TRADE_v1 in DEMO only; LIVE forbidden")
    if record.get("currency") != "USD":
        raise AccountingError("import: normalized USD evidence required")
    canonical = _canonical(record)
    if source_bytes is not None:
        if not isinstance(source_bytes, bytes) or loads_json(source_bytes) != record:
            raise AccountingError("import: source bytes must match the normalized record")
    source_hash = hashlib.sha256(source_bytes if source_bytes is not None else canonical).hexdigest()
    content_hash = hashlib.sha256(canonical).hexdigest()
    record_id = _text(record.get("source_record_id"), "source_record_id")
    source = _text(record.get("source"), "source")
    stamp = _time(record.get("observed_at"), "observed_at")
    ownership = {key: _text(_object(record.get("ownership"), "ownership").get(key), key)
                 for key in OWNERSHIP_KEYS}
    fill_status = record.get("fill_status")
    if fill_status not in ("PREVIEW", "FINAL"):
        raise AccountingError("fill_status: explicit PREVIEW or FINAL required")
    override = _boolean(record.get("external_override", True), "external_override")
    include = _boolean(record.get("include_in_strategy_equity", not override), "include_in_strategy_equity")
    if override and include:
        raise AccountingError("import: external override must be excluded from strategy equity")
    scope = {"external_import": True, "external_override": override,
             "include_in_strategy_equity": include,
             "classification": "EXTERNAL_OVERRIDE" if override else "DECLARED_STRATEGY_DEMO_TRADE"}
    if previous_packet is None:
        packet = {"mode": "DEMO", "ownership": ownership, "as_of": record["observed_at"],
                  "fills": [], "fee_records": [], "import_history": [], "strategy_scope": scope}
    else:
        packet = deepcopy(_object(previous_packet, "previous_packet"))
        build_trade_report(packet)
        if (packet.get("mode") != "DEMO" or packet.get("ownership") != ownership
                or packet.get("strategy_scope") != scope or not isinstance(packet.get("import_history"), list)):
            raise AccountingError("import: previous packet ownership, mode or equity scope mismatch")
        # Detect conflicting identities even when the same original observation
        # is replayed after newer observations have already been appended.
        for receipt in packet["import_history"]:
            if receipt.get("source_record_id") == record_id:
                if receipt.get("record_sha256") != content_hash or receipt.get("source_bytes_sha256") != source_hash:
                    raise AccountingError("import: conflicting source-record replay")
                return packet
        if stamp < _time(packet["as_of"], "previous_packet.as_of"):
            raise AccountingError("import: append observations in receipt order")
        packet["as_of"] = record["observed_at"]
    receipt = {"source_record_id": record_id, "source": source,
               "observed_at": record["observed_at"], "fill_status": fill_status,
               "source_bytes_sha256": source_hash, "record_sha256": content_hash,
               "source_hash_basis": "EXACT_PROVIDED_BYTES" if source_bytes is not None else "CANONICAL_NORMALIZED_RECORD",
               "evidence_authentication": "CALLER_SUPPLIED_NOT_VERIFIED_BY_IMPORTER"}
    if fill_status == "FINAL":
        supplied = _object(record.get("fill"), "fill")
        for key, expected in {**ownership, "mode": "DEMO", "currency": "USD"}.items():
            if key in supplied and supplied[key] != expected:
                raise AccountingError("import: supplied final fill ownership, mode or currency mismatch")
        fill = {**ownership, "mode": "DEMO", "currency": "USD"}
        for key in ("fill_id", "side", "quantity", "price", "filled_at", "sequence"):
            fill[key] = supplied.get(key)
        _text(fill["fill_id"], "fill_id")
        _number(fill["quantity"], "quantity", positive=True)
        _number(fill["price"], "price", positive=True)
        _integer(fill["sequence"], "sequence", positive=True)
        if fill["side"] not in ("BUY", "SELL") or _time(fill["filled_at"], "filled_at") > stamp:
            raise AccountingError("import: final fill side/time invalid")
        if "benchmark" in supplied:
            fill["benchmark"] = deepcopy(supplied["benchmark"])
        existing = next((value for value in packet["fills"] if value["fill_id"] == fill["fill_id"]), None)
        if existing is not None and existing != fill:
            raise AccountingError("import: immutable final fill conflicts with earlier history")
        if existing is None:
            packet["fills"].append(fill)
        receipt["fill_id"] = fill["fill_id"]
        finalized = _boolean(record.get("history_finalized", False), "history_finalized")
        fees = _object(record.get("fees", {}), "fees")
        complete = _boolean(fees.get("complete", False), "fees.complete")
        known = finalized and complete and fees.get("status") == "KNOWN"
        if known:
            _number(fees.get("amount"), "fees.amount")
            cost_stamp = _time(fees.get("observed_at"), "fees.observed_at")
            if cost_stamp > stamp or cost_stamp < _time(fill["filled_at"], "filled_at"):
                raise AccountingError("import: final fee history time invalid")
        else:
            cost_stamp = stamp
        active = [value for value in packet["fee_records"] if value["fill_id"] == fill["fill_id"]]
        superseded = {value.get("supersedes_cost_id") for value in active}
        prior = next((value for value in active if value["cost_id"] not in superseded), None)
        # Never regress final charge history to a provisional UNKNOWN snapshot.
        if prior is None or (known and (prior["status"] != "KNOWN" or prior.get("amount") != fees["amount"])):
            cost = {**ownership, "mode": "DEMO", "currency": "USD",
                    "cost_id": "IMPORT_COST_" + record_id, "fill_id": fill["fill_id"],
                    "status": "KNOWN" if known else "UNKNOWN", "complete": known,
                    "amount": fees["amount"] if known else None, "source": source,
                    "observed_at": cost_stamp.isoformat()}
            if prior:
                if cost_stamp <= _time(prior["observed_at"], "prior_fee.observed_at"):
                    raise AccountingError("import: fee correction must follow prior immutable observation")
                cost["supersedes_cost_id"] = prior["cost_id"]
            packet["fee_records"].append(cost)
    # A preview may update neither the owned fill list nor reconciliation. Final
    # snapshots remain independently supplied evidence, not inferred from fills.
    if fill_status == "FINAL":
        for name in ("reconciliation", "mark"):
            if name in record:
                packet[name] = deepcopy(record[name])
    packet["import_history"].append(receipt)
    build_trade_report(packet)
    return packet
