"""Reconcile normalized private fills and fees; no broker access or publishing."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from active_trading.reporting.accounting import AccountingError, build_trade_report
from active_trading.reporting.imports import import_demo_trade
from active_trading.jsonio import load_json, loads_json


def _private(value):
    path = Path(value).expanduser().resolve()
    if path == ROOT or ROOT in path.parents or any((parent / ".git").exists() for parent in path.parents):
        raise AccountingError("Inputs and output must be outside every Git checkout")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Private normalized accounting JSON")
    parser.add_argument("--output", required=True, help="New private report JSON; never overwritten")
    parser.add_argument("--import-demo", action="store_true", help="Normalize one external DEMO observation; previews are not fills")
    parser.add_argument("--previous-packet", help="Previous private import report or normalized packet; append without rewriting it")
    args = parser.parse_args(argv)
    try:
        source, output = _private(args.input), _private(args.output)
        raw = source.read_bytes()
        packet = loads_json(raw)
        if args.previous_packet and not args.import_demo:
            raise AccountingError("--previous-packet requires --import-demo")
        if args.import_demo:
            previous = load_json(_private(args.previous_packet)) if args.previous_packet else None
            if isinstance(previous, dict) and "normalized_accounting_packet" in previous:
                previous = previous["normalized_accounting_packet"]
            packet = import_demo_trade(packet, previous_packet=previous, source_bytes=raw)
        report = build_trade_report(packet)
        if args.import_demo:
            report["normalized_accounting_packet"] = packet
        report["identities"] = {"input_bytes_sha256": hashlib.sha256(raw).hexdigest(),
            "accounting_source_sha256": hashlib.sha256((ROOT / "src" / "active_trading" / "reporting" / "accounting.py").read_bytes()).hexdigest(),
            "committed_source_verified": False}
        with output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
        # Do not leak private account, prices, filenames or position identifiers.
        print(json.dumps({"status": "REPORT_WRITTEN", "broker_writes": False,
                          "publication": False, "net_pnl_status": report["net_pnl_status"]}))
        return 0
    except (AccountingError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "REFUSED", "broker_writes": False,
                          "error_type": type(exc).__name__, "reason": "Private report could not be validated or saved"}), file=sys.stderr)
        return 2


if __name__ == "__main__": sys.exit(main())
