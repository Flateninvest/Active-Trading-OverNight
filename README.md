# Active Trading Overnight

Daily overnight-stock research for Flateninvest, with the Active Trading workshop's research, risk, operations and reporting components.

**Current status: shadow design and runnable weekly paper comparison. No live or broker-demo orders are enabled.** The daily shortlist and four-component architecture are specified, but their integrated runtime is not yet implemented. The retained weekly engine is a separate comparison, not proof that the daily version is working or profitable.

## Start here

- [Meeting pack](docs/meeting/eToro_Active_Trading_Meeting_Pack_2026-10-08.pdf): strategy, capital/risk proposal, preparation checklist and meeting dates.
- [Daily strategy](docs/DAILY_STRATEGY.md): the selected trading rules and their limitations.
- [Workshop architecture](docs/FOUR_COMPONENTS.md): S1 research, S2 risk, S3 operations and S4 reporting.
- [Complete Grok instructions](prompts/Grok_Overnight_Stock_Bot_Prompt_Workshop_2026-10-08.txt) and [workshop additions](prompts/Grok_Active_Trading_Workshop_Addendum_2026-10-08.txt).
- [Grok setup](prompts/GROK_SETUP.md): attach the files and verify capabilities; no automatic account activation.
- [Provisional shared specification](spec/strategy_spec.provisional.json) and [draft operating mandate](spec/operating_mandate.template.json).
- [Runnable weekly paper engine](legacy/weekly-paper/README.md) and [validation](docs/VALIDATION.md).
- [Implementation backlog](docs/IMPLEMENTATION_PLAN.md) and [data policy](docs/DATA_POLICY.md).

## Current daily design

Use previous completed-session options flow, Hidden Angles and research. Upload at 08:00 Europe/Paris and freeze up to ten candidates at 08:15; review up to three for execution. Technical analysis is required. Buy qualifying long underlying cash/X1 stocks near Tuesday-Thursday US closes and exit at the next regular opening. Skip planned weekend and full-holiday holds.

Illustrative paper capital is $5,000, with a maximum 10% per stock, three positions and 30% gross exposure including pending orders. Account risk target 3-4 and a pause of new entries at 5 or above are proposals. Missing prerequisites leave cash. Existing holdings are protected by exact position ownership.

Passive bid-side buying/ask-side selling is a separate shadow execution study. Resting opening and exact-position closing support remain unverified. IOC and market-if-touched orders do not establish passive execution. The primary next-opening exit is unchanged.

## Run the portable checks

Use Python 3.12. From this repository:

```sh
python -m venv .venv
python -m pip install -r legacy/weekly-paper/requirements-rev12.txt
python scripts/validate_portable.py
```

Activate the environment first (`.venv/Scripts/Activate.ps1` on Windows or `source .venv/bin/activate` on Linux/macOS), or use its Python executable in each command.

The portable runner runs the synthetic ingestion/selection/engine tests and a synthetic paper demonstration. It does not need vendor workbooks, broker credentials or paid data. All demonstration outcomes are invented fixtures, not historical returns or executed trades. GitHub Actions runs this same check on pull requests and pushes to `main`.

The retained full historical test suite and original rebuild need separately supplied historical datasets. Those private or third-party inputs are intentionally absent. The full suite's recorded 100-test result is historical evidence, not a claim that it runs data-free here.

## Managing changes

Use a branch and pull request. State changes to parameters, methods, permissions and execution timing explicitly; record new trials separately. Do not overwrite older decisions or report hypothetical fills as real. The workshop reference repository has not been supplied: the specification and interface examples remain provisional until its exact schemas and commit are verified.

The repository contains no broker writer, deployed routine, secrets or authority to publish copier notes. An approved specification or passing tests alone cannot authorize trading.
