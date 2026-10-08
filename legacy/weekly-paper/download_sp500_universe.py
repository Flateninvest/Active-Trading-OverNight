"""Freeze the S&P 500 membership available immediately before 2025."""

from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "external" / "sp500_constituents_2025-01-02.csv"
META = ROOT / "data" / "external" / "sp500_constituents_2025-01-02.metadata.json"
REVISION_ID = 1265285344
REVISION_TIMESTAMP = "2024-12-26T04:36:28Z"
URL = f"https://en.wikipedia.org/w/index.php?title=List_of_S%26P_500_companies&oldid={REVISION_ID}"


def main() -> None:
    request = Request(URL, headers={"User-Agent": "Mozilla/5.0 research@example.invalid"})
    with urlopen(request, timeout=30) as response:
        html = response.read()
    tables = pd.read_html(io.BytesIO(html))
    frame = tables[0].copy()
    frame.columns = [str(column).strip().lower().replace(" ", "_") for column in frame.columns]
    frame["symbol"] = frame["symbol"].astype(str).str.replace("-", ".", regex=False)
    frame = frame.sort_values("symbol").reset_index(drop=True)
    if len(frame) < 500 or frame["symbol"].duplicated().any():
        raise RuntimeError("Unexpected S&P 500 constituent table")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT, index=False)
    metadata = {
        "description": "S&P 500 constituent snapshot immediately before the 2025 evaluation period",
        "source": "Wikipedia historical page revision",
        "url": URL,
        "revision_id": REVISION_ID,
        "revision_timestamp": REVISION_TIMESTAMP,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(frame)),
        "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(),
        "method_note": "Membership is frozen for 2025 to avoid using an end-of-2025 survivor list; intrayear index changes are not modeled.",
    }
    META.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved {len(frame)} constituents to {OUT}")


if __name__ == "__main__":
    main()
