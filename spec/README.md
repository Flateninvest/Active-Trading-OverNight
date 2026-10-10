# Shared specification and mandate

[Current rules](../CURRENT_RULES.md) identifies the effective owner policy. **strategy_spec.provisional.json is the single operating source of truth**; code loads it through `load_policy` and derives limits through `capital_limits`. Its provisional label concerns workshop schema/research completeness, not whether the owner has selected DEMO parameters.

| File | Purpose |
| --- | --- |
| [strategy_spec.provisional.json](strategy_spec.provisional.json) | Effective DEMO allocation, selection, schedule, caps/stress/loss rules and implementation boundaries |
| [operating_mandate.template.json](operating_mandate.template.json) | DEMO configuration template referring to that policy; private account/operators/credential approvals are configured separately |
| [research_plan.template.json](research_plan.template.json) | Unsigned research plan; actual input hashes, holdout periods, disclosed year and approval remain unset |

DEMO is eToro demo only; LIVE is rejected. The owner reports a separate local Grok build. This repository supplies no broker writer or scheduler and does not prove that build has adopted these rules. Compare exact source commit and canonical policy hash before new entries. A review PASS, test result, JSON file or merge is not platform/broker approval.

## Keep changes coherent

1. Update the applicable operating fields/version in the specification.
2. Update maintained daily/earnings and implementation documentation.
3. Update the one [current complete prompt](../prompts/Grok_Overnight_Stock_Bot_Prompt_Current.txt). Dated prompt snapshots stay archived; never maintain a competing addendum.
4. Add meaningful regressions and record committed-source verification separately.

Record owner decisions and dates without inventing a signature. The strategy ownership ID stays stable across this policy revision so exits remain linked. Policy changes invalidate pending entry reviews, not existing owned exit obligations. Private identities, keys and actual trading state stay outside Git.

## Research homework remains separate

Task 1 asks for our own JSON/YAML specification and validator, with minimum fields `hypothesis`, `universe`, `signal`, `holding`, `costs`, `expected`, `kill`, `trials`, `signed`. No external template is required. The operating policy is not a completed signed research submission.

The [portable check](../scripts/validate_portable.py) strictly decodes JSON (duplicate keys/nonfinite values refused) and tests synthetic behavior. It does not produce the daily economic harness, genuine Sharpe/turnover/break-even/deflated Sharpe, real-loader continuation or owner signature. Keep the genuine holdout unopened until externally verified owner preregistration; see [research loop](../docs/RESEARCH_LOOP.md) and [homework checklist](../docs/HOMEWORK_CHECKLIST_2026-10-09.md). Validate any later organiser-supplied shared interfaces separately.
