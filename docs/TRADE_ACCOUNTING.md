# Exact-position trade accounting

The daily reporting stage now has a deterministic, standard-library accounting function: `active_trading.reporting.build_trade_report(packet)`. It consumes normalized private fills, explicit fee evidence and a supplied position/open-order reconciliation. It performs no network access, broker writes, scheduling or publication. `SHADOW` and `DEMO` reports remain separate; `LIVE` is rejected.

This fills an actual reporting gap: the previous instructions required net results and remaining shares, but there was no daily function to calculate them. It does not establish profitability or complete the account reporting runtime.

## What it calculates

- Exact bought, sold and remaining quantities, using decimal strings rather than binary floating-point inputs.
- Weighted-average execution-price cost basis and gross realized PnL. This is operational trade accounting, not tax-lot accounting.
- Observed charges, entry fees allocated between sold/remaining units, realized net PnL and remaining basis including entry fees where coverage is complete.
- Unrealized PnL separately, only from a supplied, owned USD mark at or after the latest fill and within 60 seconds of report `as_of`. Future exit charges are not known and are not included.
- Optional per-fill midpoint differences as an execution diagnostic. Actual fill prices already embed spread; this diagnostic is **never deducted from PnL again**.
- A separate, labelled hypothetical live-cost estimate. It is never substituted for observed DEMO costs or deducted from DEMO/SHADOW PnL.

Numerical output values are decimal strings without display rounding. The function uses 50-digit decimal arithmetic and exact final subtraction so a fully sold fractional position does not retain phantom shares or basis. Presentation can round money later while retaining the original report.

## Input contract

All fields below are provisional project interfaces, not official workshop or eToro schemas. Preserve the packet, source receipts, specification/code identities and returned report privately. Actual account/position identifiers and runtime records must never enter Git.

| Field | Required evidence |
| --- | --- |
| `mode` | `SHADOW` or `DEMO` only |
| `ownership` | Nonempty exact `account_id`, `strategy_id`, `instrument_id`, `position_id`; a ticker alias cannot substitute for an instrument or position ID |
| `as_of` | Timezone-aware ISO report timestamp |
| `fills` | Records with the same ownership fields and mode, `fill_id`, `side` BUY/SELL, positive decimal-string `quantity`/`price`, `currency: USD`, aware `filled_at`, positive integer `sequence` |
| `fee_records` | Aggregate actual charge evidence per fill, described below; absent coverage is unknown |
| `reconciliation` | Optional normalized complete position **and open-order** snapshot; its absence prevents a closed/final result |
| `mark` | Optional owned, mode-matched USD price with `observed_at` and nonempty `source`; absent/stale marks remain unknown |
| `modeled_live_costs` | Optional separate USD `estimated_total_cost`, `source`, `observed_at`, boolean `includes_spread` |

The complete fill history for this exact position is required, including its opening buy. Quantities must be actual fills: an accepted order, proposed amount, touched quote or partial-fill request is not a fill. SELL before BUY, overselling and reopening a completely sold position under the same ID are rejected. Supply a new exact position identity for a new lifecycle.

Fills are ordered by actual `filled_at`, then by the supplied unique `sequence`; input-array order and alphabetical fill IDs do not control accounting. Where timestamps tie, the normalizer must preserve reliable execution order. A local receipt sequence cannot establish the true order of ambiguous out-of-order broker fills: obtain authoritative ordering or leave the packet unresolved.

An identical JSON record replay with the same ID is deduplicated. Any changed payload with the same fill/cost ID is rejected. Correct a bad fill through a reviewed, versioned source-history correction outside this function; never edit the durable fill record silently. The input object is not modified.

## Fees: unknown never becomes zero

Each active aggregate `fee_record` contains:

- `cost_id`, `fill_id`, exact ownership and mode, `currency: USD`, nonempty `source`, aware `observed_at` between the fill and report `as_of`.
- `status: KNOWN`, nonnegative decimal-string `amount`, and `complete: true` only when **all charges for that fill** have been checked. Source-backed explicit zero is valid.
- `status: UNKNOWN` has no amount (or null) and cannot claim completeness. A known partial amount may use `complete: false`.

