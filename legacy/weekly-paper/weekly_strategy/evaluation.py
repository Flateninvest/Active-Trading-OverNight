"""Descriptive fill-based evaluation; no forecasts or statistical edge claims."""
from collections import defaultdict
from datetime import date, timedelta


def evaluate(report, initial_equity=5000.0, spy_overnight_by_night=None):
    nights = defaultdict(lambda: {"gross": 0., "net": 0., "invested": 0., "cost": 0., "trades": 0,
                                 "unresolved_positions": 0, "unresolved_orders": 0})
    for decision in report.get("decisions", []):
        nights[decision["session_date"]]
    for order in report["orders"]:
        if order["status"] in {"INTENT", "ACK", "PARTIAL", "UNKNOWN"}:
            nights[order["session_date"]]["unresolved_orders"] += 1
    trades = []
    for position in report["positions"]:
        if position["strategy_id"] != report["strategy_id"]:
            continue
        entry_fills = [f for f in report["fills"] if f["position_id"] == position["position_id"] and f["action"] == "BUY"]
        invested = sum(f["quantity"] * f["price"] for f in entry_fills)
        bucket = nights[position["entry_session"]]
        bucket["invested"] += invested
        bucket["cost"] += position["entry_fees"] + position["exit_fees"]
        if position["quantity"] > 1e-8:
            nights[position["entry_session"]]["unresolved_positions"] += 1
            continue  # incomplete nights are operational exceptions, not invented exit returns
        cost = position["entry_fees"] + position["exit_fees"]
        net = position["realized_gross"] - cost
        trades.append({"ticker": position["ticker"], "night": position["entry_session"],
                       "invested_usd": invested, "gross_usd": position["realized_gross"], "cost_usd": cost,
                       "net_usd": net, "return_on_invested": net / invested if invested else None})
        bucket["gross"] += position["realized_gross"]
        bucket["net"] += net
        bucket["trades"] += 1
    equity, peak, maximum_dd = initial_equity, initial_equity, 0.
    rows, benchmark_total = [], 0.
    benchmark_complete = spy_overnight_by_night is not None
    for night, item in sorted(nights.items()):
        starting = equity
        equity += item["net"]
        peak = max(peak, equity)
        maximum_dd = min(maximum_dd, equity / peak - 1)
        spy_return = (spy_overnight_by_night or {}).get(night)
        benchmark = 0.0 if item["invested"] == 0 else item["invested"] * spy_return if spy_return is not None else None
        if benchmark is None:
            benchmark_complete = False
        else:
            benchmark_total += benchmark
        resolved = item["unresolved_positions"] == 0 and item["unresolved_orders"] == 0 and report.get("costs_complete", True)
        rows.append({"night": night, **item, "return_on_total_equity": item["net"] / starting if resolved else None,
                     "return_on_invested": item["net"] / item["invested"] if item["invested"] and resolved else None,
                     "invested_exposure": item["invested"] / starting,
                     "cash_weight": 1 - item["invested"] / starting if resolved else None,
                     "status": "completed_or_cash" if resolved else "unresolved_mark_to_market_unavailable",
                     "spy_matched_exposure_gross_usd": benchmark})
    weeks = {date.fromisoformat(n) - timedelta(days=date.fromisoformat(n).weekday()) for n in nights}
    book_complete = report["open_strategy_positions"] == 0 and report["pending_orders"] == 0 and report.get("costs_complete", True)
    return {"data_kind": report["data_kind"], "profitability_evidence": False,
            "completed_trades": len(trades), "independent_nights": len(nights), "weeks": len(weeks),
            "independent_traded_nights": sum(n["invested"] > 0 for n in nights.values()),
            "cash_or_skipped_nights": sum(n["invested"] == 0 for n in nights.values()),
            "names_are_correlated_not_independent_observations": True,
            "gross_pnl_usd": sum(t["gross_usd"] for t in trades),
            "net_pnl_usd": sum(t["net_usd"] for t in trades) if book_complete else None,
            "closed_realized_net_pnl_usd": sum(t["net_usd"] for t in trades),
            "return_on_total_strategy_equity": equity / initial_equity - 1 if book_complete else None,
            "equity_metric_scope": "completed_flat_fill_ledger" if book_complete else "closed_realized_only_complete_book_metrics_unavailable",
            "average_net_trade_usd": sum(t["net_usd"] for t in trades) / len(trades) if trades else None,
            "drawdown_on_completed_nights": maximum_dd if book_complete else None,
            "worst_completed_night_return": min((n["return_on_total_equity"] for n in rows if n["return_on_total_equity"] is not None), default=None),
            "worst_completed_stock_trade_return_on_invested": min((t["return_on_invested"] for t in trades if t["return_on_invested"] is not None), default=None),
            "trading_cost_usd": sum(n["cost"] for n in nights.values()) if report.get("costs_complete", True) else None,
            "recorded_trading_cost_usd": sum(n["cost"] for n in nights.values()),
            "execution_shortfall_usd": None,
            "execution_shortfall_status": "requires_timestamp_matched_decision_or_auction_benchmark_prices",
            "rejected_orders": sum(o["status"] == "REJECTED" for o in report["orders"]),
            "pending_orders": report["pending_orders"], "open_strategy_positions": report["open_strategy_positions"],
            "operational_exceptions": sum(e["kind"] in {"EXIT_EXCEPTION", "RECONCILIATION_EXCEPTION",
                                                       "UNKNOWN_ORDER_BLOCKS_NEW_INTENT", "EXIT_REMAINDER_REQUIRES_OPERATOR_REVIEW"}
                                          for e in report["events"]),
            "spy_matched_exposure_gross_usd": benchmark_total if benchmark_complete else None,
            "spy_benchmark_costs_status": "gross_only_requires_separately_observed_benchmark_costs",
            "cash_interest_assumption": 0.0, "nights": rows, "trades": trades}
