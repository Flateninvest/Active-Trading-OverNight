# Prompt guide

Use **one effective prompt**: [Grok_Overnight_Stock_Bot_Prompt_Current.txt](Grok_Overnight_Stock_Bot_Prompt_Current.txt), with the [specification](../spec/strategy_spec.provisional.json) at the same exact commit. Load operating numbers from that specification; prompts do not define a second policy.

| File | Status |
| --- | --- |
| [Current prompt](Grok_Overnight_Stock_Bot_Prompt_Current.txt) | **EFFECTIVE — owner DEMO policy, 10 October 2026** |
| [Setup guide](GROK_SETUP.md) | Supporting acceptance checklist, not a second prompt |
| [Workshop prompt](Grok_Overnight_Stock_Bot_Prompt_Workshop_2026-10-08.txt) | ARCHIVED; superseded |
| [Workshop addendum](Grok_Active_Trading_Workshop_Addendum_2026-10-08.txt) | ARCHIVED; superseded |
| [Research-loop addendum](Grok_Research_Loop_Addendum_2026-10-08.txt) | ARCHIVED; superseded |
| [Earnings addendum](Grok_Earnings_Overnight_Addendum_2026-10-09.txt) | ARCHIVED; superseded |
| [Shadow-controls addendum](Grok_Shadow_Controls_Addendum_2026-10-09.txt) | ARCHIVED; superseded |

This directory has eight files: one effective TXT prompt, five archived TXT snapshots and two supporting Markdown guides. **Do not append archived addenda.** Their old SHADOW, USD 5,000 and freeze instructions are historical. [Current rules](../CURRENT_RULES.md) replaces them.

Read the [repository](https://github.com/Flateninvest/Active-Trading-OverNight), record the exact commit and compare `canonical_hash(load_policy())` with the private local build. During review use the PR/branch commit: `main` remains old until a separately approved merge. Public reading does not grant writing, order authority or new permissions.

Supply vendor files, sourced TA/quotes, authenticated DEMO snapshots, final fills/fees and persistence privately outside Git. Never put keys in a prompt. Follow [setup](GROK_SETUP.md) and [alignment acceptance](../docs/DEMO_ALIGNMENT_2026-10-10.md). Text alone does not install or schedule a bot.
