# DEMO alignment — 10 October 2026

This update aligns PR #4's repository policy with the owner's stated separate Grok DEMO build. **No merge, broker writer, live trading, publishing feature, new framework or permission was added.** The local Grok build was not provided for inspection; repository changes alone cannot certify its deployment or matching behavior.

## Authority and scope

The owner's 10 October message overrides older instructions: DEMO replaces SHADOW for current operation, USD 10,000 replaces USD 5,000, intake/freeze is 09:00 Paris, DEMO risk-score gating is off and passive execution is disabled. Reported decision times are retained as owner metadata, not invented signatures. The supplied critical review helped identify defects but is not an independently authenticated broker/build audit; the same bot reports operating the local build.

`spec/strategy_spec.provisional.json` is authoritative. `policy_version` changes to OWNER_DEMO_2026-10-10_v1; the strategy ownership ID remains GROK_DAILY_OVERNIGHT_v2. The mandate is a private-configuration template with a policy pointer, not another policy engine or broker credential. Historical prompts/meeting documents retain their dates and do not override the current specification.

## Rules implemented

| Requirement | Enforcement / regression |
| --- | --- |
| Allocation-based caps including pending/costs | Shared `capital_limits`: min(10,000 allocation, account balance). Review, ledger and earnings consume policy weights/count. A USD 9,005 entry with USD 100,000 balance fails; lower balances and changed policy caps are tested. |
| DEMO only, with SHADOW compatibility | DEMO account/environment checks and scoped ledger records; LIVE rejected. Same account/position/reconciliation IDs cannot mix modes/strategies. |
| Risk-score gate off for DEMO | Mode-specific policy switch; real-account score/scope cannot govern. Existing SHADOW fixtures retain their explicit historical gate. |
| Overnight stress / automatic enhanced review | Sourced instrument-bound completed TA and 60 gaps; earnings needs eight confirmed release gaps. Max(2 ATR14/close, absolute gaps), plus round-trip costs, must fit the 0.25% basis budget. Enhanced review uses beta ≥1.5 or ATR/current ask ≥4%. |
| Strategy equity and loss pauses | Bid-marked included positions plus segregated cash; cash-flow-adjusted HWM; 1% nightly/5% drawdown limits and persistent latches. Night identity is calendar-bound. Drawdown resume needs a trusted external owner verifier. |
| Out-of-policy fill recovery | Preserve actual fills and owed exits; logged operator resolution requires distinct operator/reviewer, policy binding and fresh reconciled evidence. Known remaining purchase basis cannot shrink to an obsolete original limit after resolution. |
| Schedule | Review checks the weekday itself. Policy-defined preparation open−5, first attempt not before exchange opening, retry spacing ≥5 seconds with new reconciliation, durable alert at attempt 12. Late recovery remains possible. No scheduler is supplied. |
| External trade accounting | Preview creates no fill. Actual normalized DEMO fills import append-only; charges remain UNKNOWN until complete final evidence. Overrides default to strategy-equity exclusion. |
| One prompt | One effective current TXT; five archived TXT snapshots; two supporting guides. The directory's other seven files are labeled by role, not competing prompts. |
| Tooling hygiene | Strict duplicate-key/nonfinite JSON rejection, ignored validation output, refusal of tracked output paths, committed Git-blob and exact ZIP-byte manifest hashes. |

All dollar limits assume full USD 10,000 basis and scale down if account balance is lower. Stress is not a maximum-loss guarantee. Loss pauses apply to new entries; owned exits remain due. Reported passive/MIT capabilities are owner-provided constraints, not independently retested broker capabilities.

## Private integration contract

