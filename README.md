# Active Trading Overnight

Daily overnight-stock research for Flateninvest, with the Active Trading workshop's research, risk, operations and reporting components.

**Current status: shadow design, offline research-protocol guards and runnable weekly paper comparison. No live or broker-demo orders are enabled.** The daily shortlist and four-component architecture are specified, but their integrated runtime is not yet implemented. The retained weekly engine is a separate comparison, not proof that the daily version is working or profitable.

## Start here

| Your purpose | Where to start |
| --- | --- |
| Review the project for eToro | [Reviewer guide](docs/README.md), then the [meeting pack](docs/meeting/eToro_Active_Trading_Meeting_Pack_2026-10-08.pdf) |
| Understand the strategy and agents | [Daily strategy](docs/DAILY_STRATEGY.md) and [four components](docs/FOUR_COMPONENTS.md) |
| Set up the research instructions | [Prompt guide](prompts/README.md) and [shared specification](spec/README.md) |
| Develop or update the project | [Repository map](docs/REPOSITORY_MAP.md), [contribution guide](CONTRIBUTING.md) and [implementation plan](docs/IMPLEMENTATION_PLAN.md) |
| Check evidence or share access | [Validation](docs/VALIDATION.md), [data policy](docs/DATA_POLICY.md) and [sharing guide](docs/SHARING.md) |

## What exists today

| Part | Status |
| --- | --- |
| Daily flow/research and earnings strategies and Grok instructions | Documented; daily integrated runtime remains to build |
| Earnings calendar and conviction allocation | Offline prepared-packet shadow helper and synthetic tests; no PDF/TA/source verification runtime |
| Workshop specification and mandate | Provisional specification; unapproved SHADOW mandate |
| Weekly paper comparison | Runnable synthetic tests and demonstration in `legacy/weekly-paper/` |
| Workshop research loop | Offline plan/ablation/ledger/holdout/reproduction gates and synthetic tests; no daily backtester |
| Live or broker-demo execution | Disabled; no broker writer supplied |

The [change log](CHANGELOG.md) records project updates. Dated meeting packs and archived research preserve their original scope; they are not the source for current operating rules.

## Current daily design

Use previous completed-session options flow, Hidden Angles and research for the ordinary sleeve. The [earnings sleeve](docs/EARNINGS_STRATEGY.md) also accepts intermittent private earnings PDFs, verifies AMC/BMO release windows and rechecks event-day TA/news/risk before a proposed preclose entry. Its illustrative $2,000 ceiling and conviction weights remain inside the same shared capital limits. Both sleeves use one frozen candidate register and one exposure per underlying instrument. Upload at 08:00 Europe/Paris and freeze up to ten candidates at 08:15; review up to three for execution. Technical analysis is required. Buy qualifying long underlying cash/X1 stocks near Tuesday-Thursday US closes and exit at the next regular opening. Skip planned weekend and full-holiday holds.

Illustrative paper capital is $5,000, with a maximum 10% per stock, three positions and 30% gross exposure including pending orders. Account risk target 3-4 and a pause of new entries at 5 or above are proposals. Missing prerequisites leave cash. Existing holdings are protected by exact position ownership.

Passive bid-side buying/ask-side selling is a separate shadow execution study. Resting opening and exact-position closing support remain unverified. IOC and market-if-touched orders do not establish passive execution. The primary next-opening exit is unchanged.

## Run the portable checks

Use Python 3.12. From this repository:

Create the environment with `python -m venv .venv`. Activate it with `.\.venv\Scripts\Activate.ps1` on Windows PowerShell or `source .venv/bin/activate` on Linux/macOS. Then run:

```sh
python -m pip install -r legacy/weekly-paper/requirements-rev12.txt
python scripts/validate_portable.py
```

You can also use the environment's Python executable directly. The [validation record](docs/portable-check-result.json) identifies the exact previously tested source commit; CI checks each new pull request.

The portable runner runs the weekly synthetic ingestion/selection/engine tests, the research-protocol tests, earnings calendar/allocation guards and synthetic demonstrations. Try `python scripts/earnings_plan.py --demo` for a fictional prepared earnings packet and shadow plan. It does not parse the vendor PDF, calculate TA or connect to a broker. It does not need vendor workbooks, broker credentials or paid data. Outcomes are invented fixtures, not historical returns or executed trades. GitHub Actions runs this same check on pull requests and pushes to `main`.

The [mandatory research loop](docs/RESEARCH_LOOP.md) follows Hypothesis, Build, Ablate, Hold out and Verify, with owner preregistration before holdout access and reporting last. The [current complete Grok prompt](prompts/Grok_Overnight_Stock_Bot_Prompt_Current.txt) includes these requirements. Actual holdout dates/year and approval remain unset.

The retained full historical test suite and original rebuild need separately supplied historical datasets. Those private or third-party inputs are intentionally absent. The full suite's recorded 100-test result is historical evidence, not a claim that it runs data-free here.

## Managing changes

Use a branch and pull request, following [CONTRIBUTING.md](CONTRIBUTING.md). Keep the current strategy, specification and effective prompt consistent; preserve dated evidence. The workshop reference repository has not been supplied: the specification and interface examples remain provisional until its exact schemas and commit are verified.

`main` is the stable version to share. Public visitors can read and download it without edit permission. Human write access is held by the owner; no outside collaborators were present in the 8 October access check. Main-branch protection requires a pull request, passing checks and resolved conversations, and blocks force pushes and deletion. See the [sharing guide](docs/SHARING.md) for the access boundaries.

The repository contains no broker writer, deployed routine, secrets or authority to publish copier notes. An approved specification or passing tests alone cannot authorize trading.
