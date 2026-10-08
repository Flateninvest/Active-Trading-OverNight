# Revision 12 deterministic paper engine

This module adds a weekly operating workflow beside the retained Revision 11 code. It does not replace the old research results or pretend that the new strategy has been backtested. The only implemented submission adapter is a **synthetic paper adapter**. No real or eToro demo-account writer exists.

## Run the demonstration

From the evaluation repository with Python 3.12 and the repository dependencies installed:

```powershell
python -m weekly_strategy.cli demo
```

The demo runs one invented Tuesday-to-Wednesday night, persists its order and position state, and writes three ledgers and metric files under `results/rev12_demo`:

- Weekly flow plus research, regular-open exit A.
- The same invented flow universe without the research overlay, exit A.
- Identical research selections and entries, fixed pre-open exit B.
- A separately labelled invented SPY overnight return, multiplied by each arm's invested dollars. Cash earns zero in this demonstration. SPY is a benchmark, never an execution candidate.

Prices, theses, option support, eligibility flags, instrument IDs, fills and SPY return are **SYNTHETIC_OPERATIONAL_FIXTURE** values. These files demonstrate software behaviour. They do not show real profits, historical strategy returns or an expected return. Rerunning the same demo against its existing databases consumes the same client IDs and preserves fills rather than submitting another set.

## Audit actual workbooks

The flow-only comparison is a separately labelled configuration with `research_overlay_enabled: false` and `evaluation_variant: weekly_flow_only`. It requires proven numeric flow gates, identity, availability, daily checks and active expiry support; it never sets an unreviewed Hidden Angle to an accepted thesis. Continuing-thesis exceptions are available only to the research-overlay arm. This is a comparison, not an automatically selected live alternative.

```powershell
python -m weekly_strategy.selection
```

That command reads the supplied files from `data/rev12/raw`, retains raw source rows, writes the source audit and separate Monday-cutoff and later-rehearsal diagnostics. It creates no stock orders or stock return observations. Optional `--flow`, `--angles`, `--out` and `--config` arguments select different input files or a separately labelled output directory.

## Times and entry conditions

The calendar contains the exact NYSE published holidays and early closes for **2026–2028**. It converts America/New_York timestamps into Europe/Zurich. It fails outside that horizon; it cannot predict emergency market closures. Programme/instrument trading restrictions still need a separate broker check.

```powershell
python -m weekly_strategy.cli calendar --date 2026-10-27
```

Normal proposed timing: decision 21:30 Zurich, entry from 21:55 through 21:59, regular exit at/after 15:30 next session or alternative pre-open exit 15:25. During the October DST mismatch the code derives the earlier Swiss times from New York. It also derives earlier times on shortened regular sessions. Tuesday–Thursday entries require the next calendar day to be a regular session, so weekend and holiday bridging is excluded.

The daily decision freezes the first eligible review snapshot between close minus 30 and close minus five minutes. The entry check can remove or skip those candidates; it cannot add names rejected at that decision. A scheduler first started after the decision window skips the entry rather than fabricating a prior review.

An explicit thesis invalidation in `invalidated_candidates` is persisted for that frozen selection and survives restart and later omission of the flag. It cannot reset until a newly reviewed following-week selection. A temporary price/spread skip can be reconsidered on a later eligible night.

Proposed price checks are deliberately few: a verified real-time bid/ask with no future timestamp and at most 60 seconds of age; spread at most 20 basis points; ask within 2% of the explicitly dated Monday reference close. The optional SMA20 check is disabled by default. No VWAP, relative-volume or unverified volume feed is required. Entry also requires the instrument's underlying-share long X1 eligibility, planned position-close eligibility and a clear reviewed event gate. Mode B additionally requires verification that the same regular-hours position can be closed before the open.

Weekly support expires unless at least one supporting contract stays active through the next regular opening or an explicit reviewed continuing thesis with evidence permits the entry. A selection never proves that an options buyer still owns the contract or keeps buying. Daily active-expiry control is separate from the proposed 2–10-calendar-DTE filter at weekly selection.

## Immutable selection input

An accepted packet contains:

```json
{
  "selection_id": "unique immutable decision identifier",
  "week_start": "2026-10-05",
  "selection_cutoff": "2026-10-06T08:15:00+02:00",
  "protocol": "Monday_cutoff",
  "source_manifest": [],
  "candidates": [
    {
      "ticker": "VERIFIED_STOCK",
      "instrument_id": "EXACT_VERIFIED_BROKER_ID",
      "rank": 1,
      "source_available_at": "2026-10-06T08:00:00+02:00",
      "selection_source_availability_proven": true,
      "stock_identifier_verified": true,
      "thesis_active": true,
      "continuing_thesis": false,
      "supporting_expiries": ["2026-10-09"],
      "last_eligible_entry": "2026-10-08"
    }
  ]
}
```

This is a field example, **not an actual selection or authorization**. Real diagnostic files retain null IDs, unverified identity/thesis flags and readiness blockers. `continuing_thesis: true` also needs a nonempty `continuing_thesis_evidence` field. Null last-eligible dates are valid research diagnostics and skip all entries. Source timestamps later than the selection cutoff are rejected. The canonical hash freezes the entire weekly packet; repeated loads are safe, but changing the packet in that database raises an error. Save a declared separate variant for late revised inputs. Do not silently replace the Tuesday packet midweek.

## Market snapshot input

Use `data/rev12/templates/market_snapshot.template.json` as an unverified, empty starting point. A producer must provide new timestamped observations; the scheduler does not make stale quotes fresh. A populated quote uses these fields:

