# Implementation status and next work

## Available

- Current daily flow/research plus earnings strategy, workshop four-component instructions and updated complete Grok prompt.
- Offline earnings release/session mapping, prepared-packet guards and bounded conviction allocation with synthetic tests and CLI. No broker writes.
- Provisional shared specification and unapproved mandate template.
- Portable weekly paper engine with ingestion, source cutoffs, sizing, calendar, persistent state, reconciliation and evaluation.
- Synthetic tests/demonstration and GitHub review workflow.
- Offline plan/ablation checks, append-only trial ledger, externally verified approval/reproduction gates and a synthetic protocol demonstration; see [research loop](RESEARCH_LOOP.md).

## Not implemented or not verified

1. Daily selection plus TA pipeline and four-component orchestration using the actual workshop interfaces, including arbitrary earnings PDF ingestion, independent issuer/calendar verification and final-review snapshot production. The offline earnings helper consumes supplied normalized facts/verdicts; it does not implement these producers.
2. Independently enforced risk-review permissions and approval records for that runtime.
3. Complete prospective source archive and reliable authenticated quote/account snapshot producer.
4. Broker writer, resting passive opening/owned-position closing, actual fills/cancel behavior and next-opening exit mechanism.
5. Deployed schedules, alert delivery and approved capital/loss/drawdown/owner settings.
6. Live economic evidence, reference-schema conformity or calibrated profitability.
7. Complete daily frozen-data backtester, genuine approved holdout plan, externally controlled holdout release/signature verification and actual prospective extension.

## Suggested pull requests

1. Reference interfaces: import the official schemas/commit, map fields and validate contracts without changing the strategy.
2. Daily research: implement parser/TA arithmetic with reproducible source receipts and daily freeze; test look-ahead and expiry handling.
3. Risk and approval: bind policy results to exact proposals/specification hashes; test stale approval and pending exposure.
4. Shadow operations: implement durable single-executor intent/position ledger, entry cutoff, scheduled exits and restart/unknown-state recovery.
5. Reporting: reconcile whole-book equity/attribution, cash/missed attempts and exceptions; generate a clearly labeled tear sheet.
6. Passive execution: separate predeclared experiment with verified order support and fill evidence. Keep delayed passive exit disabled until timing policy is approved.

Each numerical result must trace to committed code, immutable inputs and configuration. Preserve failed trials and all cash/unknown outcomes. Do not enable live operation as a consequence of completing these development tasks.