- Load trusted policy once through `load_policy`, calculate its canonical hash, and pass that same object to review, earnings and `ShadowLedger(..., policy=policy)`. Do not size from the total demo NAV alone. Legacy account fields named `nav_usd`/`equity_usd` supply account balance to the capital-basis calculation; strategy equity is a separate state.
- DEMO proposals bind the current spec, exact input/code/calendar/frozen-register identities and authenticated reviewer attestation. Round-trip estimates use `costs.coverage: ROUND_TRIP`, known per-instrument source/model hash and `estimated_total_usd`; actual final fees are a different reporting fact.
- `technical_analysis` includes instrument/source/time/session, completed bars, SMA20/50, Wilder RSI14, ATR14, completed close, support/resistance and beta. `stress_sizing` binds instrument/source/as-of/complete history and chronological overnight gaps; earnings includes confirmed release identities/times/sources/gaps. The authenticated producer must establish these are truly the latest complete histories. Row count and a `complete` flag do not authenticate market data.
- `build_strategy_risk_state` consumes fresh DEMO-scoped segregated cash, balance, signed incremental cash flow, exact included/excluded positions and bid marks, plus persisted prior state. `night_id` is the entry-session date; `night_session` supplies that verified calendar session's open/close. Carry the resulting state through restart and opening valuation until the next eligible review boundary. Do not reset losses by changing a label or discarding prior history.
- Persist risk state and freeze/refresh ceilings in the external trusted service. The pure helpers cannot detect an operator replacing their complete history. Owner drawdown-resume and incident-resolution verifiers must be independently controlled, not analyst booleans or always-true callbacks.
- `plan_exit` can prepare at open−5; each DEMO retry requires current complete post-attempt reconciliation and ≥5 seconds spacing. `alert_required` is durable state, not delivered messaging. The external scheduler must make its first request at US 09:30; actual fill time is not guaranteed. Retry/alert failure must not discard an outstanding obligation.
- Use `control_exceptions`/`resolve_exception` following [order memory](ORDER_MEMORY.md); never repair SQLite by hand. Resolution retains incident facts and does not waive remaining cap violations.
- External DEMO importer schema is EXTERNAL_DEMO_TRADE_v1. A new immutable source observation uses a new `source_record_id`; finalization retains the same fill ID. `--previous-packet` preserves earlier receipts/fills/fees; output is a new private file. See [accounting](TRADE_ACCOUNTING.md) and synthetic importer tests for complete examples.

No actual 8 October OKTA fill was fabricated or imported. It remains excluded from strategy equity; authoritative actual fills/fees are required for accounting. Importing a trade does not adopt it into operating ownership or permit closing an unrelated position.

## Local Grok acceptance required

1. Record exact repository commit, local code commit and canonical policy hash; show any local-policy diff. New entries stop if policy differs; preserve owned exits.
2. Run the relevant portable regressions against the exact integrated local source and return actual results. Synthetic tests remain synthetic, never real demo fills.
3. Prove DEMO account scope and existing permissions privately. The review reports broader connection scopes; this update neither verifies nor changes credentials. An operator must establish demo-only dispatch without adding permissions.
4. Show trusted producer provenance, genuine reviewer separation, durable risk-state/freeze/intent continuity, restart recovery, full-position exit scheduling, retry reconciliation and actual alert delivery. The repository has no implementation evidence for those external services.
5. Record acceptance gaps honestly. A downloaded prompt, passing helper tests or a code merge is not proof that Grok's running build adopted these rules.

## Existing test adjustments

All original 284 test cases are retained; none were deleted. Eleven existing tests needed a fixture/assertion update to preserve their original purpose under the owner policy:

| Existing test | Reason |
| --- | --- |
| earnings: `test_shadow_and_product_boundaries_cannot_be_enabled_by_inputs` | Rejection case now uses LIVE; DEMO is supported and separately tested. |
| earnings: `test_pre_freeze_receipt_and_publication_chronology` | Invalid receipt moved one second after the new 09:00 Paris freeze. |
| earnings: `test_wrong_freeze_timezone_or_new_unregistered_event_is_refused` | Expected freeze error now says 09:00. |
| earnings: `test_ordinary_proposal_cannot_exceed_shared_name_cap` | Expected error uses policy-based name-cap terminology. |
| earnings: `test_existing_earnings_held_and_pending_use_sleeve_ceiling` | Split old USD 1,500 name into USD 1,000 + USD 500 names; same sleeve exposure, valid name caps. |
| earnings: `test_ordinary_proposal_uses_same_review_and_gross_slots` | Replace invalid USD 1,500 name with USD 1,000 name plus USD 500 existing cost reserve; original shared-capacity assertion preserved. |
| ledger: `test_cost_reserve_included_in_per_name_cap` | Message assertion allows policy-defined cap. |
| ledger: `test_existing_local_name_above_new_nav_cap_blocks_new_entry` | Message assertion allows policy-defined cap. |
| ledger: `test_existing_snapshot_name_above_cap_blocks_new_entry` | Message assertion allows policy-defined cap. |
| ledger: `test_exit_cannot_be_advanced_by_new_calendar_or_spec` | Preparation may start open−5; actual early attempt still fails. |
| ledger: `test_demo_and_live_modes_rejected` → `test_live_and_mismatched_review_modes_rejected` | DEMO supported; LIVE and mismatched review mode still refused. |

The earnings synthetic fixture's freeze timestamps moved to 09:00 Paris; it remains SHADOW and uses a smaller USD 5,000 account to exercise the lower-balance rule. Software demonstrations are not actual eToro DEMO trades. [Validation](VALIDATION.md) records actual suite counts and committed-source evidence.

## File-by-file change record

The following table identifies every changed/new project file in this alignment. Historical validation evidence remains unchanged. No dependency, workflow permission or broker integration file was added.

