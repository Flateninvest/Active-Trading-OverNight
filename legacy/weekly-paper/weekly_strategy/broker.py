"""Broker contract and SQLite-persistent synthetic paper adapter.

There is deliberately no implementation of live submission. Paper acknowledgements
and executions are fixture values, never observations of broker execution.
"""
import json
from typing import Protocol

TERMINAL = {"FILLED", "REJECTED", "CANCELLED"}
PENDING = {"ACK", "PARTIAL", "UNKNOWN", "INTENT"}
COST_KEYS = ("commission_usd", "fx_usd", "financing_usd", "other_usd", "operating_usd")


class BrokerAdapter(Protocol):
    mode: str

    def quote(self, ticker: str) -> dict | None: ...
    def submit(self, client_id: str, action: str, ticker: str,
               instrument_id: str, quantity: float, price: float,
               position_id: str | None, phase: str) -> dict: ...
    def order_status(self, client_id: str) -> dict: ...
    def cancel(self, client_id: str) -> bool: ...


class LiveExecutionDisabled:
    mode = "live"

    def __init__(self, *args, **kwargs):
        raise PermissionError("No live or demo-broker writer is implemented in Revision 12")


class PaperBroker:
    mode = "paper"

    def __init__(self, connection, market):
        self.connection = connection
        self.market = market
        connection.execute("CREATE TABLE IF NOT EXISTS paper_broker_orders "
                           "(client_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def quote(self, ticker):
        return self.market.get("quotes", {}).get(ticker)

    def costs(self):
        return self.market.get("costs")

    def account(self):
        return self.market.get("account", {})

    def submit(self, client_id, action, ticker, instrument_id, quantity,
               price, position_id, phase):
        previous = self.connection.execute(
            "SELECT payload FROM paper_broker_orders WHERE client_id=?", (client_id,)).fetchone()
        if previous:
            return json.loads(previous[0])
        scenario = self.market.get("order_scenarios", {}).get(
            f"{action}:{ticker}:{phase}", self.market.get("order_scenarios", {}).get(action, {}))
        status = scenario.get("status", "FILLED")
        if status not in TERMINAL | PENDING:
            raise ValueError("Unsupported paper order status")
        fraction = scenario.get("fill_fraction", 1.0 if status == "FILLED" else
                                0.5 if status == "PARTIAL" else 0.0)
        if not 0 <= fraction <= 1:
            raise ValueError("Invalid paper fill fraction")
        fill_price = scenario.get("fill_price", price)
        # The PAPER buy model is an IOC limit at the observed ask, not a promise
        # that an unconstrained market order preserves a cash/name cap.
        limit_rejected = action == "BUY" and fill_price > price + 1e-8
        if limit_rejected:
            status, fraction = "REJECTED", 0.0
        fill_quantity = quantity * fraction
        fees = sum(float((self.costs() or {}).get(key, 0)) for key in COST_KEYS)
        result = {"client_id": client_id, "broker_order_id": "SYNTHETIC-ORDER-" + client_id,
                  "position_id": position_id or "SYNTHETIC-POSITION-" + client_id,
                  "status": status, "requested_quantity": quantity,
                  "filled_quantity": fill_quantity,
                  "fill_price": fill_price,
                  "order_type": "SYNTHETIC_IOC_LIMIT" if action == "BUY" else "SYNTHETIC_POSITION_CLOSE",
                  "rejection_reason": "price_above_paper_IOC_limit" if limit_rejected else None,
                  "cumulative_fees_usd": fees * fraction,
                  "cancel_confirmed": scenario.get("cancel_confirmed", True),
                  "data_kind": "SYNTHETIC_OPERATIONAL_FIXTURE",
                  "action": action, "ticker": ticker, "instrument_id": instrument_id,
                  "phase": phase}
        self.connection.execute("INSERT INTO paper_broker_orders VALUES (?,?)",
                                (client_id, json.dumps(result, sort_keys=True)))
        return result

    def order_status(self, client_id):
        row = self.connection.execute("SELECT payload FROM paper_broker_orders WHERE client_id=?",
                                      (client_id,)).fetchone()
        return json.loads(row[0]) if row else {"status": "UNKNOWN"}

    def cancel(self, client_id):
        result = self.order_status(client_id)
        if result["status"] in TERMINAL:
            return True
        if not result.get("cancel_confirmed", False) or result["status"] == "UNKNOWN":
            return False
        result["status"] = "CANCELLED"
        self.set_result(client_id, result)
        return True

    def set_result(self, client_id, result):
        """Test/replay reconciliation feed; never creates a real broker fill."""
        self.connection.execute("UPDATE paper_broker_orders SET payload=? WHERE client_id=?",
                                (json.dumps(result, sort_keys=True), client_id))
