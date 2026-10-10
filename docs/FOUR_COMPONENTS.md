# Four components and one shared specification

The workshop uses four components that read one specification. The detailed Task 1 brief clarifies that we design our own JSON/YAML specification and validator; no template is provided. Keep its minimum field names: `hypothesis`, `universe`, `signal`, `holding`, `costs`, `expected`, `kill`, `trials`, `signed`. Any later shared positions/log interfaces are a separate interoperability matter, not a blocker for this homework.

| Component | Responsibility | Boundary |
| --- | --- | --- |
| S1 Research | Draft specification; interpret sources; regenerate derived figures from committed code; preserve every trial | No broker writes or self-approved rule changes |
| S2 Risk | Read exact specification, proposal and reconciled positions; run deterministic policy checks and adversarial tests | No limit changes; PASS is not execution approval |
| S3 Operations | Propose entries/owned exits; stop at approval; reconcile, monitor and log | Repository helper never dispatches; external DEMO runtime needs verified existing authority; protect unrelated holdings |
| S4 Reporting | Measure compliance, reconcile attribution and produce tear sheet/copier-note draft | No public posting or invented target ranges |

One bot can orchestrate four stages, but names/prompts do not provide independent review or credential isolation. Enforce stage permissions and report the actual review boundary.

The new [double-review helper](DOUBLE_REVIEW.md) verifies an HMAC attestation by a different reviewer identity on the exact proposal and evidence context, including mandatory/enhanced-review checks. The analyst must not possess the reviewer key. This offline mechanism does not deploy separate services or authenticate market facts. The [order-memory helper](ORDER_MEMORY.md) persists separately scoped DEMO/SHADOW intents, owned partial fills and due opening exits. The [accounting helper](TRADE_ACCOUNTING.md) calculates from normalized fills/explicit charges and keeps unknown costs unresolved. None supplies broker access or a running schedule; see [setup and upload guidance](SHADOW_CONTROLS.md).

## Shared contract

Every run records specification version/hash, code commit, input hashes, actual receipt/publication/observation times and decision IDs. Changes to the approved specification invalidate pending proposal reviews. Existing exit obligations remain tied to their owned position and effective mandate.

S1 drafts a proposal; S2 reviews that exact proposal; approval is bound to action, account, position/instrument, quantity, order type, price bounds and validity window. S3 records outcomes and reconciles before retries. S4 reads the same ledger and never rewrites its history.

Approval records from synthetic fixtures must say SIMULATED_APPROVAL. Synthetic SHADOW exercises never submit orders. The owner has selected DEMO for the separate local build; this repository supplies no writer or scheduler. LIVE and public posting remain disabled. Verify exact DEMO account scope, existing authority and policy identity; see [current rules](../CURRENT_RULES.md).

## Earnings responsibilities

The [earnings sleeve](EARNINGS_STRATEGY.md) uses these same four stages. S1 keeps the private future-event watchlist and confirms results release separately from the call. S2 challenges final TA, event timing, earnings gaps and shared-book allocations; volatile names require enhanced review. S3 preserves the next-opening owned-position exit and cannot duplicate exposure across sleeves. S4 reports earnings separately while reconciling the combined book. One shared specification and common approval boundaries still apply.

## Research homework and future interface alignment

The [research loop](RESEARCH_LOOP.md) adds mandatory experimental checks. S1 maintains the hypothesis, frozen plan and full trial log; S2 challenges leakage, cost/comparator fairness, one-change ablations and approval/reproduction evidence; S3 uses the current DEMO owner policy in its separate runtime; research fixtures remain SHADOW; S4 writes accepted performance prose only after fresh verification. Owner approval before holdout access is separate from code-review merges and from transaction approval.

Task 1 requires a locally validated complete specification, reproducible daily harness, full trial log and a real-loader one-year continuation with a delisting and a halt. The [checklist](HOMEWORK_CHECKLIST_2026-10-09.md) records remaining gaps. Existing guards and new operating helpers do not satisfy these economic-research deliverables by themselves. Leave expected ranges, genuine trial statistics and signature unclaimed until produced and verified. If later organisers supply shared interfaces, record their exact version and validate interoperability then.

The mid-November capstone calls for the stack in shadow, its governing mandate and reporting tear sheet. Confirm the exact deadline with the organisers. The current upload supplies instructions/contracts plus a runnable weekly comparison; it does not claim the entire daily stack is implemented.
