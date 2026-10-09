# Repository map

The current daily design, reusable instructions and retained weekly comparison have separate homes. Keep the weekly code in its existing folder so its imports, tests and commands continue working.

## Existing paths

| Path | Purpose |
| --- | --- |
| [Root README](../README.md) | Project overview, status, installation and portable checks |
| [docs/](README.md) | Current strategy, architecture, implementation plan, validation and review guides |
| [docs/meeting/](meeting/) | Dated meeting documents; preserve historical versions |
| [docs/research/](research/) | Archived research and comparisons, labeled by their original scope |
| [prompts/](../prompts/README.md) | Complete Grok instructions, separate update addendum and setup guide |
| [spec/](../spec/README.md) | Provisional shared specification and draft operating mandate |
| [scripts/](../scripts/) | Portable validation, research-protocol, earnings planning, shadow demonstration and private trade-report helpers |
| [src/active_trading/earnings.py](../src/active_trading/earnings.py) | Offline earnings session, final-packet and conviction-allocation guards; no broker writer |
| [src/active_trading/research/](../src/active_trading/research/) | Offline plan, ablation, ledger, holdout and artifact-verification guards; no daily backtester |
| [src/active_trading/risk/](../src/active_trading/risk/) | Offline exact-context reviewer attestation and mandatory-check gates |
| [src/active_trading/operations/](../src/active_trading/operations/) | Durable local shadow intents, owned positions and reconciliation/exit obligations |
| [src/active_trading/reporting/](../src/active_trading/reporting/) | Normalized-fill and explicit-fee accounting; unknown net results remain unknown |
| [Homework checklist](HOMEWORK_CHECKLIST_2026-10-09.md) and [demo outline](FIVE_MINUTE_DEMO.md) | Task 1 requirements, evidence gaps and honest five-minute rehearsal |
| [Shadow controls](SHADOW_CONTROLS.md) | Setup/upload guide for the three operating improvements and their boundaries |
| [tests/](../tests/) | Adversarial offline module checks using synthetic fixtures; see validation for exact suites |
| [legacy/weekly-paper/](../legacy/weekly-paper/README.md) | Retained weekly paper engine, configuration, tests and archived local instructions |
| [.github/](../.github/) | Automatic checks and pull request guidance |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Human change workflow |
| [CHANGELOG.md](../CHANGELOG.md) | Dated record of material project updates |
| [AGENTS.md](../AGENTS.md) | Instructions for coding agents working in this repository |

## Boundaries for continuing daily work

The stage packages now have offline helpers; their presence does not establish the integrated daily runtime. The daily source/TA/backtest pipeline, authoritative broker facts, separate agent services and deployed scheduler remain work. Use these homes for additions and follow the [implementation plan](IMPLEMENTATION_PLAN.md).

| Path | Existing helper and remaining work |
| --- | --- |
| `src/active_trading/research/` | Existing protocol guards; add daily parsing, TA, candidate freeze and reproducible economic harness |
| `src/active_trading/risk/` | Existing signed-review gates; add independently controlled producers/services and real approval integration |
| `src/active_trading/operations/` | Existing shadow ledger; add verified adapter/scheduler only under separate authority |
| `src/active_trading/reporting/` | Existing fill/fee arithmetic; add trusted ingestion, whole-book valuation and tear sheet |
| `tests/` | Daily unit, contract, integration and adversarial tests with synthetic fixtures |
| `examples/` | Clearly labeled synthetic source packets and interface examples |

Shared daily contracts remain under `spec/`; reusable project checks remain under `scripts/`. Keep installation instructions current when dependencies change. Private SQLite ledgers, keys, source data and reports belong outside the checkout. Do not introduce an order-writing capability as part of a folder reorganization.

## Keep updates understandable

- Link new documents from the reviewer guide or the relevant folder index.
- Describe current behavior in maintained documents; preserve dated meeting packs and historical comparisons.
- Keep generated state, private inputs, credentials and account records outside tracked files, following the [data policy](DATA_POLICY.md).
- Use branches and pull requests. Record strategy and permission changes explicitly, and keep daily, weekly and passive studies distinct.