| File | Change |
| --- | --- |
| [AGENTS.md](../AGENTS.md) | Coding-agent rules now defer to current DEMO policy, scoped persistence and logged incident resolution. |
| [CHANGELOG.md](../CHANGELOG.md) | Dated scope/authority/change record for this unmerged update. |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | One effective prompt; ignored runner output and explicitly reviewed evidence publication. |
| [CURRENT_RULES.md](../CURRENT_RULES.md) | New current-policy/prompt entry point and exact-commit/hash alignment rule. |
| [README.md](../README.md) | Current DEMO status, strategy-allocation limits, navigation and honest runtime boundaries. |
| [docs/DAILY_STRATEGY.md](DAILY_STRATEGY.md) | Current selection, schedule, capital/stress/loss/marking rules and passive-disabled status. |
| [docs/DEMO_ALIGNMENT_2026-10-10.md](DEMO_ALIGNMENT_2026-10-10.md) | This decision, integration, test-adjustment and file-by-file audit record. |
| [docs/DOUBLE_REVIEW.md](DOUBLE_REVIEW.md) | DEMO/stress/loss gates and score-switch documentation, retaining reviewer-trust boundaries. |
| [docs/EARNINGS_STRATEGY.md](EARNINGS_STRATEGY.md) | 09:00 freeze, shared allocation basis, earnings stress/cost rules and DEMO prepared packets. |
| [docs/FOUR_COMPONENTS.md](FOUR_COMPONENTS.md) | Separate owner DEMO operation from offline services and SHADOW research fixtures. |
| [docs/HOMEWORK_CHECKLIST_2026-10-09.md](HOMEWORK_CHECKLIST_2026-10-09.md) | Current-policy pointer while preserving the dated, incomplete research assessment. |
| [docs/IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Distinguish implemented owner settings from missing external services; passive execution disabled. |
| [docs/ORDER_MEMORY.md](ORDER_MEMORY.md) | Mode/strategy scope, conservative known fill capital, operator procedure, preparation/retries/alert state. |
| [docs/README.md](README.md) | Reviewer navigation and current DEMO/external-build status. |
| [docs/REPOSITORY_MAP.md](REPOSITORY_MAP.md) | Current prompt/archive roles and DEMO/SHADOW helper descriptions; no folder migration. |
| [docs/SHADOW_CONTROLS.md](SHADOW_CONTROLS.md) | Maintained integration guide now points to one prompt and DEMO acceptance; stable filename retained. |
| [docs/TRADE_ACCOUNTING.md](TRADE_ACCOUNTING.md) | External import, unknown/final fees, immutable observations and override exclusion procedure. |
| [docs/VALIDATION.md](VALIDATION.md) | Nonmutating evidence workflow and current versus historical validation distinction. |
| [prompts/GROK_SETUP.md](../prompts/GROK_SETUP.md) | Local-build hash/capability/producer/continuity acceptance checklist, not a competing prompt. |
| [prompts/Grok_Active_Trading_Workshop_Addendum_2026-10-08.txt](../prompts/Grok_Active_Trading_Workshop_Addendum_2026-10-08.txt) | ARCHIVED header added; original snapshot preserved below it and no longer effective. |
| [prompts/Grok_Earnings_Overnight_Addendum_2026-10-09.txt](../prompts/Grok_Earnings_Overnight_Addendum_2026-10-09.txt) | ARCHIVED header added; original snapshot preserved below it and no longer effective. |
| [prompts/Grok_Overnight_Stock_Bot_Prompt_Current.txt](../prompts/Grok_Overnight_Stock_Bot_Prompt_Current.txt) | Replaces appended conflicting instructions with one current policy-led DEMO prompt. |
| [prompts/Grok_Overnight_Stock_Bot_Prompt_Workshop_2026-10-08.txt](../prompts/Grok_Overnight_Stock_Bot_Prompt_Workshop_2026-10-08.txt) | ARCHIVED header added; original snapshot preserved below it and no longer effective. |
| [prompts/Grok_Research_Loop_Addendum_2026-10-08.txt](../prompts/Grok_Research_Loop_Addendum_2026-10-08.txt) | ARCHIVED header added; original snapshot preserved below it and no longer effective. |
| [prompts/Grok_Shadow_Controls_Addendum_2026-10-09.txt](../prompts/Grok_Shadow_Controls_Addendum_2026-10-09.txt) | ARCHIVED header added; original snapshot preserved below it and no longer effective. |
| [prompts/README.md](../prompts/README.md) | Explicit inventory: one effective prompt, five archived snapshots and two guides. |
| [scripts/earnings_plan.py](../scripts/earnings_plan.py) | Shared strict JSON loader; normalized private-input behavior retained. |
| [scripts/package_review_pack.py](../scripts/package_review_pack.py) | New review packager using exact committed Git blob hashes and exact ZIP payload hashes. |
| [scripts/research_loop.py](../scripts/research_loop.py) | Strict JSON for research plans rather than permissive duplicate-key parsing. |
| [scripts/shadow_workflow.py](../scripts/shadow_workflow.py) | Strict JSON decode/load for synthetic integration; remains fictional SHADOW. |
| [scripts/trade_report.py](../scripts/trade_report.py) | External DEMO import/append CLI with private new outputs and no raw-value error leaks. |
| [scripts/validate_portable.py](../scripts/validate_portable.py) | Ignored output by default, tracked/existing/Git-metadata output refusal, strict config reads and new suites. |
| [spec/README.md](../spec/README.md) | Single policy authority, current DEMO configuration and separate unsigned homework requirements. |
| [spec/operating_mandate.template.json](../spec/operating_mandate.template.json) | Owner DEMO template and explicit policy pointer; private identities/approvals remain unset. |
| [spec/strategy_spec.provisional.json](../spec/strategy_spec.provisional.json) | Effective owner decisions and policy switches; no live writer/publishing/permission enabled. |
| [src/active_trading/earnings.py](../src/active_trading/earnings.py) | Policy-based DEMO sizing, scoped risk state, automatic enhanced review and earnings round-trip stress/cost reservations. |
| [src/active_trading/jsonio.py](../src/active_trading/jsonio.py) | New recursive duplicate-key and nonfinite-number rejection with UTF-8/BOM support. |
| [src/active_trading/operations/__init__.py](../src/active_trading/operations/__init__.py) | Package description now reflects DEMO/SHADOW support; API name compatibility retained. |
| [src/active_trading/operations/ledger.py](../src/active_trading/operations/ledger.py) | Policy caps, DEMO-scoped persistence, actual known purchase basis, logged incident resolution, preparation/retries/alerts and strategy-scoped reconciliation events. |
| [src/active_trading/policy.py](../src/active_trading/policy.py) | New strict policy loader and shared Decimal allocation-based limit calculator. |
| [src/active_trading/reporting/__init__.py](../src/active_trading/reporting/__init__.py) | Exports external DEMO importer/report helper. |
| [src/active_trading/reporting/accounting.py](../src/active_trading/reporting/accounting.py) | Validates and preserves strategy-equity inclusion/exclusion metadata. |
| [src/active_trading/reporting/imports.py](../src/active_trading/reporting/imports.py) | New append-only external DEMO preview/final normalization with unknown fees, immutable identities and source hashes. |
| [src/active_trading/research/protocol.py](../src/active_trading/research/protocol.py) | Strict JSON in plan/artifact and append-only research-ledger reads. |
| [src/active_trading/risk/equity.py](../src/active_trading/risk/equity.py) | New bid-marked segregated equity, cash-flow-adjusted HWM and calendar-bound persistent pause state. |
| [src/active_trading/risk/review.py](../src/active_trading/risk/review.py) | DEMO and allocation/score/weekday/official-reference/TA/stress/loss gates; exact review binding retained. |
| [tests/test_demo_imports.py](../tests/test_demo_imports.py) | New preview/final/unknown-fee, provenance/replay, scope, exclusion and private-CLI regressions. |
| [tests/test_demo_ledger.py](../tests/test_demo_ledger.py) | New DEMO scope, caps, incident resolution, known purchase basis, preparation/retries/alert and reconciliation-scope regressions. |
| [tests/test_demo_risk.py](../tests/test_demo_risk.py) | New allocation, DEMO, score-switch, TA/stress, equity/cash-flow and pause/resume regressions. |
| [tests/test_earnings.py](../tests/test_earnings.py) | Retains 54 tests (six updated fixtures/assertions) and adds 10 DEMO regressions. |
| [tests/test_operations_ledger.py](../tests/test_operations_ledger.py) | Retains 62 tests (five updated assertions/semantics); no test deleted. |
| [tests/test_tooling_hygiene.py](../tests/test_tooling_hygiene.py) | New strict JSON, safe runner output, LF/CRLF manifest and single-effective-prompt regressions. |

## Remaining limits

No validated profitability or optimal timing is claimed. Actual daily historical research, required economic figures, real-loader continuation, untouched holdout custody/signature and exact capstone deadline remain separate work. The updated offline helpers do not authenticate supplied market/broker data, run agents, dispatch orders, deliver alerts or prove local runtime deployment. Owner-selected risk numbers are recorded policy, not invented JPMorgan/Goldman or statistically optimized defaults.
