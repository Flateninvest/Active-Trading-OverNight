"""Reproduce Rev11 workbook evidence without searching strategy parameters.

The supplied workbooks remain unchanged. Historical statistics are descriptive
of a later snapshot, not a claim of point-in-time availability. Research dated
2026 is never used in the 2023–25 historical test.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from flow_layer import (EXTERNAL, ROOT, conviction_score, daily_premium_panel,
                        find_flow_workbook, load_flow_records, load_prices,
                        newey_west_t, qualifying_mask)

OUT = ROOT / "results" / "evidence"
ANGLES = EXTERNAL / "hidden_angle_flow_database_SEP_6th_2026_updated.xlsx"
HISTORICAL_START, HISTORICAL_END = "2023-01-03", "2025-12-31"
PERIODS = {"2023-24": (HISTORICAL_START, "2024-12-31"),
           "2025": ("2025-01-01", HISTORICAL_END)}


def ticker_tokens(values: pd.Series) -> pd.Series:
    return (values.astype(str).str.replace("$", "", regex=False)
            .str.upper().str.split("/").map(lambda items: [v.strip() for v in items if v.strip()]))


def date_text(value) -> str | None:
    return None if pd.isna(value) else pd.Timestamp(value).date().isoformat()


def file_metadata(path: Path, description: str, snapshot_date: str) -> dict:
    meta = {"filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size, "provided_by": "Candidate, 7 September 2026",
            "description": description, "snapshot_date_as_labeled": snapshot_date,
            "original_workbook_preserved": True, "external_source_verification": False}
    path.with_suffix(".metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def research_summary(path: Path, tickers: list[str]) -> tuple[dict, list[dict]]:
    sheet = "Hidden Angles Database"
    notes = pd.read_excel(path, sheet_name=sheet, header=3).dropna(how="all")
    notes["source_row"] = notes.index + 5
    notes["Date"] = pd.to_datetime(notes["Date"], errors="coerce", format="mixed").dt.normalize()
    notes["tokens"] = ticker_tokens(notes["Ticker"])
    expanded = notes.explode("tokens")
    covered = expanded[expanded["tokens"].isin(tickers)]
    unique_pairs = covered[["Date", "tokens"]].drop_duplicates().reset_index(drop=True)
    live = pd.crosstab(unique_pairs["Date"], unique_pairs["tokens"]).reindex(columns=tickers, fill_value=0)
    all_dates = pd.DatetimeIndex(sorted(notes["Date"].dropna().unique()))
    live = live.reindex(all_dates, fill_value=0)
    daily_names = live.gt(0).sum(axis=1)
    weekly_names = live.rolling("7D").sum().gt(0).sum(axis=1)
    conviction = pd.read_excel(path, sheet_name="Hidden Angle Flow Analysis", header=3).dropna(how="all")
    conviction["source_row"] = conviction.index + 5
    conviction["symbol"] = conviction["Ticker"].astype(str).str.replace("$", "", regex=False).str.strip().str.upper()
    stats = {
        "workbook": path.name, "database_sheet": sheet,
        "records": int(len(notes)), "valid_dates": int(notes["Date"].notna().sum()),
        "first_date": date_text(notes["Date"].min()), "last_date": date_text(notes["Date"].max()),
        "distinct_ticker_tokens": int(expanded["tokens"].nunique()),
        "records_with_universe_name": int(covered["source_row"].nunique()),
        "universe_names_ever": int(covered["tokens"].nunique()),
        "universe_names_median_record_date": float(daily_names.median()),
        "universe_names_median_trailing_7_calendar_days": float(weekly_names.median()),
        "record_dates": int(len(all_dates)),
        "records_overlapping_2023_2025": int(notes["Date"].between(HISTORICAL_START, HISTORICAL_END).sum()),
        "conviction_snapshot_date": "2026-09-04",
        "conviction_names": int(conviction["symbol"].nunique()),
        "conviction_names_in_universe": int(conviction.loc[conviction["symbol"].isin(tickers), "symbol"].nunique()),
        "source_fields_present": False,
        "database_columns": [c for c in notes.columns if c not in {"source_row", "tokens"}],
        "ticker_count_definition": "Unique slash-separated uppercase labels, not independently verified security identifiers.",
        "weekly_coverage_definition": "Median on dates with database records; trailing seven calendar days including that date.",
    }
    examples = []
    for symbol, date in (("CI", "2026-08-26"), ("AVGO", "2026-08-27")):
        selected = notes[(notes["Date"].eq(pd.Timestamp(date))) & notes["tokens"].map(lambda v: symbol in v)]
        # Resolve by the wording quoted in Rev10, never by a guessed row number.
        needle = "Management characterized" if symbol == "CI" else "$27.48"
        selected = selected[selected["Hidden Angle"].astype(str).str.contains(needle, regex=False)]
        if len(selected) != 1:
            raise ValueError(f"Expected exactly one source note for {symbol} on {date}; found {len(selected)}")
        row = selected.iloc[0]
        cv = conviction[conviction["symbol"].eq(symbol)].iloc[0]
        angle_excerpt = row["Hidden Angle"]
        if symbol == "AVGO":
            # The report keeps the original excerpt, omitting one middle clause.
            angle_excerpt = ("…" + angle_excerpt[angle_excerpt.index("XPV"):angle_excerpt.index(" — implying")]
                             + "… " + angle_excerpt[angle_excerpt.index("He also introduces"):])
        examples.append({
            "ticker": symbol, "note_date": date, "workbook": path.name,
            "sheet": sheet, "source_row": int(row["source_row"]),
            "source_range": f"A{row['source_row']}:E{row['source_row']}",
            "hidden_angle_exact": row["Hidden Angle"], "why_it_matters_exact": row["Why It Matters"],
            "report_angle_excerpt": angle_excerpt, "report_why_excerpt": row["Why It Matters"],
            "angle_records_on_file": int(notes["tokens"].map(lambda v: symbol in v).sum()),
            "source_status": "Verbatim candidate-provided note; underlying publisher/document is not linked in the workbook.",
            "conviction_snapshot": {
                "date": "2026-09-04", "sheet": "Hidden Angle Flow Analysis", "row": int(cv["source_row"]),
                "bull_premium": float(cv["Bull Premium"]), "bear_premium": float(cv["Bear Premium"]),
                "new_position_dollars_as_labeled": float(cv["New Position $"]),
                "bull_bear_ratio_as_labeled": float(cv["Bull/Bear"]), "bull_trades": int(cv["# Bull Trades"]),
                "current_hidden_angle_exact": cv["Hidden Angle"],
                "same_note_as_report_example": bool(cv["Hidden Angle"] == row["Hidden Angle"]),
                "interpretation": "Snapshot aggregates as labeled; not same-day trade totals or verified positions, and not the historical frozen filter.",
            },
        })
    return stats, examples


def build_flow_evidence(workbook: Path, open_: pd.DataFrame, close: pd.DataFrame,
                        volume: pd.DataFrame, tickers: list[str]) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    records = load_flow_records(workbook)
    flow = records.loc[qualifying_mask(records)].copy()
    flow["signed_premium"] = np.where(flow["Sentiment"].astype(str).str.upper().eq("BULLISH"),
                                      flow["Premium"], -flow["Premium"])
    universe = pd.read_csv(ROOT / "data" / "official" / "universe.csv")
    sector_etfs = universe.loc[universe["category"].eq("sector_etf"), "ticker"].tolist()
    is_sector = flow["Symbol"].isin(sector_etfs)
    source_ok = ((is_sector & flow["source_sheet"].eq("Flow Analytics (ETFs)"))
                 | (~is_sector & flow["source_sheet"].eq("Flow Analytics (Stocks)")))
    source_excluded = flow.loc[~source_ok]
    premium = daily_premium_panel(flow, close.index, tickers)
    coverage, information = [], []
    # Index by entry session t; every score uses only t-1 and earlier records.
    next_overnight = open_.shift(-1) / close - 1.0
    # Missing exits cannot silently produce fabricated returns.
    next_overnight = next_overnight.where(open_.shift(-1).gt(0) & close.gt(0))
    for window in (1, 5, 20, 60):
        score = conviction_score(premium, close * volume, window)
        for period, (start, end) in PERIODS.items():
            sample = score.loc[start:end]
            counts = sample.abs().gt(0).sum(axis=1)
            subset = flow[flow["Date"].between(start, end)]
            coverage.append({"window_sessions": window, "period": period,
                             "sessions": len(sample), "qualifying_records_all_symbols": len(subset),
                             "qualifying_records_in_universe": int(subset["Symbol"].isin(tickers).sum()),
                             "names_ever_with_lagged_score": int(sample.abs().gt(0).any().sum()),
                             "median_names_with_lagged_score": float(counts.median()),
                             "median_bullish_names": float(sample.gt(0).sum(axis=1).median())})
            if window == 1:
                continue
            returns = next_overnight.loc[start:end]
            bull = returns.where(sample.gt(0)).mean(axis=1)
            bear = returns.where(sample.lt(0)).mean(axis=1)
            spread = (bull - bear).dropna()
            excess = (bull - returns.mean(axis=1)).dropna()
            information.append({"window_sessions": window, "period": period,
                                "bullish_days": int(bull.notna().sum()), "paired_spread_days": len(spread),
                                "bullish_minus_bearish_bp": float(spread.mean() * 1e4) if len(spread) else None,
                                "spread_newey_west_t": newey_west_t(spread.to_numpy()) if len(spread) else None,
                                "bullish_minus_universe_bp": float(excess.mean() * 1e4) if len(excess) else None,
                                "excess_newey_west_t": newey_west_t(excess.to_numpy()) if len(excess) else None})
    stats = {
        "workbook": workbook.name, "snapshot_date": "2026-09-04",
        "input_rows": records.attrs["input_rows"],
        "exact_duplicate_rows_removed": records.attrs["exact_duplicate_rows_removed"],
        "unique_source_records": len(records), "qualifying_records": len(flow),
        "distinct_symbols": int(flow["Symbol"].nunique()),
        "first_qualifying_date": date_text(flow["Date"].min()),
        "last_qualifying_date": date_text(flow["Date"].max()),
        "filter": "Side contains ask; premium >= $100,000; quantity > reported open interest; trade-date DTE 180–730 inclusive; bullish or bearish sentiment.",
        "duplicate_policy": "First exact A:J record retained; identical prints cannot be distinguished without trade IDs.",
        "timing": "Score dated entry session t contains records dated t-1 or earlier; outcome is close t to open t+1.",
        "historical_test_status": "Exploratory snapshot analysis only; no observation timestamps or completeness history provided.",
        "position_inference": "Ask-side classification and quantity above open interest do not establish trader identity, an opening position, or unhedged conviction.",
        "source_sheet_reconciliation": {
            "economic_filter_both_sheets": len(flow),
            "after_core_source_sheet_restrictions": int(source_ok.sum()),
            "excluded_by_core_source_rules": len(source_excluded),
            "non_sector_etf_or_index_records_from_etf_sheet": int((~is_sector & flow["source_sheet"].eq("Flow Analytics (ETFs)")).sum()),
            "sector_etf_records_from_stock_sheet": int((is_sector & flow["source_sheet"].eq("Flow Analytics (Stocks)")).sum()),
            "excluded_records_in_fixed_200_equities": int(source_excluded["Symbol"].isin(tickers).sum()),
            "explanation": "Report counts apply the economic filter across both sheets. The baseline's relative-flow helper additionally requires sector ETFs on the ETF sheet and other symbols on the Stocks sheet. In this snapshot that restriction changes global counts but removes no fixed-universe equity records.",
        },
    }
    return stats, pd.DataFrame(coverage), pd.DataFrame(information)


def main(angles_path: Path | None = None) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    open_, close, volume, _, tickers = load_prices()
    open_, close, volume = [frame.loc[HISTORICAL_START:HISTORICAL_END] for frame in (open_, close, volume)]
    workbook = find_flow_workbook()
    flow, coverage, information = build_flow_evidence(workbook, open_, close, volume, tickers)
    angles_path = angles_path or ANGLES
    research, examples = research_summary(angles_path, tickers)
    metadata = [file_metadata(workbook, "Candidate-provided options-flow snapshot; raw source retained.", "2026-09-04"),
                file_metadata(angles_path, "Candidate-provided research notes and conviction aggregates; no primary source links supplied.", "2026-09-04")]
    summary = {"universe": len(tickers), "historical_start": HISTORICAL_START, "historical_end": HISTORICAL_END,
               "flow": flow, "research": research, "examples": examples, "input_metadata": metadata,
               "limitations": [
                   "Dated snapshot records do not prove historical availability or coverage completeness.",
                   "The research database has no 2023–25 overlap and is a forward overlay proposal, not tested historical alpha.",
                   "The conviction sheet uses a separate aggregate definition from the frozen 180–730 DTE historical filter.",
                   "Research assertions, consensus gaps, catalysts and falsifiers require primary-source verification before forward use.",
               ]}
    coverage.to_csv(OUT / "coverage.csv", index=False)
    information.to_csv(OUT / "flow_information.csv", index=False)
    reconciliation = {key: flow[key] for key in ("input_rows", "exact_duplicate_rows_removed", "unique_source_records")}
    reconciliation.update(flow["source_sheet_reconciliation"])
    (OUT / "flow_count_reconciliation.json").write_text(json.dumps(reconciliation, indent=2) + "\n", encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Evidence: {flow['qualifying_records']:,} qualifying flow records; "
          f"{research['records']:,} research notes; {research['records_overlapping_2023_2025']} historical research overlap.")
    return summary


if __name__ == "__main__":
    main()
