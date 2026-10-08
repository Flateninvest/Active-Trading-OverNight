"""Download and freeze SPY daily OHLC from Nasdaq's public historical endpoint."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "external" / "spy_nasdaq_2023_2025.csv"
META = ROOT / "data" / "external" / "spy_nasdaq_2023_2025.metadata.json"
URL = (
    "https://api.nasdaq.com/api/quote/SPY/historical"
    "?assetclass=etf&fromdate=2023-01-01&todate=2025-12-31&limit=5000"
)


def parse_number(value: object) -> float:
    return float(str(value).replace("$", "").replace(",", "").strip())


def main() -> None:
    request = Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.nasdaq.com",
            "Referer": "https://www.nasdaq.com/",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    rows = payload["data"]["tradesTable"]["rows"]
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError("Nasdaq returned no SPY history")

    frame = frame.rename(columns={"date": "date", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"})
    frame["date"] = pd.to_datetime(frame["date"], format="%m/%d/%Y")
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = frame[column].map(parse_number)
    frame = frame[["date", "open", "high", "low", "close", "volume"]].sort_values("date")

    if frame["date"].min() > pd.Timestamp("2023-01-03") or frame["date"].max() < pd.Timestamp("2025-12-31"):
        raise RuntimeError("SPY history does not cover the required period")
    if frame["date"].duplicated().any():
        raise RuntimeError("SPY history contains duplicate dates")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT, index=False, date_format="%Y-%m-%d", float_format="%.6f")
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    metadata = {
        "symbol": "SPY",
        "source": "Nasdaq public historical endpoint",
        "url": URL,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(frame)),
        "first_date": frame["date"].min().date().isoformat(),
        "last_date": frame["date"].max().date().isoformat(),
        "sha256": digest,
        "price_note": "Unadjusted exchange-reported OHLC; expense ratio is already reflected in traded prices.",
    }
    META.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved {len(frame)} SPY rows to {OUT}")


if __name__ == "__main__":
    main()
