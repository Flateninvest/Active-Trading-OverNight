"""Exercise the three offline controls together with invented facts only."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from active_trading.risk.review import (ReviewError, authorization_verifier,
    canonical_hash, review_proposal, sign_review)
from active_trading.operations import LedgerError, ShadowLedger
from active_trading.reporting import build_trade_report
from active_trading.jsonio import load_json


def run_demo():
    fixture = load_json(ROOT / "examples" / "shadow_review_fixture.json")
    policy = load_json(ROOT / "spec" / "strategy_spec.provisional.json")
    proposal, critic, calendar = fixture["proposal"], fixture["review"], fixture["calendar"]
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    proposal.update(spec_hash=canonical_hash(policy), calendar_hash=canonical_hash(calendar), code_commit=revision)
    critic["proposal_digest"] = canonical_hash(proposal)
    # Ephemeral fixture-only secret. There is no real reviewer service in this demo.
    key = secrets.token_bytes(32)
    critic = sign_review(critic, key)
    keys = {critic["reviewer_id"]: key}
    gate = review_proposal(proposal, critic, policy, reviewer_keys=keys, now=fixture["now"])
    verify = authorization_verifier(critic, policy, keys)
    changed = deepcopy(proposal)
    changed["quantity"] = "5"
    if verify(changed, gate, fixture["now"]):
        raise AssertionError("Changed proposal retained old review")
    ownership = {k: proposal[k] for k in ("account_id", "strategy_id", "instrument_id")}
    ownership["position_id"] = "fictional-position-1"
    common = {**ownership, "mode": "SHADOW", "currency": "USD"}
    opened = "2026-10-09T13:30:00Z"
    final_at = "2026-10-09T13:30:02Z"

    def fill(fid, intent, side, quantity, price, stamp):
        return {**common, "fill_id": fid, "intent_id": intent, "side": side,
            "quantity": quantity, "price": price, "filled_at": stamp,
            "benchmark": {"mid_price": "100.00" if side == "BUY" else "101.05",
                          "source": "INVENTED_MIDPOINT", "currency": "USD", "observed_at": stamp}}

    def snapshot(ledger, rid, stamp, orders):
        return {"reconciliation_id": rid, "mode": "SHADOW", "account_id": ownership["account_id"],
            "strategy_id": ownership["strategy_id"], "source": "INVENTED_COMPLETE_SNAPSHOT", "observed_at": stamp,
            "orders_complete": True, "fills_complete": True, "positions_complete": True,
            "fill_ids": [r["fill_id"] for r in ledger.fills()], "orders": orders,
            "positions": [{k: r[k] for k in ("position_id", "instrument_id", "quantity")} for r in ledger.positions()]}

    def fee(fid, amount, stamp):
        return {**common, "cost_id": "fictional-cost-" + fid, "fill_id": fid, "status": "KNOWN",
                "complete": True, "amount": amount, "source": "INVENTED_CHARGE_NOT_ETORO_FEE", "observed_at": stamp}

    def accounting(ledger, stamp, fees, remaining, pending):
        return {"mode": "SHADOW", "ownership": ownership, "as_of": stamp, "fills": ledger.fills(),
            "fee_records": fees, "reconciliation": {**common, "source": "INVENTED_MATCHED_SNAPSHOT",
            "observed_at": stamp, "complete": True, "position_quantity": remaining, "pending_order_count": pending}}

    with tempfile.TemporaryDirectory(prefix="shadow-controls-demo-", dir=ROOT.parent) as folder:
        state = Path(folder) / "private-shadow.sqlite"
        with ShadowLedger(state, repository_root=ROOT) as ledger:
            entry = ledger.register_entry(proposal, gate, fixture["now"], calendar, authorization_verifier=verify)
            assert ledger.positions() == []  # Plan and exit obligation precede a fill.
            attempt = ledger.begin_attempt(entry["intent_id"], "fictional-entry-attempt", fixture["now"], authorization_verifier=verify)
            assert attempt["created"] and not attempt["dispatch_allowed"]
            ledger.record_accepted("fictional-entry-attempt", "fictional-entry-order", fixture["now"])
            assert ledger.positions() == []
            ledger.mark_unknown("fictional-entry-attempt", "2026-10-08T19:55:01Z", "INVENTED_TIMEOUT")
            try:
                ledger.begin_attempt(entry["intent_id"], "fictional-blind-retry", "2026-10-08T19:55:01Z", authorization_verifier=verify)
            except LedgerError:
                pass
            else:
                raise AssertionError("Unknown entry allowed a blind retry")
            ledger.record_fill(fill("fictional-buy", entry["intent_id"], "BUY", "4", "100.05", "2026-10-08T19:55:02Z"), "2026-10-08T19:55:02Z")
        # A fresh process would reopen the same durable state here.
        with ShadowLedger(state, repository_root=ROOT) as ledger:
            assert ledger.due_exits(opened)[0]["quantity"] == "4"
            entry_order = {"intent_id": entry["intent_id"], "order_id": "fictional-entry-order", "status": "FILLED", "remaining_quantity": "0"}
            ledger.reconcile(snapshot(ledger, "fictional-open-recon", opened, [entry_order]), opened)
            exit_intent = ledger.plan_exit(ownership["account_id"], ownership["position_id"], opened)
            ledger.begin_attempt(exit_intent["intent_id"], "fictional-exit-attempt", opened)
            ledger.record_accepted("fictional-exit-attempt", "fictional-exit-order", opened)
            ledger.record_fill(fill("fictional-sell-part", exit_intent["intent_id"], "SELL", "1", "101.00", "2026-10-09T13:30:01Z"), "2026-10-09T13:30:01Z")
            fees = [fee("fictional-buy", "0.50", "2026-10-08T19:55:02Z"),
                    fee("fictional-sell-part", "0.25", "2026-10-09T13:30:01Z")]
            partial_packet = accounting(ledger, "2026-10-09T13:30:01Z", fees, "3", 1)
            partial = build_trade_report(partial_packet)
            assert partial["remaining_quantity"] == "3" and not partial["closed"]
        with ShadowLedger(state, repository_root=ROOT) as ledger:
            assert ledger.due_exits(final_at)[0]["quantity"] == "3"
            ledger.record_fill(fill("fictional-sell-rest", exit_intent["intent_id"], "SELL", "3", "101.00", final_at), final_at)
            exit_order = {"intent_id": exit_intent["intent_id"], "order_id": "fictional-exit-order", "status": "FILLED", "remaining_quantity": "0"}
            ledger.reconcile(snapshot(ledger, "fictional-final-recon", final_at, [entry_order, exit_order]), final_at)
            fees.append(fee("fictional-sell-rest", "0.25", final_at))
            final_packet = accounting(ledger, final_at, fees, "0", 0)
            final = build_trade_report(final_packet)
            missing_cost = deepcopy(final_packet)
            missing_cost["fee_records"].pop()
            unknown = build_trade_report(missing_cost)
            assert unknown["final_net_pnl_usd"] is None and unknown["net_pnl_status"] == "NOT_FINAL"
            assert ledger.due_exits(final_at) == [] and final["closed"]
            event_count = len(ledger.event_log())
    return {"status": "SYNTHETIC_OPERATIONAL_FIXTURE", "mode": "SHADOW", "broker_writes": False,
        "profitability_evidence": False, "genuine_independent_reviewer_deployed": False,
        "authenticated_broker_facts": False, "actual_committed_source_verified": False,
        "source_commit_observed": revision, "spec_hash": canonical_hash(policy),
        "checks": {"changed_proposal_rejected": True, "accepted_not_filled": True,
            "blind_retry_refused": True, "owned_exit_survives_restart": True,
            "partial_sale_retains_shares": True, "unknown_fee_refuses_final_net": True},
        "event_count": event_count, "partial_accounting": partial, "final_accounting": final,
        "normalized_final_accounting_packet": final_packet}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", required=True)
    parser.add_argument("--output", help="Optional new private JSON file outside every Git checkout")
    args = parser.parse_args(argv)
    result = run_demo()
    if args.output:
        output = Path(args.output).expanduser().resolve()
        if output == ROOT or ROOT in output.parents or any((p / ".git").exists() for p in output.parents):
            parser.error("Output must be outside every Git checkout")
        with output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "mode", "broker_writes", "profitability_evidence", "checks", "event_count")}, indent=2))
    return 0


if __name__ == "__main__": sys.exit(main())
