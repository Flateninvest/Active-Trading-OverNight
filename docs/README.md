# Reviewer guide

Start here when reviewing the project for the Active Trading workshop. The selected design is a daily overnight stock shortlist. The available executable comparison uses a separate weekly shortlist.

## Suggested reading order

| Read | What it answers |
| --- | --- |
| [Meeting pack](meeting/eToro_Active_Trading_Meeting_Pack_2026-10-08.pdf) | Strategy overview, preparation requirements and meeting information |
| [Daily strategy](DAILY_STRATEGY.md) | Selection, timing, instruments, exposure and proposed risk controls |
| [Earnings setups](EARNINGS_STRATEGY.md) | Intermittent sheets, confirmed release windows, final review and bounded conviction stakes |
| [Four components](FOUR_COMPONENTS.md) | Research, risk, operations and reporting responsibilities |
| [Research loop](RESEARCH_LOOP.md) | Mandatory experimental checks, preregistration, holdout and report-last rules |
| [Implementation plan](IMPLEMENTATION_PLAN.md) | What is available, what remains to build and suggested work packages |
| [Validation evidence](VALIDATION.md) | What was actually tested and what those results establish |

## Current status

| Area | Status |
| --- | --- |
| Daily flow/research and earnings instructions | Documented; integrated daily runtime is not implemented |
| Earnings planning helper | Offline prepared-packet schedule/allocation guards and synthetic tests |
| Shared contracts | Provisional specification and unapproved mandate template |
| Weekly paper comparison | Runnable code, synthetic tests and demonstration |
| Research-loop protocol | Offline metadata/artifact guards and synthetic demonstration; not a daily backtester or holdout security system |
| Workshop interface compatibility | Awaiting the official reference repository and verified schemas |
| Live or broker-demo orders | Disabled; no broker writer is supplied |

The weekly tests establish software behavior. They do not establish the daily strategy's profitability or a working daily trading bot. The passive bid/ask study is a separate proposed shadow comparison; resting order support remains unverified.

## Further review

- [Repository map](REPOSITORY_MAP.md): where documents, prompts, contracts and code belong.
- [Prompt guide](../prompts/README.md) and [specification guide](../spec/README.md): current instructions and contract boundaries.
- [Data policy](DATA_POLICY.md): private inputs and publication limits.
- [ETF review](ETF_REVIEW.md) and [archived weekly research](research/WEEKLY_COMPARISON_RESEARCH.md): separate comparisons and their limitations.
- [Contribution guide](../CONTRIBUTING.md): how changes are proposed and checked.
- [Sharing guide](SHARING.md): public reading, owner control and main-branch protection.
- [Change log](../CHANGELOG.md): dated project updates.

Return to the [project overview](../README.md) for installation and the portable check command.
