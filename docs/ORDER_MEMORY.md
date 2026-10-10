# Order memory and safe next-opening exit obligations

The new [SQLite ledger](../src/active_trading/operations/ledger.py) supplies separately scoped durable **DEMO/SHADOW** state (the class name is retained for compatibility). It has no network code, broker writer or scheduler. Its entries, attempts, fills and complete reconciliations are supplied or simulated; nothing is inferred from a quote/bar touch.

## Why it is needed

The daily strategy previously specified restarts, exact ownership and next-opening exits in prose. The retained weekly engine had its own state, which did not operate the daily book. This package gives the daily design a separate reusable state machine and tests.

- Save one canonical account/strategy/session/instrument intent, approved quantity/price/cost ceiling and next-session opening **before** any fill. Both sleeves share that underlying exposure.
- Require the trusted backend review verifier when registering and before every entry attempt. A raw PASS cannot advance the state. Registration may occur during preclose review; an entry attempt starts no earlier than close minus five minutes and strictly before close minus one.
- Serialize local and supplied account reservations inside SQLite transactions. Combine held and pending exposure by instrument, load name/gross/position caps from policy using min(strategy allocation, account balance) for existing and proposed exposure, and conservatively subtract local reservations absent from a snapshot from its available cash. A producer must supply complete held/pending reservations; incomplete facts are not reconstructed by this library.
- Record a stable attempt before a hypothetical submission. **Accepted is not filled.** An unknown result blocks retry until complete orders, fill history and exact positions reconcile. Reusing an attempt ID returns `created: false`; it is a lookup, never permission to send again. `dispatch_allowed` is always false in this offline library.
- Keep exact strategy-owned position quantities and persistent exit obligations across restarts, proposal/specification changes and failed new-entry reviews. A partial sale leaves the unsold quantity due; an unrelated position cannot be adopted or sold.
- Derive the planned next opening from a complete supplied calendar slice. Check Tuesday-Thursday entries, next-day Wednesday-Friday exits, early closes and timezone-aware timestamps. The calendar producer still has to verify the actual exchange facts.
- Require a complete reconciliation no more than 60 seconds old before an exit attempt or retry. A halt remains an exception and an unsatisfied exit obligation. This library cannot make a halted security tradable or guarantee an opening fill.
- Block new entries while an exit is due or unresolved, including an UNKNOWN exit that appears flat locally. Missing or contradictory fills/order states stop progression.
- Refuse a reported own order without its durable attempt, or a FILLED order without sufficient matching fills after that attempt. Persistent event order prevents an earlier partial fill from covering a later retry, including timestamps that tie. Refusal preserves an UNKNOWN intent and a durable private incident containing the refused normalized snapshot before returning an error; restarting or catching the error cannot restore entry permission. A corrected complete snapshot may allow the remaining owned exit, while the incident continues to block new entries until the controlled logged operator procedure resolves it. Resolving an incident does not waive caps or erase known fill capital.
- A prior session's unfilled pending entry must be reconciled and abandoned before new exposure. An expired clock alone is not proof that a submitted order was cancelled.

The 60-second reconciliation freshness is a conservative initial software policy aligned with the existing quote freshness rule; it is not a statistically optimized trading parameter. Shorter source-specific limits may be necessary in a future adapter.

## Supplied fills and incidents

Record actual normalized owned facts rather than silently changing them to fit the plan. Duplicate identical fill IDs replay once; changed content under the same ID is rejected. A BUY beyond its approved quantity, price ceiling or submission cutoff is retained with a durable control exception and owned exit obligation. New entries remain blocked for controlled operator incident review. Local owned capital retains the larger of original limit value and remaining weighted actual purchase basis, plus pending commitments and costs. It is conservative known capital, not market NAV or bid-marked strategy equity. An incident resolution cannot hide an expensive fill behind its original limit.

Late fills can add to an owned exit obligation after an earlier partial position was sold. The accounting helper conservatively refuses a position lifecycle reopened after going flat; such a case needs explicit incident handling and a suitable accounting adapter, rather than a fabricated final report. Oversells and contradictory ownership remain refused; a future real adapter must preserve rejected raw evidence in its private incident archive and reconcile it before continuing.

## API and storage

Use `ShadowLedger(path, repository_root=..., policy=trusted_policy)` as a context manager. Keep its SQLite database, WAL/SHM files, account identifiers, fill history and signed reviewer packets in persistent access-controlled storage outside **every Git checkout**. Temporary demo databases are intentionally removed after the exercise. Persistent deployments must configure backups, service identity, recovery ownership and a scheduler separately.

Core methods: `register_entry`, `begin_attempt`, `record_accepted`, `mark_unknown`, `record_fill`, `reconcile`, `due_exits`, `plan_exit`, `record_halt`, `abandon_entry`, `control_exceptions`, `resolve_exception`. Load trusted policy into the constructor. Mixed DEMO/SHADOW journals require explicit mode where identifiers could overlap; reconciliation event identities also include strategy ID. Tests and [the synthetic integration command](../scripts/shadow_workflow.py) illustrate normalized inputs. `reconcile` checks the supplied complete snapshot; it does not authenticate the broker or retrieve missing records. These consistency checks cannot prove exact per-order attribution from the current normalized fill format; an authenticated adapter must provide and verify that linkage.

Existing intents are immutable. If fresh evidence changes the bound proposal or its review expires, this implementation refuses further entry advancement. A future explicitly reviewed amendment protocol is needed to refresh an outstanding intent; never delete it and create an untracked replacement. Existing owned exits remain active.

Run `python scripts/shadow_workflow.py --demo` and `python scripts/validate_portable.py`. These exercise invented facts, restart recovery, partial fills, duplicate attempts, unknown states, calendar/DST mapping and reservation conflicts. They do not deploy a routine or place broker orders. The owner DEMO policy supports normalized records, not a supplied execution adapter. See [review controls](DOUBLE_REVIEW.md), [accounting](TRADE_ACCOUNTING.md) and [the homework checklist](HOMEWORK_CHECKLIST_2026-10-09.md).

## Logged operator incident resolution

1. Inspect `control_exceptions(account_id, strategy_id, mode="DEMO")`; retain the original fill and incident evidence.
2. Obtain the latest fresh complete account/strategy/mode reconciliation. Unknown attempts and open owned orders must be resolved through evidence first; an operator cannot waive them.
3. Call `resolve_exception(resolution, now, operator_verifier=trusted_verifier)` with `exception_id`, new `resolution_id`, different `operator_id`/`reviewer_id`, `reason`, scoped `account_id`/`strategy_id`/`mode`, `decision: RESOLVE_INCIDENT`, exact `reconciliation_id`, current `spec_hash`, `issued_at` and `valid_until`.
4. The external verifier authenticates owner/operator authority. A supplied boolean is insufficient. The ledger appends an immutable resolution event, retaining incident/fill history and the exit obligation. Never hand-edit SQLite. Caps continue to apply after resolution.

DEMO exit planning opens at calendar open minus five minutes. `begin_attempt` refuses early dispatch, requires fresh reconciliation before each attempt, and for retries requires a new post-attempt reconciliation plus at least five seconds spacing. The twelfth attempt records `alert_required: true`; a separate service delivers the alert. Late recovery remains available and is logged rather than suppressing an owed exit. These settings are read from policy.
