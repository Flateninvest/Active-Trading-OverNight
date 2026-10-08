# Four components and one shared specification

The workshop slide specifies four components that read one specification. It states that the reference repository fixes the specification schema, positions file and log format. That repository is not available here; our formats remain provisional.

| Component | Responsibility | Boundary |
| --- | --- | --- |
| S1 Research | Draft specification; interpret sources; regenerate derived figures from committed code; preserve every trial | No broker writes or self-approved rule changes |
| S2 Risk | Read exact specification, proposal and reconciled positions; run deterministic policy checks and adversarial tests | No limit changes; PASS is not execution approval |
| S3 Operations | Propose entries/owned exits; stop at approval; reconcile, monitor and log | Shadow performs no order writes; protect unrelated holdings |
| S4 Reporting | Measure compliance, reconcile attribution and produce tear sheet/copier-note draft | No public posting or invented target ranges |

One bot can orchestrate four stages, but names/prompts do not provide independent review or credential isolation. Enforce stage permissions and report the actual review boundary.

## Shared contract

Every run records specification version/hash, code commit, input hashes, actual receipt/publication/observation times and decision IDs. Changes to the approved specification invalidate pending proposal reviews. Existing exit obligations remain tied to their owned position and effective mandate.

S1 drafts a proposal; S2 reviews that exact proposal; approval is bound to action, account, position/instrument, quantity, order type, price bounds and validity window. S3 records outcomes and reconciles before retries. S4 reads the same ledger and never rewrites its history.

Approval records from synthetic fixtures must say SIMULATED_APPROVAL. A shadow stack must not submit real or demo broker orders. Broker execution, scheduler deployment and public posting need separately authorised capabilities and mandate.

## Reference mapping still needed

The [research loop](RESEARCH_LOOP.md) adds mandatory experimental checks. S1 maintains the hypothesis, frozen plan and full trial log; S2 challenges leakage, cost/comparator fairness, one-change ablations and approval/reproduction evidence; S3 retains SHADOW permissions; S4 writes accepted performance prose only after fresh verification. Owner approval before holdout access is separate from code-review merges and from transaction approval.

Obtain the workshop repository URL and commit. Compare field names/types and run its actual validators against our specification, positions and log examples. Do not claim compatibility from a guessed schema.

The mid-November capstone calls for the stack in shadow, its governing mandate and reporting tear sheet. Confirm the exact deadline with the organisers. The current upload supplies instructions/contracts plus a runnable weekly comparison; it does not claim the entire daily stack is implemented.
