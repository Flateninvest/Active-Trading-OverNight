# Shared specification and mandate

These files describe the current intended daily design. They are provisional project contracts, pending the workshop reference repository and its actual validators.

| File | Status and purpose |
| --- | --- |
| [strategy_spec.provisional.json](strategy_spec.provisional.json) | Daily rules, timing, proposed controls, component boundaries and implementation status; not workshop validated |
| [operating_mandate.template.json](operating_mandate.template.json) | Unapproved SHADOW mandate template; account, capital, loss limits, owners and approvals remain unset |
| [research_plan.template.json](research_plan.template.json) | Unapproved research plan; actual hashes, periods, disclosed year and evaluation choices are unset |

No real or broker-demo orders are enabled. A JSON file, passing check or risk PASS does not provide execution approval. The mandate template must never contain public account credentials or actual private position identifiers.

## Keep rules synchronized

For a strategy change, update these together in the same pull request:

1. The provisional specification's applicable fields and version/date.
2. The [daily strategy](../docs/DAILY_STRATEGY.md) and relevant architecture or implementation notes.
3. The effective [current complete Grok prompt](../prompts/Grok_Overnight_Stock_Bot_Prompt_Current.txt), including both workshop sections and corresponding standalone addenda.
4. Applicable tests and validation evidence once an implementation exists.

Describe old and new values, their reason, evaluation scope and required approval. Keep historical meeting documents and research labeled by their original date. If current instructions disagree, identify the discrepancy and resolve it through review before relying on an affected rule; do not silently choose the more permissive version.

The [portable check](../scripts/validate_portable.py) confirms these JSON files can be read and exercises the offline research protocol with synthetic fixtures. The unfilled research plan is deliberately not an approved runnable study. Neither check validates official workshop schema conformity or a complete daily runtime. See [the research loop](../docs/RESEARCH_LOOP.md) for approval and holdout-custody boundaries.

## Reference alignment

When the official repository is supplied, record its URL and exact commit, map specification/positions/log fields, and run its actual validators. Keep verification flags false until that evidence exists. Follow the [four-component contract](../docs/FOUR_COMPONENTS.md), [implementation plan](../docs/IMPLEMENTATION_PLAN.md) and [contribution guide](../CONTRIBUTING.md).