```json
{
  "data_kind": "OBSERVED_READ_ONLY",
  "quotes": {
    "VERIFIED_STOCK": {
      "instrument_id": "EXACT_VERIFIED_BROKER_ID",
      "bid": 100.00,
      "ask": 100.01,
      "as_of": "2026-10-06T19:55:00+00:00",
      "realtime": true,
      "settlement_type": "real",
      "leverage": 1,
      "entry_eligible": true,
      "close_eligible": true,
      "event_gate_clear": true,
      "same_position_preopen_close_verified": false,
      "monday_reference_close": 100.00,
      "reference_date": "2026-10-05"
    }
  },
  "account": {"risk_score": 3, "as_of": "2026-10-06T19:55:00+00:00", "strategy_cash_verified": true},
  "costs": {
    "commission_usd": 0, "fx_usd": 0, "financing_usd": 0,
    "other_usd": 0, "operating_usd": 0,
    "verified_or_paper_assumed": true
  }
}
```

All numeric values and verification flags above are **format examples**. They are not an observed quote, account state or cost confirmation. Leave unsupported fields unverified; such inputs skip entries. Commission zero is a programme planning assumption pending account/instrument confirmation. Eligible underlying shares do not automatically incur CFD financing. Buy-at-ask and sell-at-bid fill prices already contain spread; do not subtract it again. Other known fees are separately charged once. Missing exit cost information does not suppress a necessary exit, but makes complete net profitability unavailable.

## One tick, replay and continuous PAPER scheduling

```powershell
python -m weekly_strategy.cli run-once --selection data/rev12/audit/Weekly_Selection_Diagnostic.json --market data/rev12/templates/market_snapshot.template.json --database results/rev12_paper/state.sqlite --report results/rev12_paper/latest_report.json
```

```powershell
python -m weekly_strategy.cli scheduler --selection data/rev12/audit/Weekly_Selection_Diagnostic.json --market data/rev12/templates/market_snapshot.template.json --database results/rev12_paper/state.sqlite --report results/rev12_paper/latest_report.json --log results/rev12_paper/scheduler.log --poll-seconds 10
```

The second command is a real continuously running local Python process until Ctrl+C. It is **PAPER**, reads the named market snapshot each tick and logs failures. It requires the computer and process to remain running, plus a separate read-only snapshot producer for fresh real observations. No live unattended agent or running service was started during this task. A Windows Task Scheduler job can launch that same paper command on logon with an absolute interpreter path, repository working directory, and a single-instance rule; it must restart the process rather than reset its database. Do not register the job or switch modes silently.

For bounded verification add `--max-ticks 1`. A fixed `--at` clock is accepted only with a one-tick scheduler check. `replay --events FILE` consumes chronological `{at, market}` records into a separately labelled paper database. This replays supplied snapshots; it never downloads missing prices or retroactively uses a later file as an earlier source.

## Persistent state and exceptions

- SQLite stores immutable weekly decisions, daily decisions, event keys, order intents, synthetic broker receipts, accounted cumulative fills, strategy-owned position IDs and cash. Transactions serialize concurrent ticks and stable client IDs prevent repeat submissions. Restart using the same configuration and database. A changed configuration requires a separate evaluation database.
- Paper buys model an IOC limit at the observed ask. Adverse prices above that limit reject without a fill. This is a paper modelling choice; an eToro IOC route has not been exercised or approved. It does not promise market or auction fills at quoted prices.
- ACK, INTENT, UNKNOWN or REJECTED responses do not establish executed quantity. Inconsistent nonzero quantities in those responses become reconciliation exceptions. PARTIAL and FILLED state reconcile actual fixture quantities. Client ID, action, ticker, instrument and the exact requested sell position must match.
- Partial entry fills remain owned positions; outstanding units are cancelled/reconciled before an exit. Unknown entry or exit orders block new entries and prevent blind retries.
- Mode B makes one pre-open close attempt per position. At the regular open it reconciles cumulative fills, confirms cancellation of outstanding pre-open units, and submits exactly one remainder order. If cancellation is unconfirmed, it alerts and submits no duplicate close. A rejected or partial regular-open remainder requires operator review; it is never blindly resubmitted. Unresolved owned positions block all new entries.
- Only recorded IDs tagged with the strategy are closed. Unrelated PLTR, RKLB and other core position IDs remain untouched, including when the sleeve owns a separate position in the same ticker.
- The initial paper budget is $5,000, at most 10% per request and three requests/30% total. Rejected/partial requests do not enlarge other slots. The later 15%/45% ceilings are disabled and rejected by this pilot constructor. These are proposed test limits, not approved live settings or guaranteed loss limits.
- Real fills, unknown fills, costs, marks and dividends/corporate actions require reconciled broker/account records before empirical performance reporting. Open positions or unknown orders leave complete equity return and drawdown unavailable. Descriptive metrics retain skipped cash nights and distinguish correlated stock trades from independent nights/weeks. Execution shortfall remains null without an independently timestamped reference benchmark.

## Tests

```powershell
python -m unittest discover -s tests -p "test_rev12*.py" -v
```

The original tests remain separate and unchanged. New tests exercise calendars, time cutoffs, membership, expiry, delayed/stale/missing data, pilot limits, order acknowledgements, partial/unknown/rejected fills, exact ownership, restart recovery, fallback, fee accounting, cash benchmarks and the scheduler command. Synthetic tests validate operation only.
