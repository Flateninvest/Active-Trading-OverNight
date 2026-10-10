# Repository review: homework and three shadow controls

Reviewed 9 October 2026. The change addresses the owner's first three ranked improvements and audits the supplied workshop homework. It does not implement the other seven suggestions, revise the trading thesis or enable orders.

## Organization

- Kept the existing stage layout: `research`, `risk`, `operations`, `reporting`. New daily controls live in their appropriate packages, with tests in the root suite and commands in `scripts`.
- Kept the legacy weekly comparison and historical meeting/prompt snapshots in place. Moving them would add churn without improving this change.
- Linked the homework checklist, five-minute outline, three implementation guides and upload instructions through the root/reviewer/prompt indexes.
- Updated the maintained specification, effective prompt and implementation statuses together. Corrected the obsolete external-template prerequisite: Task 1 uses our own schema and required field names.
- Retained one effective complete Grok prompt plus one standalone update addendum; do not append the same update twice.

## Review findings addressed

- Bound review to exact proposal/context and configured reviewer secret; rejected unsigned, tampered, stale and self-review packets. Physical credential isolation remains a deployment requirement.
- Serialized cash and exposure reservations across local memory and supplied snapshots; prevented repeated use of the same stated cash and double allocation across sleeves.
- Kept a failed/unknown exit blocking new entries even when the local fill ledger appears flat. Required fresh complete reconciliation before exit attempts/retries.
- Aligned Unicode hashing across review and ledger; separated the review window from the close-minus-five entry-attempt window.
- Preserved out-of-policy owned BUY facts and exit obligations as durable incidents, with new entries blocked. No automatic incident clearing or ad hoc mandate exception was introduced.
- Preserved unknown fees, remaining shares, fee correction history and actual-fill spread accounting. Limited position PnL is not a substitute for full-book, FX, dividend or corporate-action accounting.
- A second independent QA pass found contradictory supplied order states that could make an intent retryable. Orders without a recorded attempt and FILLED states without supporting owned fills now trigger a persistent reconciliation incident; rejected evidence cannot be bypassed by catching an error or restarting. Valid cancelled partial attempts and late owned fills retain their existing recovery paths.
- Existing active-book reservations are aggregated by instrument before checking the unchanged per-name cap. A breach blocks new entries without changing owned exit obligations.
- The private report command rejects repeated JSON object keys at every nesting level, preventing a later conflicting field from silently replacing a fee, mode or ownership value.

## Publication and evidence

Only source, authored public-safe documentation/configuration and clearly fictional examples belong in the pull request. The internal homework HTML, vendor workbooks/PDFs, private account/fill details, reviewer secrets and SQLite state are excluded. No broker calls or programme messages are part of this work.

Portable checks include all three controls and a combined fictional restart/partial-exit/accounting exercise. The machine-readable [validation record](portable-check-result.json) identifies the tested committed source; [validation notes](VALIDATION.md) explain its limits. Synthetic outcomes establish software behavior, not profitable trades or a completed daily research homework submission.

Remaining work is listed in [the homework checklist](HOMEWORK_CHECKLIST_2026-10-09.md) and [implementation plan](IMPLEMENTATION_PLAN.md). No further folder reorganization is necessary for this change.

The extra QA pass covers the supplied-input failure paths above; it is not a broker, deployment or financial-performance certification. Exact per-order source authentication and a supported incident-resolution process remain adapter/integration work. The accounting precision limits are not intended for arbitrarily large balances combined with arbitrarily small quantities.
