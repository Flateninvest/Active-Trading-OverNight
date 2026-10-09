"""Synthetic offline state-machine checks. No accounts, market prices or orders."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from active_trading.operations import LedgerError, ShadowLedger, canonical_digest, next_opening


ROOT = Path(__file__).resolve().parents[1]
ENTRY = "2026-10-07T19:55:00+00:00"
OPEN = "2026-10-08T13:30:00+00:00"


def fixture_calendar():
    return {"calendar_id": "SYNTHETIC_XNYS", "source": "SYNTHETIC_FIXTURE_NOT_MARKET_DATA",
            "observed_at": "2026-10-07T06:00:00+00:00", "complete_from": "2026-10-07",
            "complete_through": "2026-10-08", "sessions": [
                {"date": "2026-10-07", "open": "2026-10-07T13:30:00Z", "close": "2026-10-07T20:00:00Z"},
                {"date": "2026-10-08", "open": OPEN, "close": "2026-10-08T20:00:00Z"}]}


def fixture_proposal(calendar=None, **changes):
    calendar = calendar or fixture_calendar()
    proposal = {"proposal_id": "SYNTHETIC_PROPOSAL", "mode": "SHADOW", "account_id": "SYNTHETIC_ACCOUNT",
                "strategy_id": "SYNTHETIC_STRATEGY", "instrument_id": "SYNTHETIC_A",
                "sleeve": "FLOW_RESEARCH_OVERNIGHT", "entry_session": "2026-10-07", "quantity": "5",
                "spec_hash": "SYNTHETIC_SPEC_HASH", "code_commit": "SYNTHETIC_CODE_ID",
                "input_hashes": ["SYNTHETIC_INPUT_HASH"], "calendar_hash": canonical_digest(calendar),
                "entry_not_before": "2026-10-07T19:30:00Z", "entry_cutoff": "2026-10-07T19:59:00Z",
                "exit_open": OPEN, "entry_price_limit": "99", "entry_cost_reserve_usd": "5",
                "approved_notional_usd": "500", "nav_usd": "5000",
                "account_snapshot": {"available_cash_usd": "5000", "exposures": []}}
    proposal.update(changes)
    return proposal


def fixture_authorization(proposal, **changes):
    record = {"proposal_digest": canonical_digest(proposal), "reviewed": True, "boundary_verified": True,
              "mode": "SHADOW", "decision": "PASS", "review_id": "SIMULATED_APPROVAL",
              "spec_hash": proposal["spec_hash"], "checked_at": ENTRY, "valid_until": "2026-10-07T19:59:00Z"}
    record.update(changes)
    return record


def synthetic_verifier(proposal, authorization, now):
    # Deliberately only a fixture callback: this is not a deployed auth boundary.
    return authorization["review_id"] == "SIMULATED_APPROVAL"


class LedgerTests(unittest.TestCase):
    def setUp(self):
        # Portable runner redirects default temp inside Git; private state must
        # instead be outside that checkout even for fictional fixture accounts.
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-ledger-", dir=ROOT.parent)
        self.path = Path(self.temp.name) / "private-shadow.sqlite"
        self.ledger = ShadowLedger(self.path, repository_root=ROOT)

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def register(self, proposal=None, authorization=None, **kwargs):
        proposal = proposal or fixture_proposal()
        authorization = authorization or fixture_authorization(proposal)
        return self.ledger.register_entry(proposal, authorization, ENTRY, fixture_calendar(),
                                          authorization_verifier=kwargs.get("verifier", synthetic_verifier))

    def attempt(self, intent, name="SYNTHETIC_ATTEMPT", now=ENTRY):
        return self.ledger.begin_attempt(intent["intent_id"], name, now, authorization_verifier=synthetic_verifier)

    def fill(self, intent, quantity="5", *, fill_id="SYNTHETIC_BUY", side="BUY", at=ENTRY,
             position_id="SYNTHETIC_POSITION", **changes):
        record = {"fill_id": fill_id, "intent_id": intent["intent_id"], "mode": "SHADOW",
                  "account_id": "SYNTHETIC_ACCOUNT", "strategy_id": "SYNTHETIC_STRATEGY",
                  "instrument_id": "SYNTHETIC_A", "position_id": position_id, "side": side,
                  "quantity": quantity, "price": "98", "currency": "USD", "filled_at": at}
        record.update(changes)
        return self.ledger.record_fill(record, at)

    def snapshot(self, *, rid="SYNTHETIC_RECONCILIATION", at=ENTRY, orders=None, **changes):
        record = {"reconciliation_id": rid, "mode": "SHADOW", "account_id": "SYNTHETIC_ACCOUNT",
                  "strategy_id": "SYNTHETIC_STRATEGY", "observed_at": at, "source": "SYNTHETIC_FIXTURE",
                  "orders_complete": True, "fills_complete": True, "positions_complete": True,
                  "fill_ids": [row["fill_id"] for row in self.ledger.fills()], "orders": orders or [],
                  "positions": [{key: row[key] for key in ("position_id", "instrument_id", "quantity")}
                                for row in self.ledger.positions()]}
        record.update(changes)
        return record

    def bought(self, quantity="5"):
        intent = self.register()
        self.attempt(intent)
        self.fill(intent, quantity)
        return intent

    def test_register_persists_exit_before_any_fill(self):
        intent = self.register()
        self.assertEqual(intent["state"], "PLANNED")
        self.assertEqual(intent["exit_open"], OPEN)
        self.assertEqual(self.ledger.positions(), [])
        self.assertEqual(self.ledger.event_log()[0]["kind"], "ENTRY_PLANNED")

    def test_same_proposal_is_idempotent(self):
        one, two = self.register(), self.register()
        self.assertEqual(one["intent_id"], two["intent_id"])
        self.assertEqual(len(self.ledger.event_log()), 1)

    def test_same_underlying_across_sleeves_cannot_duplicate(self):
        self.register()
        with self.assertRaisesRegex(LedgerError, "different entry intent"):
            self.register(fixture_proposal(sleeve="EARNINGS_OVERNIGHT"))

    def test_raw_pass_without_external_verification_is_rejected(self):
        with self.assertRaisesRegex(LedgerError, "verification failed"):
            self.register(verifier=lambda *args: False)
        self.assertEqual(self.ledger.event_log(), [])

    def test_non_boolean_verifier_return_is_rejected(self):
        with self.assertRaises(LedgerError):
            self.register(verifier=lambda *args: "PASS")

    def test_exact_proposal_binding_rejects_changed_quantity(self):
        proposal = fixture_proposal()
        authorization = fixture_authorization(proposal)
        proposal["quantity"] = "4"
        with self.assertRaisesRegex(LedgerError, "binding"):
            self.register(proposal, authorization)

    def test_spec_binding_must_match(self):
        proposal = fixture_proposal()
        with self.assertRaisesRegex(LedgerError, "binding"):
            self.register(proposal, fixture_authorization(proposal, spec_hash="DIFFERENT"))

    def test_expired_review_rejected(self):
        proposal = fixture_proposal()
        with self.assertRaisesRegex(LedgerError, "stale"):
            self.register(proposal, fixture_authorization(proposal, valid_until="2026-10-07T19:54:00Z"))

    def test_entry_attempt_needs_fresh_verifier(self):
        intent = self.register()
        with self.assertRaisesRegex(LedgerError, "fresh external"):
            self.ledger.begin_attempt(intent["intent_id"], "NO_VERIFIER", ENTRY)

    def test_review_expiry_between_registration_and_attempt_blocks(self):
        proposal = fixture_proposal()
        intent = self.register(proposal, fixture_authorization(proposal, valid_until="2026-10-07T19:55:30Z"))
        with self.assertRaisesRegex(LedgerError, "expired"):
            self.attempt(intent, now="2026-10-07T19:56:00Z")

    def test_demo_and_live_modes_rejected(self):
        for mode in ("DEMO", "LIVE"):
            with self.subTest(mode=mode), self.assertRaisesRegex(LedgerError, "SHADOW"):
                self.register(fixture_proposal(mode=mode))

    def test_private_database_inside_git_rejected(self):
        with self.assertRaisesRegex(LedgerError, "outside"):
            ShadowLedger(ROOT / ".runtime" / "should-not-be-created.sqlite", repository_root=ROOT)

    def test_shared_book_reservation_cap_and_no_redistribution(self):
        for instrument in ("SYNTHETIC_A", "SYNTHETIC_B", "SYNTHETIC_C"):
            self.register(fixture_proposal(instrument_id=instrument))
        self.assertEqual(self.ledger.exposure_snapshot("SYNTHETIC_ACCOUNT", "SYNTHETIC_STRATEGY")["reserved_notional_usd"], "1500")
        with self.assertRaisesRegex(LedgerError, "shared-book"):
            self.register(fixture_proposal(instrument_id="SYNTHETIC_D"))

    def test_cost_reserve_included_in_per_name_cap(self):
        with self.assertRaisesRegex(LedgerError, "10%"):
            self.register(fixture_proposal(entry_cost_reserve_usd="6", approved_notional_usd="501"))

    def test_invalid_notional_and_nonfinite_inputs_rejected(self):
        for changes in ({"approved_notional_usd": "499"}, {"quantity": "NaN"}, {"quantity": True}):
            with self.subTest(changes=changes), self.assertRaises(LedgerError):
                self.register(fixture_proposal(**changes))

    def test_accepted_is_not_a_fill(self):
        intent = self.register()
        self.attempt(intent)
        self.ledger.record_accepted("SYNTHETIC_ATTEMPT", "SYNTHETIC_ORDER", ENTRY)
        self.assertEqual(self.ledger.positions(), [])
        self.assertEqual(self.ledger.get_intent(intent["intent_id"])["state"], "SUBMITTED")

    def test_fill_requires_recorded_attempt(self):
        with self.assertRaisesRegex(LedgerError, "attempt"):
            self.fill(self.register())

    def test_fill_idempotent_and_conflicts_fail_atomically(self):
        intent = self.register()
        self.attempt(intent)
        first, repeated = self.fill(intent), self.fill(intent)
        self.assertEqual(first["sequence"], repeated["sequence"])
        with self.assertRaisesRegex(LedgerError, "conflicting"):
            self.fill(intent, price="99")
        self.assertEqual(self.ledger.positions()[0]["quantity"], "5")

    def test_fill_rejects_wrong_account_instrument_and_side(self):
        intent = self.register()
        self.attempt(intent)
        for changes in ({"account_id": "UNRELATED"}, {"instrument_id": "UNRELATED"}, {"side": "SELL"}):
            with self.subTest(changes=changes), self.assertRaises(LedgerError):
                self.fill(intent, **changes)
        self.assertEqual(self.ledger.positions(), [])

    def test_partial_fills_and_sequence_survive_restart(self):
        intent = self.bought("2")
        seq1 = self.ledger.fills()[0]["sequence"]
        self.ledger.close()
        self.ledger = ShadowLedger(self.path, repository_root=ROOT)
        self.assertEqual(self.ledger.positions()[0]["quantity"], "2")
        self.assertEqual(self.ledger.get_intent(intent["intent_id"])["state"], "PARTIAL")
        seq2 = self.fill(intent, "3", fill_id="SYNTHETIC_BUY_2")["sequence"]
        self.assertGreater(seq2, seq1)
        self.assertEqual(self.ledger.positions()[0]["quantity"], "5")
        self.assertEqual(self.ledger.get_intent(intent["intent_id"])["state"], "FILLED")

    def test_timeout_blocks_retry_until_all_three_snapshot_sections(self):
        intent = self.register()
        self.attempt(intent)
        self.ledger.mark_unknown("SYNTHETIC_ATTEMPT", ENTRY, "SYNTHETIC_TIMEOUT")
        with self.assertRaisesRegex(LedgerError, "No retry"):
            self.attempt(intent, "SECOND_ATTEMPT")
        for section in ("orders_complete", "fills_complete", "positions_complete"):
            with self.subTest(section=section), self.assertRaisesRegex(LedgerError, "complete"):
                self.ledger.reconcile(self.snapshot(**{section: False}), ENTRY)
        self.ledger.reconcile(self.snapshot(), ENTRY)
        self.assertEqual(self.attempt(intent, "SECOND_ATTEMPT")["state"], "SUBMITTING")

    def test_unknown_full_fill_still_needs_order_reconciliation(self):
        intent = self.register()
        self.attempt(intent)
        self.ledger.mark_unknown("SYNTHETIC_ATTEMPT", ENTRY, "SYNTHETIC_TIMEOUT")
        self.fill(intent)
        self.assertEqual(self.ledger.get_intent(intent["intent_id"])["state"], "UNKNOWN")
        with self.assertRaisesRegex(LedgerError, "Unknown entry"):
            self.register(fixture_proposal(instrument_id="SYNTHETIC_B"))
        self.ledger.reconcile(self.snapshot(), ENTRY)
        self.assertEqual(self.ledger.get_intent(intent["intent_id"])["state"], "FILLED")

    def test_accepted_order_cannot_disappear_from_snapshot(self):
        intent = self.register()
        self.attempt(intent)
        self.ledger.record_accepted("SYNTHETIC_ATTEMPT", "SYNTHETIC_ORDER", ENTRY)
        self.ledger.mark_unknown("SYNTHETIC_ATTEMPT", ENTRY, "SYNTHETIC_TIMEOUT")
        with self.assertRaisesRegex(LedgerError, "omits an accepted"):
            self.ledger.reconcile(self.snapshot(), ENTRY)

    def test_unknown_order_discovered_by_complete_snapshot_is_bound(self):
        intent = self.register()
        self.attempt(intent)
        self.ledger.mark_unknown("SYNTHETIC_ATTEMPT", ENTRY, "SYNTHETIC_TIMEOUT")
        orders = [{"intent_id": intent["intent_id"], "order_id": "DISCOVERED_ORDER", "status": "OPEN", "remaining_quantity": "5"}]
        self.ledger.reconcile(self.snapshot(orders=orders), ENTRY)
        self.assertEqual(self.ledger.get_intent(intent["intent_id"])["state"], "SUBMITTED")
        with self.assertRaisesRegex(LedgerError, "No retry"):
            self.attempt(intent, "DUPLICATE")

    def test_position_and_fill_reconciliation_mismatch_blocks(self):
        self.bought("2")
        wrong_position = self.snapshot(positions=[{"position_id": "SYNTHETIC_POSITION", "instrument_id": "SYNTHETIC_A", "quantity": "1"}])
        with self.assertRaisesRegex(LedgerError, "position mismatch"):
            self.ledger.reconcile(wrong_position, ENTRY)
        with self.assertRaisesRegex(LedgerError, "fill history"):
            self.ledger.reconcile(self.snapshot(fill_ids=[]), ENTRY)

    def test_unrelated_positions_are_never_adopted_or_closed(self):
        self.bought()
        snapshot = self.snapshot()
        snapshot["positions"].append({"position_id": "PROTECTED_CORE_POSITION", "instrument_id": "SYNTHETIC_A", "quantity": "100"})
        self.ledger.reconcile(snapshot, ENTRY)
        self.assertEqual(len(self.ledger.positions()), 1)
        with self.assertRaisesRegex(LedgerError, "exact owned"):
            self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "PROTECTED_CORE_POSITION", OPEN)

    def test_exit_remains_due_after_restart_and_entry_review_failure(self):
        self.bought()
        self.ledger.close()
        self.ledger = ShadowLedger(self.path, repository_root=ROOT)
        with self.assertRaises(LedgerError):
            self.register(verifier=lambda *args: False)
        self.assertEqual(len(self.ledger.due_exits(OPEN)), 1)
        self.assertEqual(self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SYNTHETIC_POSITION", OPEN)["state"], "PLANNED")

    def test_halt_preserves_exit_obligation_and_original_open(self):
        self.bought()
        self.ledger.record_halt("SYNTHETIC_ACCOUNT", "SYNTHETIC_POSITION", OPEN, "SYNTHETIC_HALT")
        due = self.ledger.due_exits("2026-10-08T14:00:00Z")
        self.assertEqual(due[0]["exit_open"], OPEN)
        self.assertTrue(due[0]["overdue"])
        self.assertEqual(due[0]["quantity"], "5")

    def test_one_exit_intent_and_partial_remaining_no_oversell(self):
        self.bought()
        one = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SYNTHETIC_POSITION", OPEN)
        two = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SYNTHETIC_POSITION", OPEN)
        self.assertEqual(one["intent_id"], two["intent_id"])
        self.ledger.reconcile(self.snapshot(at=OPEN), OPEN)
        self.ledger.begin_attempt(one["intent_id"], "EXIT_ATTEMPT", OPEN)
        self.fill(one, "2", fill_id="SYNTHETIC_SELL_1", side="SELL", at=OPEN)
        self.assertEqual(self.ledger.positions()[0]["quantity"], "3")
        self.assertEqual(self.ledger.due_exits(OPEN)[0]["quantity"], "3")
        with self.assertRaisesRegex(LedgerError, "remaining shares"):
            self.fill(one, "4", fill_id="SYNTHETIC_OVERSELL", side="SELL", at=OPEN)
        with self.assertRaisesRegex(LedgerError, "No retry"):
            self.ledger.begin_attempt(one["intent_id"], "EXIT_RETRY", OPEN)
        self.ledger.reconcile(self.snapshot(at=OPEN, rid="SYNTHETIC_PARTIAL_EXIT_RECON"), OPEN)
        self.assertEqual(self.ledger.begin_attempt(one["intent_id"], "EXIT_RETRY", OPEN)["quantity"], "3")
        self.fill(one, "3", fill_id="SYNTHETIC_SELL_2", side="SELL", at=OPEN)
        self.assertEqual(self.ledger.due_exits(OPEN), [])

    def test_late_entry_fill_reopens_existing_owned_exit_obligation(self):
        entry = self.bought("2")
        exit_intent = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SYNTHETIC_POSITION", OPEN)
        self.ledger.reconcile(self.snapshot(at=OPEN), OPEN)
        self.ledger.begin_attempt(exit_intent["intent_id"], "EXIT_FIRST_PART", OPEN)
        self.fill(exit_intent, "2", fill_id="SYNTHETIC_SELL_1", side="SELL", at=OPEN)
        self.assertEqual(self.ledger.due_exits(OPEN), [])
        self.fill(entry, "3", fill_id="SYNTHETIC_LATE_ENTRY", at=OPEN)
        self.assertEqual(self.ledger.due_exits(OPEN)[0]["quantity"], "3")
        same = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SYNTHETIC_POSITION", OPEN)
        self.assertEqual(same["intent_id"], exit_intent["intent_id"])
        self.assertEqual(same["state"], "PLANNED")

    def test_abandon_partial_entry_releases_only_unfilled_reserve(self):
        intent = self.bought("2")
        with self.assertRaisesRegex(LedgerError, "Reconcile"):
            self.ledger.abandon_entry(intent["intent_id"], ENTRY, "SYNTHETIC_CUTOFF")
        self.ledger.reconcile(self.snapshot(), ENTRY)
        self.ledger.abandon_entry(intent["intent_id"], ENTRY, "SYNTHETIC_CUTOFF")
        self.assertEqual(self.ledger.exposure_snapshot("SYNTHETIC_ACCOUNT", "SYNTHETIC_STRATEGY")["reserved_notional_usd"], "200.0")
        self.assertEqual(len(self.ledger.due_exits(OPEN)), 1)

    def test_exit_cannot_be_advanced_by_new_calendar_or_spec(self):
        self.bought()
        self.assertEqual(self.ledger.due_exits("2026-10-08T13:29:59Z"), [])
        with self.assertRaisesRegex(LedgerError, "not due"):
            self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SYNTHETIC_POSITION", "2026-10-08T13:29:59Z")
        self.assertEqual(self.ledger.positions()[0]["exit_open"], OPEN)

    def test_entry_retry_cannot_extend_cutoff(self):
        intent = self.register()
        self.attempt(intent)
        self.ledger.mark_unknown("SYNTHETIC_ATTEMPT", ENTRY, "SYNTHETIC_TIMEOUT")
        self.ledger.reconcile(self.snapshot(), ENTRY)
        with self.assertRaises(LedgerError):
            self.attempt(intent, "AFTER_CUTOFF", "2026-10-07T20:00:00Z")

    def test_reconciliation_is_idempotent_conflicts_rejected(self):
        self.bought()
        snapshot = self.snapshot()
        self.ledger.reconcile(snapshot, ENTRY)
        self.assertTrue(self.ledger.reconcile(snapshot, ENTRY)["idempotent"])
        snapshot["source"] = "CONFLICTING_SOURCE"
        with self.assertRaisesRegex(LedgerError, "conflicting"):
            self.ledger.reconcile(snapshot, ENTRY)

    def test_calendar_dst_conversion_not_fixed_paris_time(self):
        from zoneinfo import ZoneInfo
        ordinary = next_opening(fixture_calendar(), "2026-10-07")
        self.assertEqual(datetime.fromisoformat(ordinary["exit_open"]).astimezone(ZoneInfo("Europe/Paris")).hour, 15)
        mismatch = {"calendar_id": "SYNTHETIC_XNYS", "source": "SYNTHETIC_FIXTURE", "observed_at": "2026-10-27T06:00:00Z",
                    "complete_from": "2026-10-27", "complete_through": "2026-10-28", "sessions": [
                        {"date": "2026-10-27", "open": "2026-10-27T13:30:00Z", "close": "2026-10-27T20:00:00Z"},
                        {"date": "2026-10-28", "open": "2026-10-28T13:30:00Z", "close": "2026-10-28T20:00:00Z"}]}
        resolved = next_opening(mismatch, "2026-10-27")
        self.assertEqual(datetime.fromisoformat(resolved["exit_open"]).astimezone(ZoneInfo("Europe/Paris")).hour, 14)

    def test_calendar_early_close_drives_entry_window(self):
        calendar = fixture_calendar()
        calendar["sessions"][0]["close"] = "2026-10-07T17:00:00Z"
        proposal = fixture_proposal(calendar, entry_not_before="2026-10-07T16:30:00Z", entry_cutoff="2026-10-07T16:59:00Z")
        auth = fixture_authorization(proposal, checked_at="2026-10-07T16:55:00Z", valid_until="2026-10-07T16:59:00Z")
        intent = self.ledger.register_entry(proposal, auth, "2026-10-07T16:55:00Z", calendar, authorization_verifier=synthetic_verifier)
        self.assertEqual(intent["exit_open"], OPEN)

    def test_calendar_holiday_bridge_and_friday_entry_blocked(self):
        calendar = fixture_calendar()
        calendar["complete_through"] = "2026-10-09"
        calendar["sessions"][1] = {"date": "2026-10-09", "open": "2026-10-09T13:30:00Z", "close": "2026-10-09T20:00:00Z"}
        with self.assertRaisesRegex(LedgerError, "bridge"):
            next_opening(calendar, "2026-10-07")
        calendar = {"calendar_id": "SYNTHETIC_XNYS", "source": "SYNTHETIC_FIXTURE", "observed_at": "2026-10-09T06:00:00Z",
                    "complete_from": "2026-10-09", "complete_through": "2026-10-12", "sessions": [
                        {"date": "2026-10-09", "open": "2026-10-09T13:30:00Z", "close": "2026-10-09T20:00:00Z"},
                        {"date": "2026-10-12", "open": "2026-10-12T13:30:00Z", "close": "2026-10-12T20:00:00Z"}]}
        with self.assertRaisesRegex(LedgerError, "Tuesday-Thursday"):
            next_opening(calendar, "2026-10-09")

    def test_calendar_incomplete_wrong_exit_and_changed_hash_blocked(self):
        calendar = fixture_calendar()
        calendar["complete_through"] = "2026-10-07"
        with self.assertRaisesRegex(LedgerError, "coverage"):
            next_opening(calendar, "2026-10-07")
        for changes in ({"exit_open": "2026-10-08T12:30:00Z"}, {"calendar_hash": "CHANGED_HASH"}):
            with self.subTest(changes=changes), self.assertRaises(LedgerError):
                self.register(fixture_proposal(**changes))

    def test_unicode_hash_matches_risk_binding(self):
        from active_trading.risk.review import canonical_hash
        proposal = fixture_proposal(proposal_id="SYNTHETIC_Flateråker–é")
        self.assertEqual(canonical_digest(proposal), canonical_hash(proposal))
        self.register(proposal)

    def test_two_connections_cannot_reserve_the_same_cash_snapshot(self):
        proposal = fixture_proposal(account_snapshot={"available_cash_usd": "500", "exposures": []})
        self.register(proposal)
        with ShadowLedger(self.path, repository_root=ROOT) as other:
            second = fixture_proposal(instrument_id="SYNTHETIC_B", account_snapshot=proposal["account_snapshot"])
            with self.assertRaisesRegex(LedgerError, "cash reservation"):
                other.register_entry(second, fixture_authorization(second), ENTRY, fixture_calendar(), authorization_verifier=synthetic_verifier)

    def test_external_plus_local_union_enforces_shared_caps(self):
        self.register(fixture_proposal(quantity="4", approved_notional_usd="401"))
        proposal = fixture_proposal(quantity="4", approved_notional_usd="401", instrument_id="SYNTHETIC_B",
            account_snapshot={"available_cash_usd": "5000", "exposures": [
                {"instrument_id": "EXTERNAL_ONE", "reserved_usd": "400"},
                {"instrument_id": "EXTERNAL_TWO", "reserved_usd": "400"},
                {"instrument_id": "EXTERNAL_THREE", "reserved_usd": "400"}]})
        with self.assertRaisesRegex(LedgerError, "shared-book"):
            self.register(proposal)

    def test_snapshot_local_overlap_is_not_double_counted(self):
        self.register()
        proposal = fixture_proposal(instrument_id="SYNTHETIC_B", account_snapshot={"available_cash_usd": "500",
            "exposures": [{"instrument_id": "SYNTHETIC_A", "reserved_usd": "500"}]})
        self.register(proposal)
        self.assertEqual(self.ledger.exposure_snapshot("SYNTHETIC_ACCOUNT", "SYNTHETIC_STRATEGY")["reserved_notional_usd"], "1000")

    def test_early_review_cannot_advance_entry_before_target(self):
        proposal = fixture_proposal()
        auth = fixture_authorization(proposal, checked_at="2026-10-07T19:30:00Z")
        intent = self.ledger.register_entry(proposal, auth, "2026-10-07T19:30:00Z", fixture_calendar(), authorization_verifier=synthetic_verifier)
        with self.assertRaisesRegex(LedgerError, "cutoff"):
            self.attempt(intent, now="2026-10-07T19:54:59Z")
        self.attempt(intent)

    def test_attempt_replay_never_grants_dispatch(self):
        intent = self.register()
        first, replay = self.attempt(intent), self.attempt(intent)
        self.assertTrue(first["created"])
        self.assertFalse(replay["created"])
        self.assertFalse(first["dispatch_allowed"])
        self.assertFalse(replay["dispatch_allowed"])

    def test_exit_requires_current_complete_reconciliation(self):
        self.bought()
        intent = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SYNTHETIC_POSITION", OPEN)
        with self.assertRaisesRegex(LedgerError, "Fresh complete"):
            self.ledger.begin_attempt(intent["intent_id"], "EXIT_STALE", OPEN)
        with self.assertRaisesRegex(LedgerError, "Stale"):
            self.ledger.reconcile(self.snapshot(at=ENTRY), OPEN)
        self.ledger.reconcile(self.snapshot(at=OPEN), OPEN)
        with self.assertRaisesRegex(LedgerError, "Fresh complete"):
            self.ledger.begin_attempt(intent["intent_id"], "EXIT_TOO_LATE", "2026-10-08T13:31:01Z")
        self.ledger.begin_attempt(intent["intent_id"], "EXIT_CURRENT", OPEN)

    def test_out_of_envelope_buy_preserves_owned_facts_and_blocks_entry(self):
        intent = self.register()
        self.attempt(intent)
        self.fill(intent, price="110")
        self.assertEqual(self.ledger.positions()[0]["quantity"], "5")
        self.assertEqual(self.ledger.get_intent(intent["intent_id"])["state"], "UNKNOWN")
        self.assertEqual(len(self.ledger.due_exits(OPEN)), 1)
        self.ledger.reconcile(self.snapshot(), ENTRY)
        with self.assertRaisesRegex(LedgerError, "control exception"):
            self.register(fixture_proposal(instrument_id="SYNTHETIC_B"))

    def test_flat_unknown_exit_blocks_future_entries_until_reconciled(self):
        self.bought()
        exit_intent = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SYNTHETIC_POSITION", OPEN)
        self.ledger.reconcile(self.snapshot(at=OPEN), OPEN)
        self.ledger.begin_attempt(exit_intent["intent_id"], "EXIT_UNKNOWN", OPEN)
        self.ledger.mark_unknown("EXIT_UNKNOWN", OPEN, "SYNTHETIC_TIMEOUT")
        self.fill(exit_intent, "5", fill_id="SYNTHETIC_EXIT_ALL", side="SELL", at=OPEN)
        self.assertEqual(self.ledger.due_exits(OPEN), [])
        calendar = fixture_calendar()
        calendar["complete_through"] = "2026-10-09"
        calendar["sessions"].append({"date": "2026-10-09", "open": "2026-10-09T13:30:00Z", "close": "2026-10-09T20:00:00Z"})
        proposal = fixture_proposal(calendar, entry_session="2026-10-08", entry_not_before="2026-10-08T19:30:00Z",
            entry_cutoff="2026-10-08T19:59:00Z", exit_open="2026-10-09T13:30:00Z", instrument_id="SYNTHETIC_B")
        auth = fixture_authorization(proposal, checked_at="2026-10-08T19:55:00Z", valid_until="2026-10-08T19:59:00Z")
        with self.assertRaisesRegex(LedgerError, "Unresolved exit"):
            self.ledger.register_entry(proposal, auth, "2026-10-08T19:55:00Z", calendar, authorization_verifier=synthetic_verifier)

    def test_unknown_other_intent_blocks_already_planned_entry_attempt(self):
        first = self.register()
        second = self.register(fixture_proposal(instrument_id="SYNTHETIC_B"))
        self.attempt(first)
        self.ledger.mark_unknown("SYNTHETIC_ATTEMPT", ENTRY, "SYNTHETIC_TIMEOUT")
        with self.assertRaisesRegex(LedgerError, "Unknown other entry"):
            self.attempt(second, "SECOND_ALREADY_PLANNED")

    def test_expired_unfilled_entry_blocks_later_session_until_abandoned(self):
        old = self.register()
        calendar = fixture_calendar()
        calendar["complete_through"] = "2026-10-09"
        calendar["sessions"].append({"date": "2026-10-09", "open": "2026-10-09T13:30:00Z", "close": "2026-10-09T20:00:00Z"})
        proposal = fixture_proposal(calendar, entry_session="2026-10-08", entry_not_before="2026-10-08T19:30:00Z",
            entry_cutoff="2026-10-08T19:59:00Z", exit_open="2026-10-09T13:30:00Z", instrument_id="SYNTHETIC_B")
        auth = fixture_authorization(proposal, checked_at="2026-10-08T19:55:00Z", valid_until="2026-10-08T19:59:00Z")
        with self.assertRaisesRegex(LedgerError, "Expired pending"):
            self.ledger.register_entry(proposal, auth, "2026-10-08T19:55:00Z", calendar, authorization_verifier=synthetic_verifier)
        self.ledger.abandon_entry(old["intent_id"], "2026-10-08T19:55:00Z", "UNSUBMITTED_INTENT_EXPIRED")
        self.ledger.register_entry(proposal, auth, "2026-10-08T19:55:00Z", calendar, authorization_verifier=synthetic_verifier)

    @staticmethod
    def order(intent, order_id, status="FILLED", remaining="0"):
        return {"intent_id": intent["intent_id"], "order_id": order_id,
                "status": status, "remaining_quantity": remaining}

    def reopen(self):
        self.ledger.close()
        self.ledger = ShadowLedger(self.path, repository_root=ROOT)

    def test_phantom_filled_entry_is_persistent_incident_not_retry_permission(self):
        intent = self.register()
        self.attempt(intent)
        self.ledger.record_accepted("SYNTHETIC_ATTEMPT", "ENTRY_ORDER", ENTRY)
        packet = self.snapshot(orders=[self.order(intent, "ENTRY_ORDER")])
        for _ in range(2):
            with self.assertRaisesRegex(LedgerError, "FILLED entry"):
                self.ledger.reconcile(packet, ENTRY)
            self.reopen()
            self.assertEqual(self.ledger.get_intent(intent["intent_id"])["state"], "UNKNOWN")
            with self.assertRaisesRegex(LedgerError, "No retry"):
                self.attempt(intent, "PHANTOM_RETRY")
        incidents = [r for r in self.ledger.event_log() if r["kind"] == "RECONCILIATION_CONFLICT_NEW_ENTRIES_BLOCKED"]
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["payload"]["snapshot"], packet)
        self.assertEqual(incidents[0]["payload"]["snapshot_digest"], canonical_digest(packet))
        self.assertEqual(self.ledger.positions(), [])
        # Corrected evidence may reconcile state, but it cannot erase the incident.
        self.ledger.reconcile(self.snapshot(rid="CORRECTED_ENTRY", orders=[self.order(intent, "ENTRY_ORDER", "CANCELLED")]), ENTRY)
        with self.assertRaisesRegex(LedgerError, "Control exception"):
            self.attempt(intent, "CORRECTED_BUT_UNREVIEWED")

    def test_phantom_filled_partial_entry_is_refused(self):
        intent = self.bought("2")
        self.ledger.reconcile(self.snapshot(rid="PRE_ACCEPT", at=ENTRY), ENTRY)
        # Map the fixture's still-unassigned attempt to the reported terminal order.
        with self.assertRaisesRegex(LedgerError, "FILLED entry"):
            self.ledger.reconcile(self.snapshot(orders=[self.order(intent, "PARTIAL_ENTRY_ORDER")]), ENTRY)
        self.assertEqual(self.ledger.positions()[0]["quantity"], "2")
        self.assertEqual(self.ledger.get_intent(intent["intent_id"])["state"], "UNKNOWN")

    def test_phantom_filled_exit_keeps_owned_units_due_after_restart(self):
        self.bought()
        intent = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SYNTHETIC_POSITION", OPEN)
        self.ledger.reconcile(self.snapshot(at=OPEN), OPEN)
        self.ledger.begin_attempt(intent["intent_id"], "EXIT_A", OPEN)
        self.ledger.record_accepted("EXIT_A", "EXIT_ORDER", OPEN)
        with self.assertRaisesRegex(LedgerError, "post-attempt fill evidence"):
            self.ledger.reconcile(self.snapshot(at=OPEN, rid="PHANTOM_EXIT", orders=[self.order(intent, "EXIT_ORDER")]), OPEN)
        self.reopen()
        self.assertEqual(self.ledger.due_exits(OPEN)[0]["quantity"], "5")
        with self.assertRaisesRegex(LedgerError, "No retry"):
            self.ledger.begin_attempt(intent["intent_id"], "EXIT_DUPLICATE", OPEN)
        # A corrected cancellation snapshot permits the owned exit, not new entries.
        self.ledger.reconcile(self.snapshot(at=OPEN, rid="EXIT_CORRECTED", orders=[self.order(intent, "EXIT_ORDER", "CANCELLED")]), OPEN)
        self.assertEqual(self.ledger.begin_attempt(intent["intent_id"], "SAFE_OWNED_EXIT", OPEN)["quantity"], "5")

    def test_own_order_without_entry_attempt_persists_unknown_incident(self):
        intent = self.register()
        with self.assertRaisesRegex(LedgerError, "no recorded attempt"):
            self.ledger.reconcile(self.snapshot(orders=[self.order(intent, "UNTRACKED_ENTRY", "OPEN", "5")]), ENTRY)
        self.reopen()
        with self.assertRaisesRegex(LedgerError, "No retry"):
            self.attempt(intent, "DUPLICATE_UNTRACKED")
        with self.assertRaisesRegex(LedgerError, "Unknown entry"):
            self.register(fixture_proposal(instrument_id="SYNTHETIC_B"))

    def test_untracked_own_order_with_unknown_fills_still_persists_incident(self):
        intent = self.register()
        packet = self.snapshot(fill_ids=["UNRECORDED_FILL"], orders=[
            self.order(intent, "UNTRACKED_WITH_UNKNOWN_FILL", "OPEN", "4")])
        with self.assertRaisesRegex(LedgerError, "no recorded attempt"):
            self.ledger.reconcile(packet, ENTRY)
        self.reopen()
        self.assertEqual(self.ledger.get_intent(intent["intent_id"])["state"], "UNKNOWN")
        with self.assertRaisesRegex(LedgerError, "No retry"):
            self.attempt(intent, "UNSAFE_AFTER_MISMATCH")

    def test_own_order_without_exit_attempt_preserves_due_obligation(self):
        self.bought()
        intent = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SYNTHETIC_POSITION", OPEN)
        with self.assertRaisesRegex(LedgerError, "no recorded attempt"):
            self.ledger.reconcile(self.snapshot(at=OPEN, orders=[self.order(intent, "UNTRACKED_EXIT", "OPEN", "5")]), OPEN)
        self.reopen()
        self.assertEqual(self.ledger.get_intent(intent["intent_id"])["state"], "UNKNOWN")
        self.assertEqual(self.ledger.due_exits(OPEN)[0]["quantity"], "5")

    def test_old_partial_cannot_cover_phantom_filled_exit_retry_at_same_timestamp(self):
        self.bought()
        intent = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SYNTHETIC_POSITION", OPEN)
        self.ledger.reconcile(self.snapshot(at=OPEN), OPEN)
        self.ledger.begin_attempt(intent["intent_id"], "EXIT_A", OPEN)
        self.ledger.record_accepted("EXIT_A", "ORDER_A", OPEN)
        self.fill(intent, "4", fill_id="OLD_PARTIAL", side="SELL", at=OPEN)
        cancelled = self.order(intent, "ORDER_A", "CANCELLED")
        self.ledger.reconcile(self.snapshot(at=OPEN, rid="CANCEL_FIRST", orders=[cancelled]), OPEN)
        self.ledger.begin_attempt(intent["intent_id"], "EXIT_B", OPEN)
        self.ledger.record_accepted("EXIT_B", "ORDER_B", OPEN)
        with self.assertRaisesRegex(LedgerError, "post-attempt fill evidence"):
            self.ledger.reconcile(self.snapshot(at=OPEN, rid="PHANTOM_RETRY", orders=[cancelled, self.order(intent, "ORDER_B")]), OPEN)
        self.assertEqual(self.ledger.due_exits(OPEN)[0]["quantity"], "1")

    def test_old_partial_cannot_cover_phantom_filled_entry_retry(self):
        intent = self.bought("4")
        self.ledger.reconcile(self.snapshot(rid="FIRST_CANCELLED"), ENTRY)
        self.attempt(intent, "ENTRY_RETRY")
        self.ledger.record_accepted("ENTRY_RETRY", "RETRY_ORDER", ENTRY)
        with self.assertRaisesRegex(LedgerError, "FILLED entry"):
            self.ledger.reconcile(self.snapshot(rid="PHANTOM_RETRY", orders=[self.order(intent, "RETRY_ORDER")]), ENTRY)
        self.assertEqual(self.ledger.positions()[0]["quantity"], "4")

    def test_valid_cancelled_partial_and_filled_retry_on_both_sides(self):
        entry = self.register()
        self.attempt(entry)
        self.ledger.record_accepted("SYNTHETIC_ATTEMPT", "BUY_A", ENTRY)
        self.fill(entry, "4")
        buy_cancelled = self.order(entry, "BUY_A", "CANCELLED")
        self.ledger.reconcile(self.snapshot(rid="BUY_CANCEL", orders=[buy_cancelled]), ENTRY)
        self.attempt(entry, "BUY_RETRY")
        self.ledger.record_accepted("BUY_RETRY", "BUY_B", ENTRY)
        self.fill(entry, "1", fill_id="BUY_NEW_FILL")
        buy_orders = [buy_cancelled, self.order(entry, "BUY_B")]
        self.ledger.reconcile(self.snapshot(rid="BUY_DONE", orders=buy_orders), ENTRY)
        exit_intent = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SYNTHETIC_POSITION", OPEN)
        self.ledger.reconcile(self.snapshot(at=OPEN, rid="BEFORE_EXIT", orders=buy_orders), OPEN)
        self.ledger.begin_attempt(exit_intent["intent_id"], "SELL_A", OPEN)
        self.ledger.record_accepted("SELL_A", "SELL_ORDER_A", OPEN)
        self.fill(exit_intent, "4", fill_id="SELL_PART", side="SELL", at=OPEN)
        cancelled = self.order(exit_intent, "SELL_ORDER_A", "CANCELLED")
        self.ledger.reconcile(self.snapshot(at=OPEN, rid="SELL_CANCEL", orders=buy_orders + [cancelled]), OPEN)
        self.ledger.begin_attempt(exit_intent["intent_id"], "SELL_B", OPEN)
        self.ledger.record_accepted("SELL_B", "SELL_ORDER_B", OPEN)
        self.fill(exit_intent, "1", fill_id="SELL_REST", side="SELL", at=OPEN)
        self.ledger.reconcile(self.snapshot(at=OPEN, rid="SELL_DONE", orders=buy_orders + [cancelled, self.order(exit_intent, "SELL_ORDER_B")]), OPEN)
        self.assertEqual(self.ledger.get_intent(exit_intent["intent_id"])["state"], "FILLED")
        self.assertEqual(self.ledger.due_exits(OPEN), [])

    def test_filled_exit_then_late_buy_remains_reconcilable_and_due(self):
        entry = self.bought("2")
        intent = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SYNTHETIC_POSITION", OPEN)
        self.ledger.reconcile(self.snapshot(at=OPEN), OPEN)
        self.ledger.begin_attempt(intent["intent_id"], "FIRST_EXIT", OPEN)
        self.ledger.record_accepted("FIRST_EXIT", "FIRST_EXIT_ORDER", OPEN)
        self.fill(intent, "2", fill_id="SELL_TWO", side="SELL", at=OPEN)
        filled_order = self.order(intent, "FIRST_EXIT_ORDER")
        self.ledger.reconcile(self.snapshot(at=OPEN, rid="FIRST_FLAT", orders=[filled_order]), OPEN)
        self.fill(entry, "3", fill_id="LATE_BUY", at=OPEN)
        self.ledger.reconcile(self.snapshot(at=OPEN, rid="REOPENED", orders=[filled_order]), OPEN)
        self.assertEqual(self.ledger.due_exits(OPEN)[0]["quantity"], "3")
        self.assertEqual(self.ledger.begin_attempt(intent["intent_id"], "REOPENED_EXIT", OPEN)["quantity"], "3")
        self.ledger.record_accepted("REOPENED_EXIT", "SECOND_EXIT_ORDER", OPEN)
        self.fill(intent, "3", fill_id="SELL_LATE_UNITS", side="SELL", at=OPEN)
        self.ledger.reconcile(self.snapshot(at=OPEN, rid="SECOND_FLAT", orders=[
            filled_order, self.order(intent, "SECOND_EXIT_ORDER")]), OPEN)
        self.assertEqual(self.ledger.due_exits(OPEN), [])

    def test_reconciliation_conflict_rolls_back_other_intent_transitions(self):
        first = self.register()
        second = self.register(fixture_proposal(instrument_id="SYNTHETIC_B"))
        self.attempt(first, "ATTEMPT_A")
        self.ledger.record_accepted("ATTEMPT_A", "ORDER_A", ENTRY)
        self.attempt(second, "ATTEMPT_B")
        self.ledger.record_accepted("ATTEMPT_B", "ORDER_B", ENTRY)
        with self.assertRaisesRegex(LedgerError, "FILLED entry"):
            self.ledger.reconcile(self.snapshot(orders=[self.order(first, "ORDER_A", "CANCELLED"), self.order(second, "ORDER_B")]), ENTRY)
        self.assertEqual(self.ledger.get_intent(first["intent_id"])["state"], "SUBMITTED")
        self.assertEqual(self.ledger.get_intent(second["intent_id"])["state"], "UNKNOWN")
        self.assertIsNone(self.ledger.db.execute("SELECT 1 FROM reconciliations").fetchone())

    def test_existing_snapshot_name_above_cap_blocks_new_entry(self):
        proposal = fixture_proposal(instrument_id="SYNTHETIC_B", account_snapshot={
            "available_cash_usd": "5000", "exposures": [{"instrument_id": "EXTERNAL_OWNED", "reserved_usd": "501"}]})
        with self.assertRaisesRegex(LedgerError, "10% per-name"):
            self.register(proposal)

    def test_existing_local_name_above_new_nav_cap_blocks_new_entry(self):
        self.register()
        proposal = fixture_proposal(instrument_id="SYNTHETIC_B", nav_usd="4900", quantity="4", approved_notional_usd="401")
        with self.assertRaisesRegex(LedgerError, "10% per-name"):
            self.register(proposal)


if __name__ == "__main__":
    unittest.main()
