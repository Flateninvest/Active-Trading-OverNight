"""Synthetic DEMO allocation, journal recovery and next-open controls."""
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from active_trading.operations import LedgerError, ShadowLedger, canonical_digest
from active_trading.policy import load_policy
from test_operations_ledger import ENTRY, OPEN, fixture_calendar, fixture_proposal, fixture_authorization, synthetic_verifier


class DemoLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-demo-ledger-", dir=ROOT.parent)
        self.path = Path(self.temp.name) / "memory.sqlite"
        self.policy = load_policy()
        self.ledger = ShadowLedger(self.path, repository_root=ROOT, policy=self.policy)

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def proposal(self, **changes):
        proposal = fixture_proposal(mode="DEMO", nav_usd="100000", spec_hash=canonical_digest(self.policy),
            account_snapshot={"mode": "DEMO", "account_environment": "DEMO", "available_cash_usd": "100000", "exposures": []})
        proposal.update(changes)
        return proposal

    def register(self, proposal=None):
        proposal = proposal or self.proposal()
        return self.ledger.register_entry(proposal, fixture_authorization(proposal, mode=proposal["mode"]), ENTRY,
            fixture_calendar(), authorization_verifier=synthetic_verifier)

    def attempt(self, intent, aid="BUY_ATTEMPT", now=ENTRY):
        return self.ledger.begin_attempt(intent["intent_id"], aid, now, authorization_verifier=synthetic_verifier)

    def fill(self, intent, *, fid="BUY_FILL", side="BUY", quantity="5", price="98", at=ENTRY):
        return self.ledger.record_fill({"fill_id": fid, "intent_id": intent["intent_id"], "mode": intent["mode"],
            "account_id": intent["account_id"], "strategy_id": "SYNTHETIC_STRATEGY", "instrument_id": "SYNTHETIC_A",
            "position_id": "SAME_POSITION_ID", "side": side, "quantity": quantity,
            "price": price, "currency": "USD", "filled_at": at}, at)

    def snapshot(self, *, rid="RECON", at=ENTRY, mode="DEMO", orders=None):
        return {"reconciliation_id": rid, "mode": mode, "account_id": "SYNTHETIC_ACCOUNT",
            "strategy_id": "SYNTHETIC_STRATEGY", "observed_at": at, "source": "SYNTHETIC_FIXTURE",
            "orders_complete": True, "fills_complete": True, "positions_complete": True,
            "fill_ids": [r["fill_id"] for r in self.ledger.fills(mode=mode)], "orders": orders or [],
            "positions": [{k: p[k] for k in ("position_id", "instrument_id", "quantity")}
                for p in self.ledger.positions(mode=mode)]}

    def bought(self, *, price="98"):
        intent = self.register()
        self.attempt(intent)
        self.fill(intent, price=price)
        return intent

    def resolution(self, *, at=ENTRY, **changes):
        incident = self.ledger.control_exceptions("SYNTHETIC_ACCOUNT", "SYNTHETIC_STRATEGY", mode="DEMO")[0]
        record = {"exception_id": incident["exception_id"], "resolution_id": "OWNER_RESOLUTION",
            "operator_id": "SYNTHETIC_OWNER", "reviewer_id": "SYNTHETIC_INDEPENDENT_REVIEWER",
            "reason": "Reconciled the supplied out-of-policy fill and retained its owned exit",
            "account_id": "SYNTHETIC_ACCOUNT", "strategy_id": "SYNTHETIC_STRATEGY", "mode": "DEMO",
            "decision": "RESOLVE_INCIDENT", "reconciliation_id": "RECON", "spec_hash": canonical_digest(self.policy),
            "issued_at": at, "valid_until": (datetime.fromisoformat(at) + timedelta(minutes=1)).isoformat()}
        record.update(changes)
        return record

    def test_9005_entry_with_100k_balance_fails_allocation_cap(self):
        with self.assertRaisesRegex(LedgerError, "per-name"):
            self.register(self.proposal(quantity="90", entry_price_limit="100", approved_notional_usd="9005"))

    def test_lower_account_balance_reduces_cap(self):
        with self.assertRaisesRegex(LedgerError, "per-name"):
            self.register(self.proposal(nav_usd="4000"))

    def test_policy_configures_name_gross_and_position_limits(self):
        self.policy["risk"].update(maximum_name_weight=.06, maximum_gross_weight_including_pending=.08, maximum_positions=1)
        self.ledger.close()
        self.ledger = ShadowLedger(self.path, repository_root=ROOT, policy=self.policy)
        self.register()
        with self.assertRaisesRegex(LedgerError, "shared-book"):
            self.register(self.proposal(instrument_id="SECOND"))
        with self.assertRaisesRegex(LedgerError, "per-name"):
            self.register(self.proposal(instrument_id="THIRD", quantity="7", approved_notional_usd="698"))

    def test_demo_accepted_live_and_unbound_policy_rejected(self):
        self.assertEqual(self.register()["mode"], "DEMO")
        for proposal in (self.proposal(mode="LIVE"), self.proposal(spec_hash="OLD_SPEC"),
                         self.proposal(account_snapshot={"mode": "LIVE", "account_environment": "LIVE"})):
            with self.subTest(proposal=proposal), self.assertRaises(LedgerError):
                self.register(proposal)

    def test_same_account_position_fill_and_reconciliation_ids_are_mode_scoped(self):
        demo = self.bought()
        self.ledger.reconcile(self.snapshot(), ENTRY)
        shadow = self.register(fixture_proposal())
        self.attempt(shadow, aid="SHADOW_BUY")
        self.fill(shadow)
        self.ledger.reconcile(self.snapshot(mode="SHADOW"), ENTRY)
        self.assertEqual(self.ledger.positions(mode="DEMO")[0]["quantity"], "5")
        self.assertEqual(self.ledger.positions(mode="SHADOW")[0]["quantity"], "5")
        self.assertNotEqual(self.ledger.fills(mode="DEMO")[0]["sequence"], self.ledger.fills(mode="SHADOW")[0]["sequence"])
        self.assertEqual(len(self.ledger.due_exits(OPEN, mode="DEMO")), 1)
        self.assertEqual(len(self.ledger.due_exits(OPEN, mode="SHADOW")), 1)
        self.assertNotEqual(demo["intent_id"], shadow["intent_id"])
        with self.assertRaisesRegex(LedgerError, "explicit mode"):
            self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SAME_POSITION_ID", OPEN)
        with self.assertRaisesRegex(LedgerError, "explicit mode"):
            self.ledger.positions()

    def test_shadow_reconciliation_cannot_unlock_demo_exit(self):
        self.bought()
        self.ledger.reconcile(self.snapshot(mode="SHADOW", at=OPEN), OPEN)
        planned = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SAME_POSITION_ID", OPEN, mode="DEMO")
        with self.assertRaisesRegex(LedgerError, "Fresh"):
            self.ledger.begin_attempt(planned["intent_id"], "EXIT", OPEN)

    def test_fills_cannot_cross_modes(self):
        demo = self.register()
        self.attempt(demo)
        with self.assertRaisesRegex(LedgerError, "ownership"):
            self.fill(dict(demo, mode="SHADOW"))
        self.assertEqual(self.ledger.positions(mode="DEMO"), [])

    def test_logged_operator_resolution_preserves_facts_exits_and_requires_authority(self):
        self.bought(price="100")
        self.ledger.reconcile(self.snapshot(), ENTRY)
        candidate = self.proposal(instrument_id="SECOND")
        with self.assertRaisesRegex(LedgerError, "exception"):
            self.register(candidate)
        resolution = self.resolution()
        with self.assertRaisesRegex(LedgerError, "authorisation"):
            self.ledger.resolve_exception(resolution, ENTRY, operator_verifier=lambda *args: False)
        result = self.ledger.resolve_exception(resolution, ENTRY, operator_verifier=lambda *args: True)
        self.assertEqual(result["status"], "RESOLVED")
        self.assertTrue(self.ledger.resolve_exception(resolution, ENTRY, operator_verifier=lambda *args: True)["idempotent"])
        with self.assertRaisesRegex(LedgerError, "conflicting"):
            self.ledger.resolve_exception(dict(resolution, reason="CHANGED"), ENTRY, operator_verifier=lambda *args: True)
        self.assertTrue(self.ledger.control_exceptions("SYNTHETIC_ACCOUNT", "SYNTHETIC_STRATEGY", mode="DEMO")[0]["resolved"])
        self.assertEqual(len(self.ledger.fills(mode="DEMO")), 1)
        self.assertEqual(len(self.ledger.due_exits(OPEN, mode="DEMO")), 1)
        self.register(candidate)
        self.ledger.close()
        self.ledger = ShadowLedger(self.path, repository_root=ROOT, policy=self.policy)
        self.assertTrue(self.ledger.control_exceptions("SYNTHETIC_ACCOUNT", "SYNTHETIC_STRATEGY", mode="DEMO")[0]["resolved"])

    def test_resolution_requires_fresh_complete_reconciliation_and_correct_scope(self):
        self.bought(price="100")
        with self.assertRaisesRegex(LedgerError, "Fresh"):
            self.ledger.resolve_exception(self.resolution(), ENTRY, operator_verifier=lambda *args: True)
        self.ledger.reconcile(self.snapshot(), ENTRY)
        for changes in ({"account_id": "OTHER"}, {"reconciliation_id": "WRONG"}, {"reviewer_id": "SYNTHETIC_OWNER"}, {"spec_hash": "OLD"}):
            with self.subTest(changes=changes), self.assertRaises(LedgerError):
                self.ledger.resolve_exception(self.resolution(**changes), ENTRY, operator_verifier=lambda *args: True)

    def test_resolution_cannot_clear_open_owned_order(self):
        intent = self.register()
        self.attempt(intent)
        self.ledger.record_accepted("BUY_ATTEMPT", "OPEN_ORDER", ENTRY)
        self.fill(intent, quantity="2", price="100")
        order = {"intent_id": intent["intent_id"], "order_id": "OPEN_ORDER", "status": "OPEN", "remaining_quantity": "3"}
        self.ledger.reconcile(self.snapshot(orders=[order]), ENTRY)
        with self.assertRaisesRegex(LedgerError, "unresolved"):
            self.ledger.resolve_exception(self.resolution(), ENTRY, operator_verifier=lambda *args: True)

    def test_prepare_five_minutes_before_calendar_open_never_dispatch_early(self):
        self.bought()
        before = "2026-10-08T13:24:59+00:00"
        prepare = "2026-10-08T13:25:00+00:00"
        self.assertEqual(self.ledger.due_exits(before, mode="DEMO", prepare=True), [])
        self.assertEqual(len(self.ledger.due_exits(prepare, mode="DEMO", prepare=True)), 1)
        exit_intent = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SAME_POSITION_ID", prepare, mode="DEMO")
        with self.assertRaisesRegex(LedgerError, "not due"):
            self.ledger.begin_attempt(exit_intent["intent_id"], "EARLY", prepare)

    def test_retry_every_five_seconds_reconcile_each_and_alert_at_twelve(self):
        self.bought()
        planned = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SAME_POSITION_ID", OPEN, mode="DEMO")
        for index in range(12):
            at = (datetime.fromisoformat(OPEN) + timedelta(seconds=5 * index)).isoformat()
            if index:
                with self.assertRaisesRegex(LedgerError, "No retry"):
                    self.ledger.begin_attempt(planned["intent_id"], "UNRECONCILED", at)
            self.ledger.reconcile(self.snapshot(at=at, rid="RECON_" + str(index)), at)
            if index:
                with self.assertRaisesRegex(LedgerError, "five seconds"):
                    self.ledger.begin_attempt(planned["intent_id"], "TOO_FAST", (datetime.fromisoformat(at)-timedelta(seconds=1)).isoformat())
            attempt = self.ledger.begin_attempt(planned["intent_id"], "EXIT_" + str(index), at)
            self.assertEqual(attempt["quantity"], "5")
            self.assertEqual(attempt["alert_required"], index == 11)
            self.assertFalse(attempt["dispatch_allowed"])
            self.ledger.mark_unknown("EXIT_" + str(index), at, "SYNTHETIC_TIMEOUT")
        self.assertEqual(sum(e["kind"] == "OWNED_EXIT_RETRY_ALERT_REQUIRED" for e in self.ledger.event_log()), 1)
        repeated = self.ledger.begin_attempt(planned["intent_id"], "EXIT_11", at)
        self.assertTrue(repeated["alert_required"])
        self.assertFalse(repeated["created"])

    def test_unchanged_old_reconciliation_cannot_authorize_next_retry(self):
        self.bought()
        planned = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SAME_POSITION_ID", OPEN, mode="DEMO")
        snapshot = self.snapshot(at=OPEN)
        self.ledger.reconcile(snapshot, OPEN)
        self.ledger.begin_attempt(planned["intent_id"], "FIRST_EXIT", OPEN)
        self.ledger.mark_unknown("FIRST_EXIT", OPEN, "SYNTHETIC_TIMEOUT")
        later = (datetime.fromisoformat(OPEN) + timedelta(seconds=5)).isoformat()
        self.ledger.reconcile(snapshot, later)  # An identical old snapshot adds no evidence.
        with self.assertRaisesRegex(LedgerError, "No retry"):
            self.ledger.begin_attempt(planned["intent_id"], "BLIND_RETRY", later)

    def test_policy_update_blocks_old_demo_entry_but_preserves_owned_exit(self):
        intent = self.register()
        self.policy["risk"]["maximum_name_weight"] = .09
        self.ledger.close()
        self.ledger = ShadowLedger(self.path, repository_root=ROOT, policy=self.policy)
        with self.assertRaisesRegex(LedgerError, "current configured policy"):
            self.attempt(intent)

    def test_resolving_high_price_fill_keeps_actual_capital_cap_until_owned_exit(self):
        self.bought(price="2000")  # Actual purchase value $10,000, original reservation $500.
        self.ledger.reconcile(self.snapshot(), ENTRY)
        self.ledger.resolve_exception(self.resolution(), ENTRY, operator_verifier=lambda *args: True)
        exposure = self.ledger.exposure_snapshot("SYNTHETIC_ACCOUNT", "SYNTHETIC_STRATEGY", mode="DEMO")
        self.assertEqual(exposure["reserved_notional_usd"], "10005")
        with self.assertRaisesRegex(LedgerError, "per-name"):
            self.register(self.proposal(instrument_id="SECOND"))
        planned = self.ledger.plan_exit("SYNTHETIC_ACCOUNT", "SAME_POSITION_ID", OPEN, mode="DEMO")
        self.ledger.reconcile(self.snapshot(at=OPEN, rid="BEFORE_FULL_EXIT"), OPEN)
        self.ledger.begin_attempt(planned["intent_id"], "FULL_OWNED_EXIT", OPEN)
        self.fill(planned, fid="SELL_ALL", side="SELL", at=OPEN, quantity="5", price="1900")
        self.ledger.reconcile(self.snapshot(at=OPEN, rid="AFTER_FULL_EXIT"), OPEN)
        self.assertEqual(self.ledger.exposure_snapshot("SYNTHETIC_ACCOUNT", "SYNTHETIC_STRATEGY", mode="DEMO")["reserved_notional_usd"], "0")
        calendar = fixture_calendar()
        calendar.update(complete_from="2026-10-08", complete_through="2026-10-09")
        calendar["sessions"] = [
            {"date": "2026-10-08", "open": OPEN, "close": "2026-10-08T20:00:00Z"},
            {"date": "2026-10-09", "open": "2026-10-09T13:30:00Z", "close": "2026-10-09T20:00:00Z"}]
        proposal = self.proposal(instrument_id="SECOND", entry_session="2026-10-08",
            entry_not_before="2026-10-08T19:30:00Z", entry_cutoff="2026-10-08T19:59:00Z",
            calendar_hash=canonical_digest(calendar), exit_open="2026-10-09T13:30:00Z")
        at = "2026-10-08T19:55:00Z"
        review = fixture_authorization(proposal, mode="DEMO", checked_at=at, valid_until=proposal["entry_cutoff"])
        self.assertEqual(self.ledger.register_entry(proposal, review, at, calendar,
            authorization_verifier=synthetic_verifier)["state"], "PLANNED")

    def test_reconciliation_event_ids_include_strategy_scope(self):
        first = self.snapshot(rid="SAME_RECON_ID")
        second = dict(first, strategy_id="SECOND_STRATEGY")
        self.assertFalse(self.ledger.reconcile(first, ENTRY)["idempotent"])
        self.assertFalse(self.ledger.reconcile(second, ENTRY)["idempotent"])
        self.assertTrue(self.ledger.reconcile(first, ENTRY)["idempotent"])
        self.assertTrue(self.ledger.reconcile(second, ENTRY)["idempotent"])
        events = [e for e in self.ledger.event_log() if e["kind"] == "COMPLETE_SUPPLIED_RECONCILIATION"]
        self.assertEqual(len(events), 2)
        self.assertEqual({e["payload"]["strategy_id"] for e in events}, {"SYNTHETIC_STRATEGY", "SECOND_STRATEGY"})


if __name__ == "__main__":
    unittest.main()
