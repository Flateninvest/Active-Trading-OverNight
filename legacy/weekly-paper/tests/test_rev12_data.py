"""Meaningful deterministic data controls; fixtures are synthetic and show no edge."""
import unittest
from datetime import date
from weekly_strategy.ingest import infer_direction, expiry_fields, parse_date, ticker_tokens
from weekly_strategy.selection import weekly_selection, receipt_times, reviewed_theses


def flow(source_id="flow:1", ticker="AAPL", direction="BULLISH", premium=1_200_000,
         trade="2026-10-05", expiry="2026-10-09", quantity=1000):
    return {"source_id": source_id, "source_file": "flow.xlsx", "source_row": 6, "source_sheet": "Flow Analytics (Stocks)",
            "trade_date": trade, "ticker": ticker, "direction": direction, "premium_usd": premium,
            "asset_category": "stock", "side": "On Ask", "option_type": "CALL" if direction == "BULLISH" else "PUT",
            "expiry": expiry, "reported_trade_dte": (date.fromisoformat(expiry)-date.fromisoformat(trade)).days,
            "quantity": quantity, "quantity_exceeds_oi": True, "expiry_validation_flags": [], "validation_flags": []}


def research(source_id="angle:1", day="2026-10-05", ticker="AAPL"):
    return {"source_id": source_id, "source_file": "angles.xlsx", "source_row": 5, "source_sheet": "Hidden Angles Database",
            "research_date": day, "tickers": [ticker], "hidden_angle": "SYNTHETIC mechanism", "why_it_matters": "SYNTHETIC ongoing thesis",
            "company_name": "SYNTHETIC company", "thesis_verified": False}


TIMES={"flow.xlsx":"2026-10-05T23:00:00+02:00","angles.xlsx":"2026-10-05T21:00:00+02:00"}


def select(rows, angles=None, **kwargs):
    return weekly_selection(rows, angles if angles is not None else [research()], "2026-10-06", "2026-10-06T08:15:00+02:00", **kwargs)