The adapter must aggregate commission, tax/levy or other applicable charges consistently, without folding an already embedded spread into a fee. Allocate any order/position-level charge across its actual fills exactly once; do not charge a flat commission again for each partial execution. Preserve the source total and allocation method privately. A fee total copied from a proposed order is not final fill-charge evidence. If a charge can still arrive, leave coverage incomplete.

One fill has one effective aggregate charge record. Late charge discovery is append-only: a new `cost_id` may specify `supersedes_cost_id`, with the same fill/ownership and a strictly later observation time. The earlier record must be supplied; branched corrections or unrelated targets are rejected. The report lists the whole cost-ID history and effective records. Preserve each dated report so a correction cannot erase the earlier unknown result.

`known_observed_fees_usd` is only the known component. Missing, unknown or incomplete coverage leaves `observed_fees_usd`, `realized_net_pnl_usd` and `final_net_pnl_usd` null as applicable; it does not imply free trading. The cost estimate for a possible future live account remains under `modeled_live_costs` with `deducted_from_observed_pnl: false`.

## A flat fill ledger is not yet a closed trade

The supplied reconciliation must carry exact ownership/mode, `source`, aware `observed_at`, `complete`, decimal-string `position_quantity` and nonnegative integer `pending_order_count`. It must cover the exact position and its outstanding entry/exit orders. A positions-only snapshot cannot legitimately assert zero pending orders.

- Missing, incomplete, mismatched or pending-order reconciliation prevents `CLOSED_RECONCILED`.
- A snapshot before the latest fill, after report `as_of`, or more than 60 seconds before `as_of` is not current enough for closure. For a historical report, use the historical reconciliation time as `as_of`.
- Zero computed remaining units plus a matching complete snapshot and no pending orders yields `closed: true`. This is closure on **supplied evidence**, not independently authenticated broker state.
- `net_pnl_status: FINAL` additionally requires all fill-charge coverage complete. Otherwise final net stays null. A partially sold position always remains open; its realized result and unrealized mark remain separate.
- An empty fill list is `NO_FILLS`, never a completed trade or a zero-return win.

For example, the synthetic tests buy 10 shares at $50, sell 4 at $51, with $1 entry fees and $0.50 exit fees. Six shares remain with $300 fill-price basis and $0.60 allocated entry fees. Realized gross is $4 and realized net is $3.10; the trade is still open. These are fictional arithmetic fixtures, not observed prices, a fee schedule or performance evidence.

## Spread, currency and unsupported events

An optional fill `benchmark` has USD `mid_price`, `observed_at` and `source`. Its observation must be at/before that fill and no more than 60 seconds old. The signed adverse difference is `(buy fill - mid) * quantity` or `(mid - sell fill) * quantity`. Missing/stale/future benchmarks remain unknown. This diagnostic mixes spread and execution slippage and is not a claim that all difference is a separately payable spread charge.

This first interface supports USD only. NOK or other currency cashflows are rejected: there is no implicit FX conversion. Corporate actions, dividends, transfers, rebates/negative charges, financing and other non-fill cash movements need a supported adapter and explicit extension. Supplied nonempty `corporate_actions` or `other_cash_movements` are rejected rather than ignored. Final PnL is scoped to this position's fills and declared charges, **not whole-account equity or total economic return**. If such an event affects the position, do not present this limited report as complete economic accounting.

## Integration and verification

The operating ledger can supply normalized exact-owned fills; a future broker/data adapter must supply authenticated complete histories, source-backed charges and fresh reconciled positions/open orders. Accounting checks consistency, never provenance or authority. Reports can be used by S4; none of their statuses approves an order or a public GitHub upload. Sanitize only owner-authorized summaries before publication.

Synthetic tests cover fractional quantities, partial exits, multiple entry prices, unknown/zero/late fees, conflicting replay, mixed ownership/modes, overselling, restart-order ambiguity, unreconciled closure, stale marks, spread double-counting and modeled-live separation. Run the repository's portable checks for the full integration evidence. No historical trading edge is claimed.

For normalized private inputs, run `python scripts/trade_report.py --input PRIVATE_INPUT.json --output NEW_PRIVATE_REPORT.json`. Both files must be outside every Git checkout; existing reports are never overwritten and private record values are not printed on errors. Duplicate JSON object keys are rejected at every nesting level so conflicting input fields cannot silently replace fee or ownership evidence. This command calculates a report only. It does not fetch data, verify a broker, schedule a daily upload or publish anything.
