"""Frozen weekly stock research selection, separate from deterministic daily entry checks.

The v0.2 numeric thresholds are untuned research starting values. Revision 12
applies DTE at weekly selection and expires the original supporting evidence at
subsequent entries unless a reviewed continuing thesis is explicit. No matched
call/put or identical-looking source rows are deleted.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .ingest import parse_date

DEFAULT_SELECTION = {
    "minimum_row_premium_usd": 100_000,
    "selection_dte_min_calendar": 2,
    "selection_dte_max_calendar": 10,
    "minimum_net_bull_premium_usd": 1_000_000,
    "minimum_bull_share": 0.70,
    "research_age_max_calendar_days": 30,
    "maximum_weekly_candidates": 10,
    "threshold_status": "v0.2_verified_untuned_starting_values_with_Rev12_weekly_timing_change",
    "duplicate_policy": "retain_all_without_proven_vendor_execution_duplicates",
    "linked_leg_policy": "possible_pairs_report_only_no_exclusion_without_evidence",
    "dte_policy": "2_to_10_at_selection_then_active_support_through_exit_or_explicit_reviewed_continuing_thesis",
    "research_overlay_enabled": True,
    "evaluation_variant": "weekly_flow_plus_hidden_angles",
}


def selection_config(config: dict | None = None) -> dict:
    """Accept the repository's single rev12_config.json or explicit selection settings."""
    config = config or {}
    values = config.get("selection_rules_proposed", config)
    aliases = {"minimum_net_bullish_premium_usd": "minimum_net_bull_premium_usd",
               "minimum_bullish_share_filtered_sample": "minimum_bull_share",
               "weekly_selection_dte_min": "selection_dte_min_calendar",
               "weekly_selection_dte_max": "selection_dte_max_calendar"}
    cfg = dict(DEFAULT_SELECTION)
    for key, value in values.items():
        target = aliases.get(key, key)
        if target in cfg:
            cfg[target] = value
    for key in ("research_overlay_enabled", "evaluation_variant"):
        if key in config: cfg[key] = config[key]
    if "maximum_candidates" in config:
        cfg["maximum_weekly_candidates"] = config["maximum_candidates"]
    if not 0 <= cfg["minimum_bull_share"] <= 1 or not 0 <= cfg["maximum_weekly_candidates"] <= 10:
        raise ValueError("Bull share must be 0--1 and the weekly candidate ceiling 0--10")
    if cfg["selection_dte_min_calendar"] > cfg["selection_dte_max_calendar"]:
        raise ValueError("Selection DTE minimum must not exceed maximum")
    if cfg["research_overlay_enabled"] is False and cfg["evaluation_variant"] != "weekly_flow_only":
        raise ValueError("Disabling research requires the explicit weekly_flow_only comparison label")
    return cfg


def _timestamp(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("knowledge/selection timestamp must include a timezone")
    return timestamp


def _week(day: date) -> tuple[date, date]:
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=3)


def _availability(records: list[dict], cutoff: datetime, times: dict) -> tuple[bool, list[dict]]:
    files = sorted({r["source_file"] for r in records})
    controls = []
    for name in files:
        supplied = times.get(name)
        available = _timestamp(supplied) if supplied else None
        controls.append({"source_file": name, "available_at": supplied,
                         "availability_proven": bool(available),
                         "available_by_cutoff": bool(available and available <= cutoff)})
    return bool(files) and all(c["available_by_cutoff"] for c in controls), controls


def _research_for(ticker: str, records: list[dict], selection_day: date, max_age: int) -> list[dict]:
    hits = [r for r in records if ticker in r.get("tickers", []) and r.get("research_date")
            and 0 <= (selection_day - date.fromisoformat(r["research_date"])).days <= max_age]
    return sorted(hits, key=lambda r: (r["research_date"], r["source_row"]), reverse=True)


def _research_excerpt(r: dict) -> dict:
    return {k: r.get(k) for k in ("source_id", "source_file", "source_sheet", "source_row", "research_date", "company_name", "hidden_angle", "why_it_matters", "original_publisher", "original_source_url", "event_date_verified", "thesis_verified")}


