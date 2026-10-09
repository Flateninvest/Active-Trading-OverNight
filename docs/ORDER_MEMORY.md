# Order memory and safe next-opening exit obligations

The new [SQLite ledger](../src/active_trading/operations/ledger.py) supplies durable **SHADOW** state. It has no network code, broker writer or scheduler. Its entries, attempts, fills and complete reconciliations are supplied or simulated; nothing is inferred from a quote/bar touch.

## Why it is needed

The daily strategy previously specified restarts, exact ownership and next-opening exits in prose. The retained weekly engine had its own state, which did not operate the daily book. This package gives the daily design a separate reusable state machine and tests.

- Save one canonical account/strategy/session/instrument intent, approved quantity/price/cost ceiling and next-session opening **before** any fill. Both sleeves share that underlying exposure.
- Require the trusted backend review verifier when registering and before every entry attempt. A raw PASS cannot advance the state. Registration may occur during preclose review; an entry attempt starts no earlier than close minus five minutes and strictly before close minus one.
- Serialize local and supplied account reservations inside SQLite transactions. Combine held and pending exposure by instrument, preserve three-name/30%-gross/10%-name caps, and conservatively subtract local reservations absent from a snapshot from its available cash. A producer must supply complete held/pending reservations; incomplete facts are not reconstructed by this library.
- Record a stable attempt before a hypothetical submission. **Accepted is not filled.** An unknown result blocks retry until complete orders, fill history and exact positions reconcile. Reusing an attempt ID returns `created: false`; it is a lookup, never permission to send again. `dispatch_allowed` is always false in this shadow library.
- Keep exact strategy-owned position quantities and persistent exit obligations across restarts, proposal/specification changes and failed new-entry reviews. A partial sale leaves the unsold quantity due; an unrelated position cannot be adopted or sold.
- Derive the planned next opening from a complete supplied calendar slice. Check Tuesday-Thursday entries, next-day Wednesday-Friday exits, early closes and timezone-aware timestamps. The calendar producer still has to verify the actual exchange facts.
- Require a complete reconciliation no more than 60 seconds old before an exit attempt or retry. A halt remains an exception and an unsatisfied exit obligation. This library cannot make a halted security tradable or guarantee an opening fill.
- Block new entries while an exit is due or unresolved, including an UNKNOWN exit that appears flat locally. Missing or contradictory fills/order states stop progression.
- A prior session's unfilled pending entry must be reconciled and abandoned before new exposure. An expired clock alone is not proof that a submitted order was cancelled.

The 60-second reconciliation freshness is a conservative initial software policy aligned with the existing quote freshness rule; it is not a statistically optimized trading parameter. Shorter source-specific limits may be necessary in a future adapter.

## Supplied fills and incidents

Record actual normalized owned facts rather than silently changing them to fit the plan. Duplicate identical fill IDs replay once; changed content under the same ID is rejected. A BUY beyond its approved quantity, price ceiling or submission cutoff is retained with a durable control exception and owned exit obligation. New entries remain blocked for operator incident review; this version deliberately has no automatic incident-clearing mechanism. Local price-limit reservations are not a mark-to-market risk calculation.

Late fills can add to an owned exit obligation after an earlier partial position was sold. The accounting helper conservatively refuses a position lifecycle reopened after going flat; such a case needs explicit incident handling and a suitable accounting adapter, rather than a fabricated final report. Oversells and contradictory ownership remain refused; a future real adapter must preserve rejected raw evidence in its private incident archive and reconcile it before continuing.

## API and storage

Use `ShadowLedger(path, repository_root=...)` as a context manager. Keep its SQLite database, WAL/SHM files, account identifiers, fill history and signed reviewer packets in persistent access-controlled storage outside **every Git checkout**. Temporary demo databases are intentionally removed after the exercise. Persistent deployments must configure backups, service identity, recovery ownership and a scheduler separately.

Core methods: `register_entry`, `begin_attempt`, `record_accepted`, `mark_unknown`, `record_fill`, `reconcile`, `due_exits`, `plan_exit`, `record_halt`, `abandon_entry`. Tests and [the synthetic integration command](../scripts/shadow_workflow.py) illustrate normalized inputs. `reconcile` checks the supplied complete snapshot; it does not authenticate the broker or retrieve missing records.

Existing intents are immutable. If fresh evidence changes the bound proposal or its review expires, this implementation refuses further entry advancement. A future explicitly reviewed amendment protocol is needed to refresh an outstanding intent; never delete it and create an untracked replacement. Existing owned exits remain active.

Run `python scripts/shadow_workflow.py --demo` and `python scripts/validate_portable.py`. These exercise invented facts, restart recovery, partial fills, duplicate attempts, unknown states, calendar/DST mapping and reservation conflicts. They neither deploy a routine nor enable demo/live orders. See [review controls](DOUBLE_REVIEW.md), [accounting](TRADE_ACCOUNTING.md) and [the homework checklist](HOMEWORK_CHECKLIST_2026-10-09.md).
