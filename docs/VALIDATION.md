# Validation evidence

## Portable repository checks

`python scripts/validate_portable.py` runs the weekly synthetic ingestion/selection/engine tests and the offline research-protocol tests, confirms provisional JSON files can be read, and runs the earnings session/allocation guards and synthetic demonstrations. Earnings tests exercise supplied fictional normalized facts/verdicts, not independent source verification, general PDF parsing, actual TA or broker operations. It fetches no prices and places no real/demo broker orders. Actual results are recorded in [portable-check-result.json](portable-check-result.json), including total and separate suite counts, checkout commit and runner hash. Relevant uncommitted source is recorded explicitly and the commit is null, never invented.

GitHub Actions uses the same portable command. Weekly tests provide software evidence for that comparison. Research-protocol tests challenge frozen identities/costs, correct one-change ablations, ledger replay and trial counts, owner-verifier holdout gates and committed/reproduced headline artifacts. Neither validates a daily backtester, independent agent permissions, owner signature infrastructure or profitability.

The protocol demonstration uses invented return/cost data and explicitly simulated verification seams. It reports genuine-owner approval, actual committed-code verification, genuine research readiness and profitability evidence as false. A successfully exercised gate with synthetic inputs is not a real approved holdout result.

## Recorded full check from 7 October

The original local package passed 100 tests: 35 retained original numerical, 20 source/selection and 45 engine/calendar/accounting. Six additional adversarial groups passed. The historical price-based/gated rebuild matched 21 output CSVs and its summary; proprietary-flow/PDF generation was excluded.

Those checks used private historical inputs and are not a claim that the data-free GitHub copy can reproduce them. Original test source is retained, but the full historical run requires separately provided datasets. The portable synthetic suite is the CI gate here.

Synthetic results do not establish profits. The actual-file missing-data rehearsal retained $5,000 modeled cash and no orders/fills. No real/demo trades, live writer, daily integrated runtime or production scheduling are established by these tests.