def _flow_gates(rows: list[dict], day: date, cfg: dict) -> tuple[list[dict], list[dict]]:
    qualifying, excluded = [], []
    for record in rows:
        reasons = []
        expiry = parse_date(record.get("expiry"))
        selection_dte = (expiry - day).days if expiry else None
        if record.get("asset_category") != "stock": reasons.append("ETF/index context is outside stock strategy")
        if record.get("also_appears_in_ETF_index_sheet"): reasons.append("ticker is present in ETF/index worksheet; underlying-stock classification unresolved")
        if record.get("premium_usd") is None or record["premium_usd"] < cfg["minimum_row_premium_usd"]: reasons.append("premium below threshold or missing")
        if str(record.get("side") or "").lower().strip() not in ("near ask", "on ask", "above ask", "at ask", "ask"): reasons.append("not an unambiguous ask-side row")
        if record.get("direction") not in ("BULLISH", "BEARISH"): reasons.append("direction unclassified or conflicts")
        if selection_dte is None or not cfg["selection_dte_min_calendar"] <= selection_dte <= cfg["selection_dte_max_calendar"]: reasons.append("outside weekly selection DTE band or expiry unavailable")
        if record.get("expiry_validation_flags"): reasons.append("contract expiry validation unresolved")
        if record.get("validation_flags"):
            reasons.extend("source validation: " + flag for flag in record["validation_flags"])
        copy = {**record, "selection_dte": selection_dte, "flow_gate_reasons": reasons}
        (excluded if reasons else qualifying).append(copy)
    return qualifying, excluded


def _possible_pairs(rows: list[dict]) -> list[dict]:
    """Report candidates for linked legs without inferring they are the same investor."""
    pairs = []
    grouped = defaultdict(lambda: {"CALL": [], "PUT": []})
    for r in rows:
        if r.get("option_type") in ("CALL", "PUT") and r.get("quantity"):
            grouped[(r["ticker"], r["expiry"])][r["option_type"]].append(r)
    for (ticker, expiry), sides in grouped.items():
        for call in sides["CALL"]:
            for put in sides["PUT"]:
                if abs(call["quantity"] - put["quantity"]) / max(call["quantity"], put["quantity"]) <= 0.10:
                    pairs.append({"ticker": ticker, "expiry": expiry, "call_source_id": call["source_id"], "put_source_id": put["source_id"],
                                  "status": "similar quantities only; linked legs unproven; both raw rows retained"})
    return pairs


