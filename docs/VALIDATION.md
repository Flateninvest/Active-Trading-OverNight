# Validation evidence

## Portable repository checks

`python scripts/validate_portable.py` runs weekly synthetic ingestion/selection/engine tests, offline research-protocol checks, earnings session/allocation guards and the three shadow controls plus their demonstrations. It also confirms provisional JSON files can be read. Earnings and shadow checks use fictional normalized facts/verdicts, not independent source verification, general PDF parsing, actual TA or broker operations. It fetches no prices and places no real/demo broker orders. The runner now writes ignored `.runtime/portable/check-result.json`, including suite counts, source commit and runner hash. It refuses tracked output paths and never rewrites dated evidence. [portable-check-result.json](portable-check-result.json) is the preserved 9 October record, not the output destination. New committed-source evidence is published separately after review. Relevant uncommitted source is recorded explicitly and the commit is null, never invented.

GitHub Actions uses the same portable command. Weekly tests provide software evidence for that comparison. Research-protocol tests challenge frozen identities/costs, correct one-change ablations, ledger replay and trial counts, owner-verifier holdout gates and committed/reproduced headline artifacts. Neither validates a daily backtester, independent agent permissions, owner signature infrastructure or profitability.

The protocol demonstration uses invented return/cost data and explicitly simulated verification seams. It reports genuine-owner approval, actual committed-code verification, genuine research readiness and profitability evidence as false. A successfully exercised gate with synthetic inputs is not a real approved holdout result.

## DEMO alignment checked 10 October 2026

The portable runner passed **378 tests** at 15:14:02 UTC on committed source [7d425cca8c7b170480ca0e47c219fe4fab7236b5](https://github.com/Flateninvest/Active-Trading-OverNight/commit/7d425cca8c7b170480ca0e47c219fe4fab7236b5), using Python 3.12.14. Zero failures/errors; all four synthetic demonstrations completed without broker writes. The checkout remained clean after the runner. The [dated machine-readable record](validation/portable-check-2026-10-10.json) was copied explicitly into this separate evidence commit; the runner did not write it or change the older record. Its runner hash matches the exact committed Git blob.

| Suite | Tests |
| --- | ---: |
| Retained weekly comparison | 65 |
| Research protocol | 44 |
| Earnings, including ten new DEMO checks | 64 |
| Existing exact-proposal review | 21 |
| Existing fill/fee accounting | 34 |
| Existing order memory | 62 |
| Existing integration/CLI | 4 |
| New DEMO risk/equity checks | 34 |
| New DEMO ledger checks | 16 |
| New external-import checks | 18 |
| New JSON/runner/manifest/prompt hygiene checks | 16 |

All original 284 tests are retained; 94 regressions were added. Eleven existing fixture/assertion adjustments are listed individually with reasons in [the alignment record](DEMO_ALIGNMENT_2026-10-10.md). Adversarial cross-review additionally caught and fixed same-night pause reset, an opening timestamp used as close, understated known fill capital after incident resolution, reconciliation-event strategy collisions and the ATR/current-price enhanced-review trigger. These are software checks on supplied facts, not proof of profitability or the separate Grok build's integration.

The organization check covered 26 maintained Markdown files and 237 local links before this evidence addition, with zero broken links. Historical prompt text is preserved below explicit archive labels. One current prompt and five archived TXT snapshots are enforced by tests. No dependencies or workflow permissions changed; no merge occurred.

## Additional QA checked 9 October 2026

The portable runner passed **284 tests** at 14:21:40 UTC on committed source [d0f583eed3bd1774c708338f7231da6044a3ecee](https://github.com/Flateninvest/Active-Trading-OverNight/commit/d0f583eed3bd1774c708338f7231da6044a3ecee), using Python 3.12.14: 65 weekly, 44 research-protocol, 54 earnings, 21 review, 34 accounting, 62 order-memory and 4 integration/CLI checks. Zero failures/errors; all four synthetic demonstrations completed without broker writes. The historical [machine-readable record](portable-check-result.json) identifies that run and its then-current runner hash.

The extra 17 tests cover phantom FILLED states, own orders with no recorded attempt, same-clock partial-fill retries, persistent incidents after restart, atomic rollback of other intents, valid cancellations/late fills, existing per-instrument reservations and ambiguous JSON fields. Four selected new ledger regressions were also run against the previous ledger source at `973d2d0563569a98c1686427e790a55ee4b3c30e`; all four failed as expected with zero test errors, confirming they detect the prior defects. This negative control is separate from the 284 passing current-source checks.

Organization review checked 25 maintained Markdown files and 179 local links: no broken links. The effective Grok prompt contains its shadow-controls addendum exactly once. No folder migration, dependency, trading-threshold or order-permission change was needed. The documented deployment, source-authentication and research-homework gaps remain.

## Three shadow controls checked earlier on 9 October 2026

The portable runner passed **267 tests** at 13:58:58 UTC on committed source [51a3b146e31cb1341e27b11c707f73ed14fc9bf6](https://github.com/Flateninvest/Active-Trading-OverNight/commit/51a3b146e31cb1341e27b11c707f73ed14fc9bf6), using Python 3.12.14. Zero failures/errors; all four synthetic demonstrations completed without broker writes. That run's [saved record](https://github.com/Flateninvest/Active-Trading-OverNight/blob/973d2d0563569a98c1686427e790a55ee4b3c30e/docs/portable-check-result.json) remains in its evidence commit; the current record describes the later QA run above.

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

The portable runner passed **163 tests** on committed source [4722cdc2bed9126fc77dbb733e5c6693e96c0c12](https://github.com/Flateninvest/Active-Trading-OverNight/commit/4722cdc2bed9126fc77dbb733e5c6693e96c0c12): 65 weekly, 44 research-protocol and 54 earnings tests. All three synthetic demonstrations completed without broker writes. Its [historical machine-readable record](https://github.com/Flateninvest/Active-Trading-OverNight/blob/a4e34d9b2aa9bdc98346ee32e350e8b7fac7e4aa/docs/portable-check-result.json) retains the time, Python version and runner hash.

Earnings checks cover AMC/BMO mapping, allowed weekdays, calendar bridges/early closes/DST, receipt/freeze chronology, final evidence/quote/reference checks, reconciled account state, shared and earnings-used budgets, duplicate exposure, conviction downgrades, clipped/rejected cash and preserved refresh ceilings. Passing these invented fixtures establishes helper behavior only. It does not establish a working broker bot, independently verified data, a durable ledger or profitable earnings trades.

## Recorded full check from 7 October

The original local package passed 100 tests: 35 retained original numerical, 20 source/selection and 45 engine/calendar/accounting. Six additional adversarial groups passed. The historical price-based/gated rebuild matched 21 output CSVs and its summary; proprietary-flow/PDF generation was excluded.

Those checks used private historical inputs and are not a claim that the data-free GitHub copy can reproduce them. Original test source is retained, but the full historical run requires separately provided datasets. The portable synthetic suite is the CI gate here.

Synthetic results do not establish profits. The actual-file missing-data rehearsal retained $5,000 modeled cash and no orders/fills. No real/demo trades, live writer, daily integrated runtime or production scheduling are established by these tests.
