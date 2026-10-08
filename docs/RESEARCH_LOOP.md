# Workshop research loop

The second workshop slide adds **Hypothesis -> Build -> Ablate -> Hold out -> Verify**, with a full trial log, owner-signed preregistration and reporting last. These are research requirements, not a new trading mandate.

## Current implementation

The [offline protocol module](../src/active_trading/research/protocol.py) and [command-line helper](../scripts/research_loop.py) check plans, comparisons, trial records, holdout approval metadata and reproduction artifacts. They do not supply the daily market-data pipeline, backtester, agent orchestration, cryptographic owner authentication or protected holdout storage. The weekly engine remains a separate comparison.

The [shared strategy specification](../spec/strategy_spec.provisional.json) records the policy. The [research plan template](../spec/research_plan.template.json) is deliberately unapproved and incomplete. Actual dates/year, identities, evaluation choices and owner approval must be supplied before a genuine holdout can pass.

## Required steps

| Step | Required evidence | Stop when |
| --- | --- | --- |
| You: Hypothesis | One falsifiable sentence, economic mechanism, net outcome and suitable comparator | Hypothesis or acceptance criterion is missing |
| Agent: Build | Frozen point-in-time inputs/configuration, committed code, costs from the first run, every attempt logged | Hashes, source availability, costs or execution evidence are missing |
| Agent: Ablate | One predeclared change against the recorded parent on the same opportunities and cost assumptions | More than one factor or the wrong comparator changes |
| Agent: Hold out | Chronological walk-forward protocol, disclosed year and a future extension | Data were previously viewed, dates overlap or preregistration is unapproved |
| You: Verify | Actual committed source, frozen input/configuration hashes, fresh regenerated artifacts and headline agreement | Reproduction, owner verification or artifact comparison is incomplete |
| Agent: Report last | Only accepted regenerated figures, full trial count and limitations | An unverified headline is presented as an accepted result |

Draft hypothesis for owner review: previous-session directional flow, corroborated by Hidden Angles, research and TA, selects positions with positive average net overnight sleeve returns above an exposure-matched SPY comparator because information-driven repricing persists overnight. This is unproven. SPY is a research benchmark; the stock-only trading universe is unchanged.

## Trial accounting and comparisons

Start a uniquely identified trial before execution. Preserve successful, failed, rejected, abandoned and unviewed attempts. Append outcomes and linked corrections instead of overwriting records. An unfinished trial remains visible and counted. Use the full attempt count when discussing searches and selection bias.

The local ledger uses chained content hashes and a write lock to detect modifications, broken chains and conflicting writes. A trusted tail hash stored separately helps detect truncation. This is not tamper-proof storage: someone controlling the files and anchor can rewrite them, and code run outside the harness can evade logging.

For an ablation, freeze the parent comparator, dataset, eligibility/calendar, budget, costs and evaluation definitions; alter one declared setting. Retain common opportunities, cash and missed outcomes even if the tested component changes selected stocks. Predeclare a broader search separately. Do not mix daily, weekly and passive results or compare different exposure/time budgets as though the signal were the only change.

Define applicable costs and their basis, including spread conventions and missed fills. Unknown costs block a net-performance claim. The protocol checks declarations; it does not calculate actual broker costs or validate a fill model. Quotes or OHLC touches alone cannot establish passive fills.

## Preregistration and holdout custody

The owner approves the exact plan, code, configuration and dataset identities before first holdout access. The plan includes training/validation/holdout boundaries, chronological folds, selected variant, costs/comparator, metrics, sample/failure rules and prospective extension beyond development data. Do not guess the workshop's disclosed year.

A local approval string is not an authenticated signature. Genuine use needs an externally controlled owner verifier and preserved approval receipt. The module checks that verifier's outcome and matching identities/timestamps; it does not provide the verifier's trust mechanism. Synthetic approval is valid only for a synthetic demonstration.

True secrecy requires separately protected data storage and an owner or custodian controlling release. The library cannot stop direct file access. A seen or leaked holdout is no longer fresh; disclose it and use an untouched prospective period under a new preregistration. A GitHub merge, passing tests or this prompt update does not sign a research plan or release data.

## Reproduce before reporting

Verify actual local bytes of configuration, datasets, original results and regenerated results. Regeneration must use recorded committed source and prescribed inputs; agreement within a predeclared tolerance does not excuse changed inputs. Record the command, output identities and external verification evidence. The report gate checks supplied artifacts and verification evidence rather than running a full strategy backtest for you.

Reports may explain incomplete or failed work. Accepted performance headlines require fresh reproduction and must retain losses, costs, cash nights, unresolved states, all variants and uncertainty. Several stocks on one night are not independent overnight samples. Missing or insufficient data means inconclusive evidence, not profitability.

## Run the available checks

From the repository root with Python 3.12:

```sh
python scripts/research_loop.py validate --plan spec/research_plan.template.json
```

The unfilled template is expected to be refused. To exercise the protocol with invented data only:

```sh
python scripts/research_loop.py demo --output .runtime/research-loop-demo
python -m unittest discover -s tests -p "test_research_protocol.py"
python scripts/validate_portable.py
```

The demonstration establishes protocol behavior, not economic returns. The portable runner also retains the weekly synthetic checks. See [validation](VALIDATION.md), [the current Grok prompt](../prompts/Grok_Overnight_Stock_Bot_Prompt_Current.txt) and [implementation work still needed](IMPLEMENTATION_PLAN.md).
