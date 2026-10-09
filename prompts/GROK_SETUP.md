# Grok workshop setup

Use [the current complete prompt](Grok_Overnight_Stock_Bot_Prompt_Current.txt), plus the actual daily flow, Hidden Angles and research files supplied privately. The workshop, research-loop, earnings and shadow-control addenda are already included; do not append them again. Supply intermittent earnings setup PDFs privately, and read [the earnings workflow](../docs/EARNINGS_STRATEGY.md). Sunday/Monday uploads prepare the watchlist; they do not change entry weekdays. Previous dated standalone prompts are archives.

1. Default to SHADOW. Do not call real or demo order-writing tools.
2. Verify complete worksheet parsing, sourced TA data, timestamped quotes and persistence. State missing capabilities honestly.
3. Use the four components around one effective specification. Read [the new shadow controls](../docs/SHADOW_CONTROLS.md) first. A distinct reviewer identity and HMAC attestation can protect exact-context review when its key is controlled separately; one bot holding both keys remains self-review. OS/service isolation is not deployed here.
4. For Task 1, design our own JSON/YAML schema/validator with the exact homework field names. No external template is required. Use [the homework checklist](../docs/HOMEWORK_CHECKLIST_2026-10-09.md); keep any later shared-interface alignment separate.
5. Reproduce derived figures from committed code and preserved private inputs; keep every trial and exception.
6. Demonstrate the lifecycle without broker writes: intake/freeze, proposal, risk verdict on that exact proposal, labeled approval record, modeled entry/exit and reconciled tear sheet.
7. Keep passive bid/ask execution as a separate experiment. Verify resting open/close support; do not infer fills from quotes or extend the primary opening exit.
8. Only configure routines after the exact owner, timezone/calendar behavior, permissions and missing-input/recovery rules are verified and authorised. This repository does not create them.
9. Apply [the mandatory research loop](../docs/RESEARCH_LOOP.md). Draft the falsifiable hypothesis, freeze data and costs, log every variant, ablate one change, obtain owner-signed preregistration before opening a fresh holdout and regenerate the headline before reporting it. Actual holdout dates/year and approval remain unset.
10. The offline demonstration can be run with `python scripts/research_loop.py demo --output .runtime/research-loop-demo`. It checks metadata/artifact workflow using invented fixtures; it is not a real strategy simulation or authenticated owner approval.
11. Use [double review](../docs/DOUBLE_REVIEW.md), [order memory](../docs/ORDER_MEMORY.md) and [trade accounting](../docs/TRADE_ACCOUNTING.md) only within their stated contracts. Keep keys and SQLite ledgers outside the checkout. Require the gate verifier, reconcile unknown submissions before retry and keep owned opening exits visible after restarts. A proposed exit is not a fill.
12. For reporting, supply normalized private fill/fee records with explicit known/unknown costs. Keep actual DEMO/SHADOW observations separate from hypothetical live-cost scenarios. Actual execution prices already embed spread; do not deduct it again. Unsold units mean the trade is still open.
13. Ask the bot for an integration plan and capability inventory before writing adapters or deploying routines. The supplied local code has no network Grok adapter, broker writer or deployed scheduler. A prompt upload cannot create those capabilities.

Live capital, loss/drawdown limits, ownership IDs, execution capability and permission remain unapproved/unset. A risk PASS, test success or prompt upload is not transaction approval. Do not publish the copier-note draft without permission.
