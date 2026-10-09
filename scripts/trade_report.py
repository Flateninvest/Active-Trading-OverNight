"""Reconcile normalized private fills and fees; no broker access or publishing."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from active_trading.reporting.accounting import AccountingError, build_trade_report


def _private(value):
    path = Path(value).expanduser().resolve()
    if path == ROOT or ROOT in path.parents or any((parent / ".git").exists() for parent in path.parents):
        raise AccountingError("Inputs and output must be outside every Git checkout")
    return path


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Private normalized accounting JSON")
    parser.add_argument("--output", required=True, help="New private report JSON; never overwritten")
    args = parser.parse_args(argv)
    try:
        source, output = _private(args.input), _private(args.output)
        raw = source.read_bytes()
        packet = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        report = build_trade_report(packet)
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
