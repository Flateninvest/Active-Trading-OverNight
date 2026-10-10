# Active Trading Overnight

Daily overnight-stock research and DEMO operating controls for Flateninvest's Active Trading workshop project.

**Current owner policy: eToro DEMO only, USD 10,000 strategy allocation. LIVE is rejected.** This repository supplies offline review, planning, accounting and durable order-memory helpers. Grok's separate local trading build is reported by the owner; it has not been inspected or deployed from this repository. There is no repository broker writer, running scheduler or public performance publisher.

## Start here

| Purpose | Read |
| --- | --- |
| Current rules and changes | [Current rules](CURRENT_RULES.md), [10 October alignment](docs/DEMO_ALIGNMENT_2026-10-10.md) |
| Strategy and agents | [Daily strategy](docs/DAILY_STRATEGY.md), [earnings](docs/EARNINGS_STRATEGY.md), [four components](docs/FOUR_COMPONENTS.md) |
| Grok instructions | [Prompt guide](prompts/README.md), [one effective prompt](prompts/Grok_Overnight_Stock_Bot_Prompt_Current.txt), [specification](spec/README.md) |
| Implementation | [Review gates](docs/DOUBLE_REVIEW.md), [order memory](docs/ORDER_MEMORY.md), [accounting](docs/TRADE_ACCOUNTING.md) |
| Homework and evidence | [Homework checklist](docs/HOMEWORK_CHECKLIST_2026-10-09.md), [validation](docs/VALIDATION.md), [reviewer guide](docs/README.md) |
| Develop or share | [Repository map](docs/REPOSITORY_MAP.md), [contributing](CONTRIBUTING.md), [data policy](docs/DATA_POLICY.md), [sharing](docs/SHARING.md) |

## Current design

- Freeze one combined register at **09:00 Europe/Paris**: up to ten candidates and three review priorities from previous-session flow, Hidden Angles/research and separately verified earnings setups.
- Long underlying cash/X1 stocks or verified US ADRs only. No options trades, shorts, leverage, CFDs or ETFs.
- Enter Tuesday–Thursday from the exchange close minus five minutes until minus one minute. Prepare owned exits five minutes before the next opening; first close attempt at the US 09:30 regular open. Exchange-calendar times govern clock-change weeks and early closes.
- Capital basis is the lower of the **USD 10,000 strategy allocation and account balance**. At the full allocation: USD 1,000 per stock, three positions and USD 3,000 gross, including pending commitments and reserved costs.
- Stress sizing adds round-trip costs to the larger of twice ATR14/close and the largest absolute overnight gap in 60 sessions. Earnings also uses the last eight confirmed release gaps. Position risk budget is USD 25; new entries pause at USD 100 nightly loss or USD 500 cash-flow-adjusted drawdown. Drawdown resumption requires verified owner review.
- DEMO account risk score does not gate entries. The real account's score never governs. Passive execution is disabled under the owner-reported eToro interface.

Values come from the [effective specification](spec/strategy_spec.provisional.json); dollar examples assume balance is at least the allocation. Missing prerequisites leave cash. Review PASS is not broker/platform approval. Entry failures never cancel an already-owned exit obligation.

## What exists

| Part | Status |
| --- | --- |
| Daily flow/research and earnings selection | Documented; prepared-packet earnings planner available; daily parser/TA/data producers are not implemented here |
| DEMO/SHADOW review and risk state | Offline exact-context attestations, allocation/stress/loss gates and bid-marked strategy equity |
| Order memory | Private SQLite intents, reservations, owned fills, exits, retries and incident audit records; no broker dispatch |
| Accounting | Normalized fills/fees, remaining shares and external DEMO import with unknown fees preserved |
| Research loop | Offline plan/trial/ablation/holdout/reproduction guards; no complete daily backtester or validated overnight edge |
| Weekly paper engine | Separate runnable comparison in `legacy/weekly-paper/`; does not validate daily selection |
| External Grok build | Owner-reported; alignment needs exact policy hash and local acceptance evidence |

## Run checks

Use Python 3.12, create and activate a virtual environment, then run:

```sh
python -m pip install -r legacy/weekly-paper/requirements-rev12.txt
python scripts/validate_portable.py
```

The runner writes ignored `.runtime/portable/check-result.json`, never tracked evidence. Optional `--output` must name a new untracked file. See [validation](docs/VALIDATION.md) for committed-source evidence. Demonstrations use fictional SHADOW records: `--demo` means a software demonstration, not an eToro DEMO order. No check fetches prices or places orders.

Use a branch and pull request. **PR #4 remains unmerged.** `main` is the shared stable version; public visitors can read/download without edit permission. Dated meeting packs, historical prompts and validation records retain their original context and do not override current rules. Private vendor files, credentials, account identifiers and trading state stay outside Git.
