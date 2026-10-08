# Prompt guide

These instructions describe the selected daily overnight strategy and the workshop's four-component approach. Uploading a prompt does not create a running bot or enable trading.

| File | Use |
| --- | --- |
| [Current complete prompt](Grok_Overnight_Stock_Bot_Prompt_Current.txt) | Effective instructions, including both workshop addenda and the mandatory research loop |
| [Research-loop addendum](Grok_Research_Loop_Addendum_2026-10-08.txt) | Update an existing bot with Hypothesis/Build/Ablate/Hold out/Verify and report-last requirements |
| [Archived workshop prompt](Grok_Overnight_Stock_Bot_Prompt_Workshop_2026-10-08.txt) | Earlier 8 October snapshot; lacks the new research-loop addition |
| [Four-component addendum](Grok_Active_Trading_Workshop_Addendum_2026-10-08.txt) | Update an older prompt with the S1-S4 architecture |
| [Grok setup](GROK_SETUP.md) | Check parsing, data, persistence and stage capabilities before a shadow exercise |

**The current complete prompt already includes both addenda. Do not append either a second time.** Read the complete current prompt when reviewing effective instructions; an addendum alone is not the full strategy. The old dated workshop snapshot remains unchanged as history.

For a bot that can read URLs, use the [plain-text current prompt](https://raw.githubusercontent.com/Flateninvest/Active-Trading-OverNight/main/prompts/Grok_Overnight_Stock_Bot_Prompt_Current.txt). Record the exact commit used; `main` changes as the project develops. If URL reading is unavailable, download and supply the file. A public URL grants reading, not GitHub write or trading permissions.

## Updating instructions

- Keep the [daily strategy](../docs/DAILY_STRATEGY.md), [provisional specification](../spec/strategy_spec.provisional.json) and effective complete prompt consistent in the same pull request.
- State rule changes, version/date, information cutoff and validation evidence. A rewritten prompt does not approve a changed trading mandate.
- When replacing dated files, retain previous versions as clearly labeled history and update this guide and the root links to the effective version.
- If maintaining a standalone addendum, keep it consistent with its included section in the complete prompt.
- Supply actual flow, Hidden Angles and research files privately under the [data policy](../docs/DATA_POLICY.md).
- Follow the [research-loop protocol](../docs/RESEARCH_LOOP.md): log every attempt, obtain actual owner preregistration before holdout access and regenerate artifacts before accepted numerical reporting. Do not invent a signature or disclosed year.

Default mode remains SHADOW. The integrated daily runtime and independently enforced four-component boundaries remain implementation work; the retained weekly engine is a separate paper comparison.

See the [reviewer guide](../docs/README.md), [specification guide](../spec/README.md) and [contribution guide](../CONTRIBUTING.md) for the wider context.