class Rev12DataTests(unittest.TestCase):
    def test_direction_inference_does_not_treat_every_call_as_bullish(self):
        self.assertEqual(infer_direction("On Ask", "CALL")[0], "BULLISH")
        self.assertEqual(infer_direction("On Bid", "CALL")[0], "BEARISH")
        self.assertEqual(infer_direction("Above Ask", "PUT")[0], "BEARISH")
        self.assertIsNone(infer_direction("Mid", "CALL")[0])

    def test_date_storage_types_and_multi_company_identifiers(self):
        self.assertEqual(parse_date("2026-10-05"),date(2026,10,5))
        self.assertEqual(parse_date("10/05/2026"),date(2026,10,5))
        self.assertEqual(ticker_tokens("$AAPL / WDC"),["AAPL","WDC"])
        self.assertEqual(ticker_tokens("Company prose is not a ticker"),[])

    def test_expiry_requires_calendar_dte_and_flags_text_conflict(self):
        actual=expiry_fields(date(2026,10,5),4.0,"AAPL Oct26 9th 250 Calls")
        self.assertEqual(actual["expiry"],"2026-10-09")
        self.assertEqual(actual["expiry_validation_flags"],[])
        bad=expiry_fields(date(2026,10,5),5.0,"AAPL Oct26 9th 250 Calls")
        self.assertTrue(bad["expiry_validation_flags"])
        self.assertIsNone(expiry_fields(date(2026,10,5),4.5,"AAPL Oct26 Calls")["expiry"])

    def test_future_flow_cannot_change_tuesday_morning_selection(self):
        first=select([flow()],source_availability=TIMES)
        future=flow("flow:2",ticker="MU",trade="2026-10-06",premium=100_000_000)
        after=select([flow(),future],source_availability=TIMES)
        self.assertEqual([c["ticker"] for c in first["candidates"]],["AAPL"])
        self.assertEqual([c["ticker"] for c in after["candidates"]],["AAPL"])
        self.assertEqual(after["lookahead_controls"]["later_flow_rows_excluded"],1)

    def test_later_edited_hidden_angle_is_never_backdated(self):
        packet=select([flow()],[research(day="2026-10-07")],source_availability=TIMES)
        self.assertEqual(packet["candidates"][0]["research_match_count_last_30_calendar_days"],0)
        self.assertFalse(packet["candidates"][0]["thesis_active"])
        self.assertEqual(packet["lookahead_controls"]["later_research_rows_excluded"],1)

    def test_missing_or_late_receipt_time_blocks_forward_claim(self):
        unknown=select([flow()])
        self.assertEqual(unknown["status"],"INCOMPLETE_POINT_IN_TIME_RECONSTRUCTION")
        late=select([flow()],source_availability={**TIMES,"flow.xlsx":"2026-10-06T09:00:00+02:00"})
        self.assertEqual(late["status"],"INCOMPLETE_POINT_IN_TIME_RECONSTRUCTION")
        self.assertEqual(late["planned_orders"],[])

    def test_expired_zero_dte_is_historical_context(self):
        packet=select([flow(expiry="2026-10-05")])
        self.assertEqual(packet["candidates"],[])
        self.assertEqual(packet["excluded_source_rows"][0]["selection_dte"],-1)

    def test_source_identical_prints_retained_without_execution_id_proof(self):
        a=flow("flow:1",premium=600_000)
        b={**a,"source_id":"flow:2","source_row":7}
        self.assertEqual(select([a])["candidates"],[])
        packet=select([a,b])
        self.assertEqual(packet["candidates"][0]["bull_premium_usd"],1_200_000)
        self.assertEqual(packet["candidates"][0]["source_flow_ids"],["flow:1","flow:2"])

    def test_possible_linked_call_put_pair_reported_without_deletion(self):
        packet=select([flow(premium=2_000_000),flow("flow:2",direction="BEARISH",premium=200_000)])
        c=packet["candidates"][0]
        self.assertEqual(c["bear_premium_usd"],200_000)
        self.assertEqual(len(packet["possible_linked_leg_pairs_report_only"]),1)
        self.assertFalse(c["confirmed_opening_activity"])

    def test_expiry_must_cover_next_exit_or_explicit_continuing_thesis(self):
        packet=select([flow(expiry="2026-10-08")])
        self.assertEqual(packet["candidates"][0]["eligible_nights"],["2026-10-06","2026-10-07"])
        accepted={"AAPL":{"review_status":"accepted","direction":"BULLISH","supporting_source_ids":["angle:1"],
                          "invalidation_condition":"SYNTHETIC explicit failure","original_sources_verified":True,"continuing_thesis":True,
                          "continuing_thesis_evidence":"SYNTHETIC mechanism persists after expiry"}}
        continuing=select([flow(expiry="2026-10-08")],thesis_reviews=accepted)
        self.assertEqual(continuing["candidates"][0]["eligible_nights"],["2026-10-06","2026-10-07","2026-10-08"])
        self.assertFalse(continuing["candidates"][0]["execution_eligible"])

    def test_research_review_cannot_reference_unmatched_source(self):
        forged={"AAPL":{"review_status":"accepted","direction":"BULLISH","supporting_source_ids":["missing:1"],
                        "invalidation_condition":"SYNTHETIC","original_sources_verified":True,"continuing_thesis":True}}
        self.assertFalse(select([flow()],thesis_reviews=forged)["candidates"][0]["thesis_active"])

    def test_accepted_review_cannot_bypass_missing_hidden_angle_receipt(self):
        reviewed={"AAPL":{"review_status":"accepted","direction":"BULLISH","supporting_source_ids":["angle:1"],
                          "invalidation_condition":"SYNTHETIC","original_sources_verified":True}}
        packet=select([flow()],thesis_reviews=reviewed,source_availability={"flow.xlsx":TIMES["flow.xlsx"]})
        self.assertTrue(packet["candidates"][0]["thesis_review_accepted"])
        self.assertFalse(packet["candidates"][0]["thesis_active"])
        self.assertIsNone(packet["candidates"][0]["source_available_at"])

    def test_strict_monday_session_and_timezone_controls(self):
        with self.assertRaises(ValueError): select([flow()],flow_session="2026-10-06")
        with self.assertRaises(ValueError): weekly_selection([flow()],[research()],"2026-10-07","2026-10-07T08:15:00+02:00")
        with self.assertRaises(ValueError): weekly_selection([flow()],[research()],"2026-10-06","2026-10-06T08:15:00")

    def test_etf_context_cannot_be_a_stock_selection(self):
        etf={**flow(ticker="SPY",premium=100_000_000),"asset_category":"ETF_or_index_context"}
        self.assertEqual(select([etf])["candidates"],[])
        misplaced={**flow(ticker="TECL",premium=100_000_000),"also_appears_in_ETF_index_sheet":True}
        self.assertEqual(select([misplaced])["candidates"],[])

    def test_premium_arithmetic_error_cannot_drive_selection(self):
        malformed={**flow(),"validation_flags":["premium differs from quantity x price x assumed100 multiplier"]}
        self.assertEqual(select([malformed])["candidates"],[])

    def test_ten_is_a_ceiling_and_ranking_is_repeatable(self):
        rows=[flow(f"flow:{i}",ticker=f"T{i:02}",premium=1_200_000+i) for i in range(12)]
        packet=select(rows)
        self.assertEqual(len(packet["candidates"]),10)
        self.assertEqual(len(packet["overflow_candidates"]),2)
        self.assertEqual(packet["selection_id"],select(rows)["selection_id"])
        self.assertEqual(select([])["candidates"],[])

    def test_repository_configuration_controls_selection_thresholds(self):
        settings={"maximum_candidates":3,"selection_rules_proposed":{"minimum_net_bullish_premium_usd":2_000_000,
                   "minimum_bullish_share_filtered_sample":0.8,"weekly_selection_dte_min":2,"weekly_selection_dte_max":10}}
        self.assertEqual(select([flow()],config=settings)["candidates"],[])
        rows=[flow(f"flow:{i}",ticker=f"T{i:02}",premium=3_000_000) for i in range(4)]
        self.assertEqual(len(select(rows,config=settings)["candidates"]),3)

    def test_recorded_receipt_is_bound_to_exact_snapshot(self):
        manifest=[{"file":"flow.xlsx","sha256":"abc"}]
        self.assertEqual(receipt_times({"flow.xlsx":{"sha256":"abc","received_at":None,"verified":False}},manifest),{})
        with self.assertRaises(ValueError):receipt_times({"flow.xlsx":{"sha256":"wrong","verified":True}},manifest)
        with self.assertRaises(ValueError):receipt_times({"flow.xlsx":{"sha256":"abc","received_at":TIMES["flow.xlsx"],"verified":True}},manifest)
        supplied={"flow.xlsx":{"sha256":"abc","received_at":TIMES["flow.xlsx"],"evidence_reference":"SYNTHETIC receipt","verified":True}}
        self.assertEqual(receipt_times(supplied,manifest),{"flow.xlsx":TIMES["flow.xlsx"]})

    def test_pending_or_later_review_cannot_claim_validation(self):
        cutoff="2026-10-06T08:15:00+02:00"
        pending={"AAPL":{"review_status":"pending","original_sources_verified":False}}
        self.assertEqual(reviewed_theses(pending,cutoff),pending)
        with self.assertRaises(ValueError):reviewed_theses({"AAPL":{"review_status":"accepted"}},cutoff)
        later={"AAPL":{"review_status":"accepted","reviewed_at":"2026-10-06T09:00:00+02:00"}}
        with self.assertRaises(ValueError):reviewed_theses(later,cutoff)

    def test_flow_only_variant_is_explicit_and_does_not_manufacture_thesis(self):
        cfg={"research_overlay_enabled":False,"evaluation_variant":"weekly_flow_only"}
        packet=select([flow()],angles=[],config=cfg,source_availability={"flow.xlsx":TIMES["flow.xlsx"]})
        self.assertEqual(packet["evaluation_variant"],"weekly_flow_only")
        self.assertEqual(packet["status"],"DIAGNOSTIC_RESEARCH_ONLY")
        self.assertFalse(packet["candidates"][0]["thesis_active"])
        self.assertEqual(packet["candidates"][0]["source_available_at"],TIMES["flow.xlsx"])
        with self.assertRaises(ValueError):select([flow()],config={"research_overlay_enabled":False})


if __name__ == "__main__": unittest.main()
