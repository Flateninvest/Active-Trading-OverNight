# Implementation status and next work

## Available

- Current daily flow/research plus earnings strategy, workshop four-component instructions and updated complete Grok prompt.
- Offline earnings release/session mapping, prepared-packet guards and bounded conviction allocation with synthetic tests and CLI. No broker writes.
- Effective owner DEMO parameters in the provisional shared specification; private operator/account configuration and genuine research signature remain separate.
- Portable weekly paper engine with ingestion, source cutoffs, sizing, calendar, persistent state, reconciliation and evaluation.
- Synthetic tests/demonstration and GitHub review workflow.
- Offline plan/ablation checks, append-only trial ledger, externally verified approval/reproduction gates and a synthetic protocol demonstration; see [research loop](RESEARCH_LOOP.md).
- Offline HMAC-bound [double-review gates](DOUBLE_REVIEW.md), durable [DEMO/SHADOW order/position memory](ORDER_MEMORY.md) and normalized-fill [trade accounting](TRADE_ACCOUNTING.md). Read their limits and [integration guide](SHADOW_CONTROLS.md); these are local helpers, not a deployed trading bot.

## Not implemented or not verified

1. Daily selection plus TA pipeline and four-component orchestration, including arbitrary earnings PDF ingestion, independent issuer/calendar verification and final-review snapshot production. The offline earnings helper consumes supplied normalized facts/verdicts; it does not implement these producers.
2. OS/service-enforced analyst/reviewer separation, trusted snapshot producers and capital-approval infrastructure for that runtime. Reviewer attestations protect the supplied context only when keys and verification are controlled independently.
3. Complete prospective source archive and reliable authenticated quote/account snapshot producer.
4. Repository broker writer, authenticated fill/cancel feed and deployed next-opening scheduling. Passive execution is disabled under the reported interface. Grok reports a separate local build; its actual implementation remains uninspected here. The offline ledger preserves the obligation; it does not execute it.
5. Deployed schedules and alert delivery. Owner DEMO allocation/loss/drawdown settings are recorded; private operator and credential integration still need verification.
6. Live economic evidence, any future supplied interface conformity or calibrated profitability.
7. Complete daily frozen-data backtester, per-instrument historical cost model, required Sharpe/turnover/break-even and deflated-Sharpe calculations, genuine approved holdout plan, externally controlled holdout release/signature verification and actual real-loader one-year continuation.

## Suggested pull requests

1. Research homework: design our own schema/validator using Task 1's required field names. Complete the [homework checklist](HOMEWORK_CHECKLIST_2026-10-09.md) before Session 2 on 15 October; no external template is required. Check separately any later supplied interfaces.
2. Daily research: implement parser/TA arithmetic with reproducible source receipts and daily freeze; test look-ahead and expiry handling.
3. Risk integration: deploy controlled reviewer identity/key separation and authoritative snapshots around the existing offline attestation checks. Keep capital approval separate; test changed evidence and pending exposure.
4. Shadow operations integration: connect normalized facts to the durable ledger, preserve entry cutoffs and opening-exit obligations, and verify restart/unknown-state recovery without broker writes. A future scheduler/adapter needs separate review and authority.
5. Reporting integration: ingest verified fill/fee records into the accounting helper, then reconcile whole-book equity/attribution, cash/missed attempts and exceptions. Generate a clearly labeled tear sheet only from sufficient inputs.
6. Passive execution remains disabled. Do not implement resting-order behavior or spread capture under the owner-reported MIT/close interface.

Each numerical result must trace to committed code, immutable inputs and configuration. Preserve failed trials and all cash/unknown outcomes. Do not enable live operation as a consequence of completing these development tasks.
