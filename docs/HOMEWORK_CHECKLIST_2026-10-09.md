# Research-agent homework checklist

**Due before Session 2, Thursday 15 October 2026. Demo: five minutes.**

This audit uses the participant-supplied Research Agent Task brief. The internal source sheet and private research inputs are not redistributed. Status is based on the repository evidence reviewed on 9 October, including the three new offline operating improvements and their synthetic checks.

**Assessment: useful foundations exist, but the daily research homework is not ready for sign-off.** We have the intended strategy, agent instructions, offline research guards and portable synthetic checks. We do not yet have the complete daily study, required statistical outputs, a passing continuation through the daily pipeline or an owner-signed research specification. The weekly comparison is separate evidence.

For this task we design our own JSON or YAML specification and validator. An external reference repository is **not** a prerequisite. Keep these exact minimum field names: `hypothesis`, `universe`, `signal`, `holding`, `costs`, `expected`, `kill`, `trials`, `signed`.

## The four deliverables

| Deliverable | Existing foundation | What remains before it passes |
| --- | --- | --- |
| 1. Machine-readable strategy specification | [Current strategy contract](../spec/strategy_spec.provisional.json), [draft research plan](../spec/research_plan.template.json), [daily strategy](DAILY_STRATEGY.md) and separate [earnings rules](EARNINGS_STRATEGY.md) | Create and validate the homework contract with every minimum field. Derive expected **ranges** for net Sharpe, turnover and break-even cost from the actual study. Include trial count, effective count and deflated Sharpe; an owner-selected non-overridable kill rule; and a genuine signature before first holdout access. Current draft is unsigned and incomplete. |
| 2. Research instructions and executable harness | [Research loop](RESEARCH_LOOP.md), [protocol module](../src/active_trading/research/protocol.py), [CLI](../scripts/research_loop.py), [current Grok prompt](../prompts/Grok_Overnight_Stock_Bot_Prompt_Current.txt) and pinned direct dependencies | Connect frozen daily inputs to the actual daily strategy engine. Lock costs, universe and dates across each ablation table; enforce one actual setting change. Print gross/net Sharpe, turnover and break-even cost on every run. A clean-checkout command must regenerate **all homework figures**, not merely pass synthetic tests. |
| 3. Complete trial log | Protocol reserves attempts before execution, retains failed/unviewed attempts, checks hash chains and counts planned trials | Connect all actual daily experiments to the ledger. Store per-run baseline identity, change, evaluation period and required metrics; derive effective count and deflated Sharpe reproducibly. Export the hand-in view without deleting failures. No genuine completed daily study log is currently demonstrated. |
| 4. Passing continuation test | Future extension is represented in protocol metadata | Add one plausible year to the actual daily data panel, including a delisting and a halted name. Use the real loader and pipeline, assert new-period output, and make the test mandatory before sign-off. Metadata and invented-return fixtures do not satisfy this test. |

## The eleven submission checks

Unchecked means the full submission condition has not been verified; a foundation is not a completed deliverable.

