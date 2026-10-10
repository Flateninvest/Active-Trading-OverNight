# Three useful controls for the Grok workflow

This maintained guide now covers DEMO/SHADOW helpers; its historical filename is retained for stable links. [Current owner policy](../CURRENT_RULES.md) is DEMO with allocation-based caps and loss/stress gates. No broker writer, network Grok adapter or scheduler is supplied; the separate local build is not verified here.

```text
S1: propose with frozen evidence
            |
S2: challenge exact proposal + sign review context
            |
Code: verify review and current context + preserve approval boundary
            |
S3: record scoped DEMO/SHADOW intent, owned fills and due next-opening exit
            |
S4: reconcile fills, costs and unsold shares
```

## What improves

| Control | Why it is useful here | Boundary |
| --- | --- | --- |
| [Financial double check](DOUBLE_REVIEW.md) | A raw PASS previously depended on supplied narrative. Signed review attestations now bind the reviewer, exact proposal, specification and evidence context; missing mandatory checks and enhanced high-beta review cannot be waved away by a score | The analyst must not hold the reviewer key. HMAC validates possession of that secret and bound content, not the truth of TA/news/account facts. Separate service/OS permissions still need deployment |
| [Profit, costs and remaining shares](TRADE_ACCOUNTING.md) | Fill-based arithmetic distinguishes realized profit from unsold exposure and prevents unknown fees from becoming a false net-profit claim | Normalized trusted inputs are required; there is no automatic broker feed, tax/FX/corporate-action engine or full-book valuation service |
| [Order memory and next-opening exits](ORDER_MEMORY.md) | A local SQLite ledger preserves stable intents, partial owned quantities, reservations and exit obligations across restarts. Unknown submission outcomes require reconciliation before retry | The ledger needs its required gate verifier and private persistent storage. It does not send orders, wake itself at the open or verify broker facts independently |

## What to give Grok

1. **The effective instructions:** replace the old operating prompt with [the complete current prompt](../prompts/Grok_Overnight_Stock_Bot_Prompt_Current.txt). It implements the current policy as one set of instructions. All dated addenda are archived; do not append or execute them.
2. **The actual source and rules:** give the bot this [GitHub repository](https://github.com/Flateninvest/Active-Trading-OverNight) and record the exact commit it reads. It should inspect the strategy specification, daily/earnings rules and the three linked implementation guides. If it cannot read URLs, download the current source and these documents and supply them privately. Read access does not grant write/trading authority.
3. **The daily evidence, privately:** options flow, Hidden Angles, research and any earnings sheet, with actual receipt/source dates. The bot must still verify TA, quotes, event timing and account snapshots; attaching files does not verify them.
4. **Reconciliation evidence, privately when available:** normalized fills, charges, owned-position quantities and reliable session information in the formats required by the helpers. Declare absent/unknown facts; do not improvise fill prices, zero fees, signatures or a successful broker response.
5. **For research homework:** [the checklist](HOMEWORK_CHECKLIST_2026-10-09.md), [research loop](RESEARCH_LOOP.md) and [demo outline](FIVE_MINUTE_DEMO.md). We design our own specification/validator. Do not ask Grok to invent expected ranges or sign for the owner.

Never upload reviewer secrets, API tokens, raw private account IDs or SQLite state to GitHub or paste them into the prompt. An independently controlled operator configures the reviewer secret outside Git and keeps it unavailable to the analyst. A chat environment without that separation must disclose self-review.

## First run and acceptance

- Ask Grok to inventory the exact source commit, readable files, executable code, available facts and missing integrations, then propose an integration plan. It must not claim a prompt installed or scheduled anything.
- Run the repository's offline synthetic workflow and portable checks using the commands documented in [validation](VALIDATION.md) and the implementation guides. Record actual command/results and label invented fills/approvals synthetic.
- Verify changed proposals and evidence invalidate old review, unknown submissions are not retried blindly, duplicate/cross-sleeve exposure is refused, partial fills retain ownership and a due exit survives a restart.
- Verify unknown applicable fees leave net P&L unresolved; partial sales retain remaining units; observed demo/shadow costs and hypothetical live costs appear separately. Spread diagnostics never become a second deduction from actual-fill P&L.
- This repository remains offline. Require the separate DEMO build to return the [alignment acceptance evidence](DEMO_ALIGNMENT_2026-10-10.md), including policy hash, trusted producers, reviewer isolation and durable exit/risk continuity. Do not add permissions or deploy a new writer/scheduler from this update.

The Task 1 daily research harness, statistics, real-loader continuation and owner signature remain separate unfinished work. These controls improve process reliability; they do not establish profitability or complete the homework.
