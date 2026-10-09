# Validation evidence

## Portable repository checks

`python scripts/validate_portable.py` runs weekly synthetic ingestion/selection/engine tests, offline research-protocol checks, earnings session/allocation guards and the three shadow controls plus their demonstrations. It also confirms provisional JSON files can be read. Earnings and shadow checks use fictional normalized facts/verdicts, not independent source verification, general PDF parsing, actual TA or broker operations. It fetches no prices and places no real/demo broker orders. Actual results are recorded in [portable-check-result.json](portable-check-result.json), including total and separate suite counts, checkout commit and runner hash. Relevant uncommitted source is recorded explicitly and the commit is null, never invented.

GitHub Actions uses the same portable command. Weekly tests provide software evidence for that comparison. Research-protocol tests challenge frozen identities/costs, correct one-change ablations, ledger replay and trial counts, owner-verifier holdout gates and committed/reproduced headline artifacts. Neither validates a daily backtester, independent agent permissions, owner signature infrastructure or profitability.

The protocol demonstration uses invented return/cost data and explicitly simulated verification seams. It reports genuine-owner approval, actual committed-code verification, genuine research readiness and profitability evidence as false. A successfully exercised gate with synthetic inputs is not a real approved holdout result.

## Three shadow controls checked 9 October 2026

The portable runner passed **267 tests** at 13:58:58 UTC on committed source [51a3b146e31cb1341e27b11c707f73ed14fc9bf6](https://github.com/Flateninvest/Active-Trading-OverNight/commit/51a3b146e31cb1341e27b11c707f73ed14fc9bf6), using Python 3.12.14. Zero failures/errors; all four synthetic demonstrations completed without broker writes. The saved record gives the runner hash and complete timestamp.

| Suite | Tests |
| --- | ---: |
| Retained weekly comparison | 65 |
| Research protocol | 44 |
| Earnings helper | 54 |
| Exact-proposal financial review | 18 |
| Position fill/fee accounting | 34 |
| Durable order/owned-exit memory | 49 |
| Combined workflow and private report CLI | 3 |

The 104 added tests challenge signed-review mutation/self-review/staleness, unknown costs, partial and fractional accounting, fee corrections, spread double-counting, shared cash/exposure reservations, unknown outcomes, exact ownership, Unicode identity, entry timing, calendar/DST, restarts, stale reconciliation, expired unfilled entries and persistent next-opening obligations. The combined exercise uses invented fills and an ephemeral synthetic reviewer key; it does not deploy a reviewer service or validate any historical trading edge.

`python scripts/shadow_workflow.py --demo` runs that fictional combined exercise. `python scripts/trade_report.py --input PRIVATE.json --output NEW_PRIVATE_REPORT.json` calculates a report from normalized privately supplied records outside Git. Neither fetches/validates broker data, places an order, schedules itself or uploads a report. Genuine Grok service isolation, trusted data producers, full-book accounting and the research homework's daily harness/statistics/continuation remain unverified or unimplemented.

## Earnings addition checked 9 October 2026

The portable runner passed **163 tests** on committed source [4722cdc2bed9126fc77dbb733e5c6693e96c0c12](https://github.com/Flateninvest/Active-Trading-OverNight/commit/4722cdc2bed9126fc77dbb733e5c6693e96c0c12): 65 weekly, 44 research-protocol and 54 earnings tests. All three synthetic demonstrations completed without broker writes. See the machine-readable record for time, Python version and runner hash.

Earnings checks cover AMC/BMO mapping, allowed weekdays, calendar bridges/early closes/DST, receipt/freeze chronology, final evidence/quote/reference checks, reconciled account state, shared and earnings-used budgets, duplicate exposure, conviction downgrades, clipped/rejected cash and preserved refresh ceilings. Passing these invented fixtures establishes helper behavior only. It does not establish a working broker bot, independently verified data, a durable ledger or profitable earnings trades.

## Recorded full check from 7 October

The original local package passed 100 tests: 35 retained original numerical, 20 source/selection and 45 engine/calendar/accounting. Six additional adversarial groups passed. The historical price-based/gated rebuild matched 21 output CSVs and its summary; proprietary-flow/PDF generation was excluded.

Those checks used private historical inputs and are not a claim that the data-free GitHub copy can reproduce them. Original test source is retained, but the full historical run requires separately provided datasets. The portable synthetic suite is the CI gate here.

Synthetic results do not establish profits. The actual-file missing-data rehearsal retained $5,000 modeled cash and no orders/fills. No real/demo trades, live writer, daily integrated runtime or production scheduling are established by these tests.
