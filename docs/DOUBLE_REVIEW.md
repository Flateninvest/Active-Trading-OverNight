# Financial double-check and deterministic review

This implements the first ranked improvement as a reusable **offline DEMO/SHADOW backend**, not a deployed pair of Grok bots. One analyst proposes; a separately configured critic challenges that exact packet; code applies common entry checks. Risk PASS permits only a reviewed intent to advance to offline order memory. It is never transaction approval.

## Why this improves the existing structure

The previous architecture described S1 and S2 in prompts but had no daily proposal-review binding. An analyst could change a quantity or source after a written PASS. The new [review module](../src/active_trading/risk/review.py) binds a signed reviewer attestation to the entire proposal, including account, instrument, quantity/price/cost ceiling, specification, source commit, input hashes, calendar, frozen register, quote, account snapshot and planned entry/exit window. Changes require a fresh review.

- A different reviewer identity and valid service-held signature are required. An unsigned JSON PASS or a self-review is refused.
- The critic must address sources, thesis, TA, events/calendar, costs/liquidity, ownership/account and exposure. Every required check needs PASS plus evidence references. High-beta or volatile names also need enhanced review.
- Code checks DEMO/SHADOW mode (LIVE rejected), long cash/X1 product, costs, quote/spread, Monday reference, reconciled scope and allocation-based held/pending caps. DEMO additionally requires sourced TA/stress history and strategy equity/pause state. Its account risk-score switch is off; a real-account score never governs.
- Existing active-book reservations are aggregated by instrument; a per-name capital-cap breach blocks new entries while existing owned exit obligations remain unchanged.
- Unknown costs, stale snapshots, changed inputs/specification, expired reviews and missing evidence stop new entries. A failed entry review does not remove an existing owned-position exit obligation.

These checks operate on normalized supplied facts. They do not calculate TA, authenticate a broker response, verify an issuer, establish source receipt, or prove a financial assertion is true. Those producers still need implementation. The existing earnings helper remains responsible for earnings qualification, event timing and bounded conviction allocation before this common gate.

## Reviewer authority and permissions

`sign_review` uses a minimum 32-byte secret key and HMAC-SHA256. The backend trusts only reviewer keys loaded through operator-controlled service configuration. Keys are never read from the proposal, included in Git or given to the proposing agent. The returned `boundary_verified` field means that the configured signature and exact binding passed; it does **not** certify physical process isolation or financial truth.

In a future deployment:

1. Analyst credentials can read sources and submit proposals; they cannot access reviewer keys, alter trusted policy or write operating state directly.
2. The reviewer service alone signs its own explicit verdict. It cannot raise limits or grant capital authority.
3. The operating service recomputes the gate through `authorization_verifier` before recording an intent and before an entry attempt. An input's `reviewed: true` is insufficient.
4. Mandatory human, platform and broker approvals remain separate. No orders follow from a review key or a GitHub merge.

Grok's named bots can share access, so prompt labels alone do not provide these permissions. Actual credential/process isolation and model service adapters are **not deployed here**. Do not load a production signing key into a bot environment that also exposes it to the analyst. The demo uses an explicitly synthetic key solely to test the mechanism.

## Run and review

`python scripts/shadow_workflow.py --demo` exercises signed review, durable order memory and reconciled accounting with invented data and no broker calls. `python scripts/validate_portable.py` includes adversarial tests. Tests cover tampering, self-review, unsigned/expired evidence, high-volatility review, stale/crossed quotes, missing fees, account scope, pending exposure and proposal changes.

The 10 October update applies the [current DEMO owner decisions](DEMO_ALIGNMENT_2026-10-10.md): shared strategy-allocation caps, automatic enhanced review, stress sizing and latched loss/drawdown pauses. These limits are policy, not optimized estimates. It does not complete the research-agent homework; see [the checklist](HOMEWORK_CHECKLIST_2026-10-09.md).

## Primary references

- [Grok computer/app access](https://docs.x.ai/grok-bot/computer-and-apps): verify the actual environment and shared-access boundaries before deployment.
- [eToro fee information](https://www.etoro.com/trading/fees/): use the applicable instrument/account costs; this code has no universal flat fee default.
- [eToro asynchronous demo order contract](https://api-portal.etoro.com/api-reference/trading--demo/submit-an-order-for-asynchronous-processing): an accepted request is not a confirmed fill.
- [eToro close by owned position units](https://api-portal.etoro.com/api-reference/trading--demo/close-demo-position-by-units): future adapters must preserve exact position ownership and remaining units.
