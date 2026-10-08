"""Run with python -m weekly_strategy.cli. All commands are PAPER only."""
import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from .calendar import aware, schedule
from .engine import WeeklyEngine
from .evaluation import evaluate
from .fixtures import synthetic_market, synthetic_selection

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def run_demo(output, config):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    comparisons = {}
    for label, mode, overlay in (("weekly_with_research_A", "A", True),
                                 ("weekly_flow_only_A", "A", False),
                                 ("weekly_with_research_B", "B", True)):
        setting = {**config, "exit_mode": mode, "research_overlay_enabled": overlay,
                   "evaluation_variant": "weekly_flow_plus_hidden_angles" if overlay else "weekly_flow_only"}
        engine = WeeklyEngine(output / (label + ".sqlite"), setting)
        engine.load_selection(synthetic_selection(overlay=overlay))
        events = [("2026-10-06T19:30:00+00:00", "ENTRY"), ("2026-10-06T19:55:00+00:00", "ENTRY"),
                  ("2026-10-07T13:25:00+00:00", "PREOPEN"), ("2026-10-07T13:30:00+00:00", "OPEN")]
        for at, phase in events:
            report = engine.tick(at, synthetic_market(at, phase))
        write(output / (label + "_ledger.json"), report)
        # Explicitly invented SPY 0.10% fixture, exposure matched, zero cash yield.
        metrics = evaluate(report, setting["pilot_equity_usd"], {"2026-10-06": .001})
        write(output / (label + "_metrics.json"), metrics)
        comparisons[label] = metrics
        engine.close()
    comparisons["paired_exit_comparison"] = {
        "identical_selections_and_entries": True,
        "mode_A_net_usd": comparisons["weekly_with_research_A"]["net_pnl_usd"],
        "mode_B_net_usd": comparisons["weekly_with_research_B"]["net_pnl_usd"],
        "posthoc_exit_choice_permitted": False}
    write(output / "Synthetic_Demonstration_Comparison.json", {
        "data_kind": "SYNTHETIC_OPERATIONAL_FIXTURE", "profitability_evidence": False,
        "notice": "Invented prices and theses demonstrate operation only; no backtest or actual fills.",
        "comparisons": comparisons})
    write(output / "synthetic_selection.json", synthetic_selection())
    write(output / "synthetic_market.json", synthetic_market(events[1][0]))
    return {"status": "SYNTHETIC_PAPER_DEMO_COMPLETED", "output": str(output.resolve()),
            "comparisons": list(comparisons), "profitability_evidence": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Revision12 paper engine; no live orders")
    parser.add_argument("--config", default=str(ROOT / "rev12_config.json"))
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="synthetic operational demonstration, not trading evidence")
    demo.add_argument("--output", default=str(ROOT / "results" / "rev12_demo"))
    cal = sub.add_parser("calendar")
    cal.add_argument("--date", required=True)
    for name in ("run-once", "scheduler", "replay"):
        child = sub.add_parser(name)
        child.add_argument("--selection", required=True)
        child.add_argument("--database", required=True)
        child.add_argument("--report", required=True)
        if name == "replay":
            child.add_argument("--events", required=True, help="JSON array of {at,market} records")
        else:
            child.add_argument("--market", required=True, help="timestamped paper/read-only quote snapshot JSON")
            child.add_argument("--at", help="explicit replay time; scheduler accepts this only with --max-ticks 1")
        if name == "scheduler":
            child.add_argument("--poll-seconds", type=float, default=10.)
            child.add_argument("--max-ticks", type=int, default=0, help="0 runs continuously until Ctrl+C")
            child.add_argument("--log", required=True)
    args = parser.parse_args(argv)
    config = read(args.config)
    if args.command == "demo":
        result = run_demo(args.output, config)
    elif args.command == "calendar":
        result = schedule(args.date, config)
    else:
        if args.command == "scheduler" and args.at and args.max_ticks != 1:
            parser.error("Fixed --at is only allowed for a one-tick scheduler verification")
        if args.command == "scheduler" and args.poll_seconds <= 0:
            parser.error("poll-seconds must be positive")
        engine = WeeklyEngine(args.database, config)
        engine.load_selection(read(args.selection))
        log_handler = None
        try:
            if args.command == "replay":
                events = read(args.events)
                times = [aware(item["at"]) for item in events]
                if times != sorted(times):
                    raise ValueError("Replay event timestamps must be chronological")
                for item in events:
                    result = engine.tick(item["at"], item["market"])
                result = engine.report()
                write(args.report, result)
            elif args.command == "run-once":
                result = engine.tick(args.at or datetime.now(timezone.utc), read(args.market))
                write(args.report, result)
            else:
                Path(args.log).parent.mkdir(parents=True, exist_ok=True)
                logger = logging.getLogger("rev12-paper-scheduler")
                logger.setLevel(logging.INFO)
                log_handler = logging.FileHandler(args.log, encoding="utf-8")
                log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
                logger.addHandler(log_handler)
                count = 0
                while True:
                    now = aware(args.at) if args.at else datetime.now(timezone.utc)
                    try:
                        # Never refresh a stale quote's timestamp. Producer must write new observations.
                        result = engine.tick(now, read(args.market))
                        write(args.report, result)
                        logger.info("PAPER tick at=%s cash=%s open=%s pending=%s", now.isoformat(),
                                     result["cash_usd"], result["open_strategy_positions"], result["pending_orders"])
                    except Exception:
                        logger.exception("PAPER tick failed; no live writer exists")
                        if args.max_ticks:
                            raise
                    count += 1
                    if args.max_ticks and count >= args.max_ticks:
                        break
                    time.sleep(args.poll_seconds)
        finally:
            engine.close()
            if log_handler is not None:
                logger.removeHandler(log_handler)
                log_handler.close()
    print(json.dumps(result if args.command in ("demo", "calendar") else
                     {"mode": result["mode"], "cash_usd": result["cash_usd"],
                      "open_strategy_positions": result["open_strategy_positions"],
                      "pending_orders": result["pending_orders"], "profitability_evidence": False}, indent=2))
    return result


if __name__ == "__main__":
    main()
