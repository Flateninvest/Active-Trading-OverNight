# Validation evidence

## Portable repository checks

`python scripts/validate_portable.py` runs the retained synthetic ingestion/selection/engine tests, validates the provisional JSON files can be read, and completes the weekly synthetic demo. It fetches no prices and places no real/demo broker orders. Actual local results are recorded in [portable-check-result.json](portable-check-result.json) after validation, with the checkout commit and runner hash. A missing commit before the first commit is recorded as null, never invented.

GitHub Actions uses the same portable command. Synthetic tests are numerical/operational evidence for the weekly comparison, not an end-to-end daily TA pipeline or independent four-agent review.

## Recorded full check from 7 October

The original local package passed 100 tests: 35 retained original numerical, 20 source/selection and 45 engine/calendar/accounting. Six additional adversarial groups passed. The historical price-based/gated rebuild matched 21 output CSVs and its summary; proprietary-flow/PDF generation was excluded.

Those checks used private historical inputs and are not a claim that the data-free GitHub copy can reproduce them. Original test source is retained, but the full historical run requires separately provided datasets. The portable synthetic suite is the CI gate here.

Synthetic results do not establish profits. The actual-file missing-data rehearsal retained $5,000 modeled cash and no orders/fills. No real/demo trades, live writer, daily integrated runtime or production scheduling are established by these tests.
