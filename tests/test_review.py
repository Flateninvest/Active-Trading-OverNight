"""Adversarial exact-proposal shadow review tests. All financial facts invented."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from active_trading.risk.review import (ReviewError, authorization_verifier,
    canonical_hash, review_proposal, sign_review)

KEY = b"SYNTHETIC_TEST_KEY_NEVER_DEPLOY_THIS" * 2


def fixture():
    packet = json.loads((ROOT / "examples" / "shadow_review_fixture.json").read_text())
    policy = json.loads((ROOT / "spec" / "strategy_spec.provisional.json").read_text())
    proposal = packet["proposal"]
    proposal["spec_hash"] = canonical_hash(policy)
    proposal["calendar_hash"] = canonical_hash(packet["calendar"])
    proposal["code_commit"] = "a" * 40
    packet["review"]["proposal_digest"] = canonical_hash(proposal)
    packet["review"] = sign_review(packet["review"], KEY)
    return packet, policy


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.packet, self.policy = fixture()

    def check(self):
        return review_proposal(self.packet["proposal"], self.packet["review"], self.policy,
            reviewer_keys={"fictional-reviewer": KEY}, now=self.packet["now"])

    def resign(self):
        self.packet["proposal"]["spec_hash"] = canonical_hash(self.policy)
        self.packet["review"]["proposal_digest"] = canonical_hash(self.packet["proposal"])
        self.packet["review"] = sign_review(self.packet["review"], KEY)

    def test_pass_records_no_capital_authority(self):
        result = self.check()
        self.assertTrue(result["reviewed"])
        self.assertFalse(result["capital_approval"])
        self.assertFalse(result["broker_writes"])

    def test_raw_unsigned_pass_rejected(self):
        self.packet["review"].pop("signature")
        with self.assertRaises(ReviewError): self.check()

    def test_tampered_reviewer_packet_rejected(self):
        self.packet["review"]["checks"]["ta"]["evidence"] = ["changed"]
        with self.assertRaises(ReviewError): self.check()

    def test_unknown_reviewer_and_wrong_key_rejected(self):
        for keys in ({}, {"fictional-reviewer": b"wrong-key" * 5}):
            with self.subTest(keys=len(keys)), self.assertRaises(ReviewError):
                review_proposal(self.packet["proposal"], self.packet["review"], self.policy,
                    reviewer_keys=keys, now=self.packet["now"])

    def test_self_review_rejected(self):
        self.packet["proposal"]["analyst_id"] = "fictional-reviewer"
        self.resign()
        with self.assertRaises(ReviewError): self.check()

    def test_changed_proposal_invalidates_review(self):
        for key, value in (("quantity", "5"), ("account_id", "another"),
                           ("input_hashes", ["d" * 64]), ("code_commit", "b" * 40)):
            packet, policy = fixture()
            packet["proposal"][key] = value
            with self.subTest(key=key), self.assertRaises(ReviewError):
                review_proposal(packet["proposal"], packet["review"], policy,
                    reviewer_keys={"fictional-reviewer": KEY}, now=packet["now"])

    def test_changed_policy_invalidates_review(self):
        self.policy["risk"]["maximum_positions"] = 2
        with self.assertRaises(ReviewError): self.check()

    def test_missing_or_rejecting_check_fails(self):
        for field in ("source_quality", "thesis", "ta", "calendar_events", "costs_liquidity",
                      "ownership_account", "risk_exposure"):
            self.packet, self.policy = fixture()
            del self.packet["review"]["checks"][field]
            self.resign()
            with self.subTest(field=field), self.assertRaises(ReviewError): self.check()
        self.packet, self.policy = fixture()
        self.packet["review"]["checks"]["ta"]["status"] = "FAIL"
        self.resign()
        with self.assertRaises(ReviewError): self.check()

    def test_high_volatility_requires_enhanced_review(self):
        self.packet["proposal"]["high_beta_or_volatile"] = True
        self.resign()
        with self.assertRaises(ReviewError): self.check()
        self.packet["review"]["checks"]["enhanced_volatility"] = {
            "status": "PASS", "evidence": ["INVENTED_ENHANCED_REVIEW"]}
        self.resign()
        self.assertEqual(self.check()["decision"], "PASS")

    def test_expired_or_future_review_rejected(self):
        self.packet["now"] = "2026-10-08T19:56:00Z"
        with self.assertRaises(ReviewError): self.check()
        self.packet["now"] = "2026-10-08T19:54:59Z"
        with self.assertRaises(ReviewError): self.check()

    def test_stale_future_or_crossed_quotes_rejected(self):
        for field, value in (("observed_at", "2026-10-08T19:53:59Z"),
                             ("observed_at", "2026-10-08T19:55:01Z"), ("bid", "101"),
                             ("bid", "99")):
            self.packet, self.policy = fixture()
            self.packet["proposal"]["quote"][field] = value
            self.resign()
            with self.subTest(field=field, value=value), self.assertRaises(ReviewError): self.check()

    def test_unknown_cost_or_omitted_reserve_rejected(self):
        self.packet["proposal"]["costs"]["status"] = "UNKNOWN"
        self.resign()
        with self.assertRaises(ReviewError): self.check()
        self.packet, self.policy = fixture()
        self.packet["proposal"]["entry_cost_reserve_usd"] = "0"
        self.resign()
        with self.assertRaises(ReviewError): self.check()

    def test_risk_snapshot_blocks_high_score_unreconciled_stale(self):
        for field, value in (("broker_risk_score", "6"), ("reconciled", False),
                             ("observed_at", "2026-10-08T19:50:00Z"),
                             ("mode", "DEMO"), ("available_cash_usd", "400")):
            self.packet, self.policy = fixture()
            self.packet["proposal"]["account_snapshot"][field] = value
            self.resign()
            with self.subTest(field=field), self.assertRaises(ReviewError): self.check()

    def test_shared_pending_exposure_and_duplicate_underlying(self):
        for exposures in ([{"instrument_id": "fictional-instrument-1", "reserved_usd": "1"}],
                          [{"instrument_id": "other", "reserved_usd": "1200"}],
                          [{"instrument_id": str(i), "reserved_usd": "1"} for i in range(3)]):
            self.packet, self.policy = fixture()
            self.packet["proposal"]["account_snapshot"]["exposures"] = exposures
            self.resign()
            with self.subTest(exposures=exposures), self.assertRaises(ReviewError): self.check()

    def test_quantity_name_limit_and_notional_consistency(self):
        for qty, notional in (("5", "501.25"), ("4", "400.20"), ("NaN", "401.20")):
            self.packet, self.policy = fixture()
            self.packet["proposal"]["quantity"] = qty
            self.packet["proposal"]["approved_notional_usd"] = notional
            self.resign()
            with self.subTest(qty=qty), self.assertRaises(ReviewError): self.check()

    def test_existing_name_breach_blocks_new_entry_including_split_rows(self):
        for amounts in (("600",), ("300", "300")):
            self.packet, self.policy = fixture()
            self.packet["proposal"]["account_snapshot"]["exposures"] = [
                {"instrument_id": "other", "reserved_usd": amount} for amount in amounts]
            self.resign()
            with self.subTest(amounts=amounts), self.assertRaisesRegex(ReviewError, "Existing held/pending"):
                self.check()

    def test_existing_name_at_cap_allows_new_entry_including_split_rows(self):
        for amounts in (("500",), ("250", "250")):
            self.packet, self.policy = fixture()
            self.packet["proposal"]["account_snapshot"]["exposures"] = [
                {"instrument_id": "other", "reserved_usd": amount} for amount in amounts]
            self.resign()
            with self.subTest(amounts=amounts):
                self.assertEqual(self.check()["decision"], "PASS")

    def test_existing_name_limit_uses_trusted_policy_weight(self):
        self.policy["risk"]["maximum_name_weight"] = 0.08
        self.packet["proposal"]["quantity"] = "3"
        self.packet["proposal"]["approved_notional_usd"] = "301.15"
        self.packet["proposal"]["account_snapshot"]["exposures"] = [
            {"instrument_id": "other", "reserved_usd": "400"}]
        self.resign()
        self.assertEqual(self.check()["decision"], "PASS")
        self.packet["proposal"]["account_snapshot"]["exposures"][0]["reserved_usd"] = "400.01"
        self.resign()
        with self.assertRaisesRegex(ReviewError, "Existing held/pending"):
            self.check()

    def test_missing_wrong_week_or_outside_band_reference(self):
        for field, value in (("date", "2026-09-28"), ("date", "2026-10-06"), ("close", "90")):
            self.packet, self.policy = fixture()
            self.packet["proposal"]["monday_reference"][field] = value
            self.resign()
            with self.subTest(field=field), self.assertRaises(ReviewError): self.check()

    def test_real_demo_short_cfd_unfrozen_proposals_rejected(self):
        for field, value in (("mode", "LIVE"), ("mode", "DEMO"), ("side", "SELL"),
                             ("product", "CFD"), ("leverage", 2), ("currency", "EUR"),
                             ("in_frozen_register", False), ("protected_or_unrelated_position", True)):
            self.packet, self.policy = fixture()
            self.packet["proposal"][field] = value
            self.resign()
            with self.subTest(field=field), self.assertRaises(ReviewError): self.check()

    def test_verifier_recomputes_checks_instead_of_trusting_pass(self):
        gate = self.check()
        verify = authorization_verifier(self.packet["review"], self.policy, {"fictional-reviewer": KEY})
        self.assertTrue(verify(self.packet["proposal"], gate, self.packet["now"]))
        tampered = deepcopy(gate)
        tampered["capital_approval"] = True
        self.assertFalse(verify(self.packet["proposal"], tampered, self.packet["now"]))
        self.assertFalse(verify(self.packet["proposal"], gate, "2026-10-08T19:56:00Z"))


if __name__ == "__main__": unittest.main()
