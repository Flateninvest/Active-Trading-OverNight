# Prompt guide

These instructions describe the selected daily overnight strategy and the workshop's four-component approach. Uploading a prompt does not create a running bot or enable trading.

| File | Use |
| --- | --- |
| [Complete workshop prompt](Grok_Overnight_Stock_Bot_Prompt_Workshop_2026-10-08.txt) | Start or replace the bot's operating instructions |
| [Workshop addendum](Grok_Active_Trading_Workshop_Addendum_2026-10-08.txt) | Update an older prompt that does not contain the workshop additions |
| [Grok setup](GROK_SETUP.md) | Check parsing, data, persistence and stage capabilities before a shadow exercise |

**The complete workshop prompt already includes the addendum. Do not append it a second time.** Read the complete prompt when reviewing the effective instructions; the addendum alone is not the full strategy.

## Updating instructions

- Keep the [daily strategy](../docs/DAILY_STRATEGY.md), [provisional specification](../spec/strategy_spec.provisional.json) and effective complete prompt consistent in the same pull request.
- State rule changes, version/date, information cutoff and validation evidence. A rewritten prompt does not approve a changed trading mandate.
- When replacing dated files, retain previous versions as clearly labeled history and update this guide and the root links to the effective version.
- If maintaining a standalone addendum, keep it consistent with its included section in the complete prompt.
- Supply actual flow, Hidden Angles and research files privately under the [data policy](../docs/DATA_POLICY.md).

Default mode remains SHADOW. The integrated daily runtime and independently enforced four-component boundaries remain implementation work; the retained weekly engine is a separate paper comparison.

See the [reviewer guide](../docs/README.md), [specification guide](../spec/README.md) and [contribution guide](../CONTRIBUTING.md) for the wider context.
