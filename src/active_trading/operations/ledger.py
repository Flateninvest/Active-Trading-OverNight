"""Private, durable SHADOW intents, supplied fills and owned exit obligations.

No network, broker writer, clock scheduler or source authentication lives here.
Entry permission must be supplied by an external verifier, not a raw PASS flag.
Snapshots and fill events are normalized factual inputs whose producer remains
responsible for authenticity and completeness. Never use a quote touch as a fill.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable
from zoneinfo import ZoneInfo


class LedgerError(ValueError):
    """An inconsistent, unapproved or unsafe SHADOW state transition."""


class _ReconciliationConflict(LedgerError):
    """Contradictory own-order facts that must survive a refused snapshot."""

    def __init__(self, reason: str, intent_id: str):
        super().__init__(reason)
        self.intent_id = intent_id


NY = ZoneInfo("America/New_York")
PENDING = {"PLANNED", "SUBMITTING", "SUBMITTED", "PARTIAL", "UNKNOWN", "RECONCILED"}


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LedgerError(f"{label}: nonempty text required")
    return value.strip()


def _number(value: Any, label: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise LedgerError(f"{label}: finite number required")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise LedgerError(f"{label}: invalid decimal") from exc
    if not result.is_finite() or result < 0 or (positive and not result):
        raise LedgerError(f"{label}: finite {'positive' if positive else 'nonnegative'} number required")
    return result


def _stamp(value: Any, label: str) -> datetime:
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(_text(value, label).replace("Z", "+00:00"))
    except ValueError as exc:
        raise LedgerError(f"{label}: invalid ISO timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise LedgerError(f"{label}: timezone-aware timestamp required")
    return result.astimezone(timezone.utc)


def _day(value: Any, label: str) -> date:
    try:
        return date.fromisoformat(_text(value, label))
    except ValueError as exc:
        raise LedgerError(f"{label}: ISO date required") from exc


def _json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise LedgerError("Canonical JSON with finite numbers required") from exc


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def next_opening(calendar: dict, entry_session: str) -> dict:
    """Resolve the next regular session from a supplied complete calendar slice.

    The helper checks normalized calendar consistency, not the source's truth.
    Holidays cannot be reconstructed from missing records without a declared
    complete range. Planned non-next-day holds remain outside this strategy.
    """
    if not isinstance(calendar, dict):
        raise LedgerError("calendar: object required")
    for key in ("calendar_id", "source"):
        _text(calendar.get(key), "calendar." + key)
    _stamp(calendar.get("observed_at"), "calendar.observed_at")
    start = _day(calendar.get("complete_from"), "calendar.complete_from")
    end = _day(calendar.get("complete_through"), "calendar.complete_through")
    entry = _day(entry_session, "entry_session")
    if start > entry or end < entry + timedelta(days=1):
        raise LedgerError("calendar: complete coverage through the next day required")
    rows = calendar.get("sessions")
    if not isinstance(rows, list) or not rows:
        raise LedgerError("calendar.sessions: nonempty array required")
    sessions = []
    for row in rows:
        if not isinstance(row, dict):
            raise LedgerError("calendar session: object required")
        day = _day(row.get("date"), "session.date")
        opened, closed = _stamp(row.get("open"), "session.open"), _stamp(row.get("close"), "session.close")
        if not start <= day <= end or opened >= closed:
            raise LedgerError("calendar: invalid session range")
        if opened.astimezone(NY).date() != day or closed.astimezone(NY).date() != day:
            raise LedgerError("calendar: timestamp/session date mismatch")
        sessions.append((day, opened, closed))
    if [row[0] for row in sessions] != sorted(set(row[0] for row in sessions)):
        raise LedgerError("calendar: sessions must be unique and chronological")
    entries = [row for row in sessions if row[0] == entry]
    after = [row for row in sessions if row[0] > entry]
    if not entries or not after:
        raise LedgerError("calendar: entry and next session required")
    following = after[0]
    if entry.weekday() not in (1, 2, 3) or following[0].weekday() not in (2, 3, 4):
        raise LedgerError("calendar: Tuesday-Thursday entry and Wednesday-Friday exit required")
    if following[0] != entry + timedelta(days=1):
        raise LedgerError("calendar: planned holiday/weekend bridge is prohibited")
    return {"entry_open": entries[0][1].isoformat(), "entry_close": entries[0][2].isoformat(),
            "exit_session": following[0].isoformat(), "exit_open": following[1].isoformat()}


class ShadowLedger:
    """SQLite single-writer transactions with append-only public API events.

    The local owner can edit this database; it is not tamper-proof custody.
    A separate authenticated reviewer and permission boundary remain necessary.
    """

    def __init__(self, path: str | Path, *, repository_root: str | Path | None = None):
        self.path = Path(path).expanduser().resolve()
        root = Path(repository_root).resolve() if repository_root else Path(__file__).resolve().parents[3]
        if self.path == root or root in self.path.parents:
            raise LedgerError("Private trading state must be outside the repository")
        if any((parent / ".git").exists() for parent in self.path.parents):
            raise LedgerError("Private trading state must be outside every Git checkout")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS entries (
          intent_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, mode TEXT NOT NULL,
          strategy_id TEXT NOT NULL, instrument_id TEXT NOT NULL, entry_session TEXT NOT NULL,
          proposal_digest TEXT NOT NULL, proposal TEXT NOT NULL, authorization TEXT NOT NULL,
          quantity TEXT NOT NULL, price_limit TEXT NOT NULL, cost_reserve TEXT NOT NULL,
          nav TEXT NOT NULL, bought TEXT NOT NULL DEFAULT '0', state TEXT NOT NULL,
          created_at TEXT NOT NULL, exit_open TEXT NOT NULL, exit_session TEXT NOT NULL,
          UNIQUE(account_id,mode,strategy_id,entry_session,instrument_id));
        CREATE TABLE IF NOT EXISTS positions (
          account_id TEXT NOT NULL, mode TEXT NOT NULL, position_id TEXT NOT NULL,
          strategy_id TEXT NOT NULL, instrument_id TEXT NOT NULL, entry_intent_id TEXT NOT NULL,
          quantity TEXT NOT NULL, bought TEXT NOT NULL, sold TEXT NOT NULL,
          exit_open TEXT NOT NULL, exit_session TEXT NOT NULL,
          PRIMARY KEY(account_id,mode,position_id),
          FOREIGN KEY(entry_intent_id) REFERENCES entries(intent_id));
        CREATE TABLE IF NOT EXISTS exits (
          intent_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, mode TEXT NOT NULL,
          position_id TEXT NOT NULL, entry_intent_id TEXT NOT NULL, quantity TEXT NOT NULL,
          sold TEXT NOT NULL DEFAULT '0', state TEXT NOT NULL, created_at TEXT NOT NULL,
          UNIQUE(account_id,mode,position_id),
          FOREIGN KEY(account_id,mode,position_id) REFERENCES positions(account_id,mode,position_id));
        CREATE TABLE IF NOT EXISTS attempts (
          attempt_id TEXT PRIMARY KEY, intent_id TEXT NOT NULL, kind TEXT NOT NULL,
          quantity TEXT NOT NULL, started_at TEXT NOT NULL, order_id TEXT,
          state TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (
          sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL UNIQUE,
          kind TEXT NOT NULL, payload TEXT NOT NULL, recorded_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS fills (
          account_id TEXT NOT NULL, mode TEXT NOT NULL, fill_id TEXT NOT NULL,
          intent_id TEXT NOT NULL, position_id TEXT NOT NULL, side TEXT NOT NULL,
          payload TEXT NOT NULL, sequence INTEGER NOT NULL,
          PRIMARY KEY(account_id,mode,fill_id), FOREIGN KEY(sequence) REFERENCES events(sequence));
        CREATE TABLE IF NOT EXISTS reconciliations (
          reconciliation_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, strategy_id TEXT NOT NULL,
          observed_at TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS control_exceptions (
          exception_id TEXT PRIMARY KEY, entry_intent_id TEXT NOT NULL,
          reason TEXT NOT NULL, recorded_at TEXT NOT NULL,
          FOREIGN KEY(entry_intent_id) REFERENCES entries(intent_id));
        """)

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @contextmanager
    def _transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _event(self, key: str, kind: str, payload: dict, at: datetime) -> int:
        encoded = _json(payload)
        old = self.db.execute("SELECT * FROM events WHERE event_key=?", (key,)).fetchone()
        if old:
            if old["payload"] != encoded or old["kind"] != kind:
                raise LedgerError("Event ID reused with conflicting content")
            return old["sequence"]
        cursor = self.db.execute("INSERT INTO events(event_key,kind,payload,recorded_at) VALUES(?,?,?,?)",
                                 (key, kind, encoded, at.isoformat()))
        return cursor.lastrowid

    def _intent(self, intent_id: str) -> tuple[str, sqlite3.Row]:
        row = self.db.execute("SELECT * FROM entries WHERE intent_id=?", (intent_id,)).fetchone()
        if row:
            return "ENTRY", row
        row = self.db.execute("SELECT * FROM exits WHERE intent_id=?", (intent_id,)).fetchone()
        if row:
            return "EXIT", row
        raise LedgerError("Unknown intent ID")

    def get_intent(self, intent_id: str) -> dict:
        kind, row = self._intent(intent_id)
        result = dict(row)
        result["kind"] = kind
        if kind == "ENTRY":
            result["proposal"] = json.loads(result["proposal"])
            result["authorization"] = json.loads(result["authorization"])
        return result

    def _fresh_reconciliation(self, account_id: str, strategy_id: str, at: datetime) -> None:
        row = self.db.execute("SELECT * FROM reconciliations WHERE account_id=? AND strategy_id=? ORDER BY observed_at DESC, rowid DESC LIMIT 1",
                              (account_id, strategy_id)).fetchone()
        if row is None or not at - timedelta(seconds=60) <= _stamp(row["observed_at"], "reconciliation") <= at:
            raise LedgerError("Fresh complete reconciliation required before exit or retry")
        snapshot = json.loads(row["payload"])
        current = {r["fill_id"] for r in self.fills() if r["account_id"] == account_id and r["strategy_id"] == strategy_id}
        if set(snapshot["fill_ids"]) != current:
            raise LedgerError("Reconciliation no longer covers current fills")

    def _check_reservations(self, proposal: dict, notional: Decimal, nav: Decimal, *, exclude_intent=None) -> None:
        """Serialize the union of supplied exposures and private local memory.

        A producer must include held AND pending reservations in the snapshot.
        Any local amount not represented there is conservatively charged against
        its stated available cash. This may overblock; it never invents credit.
        """
        snapshot = proposal.get("account_snapshot")
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("exposures"), list):
            raise LedgerError("Current account snapshot exposures and cash required")
        supplied = {}
        for row in snapshot["exposures"]:
            name = _text(row.get("instrument_id"), "snapshot exposure instrument")
            supplied[name] = supplied.get(name, Decimal(0)) + _number(row.get("reserved_usd"), "snapshot exposure", positive=True)
        local = {}
        for row in self.db.execute("SELECT * FROM entries WHERE account_id=? AND strategy_id=? AND mode='SHADOW'",
                                   (proposal["account_id"], proposal["strategy_id"])):
            if row["intent_id"] == exclude_intent:
                continue
            amount = self._reservation(row)
            if amount:
                local[row["instrument_id"]] = local.get(row["instrument_id"], Decimal(0)) + amount
        union = {name: max(supplied.get(name, Decimal(0)), local.get(name, Decimal(0))) for name in supplied.keys() | local.keys()}
        if proposal["instrument_id"] in union:
            raise LedgerError("Existing owned or pending exposure prohibits another entry in this instrument")
        if any(amount > nav * Decimal("0.10") for amount in union.values()):
            raise LedgerError("Existing supplied/local exposure exceeds the 10% per-name maximum")
        if len(union) >= 3 or sum(union.values(), Decimal(0)) + notional > nav * Decimal("0.30"):
            raise LedgerError("Atomic shared-book position/gross reservation limit exceeded")
        unrepresented = sum((max(amount - supplied.get(name, Decimal(0)), Decimal(0)) for name, amount in local.items()), Decimal(0))
        cash = _number(snapshot.get("available_cash_usd"), "available cash")
        if unrepresented + notional > cash:
            raise LedgerError("Atomic cash reservation would spend the same buying power twice")

    def _check_reservations_for_attempt(self, row, proposal, at):
        self._check_expired_pending_entries(row["account_id"], row["strategy_id"], at, exclude_intent=row["intent_id"])
        if self.db.execute("SELECT 1 FROM entries WHERE account_id=? AND strategy_id=? AND intent_id<>? AND state IN ('UNKNOWN','SUBMITTING')",
                           (row["account_id"], row["strategy_id"], row["intent_id"])).fetchone():
            raise LedgerError("Unknown other entry outcome blocks new entry attempts")
        if self.db.execute("SELECT 1 FROM exits x JOIN entries e ON x.entry_intent_id=e.intent_id WHERE x.account_id=? AND e.strategy_id=? AND x.state IN ('SUBMITTING','SUBMITTED','PARTIAL','UNKNOWN')",
                           (row["account_id"], row["strategy_id"])).fetchone():
            raise LedgerError("Unresolved exit blocks new entry attempts")
        if any(p["account_id"] == row["account_id"] and p["strategy_id"] == row["strategy_id"] for p in self.due_exits(at)):
            raise LedgerError("Due owned exit blocks new entry attempts")
        if self.db.execute("SELECT 1 FROM control_exceptions c JOIN entries e ON c.entry_intent_id=e.intent_id WHERE e.account_id=? AND e.strategy_id=?",
                           (row["account_id"], row["strategy_id"])).fetchone():
            raise LedgerError("Control exception blocks new entry attempts")
        self._check_reservations(proposal, Decimal(proposal["approved_notional_usd"]),
                                 Decimal(proposal["nav_usd"]), exclude_intent=row["intent_id"])

    def _check_expired_pending_entries(self, account_id, strategy_id, at, *, exclude_intent=None):
        for row in self.db.execute("SELECT * FROM entries WHERE account_id=? AND strategy_id=?", (account_id, strategy_id)):
            if row["intent_id"] == exclude_intent:
                continue
            if (row["state"] in PENDING and Decimal(row["bought"]) < Decimal(row["quantity"])
                    and at >= _stamp(json.loads(row["proposal"])["entry_cutoff"], "entry_cutoff")):
                raise LedgerError("Expired pending entry must be reconciled/abandoned before new exposure")

    def _reservation(self, entry: sqlite3.Row) -> Decimal:
        remaining = sum((Decimal(row[0]) for row in self.db.execute(
            "SELECT quantity FROM positions WHERE entry_intent_id=?", (entry["intent_id"],))), Decimal(0))
        pending = max(Decimal(entry["quantity"]) - Decimal(entry["bought"]), Decimal(0)) if entry["state"] in PENDING else Decimal(0)
        units = remaining + pending
        if not units:
            return Decimal(0)
        reserve = Decimal(entry["cost_reserve"]) * min(units / Decimal(entry["quantity"]), Decimal(1))
        return units * Decimal(entry["price_limit"]) + reserve

    def exposure_snapshot(self, account_id: str, strategy_id: str) -> dict:
        """Local price-limit reservations, not authenticated current market NAV."""
        rows = self.db.execute("SELECT * FROM entries WHERE account_id=? AND strategy_id=? AND mode='SHADOW'",
                               (account_id, strategy_id)).fetchall()
        by_name: dict[str, Decimal] = {}
        for row in rows:
            reserved = self._reservation(row)
            if reserved:
                by_name[row["instrument_id"]] = by_name.get(row["instrument_id"], Decimal(0)) + reserved
        return {"mode": "SHADOW", "account_id": account_id, "strategy_id": strategy_id,
                "reserved_notional_usd": str(sum(by_name.values(), Decimal(0))),
                "instruments": {name: str(amount) for name, amount in sorted(by_name.items())},
                "basis": "LOCAL_ENTRY_PRICE_LIMIT_PLUS_COST_RESERVE_NOT_MARKET_NAV"}

    def register_entry(self, proposal: dict, authorization: dict, now: Any, calendar: dict, *,
                       authorization_verifier: Callable[[dict, dict, datetime], bool]) -> dict:
        """Reserve a reviewed entry and its target exit before any simulated fill."""
        if not isinstance(proposal, dict) or not isinstance(authorization, dict):
            raise LedgerError("Proposal and authorization objects required")
        if not callable(authorization_verifier):
            raise LedgerError("External authorization verifier required")
        at = _stamp(now, "now")
        for key in ("proposal_id", "account_id", "strategy_id", "instrument_id", "sleeve", "spec_hash", "code_commit"):
            _text(proposal.get(key), "proposal." + key)
        if proposal.get("mode") != "SHADOW" or authorization.get("mode") != "SHADOW":
            raise LedgerError("Only SHADOW mode is supported")
        if proposal["sleeve"] not in ("FLOW_RESEARCH_OVERNIGHT", "EARNINGS_OVERNIGHT"):
            raise LedgerError("Unknown sleeve")
        hashes = proposal.get("input_hashes")
        if not isinstance(hashes, list) or not hashes or any(not isinstance(x, str) or not x for x in hashes):
            raise LedgerError("proposal.input_hashes: nonempty source identity array required")
        digest = canonical_digest(proposal)
        if authorization.get("proposal_digest") != digest or authorization.get("spec_hash") != proposal["spec_hash"]:
            raise LedgerError("Authorization binding does not match exact proposal/specification")
        if authorization.get("reviewed") is not True or authorization.get("boundary_verified") is not True or authorization.get("decision") != "PASS":
            raise LedgerError("Verified independent review PASS required; not trade approval")
        _text(authorization.get("review_id"), "authorization.review_id")
        if not _stamp(authorization.get("checked_at"), "authorization.checked_at") <= at < _stamp(authorization.get("valid_until"), "authorization.valid_until"):
            raise LedgerError("Authorization is stale or future-dated")
        schedule = next_opening(calendar, proposal.get("entry_session"))
        if proposal.get("calendar_hash") != canonical_digest(calendar):
            raise LedgerError("Proposal calendar identity mismatch")
        if _stamp(calendar["observed_at"], "calendar.observed_at") > at:
            raise LedgerError("Future calendar receipt")
        close = _stamp(schedule["entry_close"], "entry_close")
        start = _stamp(proposal.get("entry_not_before"), "entry_not_before")
        cutoff = _stamp(proposal.get("entry_cutoff"), "entry_cutoff")
        if not close - timedelta(minutes=30) <= start <= close - timedelta(minutes=5) or cutoff != close - timedelta(minutes=1):
            raise LedgerError("Entry window differs from the current close-derived policy")
        if not start <= at < cutoff:
            raise LedgerError("New entry is outside its approved window")
        if _stamp(proposal.get("exit_open"), "exit_open") != _stamp(schedule["exit_open"], "calendar exit_open"):
            raise LedgerError("Exit opening does not match the actual next calendar session")
        quantity = _number(proposal.get("quantity"), "quantity", positive=True)
        price = _number(proposal.get("entry_price_limit"), "entry_price_limit", positive=True)
        costs = _number(proposal.get("entry_cost_reserve_usd"), "entry_cost_reserve_usd")
        nav = _number(proposal.get("nav_usd"), "nav_usd", positive=True)
        notional = quantity * price + costs
        if _number(proposal.get("approved_notional_usd"), "approved_notional_usd", positive=True) != notional:
            raise LedgerError("Approved notional must equal quantity times price limit plus cost reserve")
        if notional > nav * Decimal("0.10"):
            raise LedgerError("Entry exceeds the 10% per-name maximum including cost reserve")
        intent_id = "entry-" + digest
        with self._transaction():
            # Verification is inside the serialized reservation transaction so a
            # trusted caller can re-read current state before authorizing it.
            if authorization_verifier(proposal, authorization, at) is not True:
                raise LedgerError("External reviewer/permission verification failed")
            old = self.db.execute("SELECT * FROM entries WHERE account_id=? AND mode=? AND strategy_id=? AND entry_session=? AND instrument_id=?",
                                  (proposal["account_id"], "SHADOW", proposal["strategy_id"], proposal["entry_session"], proposal["instrument_id"])).fetchone()
            if old:
                if old["proposal_digest"] != digest:
                    raise LedgerError("Session/instrument already has a different entry intent, including across sleeves")
                return self.get_intent(old["intent_id"])
            self._check_expired_pending_entries(proposal["account_id"], proposal["strategy_id"], at)
            if self.db.execute("SELECT 1 FROM entries WHERE account_id=? AND strategy_id=? AND state IN ('UNKNOWN','SUBMITTING')",
                               (proposal["account_id"], proposal["strategy_id"])).fetchone():
                raise LedgerError("Unknown entry outcome blocks new entries until complete reconciliation")
            if self.db.execute("SELECT 1 FROM exits x JOIN entries e ON x.entry_intent_id=e.intent_id WHERE x.account_id=? AND e.strategy_id=? AND x.state IN ('SUBMITTING','SUBMITTED','PARTIAL','UNKNOWN')",
                               (proposal["account_id"], proposal["strategy_id"])).fetchone():
                raise LedgerError("Unresolved exit blocks new entries until complete reconciliation")
            if any(row["account_id"] == proposal["account_id"] and row["strategy_id"] == proposal["strategy_id"]
                   for row in self.due_exits(at)):
                raise LedgerError("Outstanding next-opening exit blocks new entries")
            if self.db.execute("SELECT 1 FROM control_exceptions c JOIN entries e ON c.entry_intent_id=e.intent_id WHERE e.account_id=? AND e.strategy_id=?",
                               (proposal["account_id"], proposal["strategy_id"])).fetchone():
                raise LedgerError("Recorded control exception requires operator incident review; new entries blocked")
            self._check_reservations(proposal, notional, nav)
            self.db.execute("""INSERT INTO entries(intent_id,account_id,mode,strategy_id,instrument_id,entry_session,
                 proposal_digest,proposal,authorization,quantity,price_limit,cost_reserve,nav,state,created_at,exit_open,exit_session)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'PLANNED',?,?,?)""",
                 (intent_id, proposal["account_id"], "SHADOW", proposal["strategy_id"], proposal["instrument_id"],
                  proposal["entry_session"], digest, _json(proposal), _json(authorization), str(quantity), str(price),
                  str(costs), str(nav), at.isoformat(), schedule["exit_open"], schedule["exit_session"]))
            self._event("register:" + intent_id, "ENTRY_PLANNED", {"proposal": proposal, "authorization": authorization,
                        "exit_open": schedule["exit_open"], "calendar_hash": canonical_digest(calendar)}, at)
        return self.get_intent(intent_id)

    def begin_attempt(self, intent_id: str, attempt_id: str, now: Any, *,
                      authorization_verifier: Callable[[dict, dict, datetime], bool] | None = None) -> dict:
        """Record an attempt BEFORE a hypothetical submission; never submits it."""
        at, attempt_id = _stamp(now, "now"), _text(attempt_id, "attempt_id")
        with self._transaction():
            kind, row = self._intent(intent_id)
            old = self.db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
            if old:
                if old["intent_id"] != intent_id:
                    raise LedgerError("Attempt ID reused for a different intent")
                return dict(old, created=False, dispatch_allowed=False, broker_writes=False)
            if row["state"] not in ("PLANNED", "RECONCILED"):
                raise LedgerError("No retry before complete reconciliation; intent is pending, unknown or finished")
            if kind == "ENTRY":
                proposal = json.loads(row["proposal"])
                authorization = json.loads(row["authorization"])
                if not callable(authorization_verifier) or authorization_verifier(proposal, authorization, at) is not True:
                    raise LedgerError("Every entry attempt needs fresh external permission verification")
                if not _stamp(authorization["checked_at"], "checked_at") <= at < _stamp(authorization["valid_until"], "valid_until"):
                    raise LedgerError("Entry-attempt review has expired")
                cutoff = _stamp(proposal["entry_cutoff"], "entry_cutoff")
                if not max(_stamp(proposal["entry_not_before"], "entry_not_before"), cutoff - timedelta(minutes=4)) <= at < cutoff:
                    raise LedgerError("Entry attempt is outside its original cutoff")
                if row["state"] == "RECONCILED":
                    self._fresh_reconciliation(row["account_id"], row["strategy_id"], at)
                self._check_reservations_for_attempt(row, proposal, at)
                quantity = Decimal(row["quantity"]) - Decimal(row["bought"])
            else:
                position = self.db.execute("SELECT * FROM positions WHERE account_id=? AND mode=? AND position_id=?",
                                           (row["account_id"], "SHADOW", row["position_id"])).fetchone()
                if at < _stamp(position["exit_open"], "exit_open"):
                    raise LedgerError("Exit is not due at the next regular opening yet")
                self._fresh_reconciliation(row["account_id"], position["strategy_id"], at)
                quantity = Decimal(position["quantity"])
            if quantity <= 0:
                raise LedgerError("No remaining approved/owned quantity")
            self.db.execute("INSERT INTO attempts VALUES(?,?,?,?,?,NULL,'SUBMITTING',?)",
                             (attempt_id, intent_id, kind, str(quantity), at.isoformat(), at.isoformat()))
            table = "entries" if kind == "ENTRY" else "exits"
            self.db.execute(f"UPDATE {table} SET state='SUBMITTING' WHERE intent_id=?", (intent_id,))
            self._event("attempt:" + attempt_id, "ATTEMPT_RECORDED", {"intent_id": intent_id, "attempt_id": attempt_id,
                        "kind": kind, "quantity": str(quantity)}, at)
        return dict(self.db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone(), created=True, dispatch_allowed=False, broker_writes=False)

    def record_accepted(self, attempt_id: str, order_id: str, now: Any) -> dict:
        """Accepted is a status only: this method never creates a position."""
        at, order_id = _stamp(now, "now"), _text(order_id, "order_id")
        with self._transaction():
            attempt = self.db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
            if not attempt:
                raise LedgerError("Unknown attempt")
            if at < _stamp(attempt["started_at"], "attempt.started_at"):
                raise LedgerError("Acceptance precedes its attempt")
            if attempt["order_id"] is not None:
                if attempt["order_id"] != order_id:
                    raise LedgerError("Attempt mapped to a conflicting order ID")
                return dict(attempt)
            if attempt["state"] != "SUBMITTING":
                raise LedgerError("Unknown/cancelled attempts require reconciliation before acceptance updates")
            _, row = self._intent(attempt["intent_id"])
            collision = self.db.execute("SELECT a.* FROM attempts a LEFT JOIN entries e ON a.intent_id=e.intent_id LEFT JOIN exits x ON a.intent_id=x.intent_id WHERE a.order_id=? AND COALESCE(e.account_id,x.account_id)=?",
                                        (order_id, row["account_id"])).fetchone()
            if collision:
                raise LedgerError("Order ID already belongs to another attempt")
            self.db.execute("UPDATE attempts SET order_id=?,state='SUBMITTED',updated_at=? WHERE attempt_id=?",
                             (order_id, at.isoformat(), attempt_id))
            table = "entries" if attempt["kind"] == "ENTRY" else "exits"
            self.db.execute(f"UPDATE {table} SET state='SUBMITTED' WHERE intent_id=?", (attempt["intent_id"],))
            self._event("accepted:" + attempt_id, "ACCEPTED_NOT_FILLED", {"attempt_id": attempt_id, "order_id": order_id}, at)
        return dict(self.db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone())

    def mark_unknown(self, attempt_id: str, now: Any, reason: str) -> None:
        at, reason = _stamp(now, "now"), _text(reason, "reason")
        with self._transaction():
            attempt = self.db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
            if not attempt or attempt["state"] not in ("SUBMITTING", "SUBMITTED", "PARTIAL", "UNKNOWN"):
                raise LedgerError("Only a pending attempt can become UNKNOWN")
            if at < _stamp(attempt["updated_at"], "attempt.updated_at"):
                raise LedgerError("Unknown observation is stale")
            self.db.execute("UPDATE attempts SET state='UNKNOWN',updated_at=? WHERE attempt_id=?", (at.isoformat(), attempt_id))
            table = "entries" if attempt["kind"] == "ENTRY" else "exits"
            self.db.execute(f"UPDATE {table} SET state='UNKNOWN' WHERE intent_id=?", (attempt["intent_id"],))
            self._event("unknown:" + attempt_id + ":" + at.isoformat(), "UNKNOWN_RECONCILE_BEFORE_RETRY", {"attempt_id": attempt_id, "reason": reason}, at)

    def record_fill(self, fill: dict, now: Any) -> dict:
        """Append an explicit supplied simulated fill, never inferred execution."""
        if not isinstance(fill, dict):
            raise LedgerError("fill: object required")
        at = _stamp(now, "now")
        for key in ("fill_id", "intent_id", "position_id", "account_id", "strategy_id", "instrument_id"):
            _text(fill.get(key), "fill." + key)
        if fill.get("mode") != "SHADOW" or fill.get("currency") != "USD" or fill.get("side") not in ("BUY", "SELL"):
            raise LedgerError("SHADOW USD BUY/SELL fill required")
        if "sequence" in fill:
            raise LedgerError("The ledger assigns its own persistent fill sequence")
        quantity = _number(fill.get("quantity"), "fill.quantity", positive=True)
        price = _number(fill.get("price"), "fill.price", positive=True)
        filled_at = _stamp(fill.get("filled_at"), "fill.filled_at")
        if filled_at > at:
            raise LedgerError("Future-dated fill")
        encoded = _json(fill)
        with self._transaction():
            old = self.db.execute("SELECT * FROM fills WHERE account_id=? AND mode='SHADOW' AND fill_id=?", (fill["account_id"], fill["fill_id"])).fetchone()
            if old:
                if old["payload"] != encoded:
                    raise LedgerError("Fill ID reused with conflicting content")
                return dict(fill, sequence=old["sequence"])
            kind, intent = self._intent(fill["intent_id"])
            entry = intent if kind == "ENTRY" else self._intent(intent["entry_intent_id"])[1]
            for key in ("account_id", "strategy_id", "instrument_id"):
                if fill[key] != entry[key]:
                    raise LedgerError("Fill ownership does not match the exact recorded intent")
            if (kind == "ENTRY") != (fill["side"] == "BUY"):
                raise LedgerError("Fill side does not match intent kind")
            attempts = self.db.execute("SELECT * FROM attempts WHERE intent_id=? ORDER BY started_at", (fill["intent_id"],)).fetchall()
            if not attempts or filled_at < _stamp(attempts[0]["started_at"], "attempt.started_at"):
                raise LedgerError("A recorded attempt must precede a fill")
            position = self.db.execute("SELECT * FROM positions WHERE account_id=? AND mode='SHADOW' AND position_id=?", (fill["account_id"], fill["position_id"])).fetchone()
            if kind == "ENTRY":
                proposal = json.loads(entry["proposal"])
                exception = (Decimal(entry["bought"]) + quantity > Decimal(entry["quantity"])
                             or price > Decimal(entry["price_limit"])
                             or filled_at >= _stamp(proposal["entry_cutoff"], "entry_cutoff"))
                if exception:
                    # Preserve the owned facts/exit obligation, never pretend an
                    # out-of-policy fill did not occur. This is an incident.
                    reason = "Supplied BUY exceeds approved quantity/price/window"
                    self.db.execute("INSERT INTO control_exceptions VALUES(?,?,?,?)",
                                     (fill["account_id"] + ":" + fill["fill_id"], entry["intent_id"], reason, at.isoformat()))
                    self._event("exception:" + fill["account_id"] + ":" + fill["fill_id"], "CONTROL_EXCEPTION_NEW_ENTRIES_BLOCKED", {"fill_id": fill["fill_id"], "reason": reason}, at)
                if position and position["entry_intent_id"] != entry["intent_id"]:
                    raise LedgerError("Position ID already belongs to another entry")
                if position:
                    remaining, bought = Decimal(position["quantity"]) + quantity, Decimal(position["bought"]) + quantity
                    self.db.execute("UPDATE positions SET quantity=?,bought=? WHERE account_id=? AND mode='SHADOW' AND position_id=?", (str(remaining), str(bought), fill["account_id"], fill["position_id"]))
                else:
                    self.db.execute("INSERT INTO positions VALUES(?,'SHADOW',?,?,?,?,?,?,'0',?,?)", (fill["account_id"], fill["position_id"], fill["strategy_id"], fill["instrument_id"], entry["intent_id"], str(quantity), str(quantity), entry["exit_open"], entry["exit_session"]))
                exit_row = self.db.execute("SELECT * FROM exits WHERE account_id=? AND mode='SHADOW' AND position_id=?",
                                           (fill["account_id"], fill["position_id"])).fetchone()
                if exit_row:
                    # A late entry fill adds an owned obligation even when an
                    # earlier partial position was already sold at the opening.
                    self.db.execute("UPDATE exits SET quantity=?,state=? WHERE intent_id=?",
                                     (str(Decimal(exit_row["quantity"]) + quantity),
                                      "PLANNED" if exit_row["state"] == "FILLED" else exit_row["state"], exit_row["intent_id"]))
                bought = Decimal(entry["bought"]) + quantity
                state = "UNKNOWN" if exception or entry["state"] == "UNKNOWN" else ("FILLED" if bought == Decimal(entry["quantity"]) else "PARTIAL")
                self.db.execute("UPDATE entries SET bought=?,state=? WHERE intent_id=?", (str(bought), state, entry["intent_id"]))
            else:
                if not position or fill["position_id"] != intent["position_id"]:
                    raise LedgerError("Sell cannot adopt or close an unrelated position")
                if filled_at < _stamp(position["exit_open"], "position.exit_open"):
                    raise LedgerError("Supplied exit fill precedes its obligated next opening")
                if quantity > Decimal(position["quantity"]):
                    raise LedgerError("Sell exceeds exact owned remaining shares")
                remaining = Decimal(position["quantity"]) - quantity
                sold = Decimal(position["sold"]) + quantity
                self.db.execute("UPDATE positions SET quantity=?,sold=? WHERE account_id=? AND mode='SHADOW' AND position_id=?", (str(remaining), str(sold), fill["account_id"], fill["position_id"]))
                state = "UNKNOWN" if intent["state"] == "UNKNOWN" else ("FILLED" if not remaining else "PARTIAL")
                self.db.execute("UPDATE exits SET sold=?,state=? WHERE intent_id=?", (str(Decimal(intent["sold"]) + quantity), state, intent["intent_id"]))
            # Do not turn UNKNOWN into permission to retry merely because one
            # partial fill arrived. All attempts still require reconciliation.
            if state == "FILLED":
                self.db.execute("UPDATE attempts SET state='FILLED',updated_at=? WHERE intent_id=? AND state IN ('SUBMITTING','SUBMITTED','PARTIAL','UNKNOWN')", (at.isoformat(), fill["intent_id"]))
            sequence = self._event("fill:" + fill["account_id"] + ":" + fill["fill_id"], "SUPPLIED_SHADOW_FILL", fill, at)
            self.db.execute("INSERT INTO fills VALUES(?,'SHADOW',?,?,?,?,?,?)", (fill["account_id"], fill["fill_id"], fill["intent_id"], fill["position_id"], fill["side"], encoded, sequence))
        return dict(fill, sequence=sequence)

    def positions(self, account_id: str | None = None) -> list[dict]:
        if account_id is None:
            rows = self.db.execute("SELECT * FROM positions ORDER BY account_id,position_id")
        else:
            rows = self.db.execute("SELECT * FROM positions WHERE account_id=? ORDER BY position_id", (account_id,))
        return [dict(row) for row in rows]

    def fills(self, position_id: str | None = None) -> list[dict]:
        rows = self.db.execute("SELECT * FROM fills ORDER BY sequence") if position_id is None else self.db.execute("SELECT * FROM fills WHERE position_id=? ORDER BY sequence", (position_id,))
        return [dict(json.loads(row["payload"]), sequence=row["sequence"]) for row in rows]

    def due_exits(self, now: Any) -> list[dict]:
        at = _stamp(now, "now")
        return [dict(row, obligation="NEXT_REGULAR_OPENING", overdue=at > _stamp(row["exit_open"], "exit_open"))
                for row in self.db.execute("SELECT * FROM positions ORDER BY exit_open,position_id")
                if Decimal(row["quantity"]) > 0 and _stamp(row["exit_open"], "exit_open") <= at]

    def plan_exit(self, account_id: str, position_id: str, now: Any) -> dict:
        """One durable exit intent per owned position; review failure cannot erase it."""
        at = _stamp(now, "now")
        with self._transaction():
            position = self.db.execute("SELECT * FROM positions WHERE account_id=? AND mode='SHADOW' AND position_id=?", (account_id, position_id)).fetchone()
            if not position or Decimal(position["quantity"]) <= 0:
                raise LedgerError("No exact owned remaining position")
            if at < _stamp(position["exit_open"], "exit_open"):
                raise LedgerError("Exit obligation is not due yet")
            old = self.db.execute("SELECT * FROM exits WHERE account_id=? AND mode='SHADOW' AND position_id=?", (account_id, position_id)).fetchone()
            if old:
                return self.get_intent(old["intent_id"])
            intent_id = "exit-" + canonical_digest([account_id, "SHADOW", position_id, position["entry_intent_id"]])
            self.db.execute("INSERT INTO exits VALUES(?,?,'SHADOW',?,?,?,'0','PLANNED',?)", (intent_id, account_id, position_id, position["entry_intent_id"], position["quantity"], at.isoformat()))
            self._event("plan:" + intent_id, "OWNED_EXIT_PLANNED", {"intent_id": intent_id, "account_id": account_id,
                        "position_id": position_id, "quantity": position["quantity"], "exit_open": position["exit_open"]}, at)
        return self.get_intent(intent_id)

    def record_halt(self, account_id: str, position_id: str, now: Any, reason: str) -> None:
        at, reason = _stamp(now, "now"), _text(reason, "reason")
        with self._transaction():
            position = self.db.execute("SELECT * FROM positions WHERE account_id=? AND mode='SHADOW' AND position_id=?", (account_id, position_id)).fetchone()
            if not position or Decimal(position["quantity"]) <= 0:
                raise LedgerError("Halt does not identify an owned remaining position")
            self._event("halt:" + account_id + ":" + position_id + ":" + at.isoformat(), "HALT_EXIT_OBLIGATION_REMAINS", {"account_id": account_id, "position_id": position_id, "reason": reason}, at)

    def reconcile(self, snapshot: dict, now: Any) -> dict:
        """Complete orders/fills/positions evidence is necessary before retry.

        The supplied adapter must scope fill_ids to this strategy's known intents;
        unrelated account positions/orders may be present and are never adopted.
        Unknown own fills must be recorded explicitly before retry is permitted.
        """
        if not isinstance(snapshot, dict) or snapshot.get("mode") != "SHADOW":
            raise LedgerError("SHADOW reconciliation object required")
        at = _stamp(now, "now")
        observed = _stamp(snapshot.get("observed_at"), "snapshot.observed_at")
        if not at - timedelta(seconds=60) <= observed <= at:
            raise LedgerError("Stale or future reconciliation snapshot")
        for key in ("reconciliation_id", "account_id", "strategy_id", "source"):
            _text(snapshot.get(key), "snapshot." + key)
        for key in ("orders_complete", "fills_complete", "positions_complete"):
            if snapshot.get(key) is not True:
                raise LedgerError("Retry requires complete orders, fills and positions evidence")
        for key in ("fill_ids", "orders", "positions"):
            if not isinstance(snapshot.get(key), list):
                raise LedgerError("snapshot." + key + ": array required")
        if len(snapshot["fill_ids"]) != len(set(snapshot["fill_ids"])):
            raise LedgerError("Duplicate snapshot fill IDs")
        conflict = None
        with self._transaction():
            # Keep conflict persistence atomic with validation: a rejected
            # snapshot cannot leave PLANNED permission available after restart.
            self.db.execute("SAVEPOINT supplied_reconciliation")
            try:
                result = self._reconcile_snapshot(snapshot, at, observed)
                self.db.execute("RELEASE supplied_reconciliation")
            except _ReconciliationConflict as exc:
                self.db.execute("ROLLBACK TO supplied_reconciliation")
                self.db.execute("RELEASE supplied_reconciliation")
                kind, intent = self._intent(exc.intent_id)
                entry_id = intent["intent_id"] if kind == "ENTRY" else intent["entry_intent_id"]
                incident_id = "reconciliation-conflict-" + canonical_digest(
                    [snapshot["reconciliation_id"], canonical_digest(snapshot), exc.intent_id, str(exc)])
                self.db.execute("INSERT OR IGNORE INTO control_exceptions VALUES(?,?,?,?)",
                                (incident_id, entry_id, str(exc), at.isoformat()))
                table = "entries" if kind == "ENTRY" else "exits"
                self.db.execute(f"UPDATE {table} SET state='UNKNOWN' WHERE intent_id=?", (exc.intent_id,))
                self._event(incident_id, "RECONCILIATION_CONFLICT_NEW_ENTRIES_BLOCKED",
                            {"intent_id": exc.intent_id, "reason": str(exc),
                             "snapshot_digest": canonical_digest(snapshot), "snapshot": snapshot}, at)
                conflict = exc
        if conflict is not None:
            raise LedgerError(str(conflict))
        return result

    def _validate_filled_orders(self, intent_id: str, table: str, intent, attempts, orders) -> None:
        """Do not turn a contradictory FILLED status into retry permission.

        Each retry requests all then-remaining units. Fill event sequences, rather
        than timestamp order, prevent an old partial fill from covering a later
        retry, including attempts sharing a clock timestamp. Per-order fill
        authentication still belongs to the normalized source adapter.
        """
        filled = []
        for attempt in attempts:
            order = orders.get(attempt["order_id"])
            if order is None or order["status"] != "FILLED":
                continue
            event = self.db.execute("SELECT sequence FROM events WHERE event_key=?",
                                    ("attempt:" + attempt["attempt_id"],)).fetchone()
            if event is None:
                raise _ReconciliationConflict("FILLED order has no durable attempt event", intent_id)
            filled.append((event["sequence"], Decimal(attempt["quantity"])))
        if not filled:
            return
        if table == "entries" and Decimal(intent["bought"]) < Decimal(intent["quantity"]):
            raise _ReconciliationConflict("FILLED entry order contradicts incomplete recorded fills", intent_id)
        side = "BUY" if table == "entries" else "SELL"
        facts = [(row["sequence"], Decimal(json.loads(row["payload"])["quantity"]))
                 for row in self.db.execute("SELECT sequence,payload FROM fills WHERE intent_id=? AND side=?",
                                            (intent_id, side))]
        for boundary, _ in filled:
            required = sum((quantity for sequence, quantity in filled if sequence >= boundary), Decimal(0))
            supplied = sum((quantity for sequence, quantity in facts if sequence > boundary), Decimal(0))
            if supplied < required:
                raise _ReconciliationConflict("FILLED order contradicts its durable post-attempt fill evidence", intent_id)

    def _reconcile_snapshot(self, snapshot: dict, at: datetime, observed: datetime) -> dict:
        entries = self.db.execute("SELECT * FROM entries WHERE account_id=? AND strategy_id=?", (snapshot["account_id"], snapshot["strategy_id"])).fetchall()
        owned_intents = {row["intent_id"]: ("entries", row) for row in entries}
        for entry in entries:
            for row in self.db.execute("SELECT * FROM exits WHERE entry_intent_id=?", (entry["intent_id"],)):
                owned_intents[row["intent_id"]] = ("exits", row)
        orders = {}
        for row in snapshot["orders"]:
            if not isinstance(row, dict):
                raise LedgerError("snapshot order: object required")
            intent_id, order_id = _text(row.get("intent_id"), "snapshot.order.intent_id"), _text(row.get("order_id"), "snapshot.order.order_id")
            if intent_id not in owned_intents:
                if row.get("strategy_id") == snapshot["strategy_id"]:
                    raise LedgerError("Unrecognized order claims this strategy; reconcile before retry")
                continue
            if order_id in orders:
                raise LedgerError("Duplicate snapshot order IDs")
            if row.get("status") not in ("OPEN", "CANCELLED", "FILLED", "REJECTED"):
                raise LedgerError("Unknown order status cannot authorize retry")
            remaining = _number(row.get("remaining_quantity"), "order.remaining_quantity")
            if (row["status"] == "OPEN") != (remaining > 0):
                raise LedgerError("Order status/remaining quantity conflict")
            orders[order_id] = row
        # An unexpected own order is an incident even if other snapshot
        # sections contain unknown or contradictory fills/positions.
        for intent_id in owned_intents:
            if (any(row["intent_id"] == intent_id for row in orders.values())
                    and self.db.execute("SELECT 1 FROM attempts WHERE intent_id=?", (intent_id,)).fetchone() is None):
                raise _ReconciliationConflict("Own order has no recorded attempt", intent_id)
        old = self.db.execute("SELECT * FROM reconciliations WHERE reconciliation_id=?", (snapshot["reconciliation_id"],)).fetchone()
        if old:
            if old["payload"] != _json(snapshot):
                raise LedgerError("Reconciliation ID reused with conflicting content")
            return {"status": "RECONCILED", "reconciliation_id": snapshot["reconciliation_id"], "idempotent": True}
        known_positions = self.db.execute("SELECT * FROM positions WHERE account_id=? AND strategy_id=?", (snapshot["account_id"], snapshot["strategy_id"])).fetchall()
        supplied_positions = {}
        for row in snapshot["positions"]:
            if not isinstance(row, dict):
                raise LedgerError("snapshot position: object required")
            position_id = _text(row.get("position_id"), "snapshot.position_id")
            _text(row.get("instrument_id"), "snapshot.instrument_id")
            _number(row.get("quantity"), "snapshot.position.quantity")
            if position_id in supplied_positions:
                raise LedgerError("Duplicate snapshot position IDs")
            supplied_positions[position_id] = row
        for position in known_positions:
            supplied = supplied_positions.get(position["position_id"])
            actual = Decimal(0) if supplied is None else _number(supplied["quantity"], "snapshot.position.quantity")
            if actual != Decimal(position["quantity"]) or (supplied is not None and supplied["instrument_id"] != position["instrument_id"]):
                raise LedgerError("Owned position mismatch: reconcile explicit missing fills before retry")
        known_fills = {row["fill_id"] for row in self.db.execute("SELECT f.* FROM fills f JOIN entries e ON (f.intent_id=e.intent_id) OR f.intent_id IN (SELECT intent_id FROM exits WHERE entry_intent_id=e.intent_id) WHERE f.account_id=? AND e.strategy_id=?", (snapshot["account_id"], snapshot["strategy_id"]))}
        if set(snapshot["fill_ids"]) != known_fills:
            raise LedgerError("Snapshot fill history differs: record missing/contradictory fills before retry")
        if any(_stamp(row["filled_at"], "fill.filled_at") > observed for row in self.fills()
               if row["account_id"] == snapshot["account_id"] and row["strategy_id"] == snapshot["strategy_id"]):
            raise LedgerError("Snapshot predates a recorded fill")
        for intent_id, (table, intent) in owned_intents.items():
            attempts = self.db.execute("SELECT * FROM attempts WHERE intent_id=?", (intent_id,)).fetchall()
            if not attempts:
                continue
            if observed < max(_stamp(row["updated_at"], "attempt.updated_at") for row in attempts):
                raise LedgerError("Snapshot predates the latest attempt/unknown event")
            for attempt in attempts:
                if attempt["order_id"] is not None and attempt["order_id"] not in orders:
                    raise LedgerError("Snapshot omits an accepted order's final/open state")
                if attempt["order_id"] in orders and orders[attempt["order_id"]]["intent_id"] != intent_id:
                    raise LedgerError("Order/intent mapping conflict")
            own_orders = [row for row in orders.values() if row["intent_id"] == intent_id]
            unmapped_orders = [row for row in own_orders if row["order_id"] not in {a["order_id"] for a in attempts}]
            unmapped_attempts = [row for row in attempts if row["order_id"] is None]
            if unmapped_orders:
                if len(unmapped_orders) != 1 or len(unmapped_attempts) != 1:
                    raise LedgerError("Cannot unambiguously reconcile unknown order/attempt mapping")
                self.db.execute("UPDATE attempts SET order_id=? WHERE attempt_id=?",
                                 (unmapped_orders[0]["order_id"], unmapped_attempts[0]["attempt_id"]))
                attempts = self.db.execute("SELECT * FROM attempts WHERE intent_id=?", (intent_id,)).fetchall()
            self._validate_filled_orders(intent_id, table, intent, attempts, orders)
            open_units = sum((_number(row["remaining_quantity"], "remaining_quantity") for row in own_orders if row["status"] == "OPEN"), Decimal(0))
            if table == "entries":
                remaining = max(Decimal(intent["quantity"]) - Decimal(intent["bought"]), Decimal(0))
            else:
                remaining = Decimal(self.db.execute("SELECT quantity FROM positions WHERE account_id=? AND mode='SHADOW' AND position_id=?", (intent["account_id"], intent["position_id"])).fetchone()[0])
            if open_units > remaining:
                raise LedgerError("Open orders exceed approved/owned remaining quantity")
            state = "FILLED" if not remaining else ("SUBMITTED" if open_units else "RECONCILED")
            # An explicitly abandoned entry never becomes retryable again.
            if table == "entries" and intent["state"] == "CANCELLED":
                state = "CANCELLED"
            self.db.execute(f"UPDATE {table} SET state=? WHERE intent_id=?", (state, intent_id))
            for attempt in attempts:
                order = orders.get(attempt["order_id"])
                if order is None:
                    # No assigned order ID after timeout: authoritative all-
                    # orders/fills/positions evidence may show no submission.
                    attempt_state = "RECONCILED"
                else:
                    attempt_state = "SUBMITTED" if order["status"] == "OPEN" else order["status"]
                self.db.execute("UPDATE attempts SET state=?,updated_at=? WHERE attempt_id=?", (attempt_state, observed.isoformat(), attempt["attempt_id"]))
        self.db.execute("INSERT INTO reconciliations VALUES(?,?,?,?,?)", (snapshot["reconciliation_id"], snapshot["account_id"], snapshot["strategy_id"], observed.isoformat(), _json(snapshot)))
        self._event("reconcile:" + snapshot["reconciliation_id"], "COMPLETE_SUPPLIED_RECONCILIATION", snapshot, at)
        return {"status": "RECONCILED", "reconciliation_id": snapshot["reconciliation_id"], "idempotent": False}

    def abandon_entry(self, intent_id: str, now: Any, reason: str) -> None:
        """Release unfilled reservation only when no unresolved attempt remains."""
        at, reason = _stamp(now, "now"), _text(reason, "reason")
        with self._transaction():
            kind, row = self._intent(intent_id)
            if kind != "ENTRY" or row["state"] not in ("PLANNED", "RECONCILED", "CANCELLED"):
                raise LedgerError("Reconcile pending/unknown orders before abandoning an entry")
            self.db.execute("UPDATE entries SET state='CANCELLED' WHERE intent_id=?", (intent_id,))
            self._event("abandon:" + intent_id, "UNFILLED_ENTRY_ABANDONED_EXIT_REMAINS", {"intent_id": intent_id, "reason": reason}, at)

    def event_log(self) -> list[dict]:
        return [dict(row, payload=json.loads(row["payload"])) for row in self.db.execute("SELECT * FROM events ORDER BY sequence")]
