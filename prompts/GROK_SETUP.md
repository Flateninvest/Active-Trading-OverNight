# Grok workshop setup

Use [the current complete prompt](Grok_Overnight_Stock_Bot_Prompt_Current.txt), plus the actual daily flow, Hidden Angles and research files supplied privately. The workshop, research-loop and earnings addenda are already included; do not append them again. Supply intermittent earnings setup PDFs privately, and read [the earnings workflow](../docs/EARNINGS_STRATEGY.md). Sunday/Monday uploads prepare the watchlist; they do not change entry weekdays. The previous dated workshop prompt is an archive.

1. Default to SHADOW. Do not call real or demo order-writing tools.
2. Verify complete worksheet parsing, sourced TA data, timestamped quotes and persistence. State missing capabilities honestly.
3. Implement the four components around one effective specification. One bot's four stages are self-review unless isolation is actually enforced.
4. Obtain the workshop reference repository/commit and validate its schema, positions and log format. Internal files remain provisional meanwhile.
5. Reproduce derived figures from committed code and preserved private inputs; keep every trial and exception.
6. Demonstrate the lifecycle without broker writes: intake/freeze, proposal, risk verdict on that exact proposal, labeled approval record, modeled entry/exit and reconciled tear sheet.
7. Keep passive bid/ask execution as a separate experiment. Verify resting open/close support; do not infer fills from quotes or extend the primary opening exit.
8. Only configure routines after the exact owner, timezone/calendar behavior, permissions and missing-input/recovery rules are verified and authorised. This repository does not create them.
9. Apply [the mandatory research loop](../docs/RESEARCH_LOOP.md). Draft the falsifiable hypothesis, freeze data and costs, log every variant, ablate one change, obtain owner-signed preregistration before opening a fresh holdout and regenerate the headline before reporting it. Actual holdout dates/year and approval remain unset.
10. The offline demonstration can be run with `python scripts/research_loop.py demo --output .runtime/research-loop-demo`. It checks metadata/artifact workflow using invented fixtures; it is not a real strategy simulation or authenticated owner approval.

Live capital, loss/drawdown limits, ownership IDs, execution capability and permission remain unapproved/unset. A risk PASS, test success or prompt upload is not transaction approval. Do not publish the copier-note draft without permission.