def weekly_selection(flow_records: list[dict], research_records: list[dict], selection_date: str,
                     selection_cutoff: str, source_availability: dict | None = None, config: dict | None = None,
                     protocol: str = "Monday_cutoff", thesis_reviews: dict | None = None,
                     summary_records: list[dict] | None = None, source_manifest: list[dict] | None = None,
                     flow_session: str | None = None) -> dict:
    """Return a reproducible research packet; missing availability keeps it diagnostic.

    source_availability contains *proven* receipt timestamps by exact source
    filename. Merely replacing a missing receipt with a vendor row date is not
    permitted. For a later rehearsal, observed ingestion can establish the new
    knowledge cutoff, but it cannot establish an earlier Tuesday decision.
    """
    cfg = selection_config(config)
    day = date.fromisoformat(selection_date); cutoff = _timestamp(selection_cutoff)
    if cutoff.astimezone(ZoneInfo("Europe/Zurich")).date() != day:
        raise ValueError("selection_date must equal the date of the supplied local cutoff")
    monday, thursday = _week(day)
    if protocol not in ("Monday_cutoff", "later_rehearsal"):
        raise ValueError("protocol must be Monday_cutoff or later_rehearsal")
    if protocol == "Monday_cutoff" and day.weekday() != 1:
        raise ValueError("The baseline weekly selection is Tuesday, using completed Monday flow")
    session = flow_session or (monday.isoformat() if protocol == "Monday_cutoff" else max((r["trade_date"] for r in flow_records if r.get("trade_date") and r["trade_date"] < selection_date), default=None))
    if session is None or session >= selection_date:
        raise ValueError("Completed flow session must precede the research selection date")
    if protocol == "Monday_cutoff" and session != monday.isoformat():
        raise ValueError("Baseline requires this week's Monday session, never later flow")
    selected_rows = [r for r in flow_records if r.get("trade_date") == session]
    future_flow_rows = [r for r in flow_records if r.get("trade_date") and r["trade_date"] > session]
    future_research_rows = [r for r in research_records if r.get("research_date") and r["research_date"] > selection_date]
    avail_times = source_availability or {}
    flow_available, flow_controls = _availability(selected_rows, cutoff, avail_times)
    research_available, research_controls = _availability(research_records, cutoff, avail_times)
    required_controls = flow_controls + (research_controls if cfg["research_overlay_enabled"] else [])
    sources_available = flow_available and (research_available if cfg["research_overlay_enabled"] else True)
    qualifying, excluded = _flow_gates(selected_rows, day, cfg)
    by_ticker = defaultdict(list)
    for r in qualifying: by_ticker[r["ticker"]].append(r)
    summary_records = summary_records or []
    reviews = thesis_reviews or {}
    all_summaries, rejected = [], []
    for ticker, rows in sorted(by_ticker.items()):
        bull = sum(r["premium_usd"] for r in rows if r["direction"] == "BULLISH")
        bear = sum(r["premium_usd"] for r in rows if r["direction"] == "BEARISH")
        net = bull - bear; share = bull / (bull + bear) if bull + bear else None
        reasons = []
        if net < cfg["minimum_net_bull_premium_usd"]: reasons.append(f"net bullish premium below ${cfg['minimum_net_bull_premium_usd']:,.0f} starting rule")
        if share is None or share < cfg["minimum_bull_share"]: reasons.append(f"bull share below {cfg['minimum_bull_share']:.0%} of qualified filtered sample")
        hits = _research_for(ticker, research_records, day, cfg["research_age_max_calendar_days"])
        review = reviews.get(ticker, {})
        hit_ids = {r["source_id"] for r in hits}
        reviewed_ids = set(review.get("supporting_source_ids", []))
        thesis_accepted = bool(review.get("review_status") == "accepted" and review.get("direction") == "BULLISH"
                               and reviewed_ids and reviewed_ids.issubset(hit_ids) and review.get("invalidation_condition")
                               and review.get("original_sources_verified") is True)
        continuing = bool(thesis_accepted and review.get("continuing_thesis") is True and review.get("continuing_thesis_evidence"))
        all_expiries = sorted({r["expiry"] for r in rows if r["direction"] == "BULLISH"})
        daily_context = [r for r in selected_rows if r.get("ticker") == ticker and r.get("asset_category") == "stock"]
        context_bull = sum(r.get("premium_usd") or 0 for r in daily_context if r.get("direction") == "BULLISH")
        context_bear = sum(r.get("premium_usd") or 0 for r in daily_context if r.get("direction") == "BEARISH")
        contract_bull_totals = defaultdict(float)
        for r in rows:
            if r["direction"] == "BULLISH": contract_bull_totals[r.get("option") or r["expiry"]] += r["premium_usd"]
        eligible_nights, night_evidence = [], []
        for offset in (1, 2, 3):
            entry_day = monday + timedelta(days=offset)
            if entry_day < day: continue
            exit_day = entry_day + timedelta(days=1)
            active = [e for e in all_expiries if date.fromisoformat(e) >= exit_day]
            active_rows = [r for r in rows if r["direction"] == "BULLISH" and r["expiry"] in active]
            night_evidence.append({"entry_date": entry_day.isoformat(), "exit_date": exit_day.isoformat(),
                                   "dte_at_entry_by_expiry": {e: (date.fromisoformat(e) - entry_day).days for e in all_expiries},
                                   "supporting_contracts_active_through_exit": active,
                                   "supporting_source_ids_active_through_exit": [r["source_id"] for r in active_rows],
                                   "historical_supporting_premium_active_through_exit_usd": sum(r["premium_usd"] for r in active_rows),
                                   "continuing_thesis_explicitly_reviewed": continuing,
                                   "calendar_requires_daily_exchange_session_check": True})
            if active or continuing: eligible_nights.append(entry_day.isoformat())
        # Research ranking is an ordinal diagnostic, never a win probability.
        stock_identity_verified = bool(review.get("verified_instrument_id") and review.get("instrument_type") in ("US_EQUITY", "US_ADR")
                                       and review.get("exact_symbol_matched") is True and review.get("instrument_identity_source_id"))
        summary = {"ticker": ticker, "instrument_id": review.get("verified_instrument_id"), "stock_identifier_verified": stock_identity_verified,
                   "instrument_classification_status": "verified_US_equity_or_ADR" if stock_identity_verified else "vendor_stock_sheet_only_unverified",
                   "flow_session": session, "bull_premium_usd": bull, "bear_premium_usd": bear, "net_bull_premium_usd": net,
                   "bull_share_of_qualifying_filtered_sample": share, "qualified_rows": len(rows),
                   "all_DTE_same_session_context": {"bull_premium_usd": context_bull, "bear_premium_usd": context_bear,
                                                     "net_bull_premium_usd": context_bull - context_bear,
                                                     "scope": "same flow session, all retained DTE; context only, not weekly numeric gate"},
                   "largest_bull_contract_share_of_qualified_bull_premium": max(contract_bull_totals.values(), default=0) / bull if bull else None,
                   "distinct_qualified_contract_description_count": len({str(r.get("option") or (r["expiry"], r["option_type"])) for r in rows}),
                   "source_flow_ids": [r["source_id"] for r in rows], "all_source_rows_retained": True,
                   "supporting_expiries": all_expiries, "last_eligible_entry": max(eligible_nights, default=None),
                   "eligible_nights": eligible_nights, "daily_evidence_expiry": night_evidence,
                   "original_trade_dte_range": [min(r["reported_trade_dte"] for r in rows), max(r["reported_trade_dte"] for r in rows)],
                   "selection_dte_range": [min(r["selection_dte"] for r in rows), max(r["selection_dte"] for r in rows)],
                   "quantity_exceeds_oi_row_count": sum(r.get("quantity_exceeds_oi") is True for r in rows),
                   "confirmed_opening_activity": False, "independent_option_buyers": None,
                   "flow_gate_pass": not reasons, "flow_gate_reasons": reasons,
                   "research_match_count_last_30_calendar_days": len(hits), "latest_research": [_research_excerpt(r) for r in hits[:3]],
                   "summary_context": [_research_excerpt(r) for r in summary_records if ticker in r.get("tickers", [])],
                   "research_direction": review.get("direction", "UNASSESSED"), "catalyst_class": review.get("catalyst_class", "UNASSESSED"),
                   "verified_event_in_holding_window": review.get("verified_event_in_holding_window", False),
                   "invalidation_condition": review.get("invalidation_condition"),
                   "thesis_review_accepted": thesis_accepted, "thesis_active": thesis_accepted and sources_available, "continuing_thesis": continuing,
                   "continuing_thesis_evidence": review.get("continuing_thesis_evidence") if continuing else None,
                   "source_available_at": max((control["available_at"] for control in required_controls if control["available_at"]), key=_timestamp, default=None) if all(control["availability_proven"] for control in required_controls) else None,
                   "selection_source_availability_proven": sources_available,
                   "execution_eligible": False, "probability_of_profit": None,
                   "readiness_blockers": ["Broker instrument and account eligibility require verification", "Daily quotes, technical and event gates have not been performed"]}
        if not sources_available: summary["readiness_blockers"].append("historical receipt times not proven by selection cutoff")
        if not thesis_accepted: summary["readiness_blockers"].append("specific directional/continuing thesis, original source and invalidation require review")
        if not eligible_nights: summary["readiness_blockers"].append("no active supporting expiry through an eligible exit and no continuing thesis")
        all_summaries.append(summary)
        if reasons: rejected.append({"ticker": ticker, "reasons": reasons, "flow": summary})
    already_summarized = set(by_ticker)
    excluded_by_ticker = defaultdict(list)
    for r in excluded:
        if r["asset_category"] == "stock" and r["ticker"] not in already_summarized:
            excluded_by_ticker[r["ticker"]].append(r)
    for ticker, records in sorted(excluded_by_ticker.items()):
        rejected.append({"ticker": ticker, "reasons": ["no rows pass the proposed weekly DTE/direction/premium/source-validity filter"],
                         "source_flow_ids": [r["source_id"] for r in records],
                         "row_reason_union": sorted({reason for r in records for reason in r["flow_gate_reasons"]}), "flow": None})
    flow_passing = [s for s in all_summaries if s["flow_gate_pass"]]
    flow_passing.sort(key=lambda s: (-s["net_bull_premium_usd"], -s["bull_share_of_qualifying_filtered_sample"], s["ticker"]))
    candidates = []
    for rank, summary in enumerate(flow_passing[:cfg["maximum_weekly_candidates"]], 1):
        candidates.append({**summary, "rank": rank,
                           "rank_basis": "untuned diagnostic net premium then filtered bull share then ticker, not probability",
                           "selection_status": "research_review_required"})
    overflow = flow_passing[cfg["maximum_weekly_candidates"]:]
    status = "DIAGNOSTIC_RESEARCH_ONLY" if sources_available else "INCOMPLETE_POINT_IN_TIME_RECONSTRUCTION"
    packet = {"strategy_version": "Rev12_weekly_overnight_1", "mode": "paper", "protocol": protocol,
              "selection_date": selection_date, "selection_cutoff": selection_cutoff, "week_start": monday.isoformat(),
              "week_final_entry_date": thursday.isoformat(), "flow_session": session,
              "status": status, "source_availability_controls": flow_controls + research_controls,
              "lookahead_controls": {"later_flow_rows_excluded": len(future_flow_rows), "later_research_rows_excluded": len(future_research_rows),
                                     "completed_session_only": True, "later_edited_file_used": True,
                                     "historical_archive_completeness_proven": False},
              "config": cfg, "source_manifest": source_manifest or [],
              "evaluation_variant": cfg["evaluation_variant"],
              "source_session_row_count": len(selected_rows), "stock_rows": sum(r.get("asset_category") == "stock" for r in selected_rows),
              "context_ETF_index_rows": sum(r.get("asset_category") != "stock" for r in selected_rows),
              "qualified_DTE_direction_premium_row_count": len(qualifying), "flow_passing_stock_count": len(flow_passing),
              "candidates": candidates, "research_overlay_accepted_candidates": [c["ticker"] for c in candidates if c["thesis_active"]],
              "accepted_weekly_stock_universe": [c["ticker"] for c in candidates if (c["thesis_active"] or not cfg["research_overlay_enabled"]) and c["stock_identifier_verified"] and sources_available],
              "candidate_list_role": "unsubmitted research diagnostics; numeric pass does not establish US-stock/broker eligibility or accepted weekly universe",
              "rejected_candidates": rejected, "overflow_candidates": [s["ticker"] for s in overflow],
              "excluded_source_rows": [{"source_id": r["source_id"], "ticker": r["ticker"], "trade_date": r["trade_date"], "expiry": r["expiry"],
                                         "selection_dte": r["selection_dte"], "premium_usd": r["premium_usd"], "reasons": r["flow_gate_reasons"]} for r in excluded],
              "possible_linked_leg_pairs_report_only": _possible_pairs(qualifying),
              "planned_orders": [], "actual_fills": [], "observed_profitability": None,
              "overall_readiness_blockers": ["Research theses have not been independently verified", "Daily broker gates unavailable", "No stock-price/fill observations supplied for this actual-data rehearsal"]}
    if not sources_available: packet["overall_readiness_blockers"].append("Point-in-time input availability is unproven")
    packet["selection_id"] = hashlib.sha256(json.dumps(packet, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]
    return packet


def build_later_rehearsal(bundle: dict, selection_date: str = "2026-10-07", cutoff: str | None = None, config: dict | None = None) -> dict:
    cutoff = cutoff or bundle["audit"]["observed_ingestion_at"]
    times = {m["file"]: m["observed_ingestion_at"] for m in bundle["audit"]["source_manifest"]}
    packet = weekly_selection(bundle["flow_records"], bundle["research_records"], selection_date, cutoff,
                              source_availability=times, protocol="later_rehearsal", summary_records=bundle["summary_records"],
                              source_manifest=bundle["audit"]["source_manifest"], config=config)
    packet["earliest_possible_entry"] = selection_date
    packet["entry_is_conditional_on_cutoff_before_final_decision_and_exchange_calendar"] = True
    packet["rehearsal_note"] = "Uses Oct6 completed flow after actual Oct7 ingestion. This is a declared later rehearsal, not the Tuesday-morning baseline and not a profit backtest."
    return packet


def write_selection(packet: dict, out_dir: str | Path, stem: str = "Weekly_Selection_Diagnostic") -> list[str]:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    jp = out / f"{stem}.json"; jp.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    local_cutoff = _timestamp(packet["selection_cutoff"]).astimezone(ZoneInfo("Europe/Zurich")).isoformat()
    lines = ["# Revision 12 weekly-selection diagnostic", "", f"Protocol: {packet['protocol']}. Selection cutoff: {local_cutoff} (Swiss local time). Flow session: {packet['flow_session']}.", "",
             f"Status: {packet['status']}. No orders or profitability observations are produced.", "",
             f"Source session: {packet['stock_rows']} stock rows and {packet['context_ETF_index_rows']} ETF/index context rows. {packet['qualified_DTE_direction_premium_row_count']} rows pass the proposed weekly row filter; {packet['flow_passing_stock_count']} stocks pass the numeric net/share rules.", "",
             "| Rank | Stock | Bull premium | Bear premium | Net bullish | Bull share of qualified sample | Supporting expiries | Thesis |", "|---:|---|---:|---:|---:|---:|---|---|"]
    for c in packet["candidates"]:
        lines.append(f"| {c['rank']} | {c['ticker']} | ${c['bull_premium_usd']:,.0f} | ${c['bear_premium_usd']:,.0f} | ${c['net_bull_premium_usd']:,.0f} | {c['bull_share_of_qualifying_filtered_sample']:.1%} | {', '.join(c['supporting_expiries'])} | requires original-source and direction review |")
    lines.extend(["", "The ranking is an untuned diagnostic ordering of qualified flow, not a conviction score, win probability or buy instruction. The research overlay has not accepted any stock without a reviewed specific directional mechanism, sources and invalidation.", "", "## Research evidence requiring review"])
    for c in packet["candidates"]:
        lines.extend(["", f"### {c['ticker']}", f"Eligible evidence nights: {', '.join(c['eligible_nights']) or 'none'}. No new flow is inferred from repeated eligibility."])
        for r in c["latest_research"]:
            lines.extend(["", f"Source: {r['source_id']}. Vendor row date: {r['research_date']}.", str(r['hidden_angle']), str(r['why_it_matters'])])
        lines.extend(["", "Outstanding: " + "; ".join(c["readiness_blockers"]) + "."])
    lines.extend(["", "## Rejected stocks", ""])
    for r in packet["rejected_candidates"]:
        lines.append(f"- {r['ticker']}: {'; '.join(r['reasons'])}.")
    lines.extend(["", "All excluded source IDs, row-level reasons, retained similar call/put pairs, research matches, evidence expiry per night and source hashes are in the JSON. ETF/index rows are context only. Costs and current broker facts remain missing, so no net-return claim is made."])
    mp = out / f"{stem}.md"; mp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [str(jp), str(mp)]


def receipt_times(receipts: dict, manifest: list[dict]) -> dict[str, str]:
    """CLI receipt claims require exact snapshot hashes and an evidence reference.

    verified=true records an operator's evidence review; it is not a claim that
    this program independently inspected the receipt record or its publisher.
    """
    by_file = {m["file"]: m["sha256"] for m in manifest}
    times = {}
    for name, receipt in receipts.items():
        if name not in by_file:
            raise ValueError(f"Receipt names a file outside the current snapshot: {name}")
        if not isinstance(receipt, dict):
            raise ValueError("Receipt entries require sha256, received_at, evidence_reference and verified fields")
        if receipt.get("sha256") != by_file[name]:
            raise ValueError(f"Receipt hash does not match the ingested snapshot: {name}")
        if receipt.get("verified") is True:
            if not receipt.get("received_at") or not receipt.get("evidence_reference"):
                raise ValueError(f"Verified receipt has no timestamp or evidence reference: {name}")
            _timestamp(receipt["received_at"])
            times[name] = receipt["received_at"]
    return times


def reviewed_theses(reviews: dict, cutoff: str) -> dict:
    """Validate accepted CLI reviews. A pending template never promotes a candidate."""
    knowledge_time = _timestamp(cutoff)
    for ticker, review in reviews.items():
        if not isinstance(review, dict):
            raise ValueError(f"Thesis review must be an object: {ticker}")
        if review.get("review_status") != "accepted":
            continue
        if not review.get("reviewed_at") or _timestamp(review["reviewed_at"]) > knowledge_time:
            raise ValueError(f"Accepted review was not recorded by the selection cutoff: {ticker}")
        if not review.get("reviewer") or not review.get("invalidation_condition"):
            raise ValueError(f"Accepted review requires reviewer and an explicit invalidation: {ticker}")
        originals = review.get("original_sources", [])
        if review.get("original_sources_verified") is not True or not originals:
            raise ValueError(f"Accepted review requires verified original-source references: {ticker}")
        for source in originals:
            if not isinstance(source, dict) or not source.get("reference") or not source.get("available_at"):
                raise ValueError(f"Original source needs reference and availability time: {ticker}")
            if _timestamp(source["available_at"]) > knowledge_time:
                raise ValueError(f"Original research source is later than the selection cutoff: {ticker}")
        if review.get("continuing_thesis") is True and not review.get("continuing_thesis_evidence"):
            raise ValueError(f"Continuing thesis requires evidence of a continuing mechanism: {ticker}")
    return reviews


def main(argv: list[str] | None = None) -> None:
    """One reproducible actual-input audit plus separate baseline and later rehearsal."""
    import argparse
    from .ingest import ingest_sources, write_audit
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Read-only Rev12 workbook audit and frozen weekly diagnostic. No orders.")
    parser.add_argument("--flow", type=Path, default=root / "data/rev12/raw/flow-135.xlsx")
    parser.add_argument("--angles", type=Path, default=root / "data/rev12/raw/hidden_angle_flow_database_OCT_6th_2026_updated.xlsx")
    parser.add_argument("--out", type=Path, default=root / "data/rev12/audit")
    parser.add_argument("--config", type=Path, default=root / "rev12_config.json")
    parser.add_argument("--thesis-reviews", type=Path, help="Structured reviewed-thesis map; pending values remain unaccepted")
    parser.add_argument("--availability", type=Path, help="Recorded receipt map with snapshot hashes and evidence references")
    parser.add_argument("--selection-date", help="Explicit selection YYYY-MM-DD; requires --cutoff")
    parser.add_argument("--cutoff", help="Explicit timezone-aware knowledge cutoff; requires --selection-date")
    parser.add_argument("--protocol", choices=("Monday_cutoff", "later_rehearsal"), default="Monday_cutoff")
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8-sig")) if args.config.exists() else None
    bundle = ingest_sources(args.flow, args.angles)
    written = write_audit(bundle, args.out)
    if bool(args.selection_date) != bool(args.cutoff):
        parser.error("--selection-date and --cutoff must be supplied together; no cutoff is backdated automatically")
    receipts = receipt_times(json.loads(args.availability.read_text(encoding="utf-8-sig")), bundle["audit"]["source_manifest"]) if args.availability else None
    reviews = json.loads(args.thesis_reviews.read_text(encoding="utf-8-sig")) if args.thesis_reviews else {}
    if not args.audit_only:
        observed = _timestamp(bundle["audit"]["observed_ingestion_at"]).astimezone(ZoneInfo("Europe/Zurich"))
        monday, _ = _week(observed.date())
        tuesday = monday + timedelta(days=1)
        baseline_cutoff = datetime.combine(tuesday, datetime.strptime("08:15", "%H:%M").time(), ZoneInfo("Europe/Zurich")).isoformat()
        if args.selection_date:
            checked_reviews = reviewed_theses(reviews, args.cutoff)
            availability = receipts if receipts is not None else {}
            packet = weekly_selection(bundle["flow_records"], bundle["research_records"], args.selection_date, args.cutoff,
                                      source_availability=availability, thesis_reviews=checked_reviews, protocol=args.protocol,
                                      summary_records=bundle["summary_records"], source_manifest=bundle["audit"]["source_manifest"], config=config)
            written += write_selection(packet, args.out, "Explicit_Weekly_Selection")
        else:
            if args.thesis_reviews or args.availability:
                parser.error("Reviewed theses or recorded receipts require an explicit --selection-date and --cutoff")
            baseline = weekly_selection(bundle["flow_records"], bundle["research_records"], tuesday.isoformat(), baseline_cutoff,
                                        summary_records=bundle["summary_records"], source_manifest=bundle["audit"]["source_manifest"], config=config)
            written += write_selection(baseline, args.out, f"Monday_Cutoff_{monday.isoformat()}_Diagnostic")
            completed_sessions = [r["trade_date"] for r in bundle["flow_records"] if r.get("trade_date") and r["trade_date"] < observed.date().isoformat()]
            if observed.weekday() in (1, 2, 3) and completed_sessions:
                later = build_later_rehearsal(bundle, observed.date().isoformat(), observed.isoformat(), config=config)
                written += write_selection(later, args.out)
            else:
                print("No eligible later-rehearsal entry weekday. Audit and baseline diagnostic saved; no candidate packet is executed.")
    print(json.dumps({"flow_rows": len(bundle["flow_records"]), "research_rows": len(bundle["research_records"]),
                      "output_files": [str(Path(p).relative_to(args.out)) for p in written], "actual_orders": 0}, indent=2))


if __name__ == "__main__": main()
