# Reviewer guide

Start here when reviewing the project for the Active Trading workshop. The selected design is a daily overnight stock shortlist. The available executable comparison uses a separate weekly shortlist.

## Suggested reading order

| Read | What it answers |
| --- | --- |
| [Current rules](../CURRENT_RULES.md) and [DEMO alignment](DEMO_ALIGNMENT_2026-10-10.md) | Effective owner policy, implementation changes and local-build acceptance |
| [Meeting pack](meeting/eToro_Active_Trading_Meeting_Pack_2026-10-08.pdf) | Historical strategy/meeting snapshot; current rules override older parameters |
| [Daily strategy](DAILY_STRATEGY.md) | Selection, timing, instruments, exposure and proposed risk controls |
| [Earnings setups](EARNINGS_STRATEGY.md) | Intermittent sheets, confirmed release windows, final review and bounded conviction stakes |
| [Four components](FOUR_COMPONENTS.md) | Research, risk, operations and reporting responsibilities |
| [Research loop](RESEARCH_LOOP.md) | Mandatory experimental checks, preregistration, holdout and report-last rules |
| [Homework checklist](HOMEWORK_CHECKLIST_2026-10-09.md) and [five-minute demo](FIVE_MINUTE_DEMO.md) | Four Task 1 deliverables, eleven self-checks, due date and actual gaps |
| [Shadow controls](SHADOW_CONTROLS.md) | Double review, fill/cost accounting, order memory and what to supply to Grok |
| [Implementation plan](IMPLEMENTATION_PLAN.md) | What is available, what remains to build and suggested work packages |
| [Validation evidence](VALIDATION.md) | What was actually tested and what those results establish |

## Current status

| Area | Status |
| --- | --- |
| Daily flow/research and earnings instructions | Documented; integrated daily runtime is not implemented |
| Earnings planning helper | Offline prepared-packet schedule/allocation guards and synthetic tests |
| Shared contracts | Draft operating specification and unapproved mandate; complete research homework contract/signature remain pending |
| Weekly paper comparison | Runnable code, synthetic tests and demonstration |
| Research-loop protocol | Offline metadata/artifact guards and synthetic demonstration; not a daily backtester or holdout security system |
| Double review, order memory and accounting | Offline helpers; source verification, isolated services, broker integration and schedule are not deployed |
| Task 1 specification format | Our own JSON/YAML schema required; no external template prerequisite. Any later shared interfaces are separate |
| Execution | Owner mode DEMO in a separate reported local build; no repository broker writer; LIVE rejected |

Offline tests establish software behavior under supplied fixtures. They do not establish the daily strategy's profitability, complete homework or a working daily trading bot. Passive execution is disabled under the owner-reported interface. Read [current rules](../CURRENT_RULES.md) and [DEMO alignment](DEMO_ALIGNMENT_2026-10-10.md) before historical meeting documents.

## Further review

- [Repository review](REPOSITORY_REVIEW_2026-10-09.md): organization, corrected review findings and publication boundaries for the homework/control update.

- [Repository map](REPOSITORY_MAP.md): where documents, prompts, contracts and code belong.
- [Prompt guide](../prompts/README.md) and [specification guide](../spec/README.md): current instructions and contract boundaries.
- [Data policy](DATA_POLICY.md): private inputs and publication limits.
- [ETF review](ETF_REVIEW.md) and [archived weekly research](research/WEEKLY_COMPARISON_RESEARCH.md): separate comparisons and their limitations.
- [Contribution guide](../CONTRIBUTING.md): how changes are proposed and checked.
- [Sharing guide](SHARING.md): public reading, owner control and main-branch protection.
- [Change log](../CHANGELOG.md): dated project updates.

Return to the [project overview](../README.md) for installation and the portable check command.
