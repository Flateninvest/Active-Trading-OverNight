"""Deterministic weekly state machine. All supported execution is PAPER.

Immutable weekly decisions; atomic SQLite events and client IDs; acknowledgements
do not create positions. Exits are tied to recorded strategy-owned position IDs.
"""
from __future__ import annotations
import hashlib
import json
import math
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from .calendar import NY, aware, entry_allowed, is_session, schedule, session
from .broker import COST_KEYS, PENDING, TERMINAL, PaperBroker

EPS = 1e-8
QUOTE_AUDIT_FIELDS = ("instrument_id", "bid", "ask", "as_of", "realtime", "settlement_type", "leverage",
                      "entry_eligible", "close_eligible", "event_gate_clear", "same_position_preopen_close_verified",
                      "monday_reference_close", "reference_date", "sma20")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class WeeklyEngine:
    def __init__(self, database, config, market=None):
        if config.get("mode") != "paper" or config.get("live_enabled") is not False:
            raise PermissionError("This implementation supports paper execution only")
        if config.get("outer_limits_enabled") or config["maximum_name_weight"] > .10 or \
                config["maximum_gross_weight"] > .30 or config["maximum_positions"] > 3:
            raise ValueError("Later-stage outer ceilings are not enabled in this pilot")
        if config["exit_mode"] not in ("A", "B"):
            raise ValueError("Exit mode must be A or B")
        if config.get("research_overlay_enabled") is False and config.get("evaluation_variant") != "weekly_flow_only":
            raise ValueError("Removing the research overlay requires an explicitly labelled flow-only evaluation variant")
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        self.config = config
        self.db = sqlite3.connect(str(database), timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS selections(week_start TEXT PRIMARY KEY,selection_hash TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS decisions(session_date TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS invalidations(selection_id TEXT NOT NULL,ticker TEXT NOT NULL,at TEXT NOT NULL,
            reason TEXT NOT NULL,PRIMARY KEY(selection_id,ticker));
        CREATE TABLE IF NOT EXISTS events(event_key TEXT PRIMARY KEY,at TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS orders(client_id TEXT PRIMARY KEY,action TEXT NOT NULL,ticker TEXT NOT NULL,
            instrument_id TEXT NOT NULL,position_id TEXT,session_date TEXT NOT NULL,phase TEXT NOT NULL,
            quantity REAL NOT NULL,status TEXT NOT NULL,accounted_quantity REAL NOT NULL DEFAULT 0,
            accounted_notional REAL NOT NULL DEFAULT 0,accounted_fees REAL NOT NULL DEFAULT 0,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS positions(position_id TEXT PRIMARY KEY,ticker TEXT NOT NULL,instrument_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL,quantity REAL NOT NULL,entry_price REAL NOT NULL,entry_session TEXT NOT NULL,
            regular_exit_at TEXT NOT NULL,preopen_exit_at TEXT NOT NULL,exit_mode TEXT NOT NULL,
            entry_fees REAL NOT NULL DEFAULT 0,realized_gross REAL NOT NULL DEFAULT 0,exit_fees REAL NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS fills(fill_id TEXT PRIMARY KEY,client_id TEXT NOT NULL,at TEXT NOT NULL,
            action TEXT NOT NULL,ticker TEXT NOT NULL,position_id TEXT NOT NULL,quantity REAL NOT NULL,
            price REAL NOT NULL,fee REAL NOT NULL,data_kind TEXT NOT NULL);
        """)
        existing = self.db.execute("SELECT value FROM meta WHERE key='config_hash'").fetchone()
        if existing and existing[0] != digest(config):
            self.db.close()
            raise ValueError("Configuration changed for persisted state; create a separately labelled evaluation database")
        self.db.execute("INSERT OR IGNORE INTO meta VALUES('config_hash',?)", (digest(config),))
        self.db.execute("INSERT OR IGNORE INTO meta VALUES('cash',?)", (str(config["pilot_equity_usd"]),))
        self.db.commit()
        self.broker = PaperBroker(self.db, market or {})
        self.db.commit()

    def close(self):
        self.db.close()

    def load_selection(self, decision):
        candidates = decision.get("candidates", [])
        week = date.fromisoformat(decision["week_start"])
        cutoff = aware(decision["selection_cutoff"])
        if week.weekday() != 0 or len(candidates) > self.config["maximum_candidates"]:
            raise ValueError("Invalid weekly date or candidate count")
        if not week + timedelta(days=1) <= cutoff.astimezone(NY).date() <= week + timedelta(days=3):
            raise ValueError("Selection must be available Tue--Thu of its declared week")
        symbols = [c["ticker"] for c in candidates]
        if len(symbols) != len(set(symbols)):
            raise ValueError("Duplicate candidate ticker")
        for candidate in candidates:
            available = candidate.get("source_available_at")
            if available is not None and aware(available) > cutoff:
                raise ValueError("Candidate source became available after the selection cutoff")
            last = date.fromisoformat(candidate["last_eligible_entry"]) if candidate.get("last_eligible_entry") else None
            if last is not None and not week + timedelta(days=1) <= last <= week + timedelta(days=3):
                raise ValueError("Last eligible entry must lie in the declared Tue--Thu week")
        selection_hash = digest(decision)
        with self.db:
            old = self.db.execute("SELECT selection_hash FROM selections WHERE week_start=?", (week.isoformat(),)).fetchone()
            if old and old[0] != selection_hash:
                raise ValueError("Weekly universe is immutable; later additions or edits require a separately labelled variant")
            self.db.execute("INSERT OR IGNORE INTO selections VALUES(?,?,?)",
                            (week.isoformat(), selection_hash, canonical(decision)))
        return selection_hash

    def _event(self, key, now, kind, payload):
        self.db.execute("INSERT OR IGNORE INTO events VALUES(?,?,?,?)", (key, now.isoformat(), kind, canonical(payload)))

    def _cash(self):
        return float(self.db.execute("SELECT value FROM meta WHERE key='cash'").fetchone()[0])

    def _set_cash(self, amount):
        self.db.execute("UPDATE meta SET value=? WHERE key='cash'", (str(amount),))

    def _owned(self):
        return list(self.db.execute("SELECT * FROM positions WHERE strategy_id=? AND quantity>? ORDER BY position_id",
                                    (self.config["strategy_id"], EPS)))

    def _pending(self, position_id=None, action=None):
        rows = list(self.db.execute("SELECT * FROM orders WHERE status IN ('INTENT','ACK','PARTIAL','UNKNOWN')"))
        return [row for row in rows if (position_id is None or row["position_id"] == position_id)
                and (action is None or row["action"] == action)]

    def _cost_reason(self):
        costs = self.broker.costs()
        if not isinstance(costs, dict) or costs.get("verified_or_paper_assumed") is not True:
            return "missing_cost_assumptions"
        if any(not number(costs.get(k)) or costs[k] < 0 for k in COST_KEYS):
            return "incomplete_or_invalid_cost_assumptions"
        return None

    def _quote_reason(self, ticker, instrument_id, now, entry=False, preopen=False):
        quote = self.broker.quote(ticker)
        if not isinstance(quote, dict):
            return "missing_quote"
        if str(quote.get("instrument_id")) != str(instrument_id):
            return "instrument_id_mismatch"
        if quote.get("realtime") is not True:
            return "delayed_or_unverified_quote"
        try:
            age = (now - aware(quote["as_of"])).total_seconds()
        except (KeyError, ValueError, TypeError):
            return "missing_or_invalid_quote_timestamp"
        if not 0 <= age <= self.config["maximum_quote_age_seconds"]:
            return "stale_or_future_quote"
        bid, ask = quote.get("bid"), quote.get("ask")
        if not number(bid) or not number(ask) or not 0 < bid <= ask:
            return "invalid_bid_ask"
        if entry:
            if (ask - bid) / ((ask + bid) / 2) * 1e4 > self.config["maximum_spread_bps"]:
                return "spread_above_proposed_limit"
            if quote.get("entry_eligible") is not True or quote.get("settlement_type") != "real":
                return "underlying_share_entry_eligibility_unverified"
            if quote.get("close_eligible") is not True or quote.get("event_gate_clear") is not True:
                return "planned_exit_or_event_review_unverified"
            if self.config["exit_mode"] == "B" and quote.get("same_position_preopen_close_verified") is not True:
                return "same_position_preopen_close_unverified_at_entry"
            if quote.get("leverage") != 1:
                return "leverage_not_one"
            reference = quote.get("monday_reference_close")
            try:
                refday = date.fromisoformat(quote["reference_date"])
            except (KeyError, ValueError, TypeError):
                return "missing_monday_reference"
            if refday.weekday() != 0 or not 0 <= (now.astimezone(NY).date() - refday).days <= self.config["maximum_reference_age_days"]:
                return "stale_or_invalid_monday_reference"
            if not number(reference) or reference <= 0:
                return "invalid_monday_reference"
            if abs(ask / reference - 1) > self.config["maximum_abs_change_from_monday_reference_close"]:
                return "price_moved_beyond_proposed_monday_band"
            if self.config["require_price_at_or_above_sma20"]:
                if not number(quote.get("sma20")) or quote["sma20"] <= 0 or ask < quote["sma20"]:
                    return "optional_sma20_check_failed"
        elif quote.get("close_eligible") is not True:
            return "position_close_eligibility_unverified"
        if preopen and quote.get("same_position_preopen_close_verified") is not True:
            return "same_position_preopen_close_unverified"
        return None

    def _account_reason(self, now):
        account = self.broker.account()
        risk = account.get("risk_score")
        if not number(risk) or not 1 <= risk <= 10:
            return "account_risk_score_missing"
        try:
            age = (now - aware(account["as_of"])).total_seconds()
        except (KeyError, TypeError, ValueError):
            return "account_timestamp_missing"
        if not 0 <= age <= self.config["maximum_quote_age_seconds"]:
            return "account_risk_snapshot_stale"
        if risk >= self.config["pause_entry_at_account_risk_score"]:
            return "account_risk_pause_proposal"
        if account.get("strategy_cash_verified") is not True:
            return "strategy_cash_not_verified"
        return None

    def _candidate_reason(self, candidate, selection, day, now):
        if aware(selection["selection_cutoff"]) > now:
            return "selection_not_yet_available"
        if candidate.get("source_available_at") is None:
            return "source_availability_unverified"
        if candidate.get("selection_source_availability_proven") is not True:
            return "selection_source_availability_unproven"
        if candidate.get("stock_identifier_verified") is not True:
            return "exact_stock_identity_unverified"
        if aware(candidate["source_available_at"]) > aware(selection["selection_cutoff"]):
            return "lookahead_source"
        if self.config.get("research_overlay_enabled", True) and candidate.get("thesis_active") is not True:
            return "thesis_not_validated_or_invalidated"
        if not self.config.get("research_overlay_enabled", True) and candidate.get("flow_gate_pass") is not True:
            return "flow_only_evaluation_requires_verified_numeric_flow_gates"
        if candidate.get("instrument_id") is None:
            return "exact_instrument_id_unverified"
        if candidate.get("last_eligible_entry") is None or day > date.fromisoformat(candidate["last_eligible_entry"]):
            return "last_eligible_entry_passed"
        # The evidence must remain active through the following regular opening.
        active = any(date.fromisoformat(expiry) >= day + timedelta(days=1)
                     for expiry in candidate.get("supporting_expiries", []))
        continuing = self.config.get("research_overlay_enabled", True) and candidate.get("continuing_thesis") is True and bool(candidate.get("continuing_thesis_evidence"))
        if not active and not continuing:
            return "supporting_options_expired_without_explicit_continuing_thesis"
        invalidated = self.broker.market.get("invalidated_candidates", [])
        if candidate["ticker"] in invalidated:
            self.db.execute("INSERT OR IGNORE INTO invalidations VALUES(?,?,?,?)",
                            (selection["selection_id"], candidate["ticker"], now.isoformat(), "explicit_thesis_invalidation"))
            self._event("invalidated:" + selection["selection_id"] + ":" + candidate["ticker"], now,
                        "WEEKLY_CANDIDATE_INVALIDATED", {"ticker": candidate["ticker"]})
        if self.db.execute("SELECT 1 FROM invalidations WHERE selection_id=? AND ticker=?",
                           (selection["selection_id"], candidate["ticker"])).fetchone():
            return "persisted_weekly_thesis_invalidation"
        return self._quote_reason(candidate["ticker"], candidate["instrument_id"], now, entry=True)

    def _record_snapshot_invalidations(self, selection, now):
        requested = set(self.broker.market.get("invalidated_candidates", []))
        for candidate in selection["candidates"]:
            if candidate["ticker"] in requested:
                self.db.execute("INSERT OR IGNORE INTO invalidations VALUES(?,?,?,?)",
                                (selection["selection_id"], candidate["ticker"], now.isoformat(), "explicit_thesis_invalidation"))
                self._event("invalidated:" + selection["selection_id"] + ":" + candidate["ticker"], now,
                            "WEEKLY_CANDIDATE_INVALIDATED", {"ticker": candidate["ticker"]})

    def _submit(self, client_id, action, ticker, instrument_id, quantity, price, position_id, day, phase, now):
        existing = self.db.execute("SELECT * FROM orders WHERE client_id=?", (client_id,)).fetchone()
        if existing:
            return
        request = {"quantity": quantity, "reference_price": price, "position_id": position_id,
                   "created_at": now.isoformat(), "data_kind": "SYNTHETIC_OPERATIONAL_FIXTURE",
                   "order_type": "SYNTHETIC_IOC_LIMIT" if action == "BUY" else "SYNTHETIC_POSITION_CLOSE",
                   "quote_snapshot": {key: (self.broker.quote(ticker) or {}).get(key) for key in QUOTE_AUDIT_FIELDS},
                   "cost_snapshot": {key: (self.broker.costs() or {}).get(key) for key in COST_KEYS}}
        self.db.execute("INSERT INTO orders(client_id,action,ticker,instrument_id,position_id,session_date,phase,quantity,status,payload) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?)", (client_id, action, ticker, str(instrument_id), position_id,
                          day.isoformat(), phase, quantity, "INTENT", canonical(request)))
        result = self.broker.submit(client_id, action, ticker, str(instrument_id), quantity, price, position_id, phase)
        self._apply_result(client_id, result, now)

    def _apply_result(self, client_id, result, now):
        order = self.db.execute("SELECT * FROM orders WHERE client_id=?", (client_id,)).fetchone()
        status = result.get("status", "UNKNOWN")
        qty = result.get("filled_quantity", 0)
        price = result.get("fill_price", 0)
        fees = result.get("cumulative_fees_usd", 0)
        request = json.loads(order["payload"])
        identity_bad = result.get("client_id") != client_id or result.get("ticker") != order["ticker"] or \
            str(result.get("instrument_id")) != order["instrument_id"] or result.get("action") != order["action"] or \
            (order["action"] == "SELL" and result.get("position_id") != order["position_id"])
        limit_bad = order["action"] == "BUY" and number(qty) and qty > EPS and \
            number(price) and price > request["reference_price"] + EPS
        ack_bad = status in {"INTENT", "ACK", "UNKNOWN", "REJECTED"} and number(qty) and qty > EPS
        if identity_bad or limit_bad or ack_bad:
            self.db.execute("UPDATE orders SET status='UNKNOWN' WHERE client_id=?", (client_id,))
            self._event("contract-mismatch:" + client_id, now, "RECONCILIATION_EXCEPTION",
                        {"reason": "order_identity_buy_limit_or_acknowledgement_mismatch", "result": result})
            return
        if status not in PENDING | TERMINAL or not number(qty) or not number(fees) or fees < 0 or \
                not order["accounted_quantity"] - EPS <= qty <= order["quantity"] + EPS or \
                (qty > 0 and (not number(price) or price <= 0)) or fees < order["accounted_fees"] - EPS:
            self.db.execute("UPDATE orders SET status='UNKNOWN' WHERE client_id=?", (client_id,))
            self._event("bad-result:" + client_id, now, "RECONCILIATION_EXCEPTION", result)
            return
        if status == "FILLED" and abs(qty - order["quantity"]) > EPS:
            status = "UNKNOWN"  # a contradictory terminal acknowledgement is not a fill
        delta = qty - order["accounted_quantity"]
        fee_delta = fees - order["accounted_fees"]
        notional = qty * price
        notional_delta = notional - order["accounted_notional"]
        if delta > EPS:
            fill_price = notional_delta / delta
            pos_id = result.get("position_id")
            if not pos_id or fill_price <= 0:
                raise ValueError("Fill lacks exact position ID or valid incremental price")
            pos = self.db.execute("SELECT * FROM positions WHERE position_id=?", (pos_id,)).fetchone()
            if order["action"] == "BUY":
                if pos and pos["strategy_id"] != self.config["strategy_id"]:
                    raise ValueError("Broker attempted to merge a fill into an unrelated position")
                if pos:
                    newqty = pos["quantity"] + delta
                    avg = (pos["quantity"] * pos["entry_price"] + notional_delta) / newqty
                    self.db.execute("UPDATE positions SET quantity=?,entry_price=?,entry_fees=entry_fees+? WHERE position_id=?",
                                    (newqty, avg, fee_delta, pos_id))
                else:
                    times = schedule(date.fromisoformat(order["session_date"]), self.config)
                    self.db.execute("INSERT INTO positions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                        pos_id, order["ticker"], order["instrument_id"], self.config["strategy_id"], delta, fill_price,
                        order["session_date"], times["regular_exit_at"], times["preopen_exit_at"], self.config["exit_mode"],
                        fee_delta, 0.0, 0.0))
                self._set_cash(self._cash() - notional_delta - fee_delta)
            else:
                if not pos or pos["strategy_id"] != self.config["strategy_id"] or delta > pos["quantity"] + EPS:
                    raise ValueError("Cannot close an unowned position or sell more than remaining units")
                self.db.execute("UPDATE positions SET quantity=?,realized_gross=realized_gross+?,exit_fees=exit_fees+? WHERE position_id=?",
                                (max(0, pos["quantity"] - delta), delta * (fill_price - pos["entry_price"]), fee_delta, pos_id))
                self._set_cash(self._cash() + notional_delta - fee_delta)
            self.db.execute("INSERT INTO fills VALUES(?,?,?,?,?,?,?,?,?,?)", (
                client_id + ":" + str(qty), client_id, now.isoformat(), order["action"], order["ticker"], pos_id,
                delta, fill_price, fee_delta, "SYNTHETIC_OPERATIONAL_FIXTURE",))
            self.db.execute("UPDATE orders SET position_id=? WHERE client_id=?", (pos_id, client_id))
        elif abs(notional_delta) > EPS or fee_delta > EPS:
            # A price correction needs explicit bookkeeping; do not silently drop it.
            self.db.execute("UPDATE orders SET status='UNKNOWN' WHERE client_id=?", (client_id,))
            self._event("correction:" + client_id, now, "RECONCILIATION_EXCEPTION", result)
            return
        self.db.execute("UPDATE orders SET status=?,accounted_quantity=?,accounted_notional=?,accounted_fees=? WHERE client_id=?",
                        (status, qty, notional, fees, client_id))

    def _reconcile(self, now):
        for order in list(self.db.execute("SELECT * FROM orders")):
            self._apply_result(order["client_id"], self.broker.order_status(order["client_id"]), now)

    def _cancel_pending(self, now, position_id=None, action=None):
        for order in self._pending(position_id, action):
            if not self.broker.cancel(order["client_id"]):
                self._event("uncancelled:" + order["client_id"], now, "UNKNOWN_ORDER_BLOCKS_NEW_INTENT",
                            {"client_id": order["client_id"], "position_id": position_id})
                return False
            self._apply_result(order["client_id"], self.broker.order_status(order["client_id"]), now)
        return not self._pending(position_id, action)

    def _exits(self, now):
        for pos in self._owned():
            opening = aware(pos["regular_exit_at"])
            preopen = aware(pos["preopen_exit_at"])
            prephase = pos["exit_mode"] == "B" and preopen <= now < opening
            if not prephase and now < opening:
                continue
            phase = "PREOPEN" if prephase else "OPEN"
            # A pending entry fill must be cancelled/reconciled before closing its position.
            if not self._cancel_pending(now, pos["position_id"], "BUY"):
                continue
            if phase == "OPEN" and not self._cancel_pending(now, pos["position_id"], "SELL"):
                continue
            if self._pending(pos["position_id"], "SELL"):
                continue
            pos = self.db.execute("SELECT * FROM positions WHERE position_id=?", (pos["position_id"],)).fetchone()
            if pos["quantity"] <= EPS:
                continue
            key = "exit:" + pos["position_id"] + ":" + phase
            previous = self.db.execute("SELECT status FROM orders WHERE client_id=?", (key,)).fetchone()
            if previous:
                self._event("remaining:" + key, now, "EXIT_REMAINDER_REQUIRES_OPERATOR_REVIEW",
                            {"position_id": pos["position_id"], "remaining_quantity": pos["quantity"], "status": previous[0]})
                continue  # same phase never submits twice, including rejection; alert instead
            reason = self._quote_reason(pos["ticker"], pos["instrument_id"], now, preopen=prephase)
            if reason:
                self._event("exit-skip:" + key, now, "EXIT_EXCEPTION", {"reason": reason, "position_id": pos["position_id"]})
                continue
            if phase == "OPEN" and pos["exit_mode"] == "B":
                self._event("fallback:" + pos["position_id"], now, "PREOPEN_FALLBACK_TO_REGULAR_OPEN", {"remaining_quantity": pos["quantity"]})
            if self._cost_reason():
                self._event("cost-unknown:" + key, now, "EXIT_COST_UNVERIFIED",
                            {"reason": self._cost_reason(), "net_pnl_unverified": True})
            quote = self.broker.quote(pos["ticker"])
            self._submit(key, "SELL", pos["ticker"], pos["instrument_id"], pos["quantity"], quote["bid"],
                         pos["position_id"], date.fromisoformat(pos["entry_session"]), phase, now)

    def _decision(self, selection, day, now):
        good, rejected = [], []
        common = self._account_reason(now) or self._cost_reason()
        for candidate in sorted(selection["candidates"], key=lambda c: (c.get("rank", 999), c["ticker"])):
            reason = common or self._candidate_reason(candidate, selection, day, now)
            if reason:
                rejected.append({"ticker": candidate["ticker"], "reason": reason})
            else:
                good.append(candidate)
        decision = {"at": now.isoformat(), "selection_hash": digest(selection), "eligible": good, "rejected": rejected,
                    "data_kind": "SYNTHETIC_OPERATIONAL_FIXTURE", "action": "PAPER_REVIEW_ONLY",
                    "market_snapshot": {
                        "quotes": {c["ticker"]: {key: (self.broker.quote(c["ticker"]) or {}).get(key) for key in QUOTE_AUDIT_FIELDS}
                                   for c in selection["candidates"]},
                        "account": {key: self.broker.account().get(key) for key in ("risk_score", "as_of", "strategy_cash_verified")},
                        "costs": {key: (self.broker.costs() or {}).get(key) for key in COST_KEYS},
                        "input_data_kind": self.broker.market["data_kind"]}}
        self.db.execute("INSERT OR IGNORE INTO decisions VALUES(?,?)", (day.isoformat(), canonical(decision)))
        self._event("decision:" + day.isoformat(), now, "DAILY_DECISION", decision)

    def _entries(self, selection, day, now):
        if self._owned() or self._pending():
            self._event("blocked:" + day.isoformat(), now, "NEW_ENTRIES_BLOCKED_PENDING_POSITION_OR_ORDER", {})
            return
        frozen_row = self.db.execute("SELECT payload FROM decisions WHERE session_date=?", (day.isoformat(),)).fetchone()
        if not frozen_row:
            self._event("no-decision:" + day.isoformat(), now, "SKIP_ENTRY", {"reason": "missing_prior_daily_decision"})
            return
        frozen = json.loads(frozen_row[0])
        if frozen["selection_hash"] != digest(selection):
            raise ValueError("Frozen daily decision and weekly selection differ")
        common = self._account_reason(now) or self._cost_reason()
        if common:
            self._event("entry-skip:" + day.isoformat(), now, "SKIP_ENTRY", {"reason": common})
            return
        equity = self._cash()  # previous night's positions must be flat before new entries
        gross, count = 0.0, 0
        costs = sum(self.broker.costs()[key] for key in COST_KEYS)
        current_members = {c["ticker"]: c for c in selection["candidates"]}
        for frozen_candidate in frozen["eligible"][:self.config["maximum_positions"]]:
            candidate = current_members[frozen_candidate["ticker"]]
            key = "entry:" + selection["selection_id"] + ":" + day.isoformat() + ":" + candidate["ticker"]
            if self.db.execute("SELECT 1 FROM orders WHERE client_id=?", (key,)).fetchone():
                continue
            reason = self._candidate_reason(candidate, selection, day, now)
            if reason or count >= self.config["maximum_positions"]:
                self._event("entry-skip:" + key, now, "SKIP_ENTRY", {"ticker": candidate["ticker"], "reason": reason or "maximum_positions"})
                continue
            ask = self.broker.quote(candidate["ticker"])["ask"]
            budget = min(equity * self.config["maximum_name_weight"],
                         equity * self.config["maximum_gross_weight"] - gross,
                         self._cash())
            scale = 10 ** self.config["share_precision"]
            qty = math.floor(max(0, budget - costs) / ask * scale) / scale
            if qty * ask < self.config["minimum_paper_order_usd"]:
                self._event("entry-skip:" + key, now, "SKIP_ENTRY", {"reason": "cash_or_minimum_size"})
                continue
            self._submit(key, "BUY", candidate["ticker"], candidate["instrument_id"], qty, ask, None, day, "ENTRY", now)
            gross += qty * ask + costs  # reserve full request even for rejected/partial/unknown
            count += 1               # do not enlarge remaining allocations or fill a rejected slot

    def tick(self, now, market=None):
        now = aware(now)
        if market is not None:
            self.broker.market = market
        if self.broker.market.get("data_kind") not in {"SYNTHETIC_OPERATIONAL_FIXTURE", "OBSERVED_READ_ONLY"}:
            raise ValueError("Paper market input must declare its data provenance")
        try:
            self.db.execute("BEGIN IMMEDIATE")
            self._reconcile(now)
            self._exits(now)
            day = now.astimezone(NY).date()
            if is_session(day):
                opening, closing = session(day)
                if now >= closing:
                    self._cancel_pending(now, action="BUY")
                if entry_allowed(day):
                    week = day - timedelta(days=day.weekday())
                    row = self.db.execute("SELECT payload FROM selections WHERE week_start=?", (week.isoformat(),)).fetchone()
                    if row:
                        selection = json.loads(row[0])
                        self._record_snapshot_invalidations(selection, now)
                        times = schedule(day, self.config)
                        decision_at, entry_at = aware(times["decision_at"]), aware(times["entry_at"])
                        if decision_at <= now < entry_at and not self.db.execute("SELECT 1 FROM decisions WHERE session_date=?", (day.isoformat(),)).fetchone():
                            self._decision(selection, day, now)
                        if entry_at <= now <= entry_at + timedelta(seconds=self.config["maximum_entry_lateness_seconds"]):
                            self._entries(selection, day, now)
                    else:
                        self._event("missing-week:" + day.isoformat(), now, "SKIP_ENTRY", {"reason": "missing_weekly_selection"})
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.report()

    def report(self):
        positions = [dict(r) for r in self.db.execute("SELECT * FROM positions ORDER BY position_id")]
        strategy_positions = [p for p in positions if p["strategy_id"] == self.config["strategy_id"]]
        orders = [dict(r) for r in self.db.execute("SELECT * FROM orders ORDER BY client_id")]
        fills = [dict(r) for r in self.db.execute("SELECT * FROM fills ORDER BY at,fill_id")]
        events = [dict(r) for r in self.db.execute("SELECT * FROM events ORDER BY at,event_key")]
        gross = sum(p["realized_gross"] for p in strategy_positions)
        fees = sum(p["entry_fees"] + p["exit_fees"] for p in strategy_positions)
        costs_complete = not any(e["kind"] == "EXIT_COST_UNVERIFIED" for e in events)
        book_complete = costs_complete and not self._owned() and not self._pending()
        return {"revision": 12, "strategy_id": self.config["strategy_id"], "mode": "paper", "data_kind": "SYNTHETIC_OPERATIONAL_FIXTURE",
                "profitability_evidence": False, "cash_usd": self._cash(), "positions": positions,
                "orders": orders, "fills": fills, "events": events,
                "gross_realized_pnl_usd": gross, "recorded_cost_usd": fees,
                "costs_complete": costs_complete,
                "net_realized_pnl_usd": gross - fees if book_complete else None,
                "book_net_status": "complete_flat_fill_ledger" if book_complete else "unresolved_positions_orders_or_costs_no_complete_equity_claim",
                "decisions": [{"session_date": r["session_date"], **json.loads(r["payload"])}
                              for r in self.db.execute("SELECT * FROM decisions ORDER BY session_date")],
                "invalidations": [dict(r) for r in self.db.execute("SELECT * FROM invalidations ORDER BY at,ticker")],
                "pending_orders": len(self._pending()), "open_strategy_positions": len(self._owned()),
                "spread_cost_method": "already_in_ask_buy_bid_sell_fills_not_subtracted_again"}
