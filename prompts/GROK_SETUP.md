# Grok DEMO setup and acceptance

Use [the current prompt](Grok_Overnight_Stock_Bot_Prompt_Current.txt), [specification](../spec/strategy_spec.provisional.json) and [current rules](../CURRENT_RULES.md) from one exact reviewed commit. Do not append historical addenda.

1. Inventory actual local source commit, policy hash, parsing/TA/quote/calendar producers, DEMO account scope, reviewer separation, durable state, scheduler and alert delivery. Report missing/unverified capabilities.
2. Compare local policy with the repository policy. Stop new entries on mismatch; preserve owned exits and existing intent/position identities.
3. Validate DEMO-only account and existing permission scope privately. Demo authorization does not authorize REAL, transfers, new credentials or public posting. Never use the real account's risk score.
4. Run supported offline checks. `python scripts/validate_portable.py` writes ignored evidence. `--demo` commands are synthetic SHADOW demonstrations, not eToro DEMO orders.
5. Supply flow, Hidden Angles/research and intermittent earnings PDFs privately with hashes and actual receipt/publication dates. Freeze one combined register at 09:00 Paris; later data removes only.
6. Produce sourced completed-bar TA, last-60-session gaps, eight confirmed release gaps for earnings, official Monday references and round-trip costs. PASS labels do not authenticate facts.
7. Separate analyst/reviewer identities and credentials. Keep service-held keys outside Git and unavailable to the analyst; never use an always-true production verifier.
8. Persist allocation-based reservations, mode-scoped records, remaining owned units and next-opening exits. Follow [order memory](../docs/ORDER_MEMORY.md) and controlled incident resolution.
9. Persist segregated strategy cash, bid marks, flows and pause latches. Drawdown resumption requires externally verified owner review. Exclude the OKTA override from equity.
10. Prepare exits open minus five, first request at US 09:30 open, reconcile before retries, wait at least five seconds and alert after twelve. Verify actual local scheduling/restart/alert evidence; the repository does not deploy these services.
11. Import external DEMO history through accounting. Preview is not a fill; fees remain UNKNOWN until final complete history confirms them. Preserve earlier records and unsold units.
12. Follow [research loop](../docs/RESEARCH_LOOP.md) and [homework checklist](../docs/HOMEWORK_CHECKLIST_2026-10-09.md). DEMO operation does not create a signature, validated edge or completed homework.

Return an acceptance receipt with actual local commit/policy hash, checks/results, policy diff, missing integrations and unchanged owned exit obligations. An uninspected separate build cannot be certified by the repository maintainer. No merge, live activation, public upload or new permission follows from this checklist.
