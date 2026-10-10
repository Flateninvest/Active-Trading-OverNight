# Current operating rules

Effective owner policy: **OWNER_DEMO_2026-10-10_v1**. Strategy ownership identifier stays `GROK_DAILY_OVERNIGHT_v2` to preserve existing position ownership.

1. [spec/strategy_spec.provisional.json](spec/strategy_spec.provisional.json) is the single machine-readable operating policy. Load with `active_trading.policy.load_policy`; derive limits with `capital_limits`. Do not copy constants into local trading code.
2. [The current complete Grok prompt](prompts/Grok_Overnight_Stock_Bot_Prompt_Current.txt) is the **only effective prompt**. Other dated prompts/addenda are historical and must not be appended.
3. [The DEMO alignment record](docs/DEMO_ALIGNMENT_2026-10-10.md) explains owner decisions, APIs, regression coverage, local-build acceptance and remaining gaps.

Allowed modes are **SHADOW simulation (no broker orders)** or **the existing eToro DEMO account that the owner confirms Grok already accesses**. DEMO remains the default. **Never place, modify or close trades on a real-money account.** LIVE, transfers and public performance posting remain disabled. Owner-selected DEMO policy is not a genuine research holdout signature or an order approval.

The private Grok runtime must record the exact repository commit and `canonical_hash(load_policy())`, compare them with its effective local policy, and stop new entries on mismatch. Downloading a prompt does not synchronize a local build. Existing owned exit obligations survive policy updates and entry pauses.

No merge or new broker permission is part of this update. The repository supplies no broker writer or scheduler. Historical documents and older dollar/schedule examples cannot override the current specification.
