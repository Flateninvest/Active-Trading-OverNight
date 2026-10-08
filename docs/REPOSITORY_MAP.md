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
| [scripts/](../scripts/) | Repository-wide checks, currently the portable validation runner |
| [legacy/weekly-paper/](../legacy/weekly-paper/README.md) | Retained weekly paper engine, configuration, tests and archived local instructions |
| [.github/](../.github/) | Automatic checks and pull request guidance |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Human change workflow |
| [CHANGELOG.md](../CHANGELOG.md) | Dated record of material project updates |
| [AGENTS.md](../AGENTS.md) | Instructions for coding agents working in this repository |

## Intended home for future daily code

These paths are a layout proposal. They do not exist yet and do not represent implemented capabilities. Create them when reviewed code is ready, following the [implementation plan](IMPLEMENTATION_PLAN.md).

| Proposed path | Intended contents |
| --- | --- |
| `src/active_trading/research/` | Daily source parsing, technical calculations, candidate freeze and research packet |
| `src/active_trading/risk/` | Deterministic checks and review bound to the exact proposal and specification |
| `src/active_trading/operations/` | Shadow intent ledger, owned positions, reconciliation and session lifecycle |
| `src/active_trading/reporting/` | Compliance, attribution, reconciled tear sheet and draft copier note |
| `tests/` | Daily unit, contract, integration and adversarial tests with synthetic fixtures |
| `examples/` | Clearly labeled synthetic source packets and interface examples |

Shared daily contracts remain under `spec/`; reusable project checks remain under `scripts/`. Add installation metadata and root instructions with the first executable daily implementation. Do not introduce an order-writing capability as part of a folder reorganization.

## Keep updates understandable

- Link new documents from the reviewer guide or the relevant folder index.
- Describe current behavior in maintained documents; preserve dated meeting packs and historical comparisons.
- Keep generated state, private inputs, credentials and account records outside tracked files, following the [data policy](DATA_POLICY.md).
- Use branches and pull requests. Record strategy and permission changes explicitly, and keep daily, weekly and passive studies distinct.
