"""Synthetic operational fixtures, never historical or expected profitability."""
from copy import deepcopy
from .calendar import aware


def synthetic_selection(overlay=True):
    names = ["AAPL", "GOOG", "MU"]
    candidates = [{"ticker": ticker, "instrument_id": "SYNTHETIC-" + ticker,
                   "rank": rank + 1, "thesis_active": True,
                   "stock_identifier_verified": True, "selection_source_availability_proven": True,
                   "flow_gate_pass": True,
                   "continuing_thesis": False, "supporting_expiries": ["2026-10-09"],
                   "last_eligible_entry": "2026-10-08", "source_available_at": "2026-10-06T06:00:00+00:00",
                   "research_overlay_permitted": ticker != "MU",
                   "thesis": "Invented fixture thesis for testing software, not an investment thesis"}
                  for rank, ticker in enumerate(names)]
    if overlay:
        candidates = [c for c in candidates if c["research_overlay_permitted"]]
    return {"selection_id": "SYNTHETIC-2026-10-05-" + ("OVERLAY" if overlay else "FLOW_ONLY"),
            "week_start": "2026-10-05", "selection_cutoff": "2026-10-06T06:15:00+00:00",
            "protocol": "SYNTHETIC_OPERATIONAL_FIXTURE", "data_kind": "SYNTHETIC_OPERATIONAL_FIXTURE",
            "source_manifest": [{"name": "invented fixtures", "sha256": None}],
            "candidates": candidates, "rejected": [{"ticker": "MU", "reason": "invented_overlay_rejection"}] if overlay else []}


def synthetic_market(at, phase="ENTRY"):
    at = aware(at).isoformat()
    base = {"AAPL": 100.0, "GOOG": 200.0, "MU": 150.0}
    prices = {"ENTRY": base,
              "PREOPEN": {"AAPL": 100.20, "GOOG": 199.60, "MU": 150.40},
              "OPEN": {"AAPL": 100.10, "GOOG": 199.80, "MU": 150.30}}
    quotes = {}
    for ticker, price in prices[phase].items():
        quotes[ticker] = {"instrument_id": "SYNTHETIC-" + ticker, "bid": price - .01,
                          "ask": price + .01, "as_of": at, "realtime": True,
                          "settlement_type": "real", "leverage": 1,
                          "entry_eligible": True, "close_eligible": True,
                          "event_gate_clear": True,
                          "same_position_preopen_close_verified": True,
                          "monday_reference_close": base[ticker], "reference_date": "2026-10-05"}
    return {"data_kind": "SYNTHETIC_OPERATIONAL_FIXTURE", "quotes": quotes,
            "account": {"risk_score": 3, "as_of": at, "strategy_cash_verified": True},
            "costs": {"commission_usd": 0.0, "fx_usd": 0.0, "financing_usd": 0.0,
                      "other_usd": 0.0, "operating_usd": 0.0, "verified_or_paper_assumed": True},
            "unrelated_core_positions": [{"position_id": "SYNTHETIC-CORE-PLTR", "ticker": "PLTR", "quantity": 100},
                                          {"position_id": "SYNTHETIC-CORE-RKLB", "ticker": "RKLB", "quantity": 100}]}