| # | Submission check | Status and evidence needed |
| --- | --- | --- |
| 1 | Complete specification passes its own validator | **Gap.** Existing JSON parses and plan validation exists, but the homework contract and exact required fields are incomplete. |
| 2 | Expected Sharpe, turnover and break-even cost are ranges | **Gap.** Produce the metrics first; owner sets defensible ranges. Do not invent favourable values. |
| 3 | At least one kill criterion the owner will not override | **Owner decision pending.** A draft falsifier exists. Select a precise trigger, sample requirement and treatment of inconclusive evidence. |
| 4 | One clean-checkout command regenerates every specification number | **Partial.** `python scripts/validate_portable.py` checks software and synthetic demonstrations. It is not the complete daily economic rebuild. |
| 5 | Full trial count and deflated Sharpe match specification and log | **Partial.** Full-attempt accounting is implemented. Effective count and deflated Sharpe computation plus genuine daily results remain absent. |
| 6 | Every ablation changes exactly one setting against its baseline | **Partial.** Metadata checks and tests exist. Actual daily configuration diffs, locked context and generated ablation output still need end-to-end evidence. |
| 7 | Costs are instrument-specific; missing applicable fees stop the run | **Partial.** Unknown declared costs are rejected, but the current plan uses declared basis-point fields rather than an integrated per-instrument historical model. Use read-only SDK facts where available or explicit documented assumptions; never silently substitute zero. |
| 8 | Continuation passes with a delisting and halt in the added year | **Gap.** The daily pipeline continuation test has not been implemented or run. |
| 9 | Owner checks narrative against regenerated results | **Owner verification pending.** Report-last guards exist. No completed daily result table or owner verification receipt is established. |
| 10 | Owner signs before held-out data are first opened | **Pending; leave unsigned.** Real periods, protected holdout custody and approval receipt remain unset. Synthetic approval is not a signature. Do not open a genuine holdout for this audit. |
| 11 | Repository is shared with the programme contact and demo fits five minutes | **Pending.** The repository is shareable and [a rehearsal outline](FIVE_MINUTE_DEMO.md) is available. Sending the link and timed rehearsal have not been recorded. |

## The most important work before Thursday

1. **Freeze the research contract.** Owner confirms the intended daily strategy, falsifiable hypothesis, comparator, universe, input availability, eligible dates and untouched holdout period. Evaluate ordinary flow and earnings separately; a combined book needs its own predeclared treatment.
2. **Secure enough point-in-time data and instrument costs.** Preserve actual source availability, corporate actions, delistings, halts and executable price/cost conventions. Missing historical flow is missing evidence, not zero flow. The intended book is long cash/X1; state that shorts, leverage and CFDs are disabled. If a future comparison enables them, model those instruments as CFDs with applicable financing rather than borrowing the cash-share costs. Disclose access limitations early to the programme team.
3. **Build the daily research harness.** Run the frozen baseline and predeclared single-setting ablations, log every attempt and calculate required statistics, uncertainty and trial adjustments. Keep costs/universe/dates fixed within an ablation table.
4. **Run continuation and reproduce.** Test the added year through the real loader, then rebuild all figures from a clean checkout. Owner reads the results and narrative before selecting ranges and signing.
5. **Only after genuine signature, open the untouched holdout once.** Report its result even if disappointing. Rehearse five minutes and have the owner send the repository link before Session 2.

Suggested order: 9-10 October contract/data/baseline; 11-12 October ablations; 13 October metrics and continuation; 14 October owner reproduction, signature and rehearsal. These are targets, not completed milestones.

## How the three operating improvements help

These improvements are **implemented as offline shadow components and covered by portable synthetic checks**. See [validation](VALIDATION.md) for the actual source commit and counts. They support the wider project; they do not replace Task 1's research evidence or constitute a deployed bot.

| Improvement | Useful contribution | Does not by itself establish |
| --- | --- | --- |
| Financial double-check agent | Challenges the exact proposal; deterministic gates can reject unresolved, stale or conflicting review evidence | Independent credentials, a true daily research harness, owner sign-off or a profitable signal |
| True profit, costs and remaining shares | Reconciles fills, explicit charges and unsold quantity; preserves unknown costs and incomplete positions | A calibrated historical per-instrument cost model, strategy Sharpe or deflated Sharpe |
| Order memory and safe next-opening exits | Preserves intent and position ownership across restarts; prevents blind retries and keeps exit obligations visible | A deployed scheduler, broker connectivity, actual fills or fulfilment of the research continuation test |

The programme task is shadow research and builds no order placement. Keep all new work offline with no broker writes. Human capital approval, research signature, software review and model risk PASS are separate decisions.

## Evidence and sharing

- [Validation evidence](VALIDATION.md) and its machine-readable record identify tested source and synthetic scope. Do not count historical weekly checks as validation of the daily study.
- Preserve raw licensed inputs, account details, fills and runtime ledgers privately under the [data policy](DATA_POLICY.md). Commit only safe source, documentation and clearly synthetic examples.
- The repository link is <https://github.com/Flateninvest/Active-Trading-OverNight>. No programme message has been sent by this audit.
