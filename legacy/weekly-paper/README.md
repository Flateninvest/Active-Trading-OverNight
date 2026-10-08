# Retained weekly paper comparison

This folder contains the existing WEEKLY implementation. The current intended DAILY design is documented at the repository root and is not implemented by this engine. No live writer is supplied.

Private datasets, vendor workbooks and prior results are omitted from this GitHub copy. For a data-free demonstration and tests, run `python scripts/validate_portable.py` from the repository root. The archived instructions below describe the original local package, including inputs not distributed here; follow them only when those inputs are supplied privately.

## Archived local package instructions

Sondre Flateraaker · Flaten · Revision 12 · 7 October 2026.

Python 3.12 is the tested runtime. The original Revision 11 modules and historical results are retained. Its original guide is `README_Rev11.md`. The new entry point is `weekly_strategy.cli`; `run.py` rebuilds the original comparison, not the weekly strategy.

## Install and demonstrate

From this `evaluation_repository` folder, create a virtual environment and install the pinned direct dependencies. On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-rev12.txt
.venv\Scripts\python.exe -m weekly_strategy.cli demo
```

On macOS/Linux use `python3.12 -m venv .venv`, then `.venv/bin/python` in the same commands. Installation requires internet access once. No credentials or paid data subscription are needed for the demonstration. The snippets below use `python`; substitute the environment's Python executable if it is not activated.

The single `demo` command runs three separately identified, persistent paper ledgers: flow plus research with opening exit A; flow-only with exit A; and flow plus research with pre-open exit B. It writes `results/rev12_demo/`. All prices, theses, risk facts, fill outcomes and SPY returns in that demonstration are **SYNTHETIC_OPERATIONAL_FIXTURE**, not historical returns or recommendations. Repeating the command reuses stable order IDs and state; a separate `--output` folder creates a new demonstration. Do not mix configurations or changed weekly packets in a state database.

Run all numerical and operational tests:

```powershell
python scripts/validate.py
```

The runner uses a workspace temporary folder, prints real results and saves `results/rev12_validation/Test_Result.json`. The package-level independent checks can be run with `python ../validation/Broker_State_Adversarial_Audit.py`.

## Inspect the actual supplied files

```powershell
python -m weekly_strategy.selection
```

This reads the supplied `data/rev12/raw/flow-135.xlsx` and Hidden Angles workbook, preserves row identities and produces the source audit plus separate Monday-cutoff and later-rehearsal diagnostics in `data/rev12/audit/`. Re-ingestion records its new actual ingestion time. Preserve each week's raw files and decision outputs in a newly dated folder; do not overwrite earlier receipt evidence.

The Monday October 5 diagnostic is not a verified Tuesday-morning selection: the supplied files were inspected October 7, and prior receipt times are unknown. The October 7 rehearsal can use completed October 6 data only after its actual observed cutoff. Neither output is a price backtest. Current numerical candidates are unaccepted pending original-source research review, exact stock/broker identity and daily gates.

Use `WEEKLY_RESEARCH_PROMPT.md` with a research AI. Return source references, contrary evidence, dated support and invalidation conditions rather than a profit probability. `AGENTS.md` tells Claude Code or an equivalent coding agent how to operate this repository. A structured packet is the handoff to deterministic code; a chat answer is not a running broker service.

The supplied `data/rev12/audit/Thesis_Review_Template.json` and `Source_Receipt_Template.json` are practical pending handoff examples. Their false/null values deliberately keep candidates unaccepted. For a future freeze, provide `--thesis-reviews`, `--availability`, `--selection-date YYYY-MM-DD` and `--cutoff` with an explicit timezone-aware timestamp to `python -m weekly_strategy.selection`; choose `--protocol Monday_cutoff`. Receipt evidence must match the exact snapshot hash. An accepted thesis requires the original-source references, their availability, a reviewed-at timestamp, reviewer, supporting row IDs and explicit invalidation. A review is the operator/AI's recorded evidence assessment, not an independent fact-check performed by the parser. See `ENGINE_OPERATIONS.md` for the engine contract.

## Daily market input and execution boundary

`weekly_strategy/fixtures.py` and the generated `synthetic_selection.json` / `synthetic_market.json` are exact runnable examples. `schemas/` describes the input contracts. These schemas are interface documentation; the engine's explicit validation and gate checks determine behavior. Do not set verification booleans merely to make a candidate pass.

A market snapshot must contain its provenance, actual timestamped bid/ask, exact instrument ID, non-delayed status, underlying settlement and leverage, entry/close eligibility, an explicit event review, the Monday reference price, timestamped account risk/capital status, and declared nonnegative cost assumptions. Pre-open mode additionally needs evidence that the exact regular-hours position can close in that session. Missing, stale, future or contradictory facts block the applicable paper action.

The current executable broker adapter is a local paper model. Paper buys are IOC-limited at the observed ask; sells use the modeled bid and declared slippage/fees. Fill scenarios are synthetic, including when the underlying quote was observed read-only. A broker acknowledgment never creates a filled position. Live execution is rejected in code. The `.env.example` lists blank names for a **future** authenticated snapshot producer; the current paper commands neither read those credentials nor establish such a producer.

Authenticated eToro quote/eligibility/candle/cost reads were verified separately and documented in `../validation/Broker_Capabilities_Review.md`. A continuously refreshed standalone snapshot producer, actual broker write adapter, alert delivery and live deployment are not supplied or established here.

## Run or schedule the paper process

Inspect exchange-derived times:

```powershell
python -m weekly_strategy.cli calendar --date 2026-10-27
```

The built-in calendar covers the official 2026–2028 schedule and rejects unsupported years. It handles daylight-saving differences, early closes, holidays and next-day session rules. Proposed decision time is close minus 30 minutes; entry is close minus five. A is the next regular opening; B is five minutes before it, followed by reconciliation and opening fallback. These are fixed test parameters, not optimized minutes.

For a bounded, repeatable scheduler proof using the demonstration files:

```powershell
python -m weekly_strategy.cli scheduler --selection results/rev12_demo/synthetic_selection.json --market results/rev12_demo/synthetic_market.json --database results/paper-proof.sqlite --report results/paper-proof.json --log results/paper-proof.log --max-ticks 1 --at 2026-10-06T19:30:00+00:00
```

For a continuously running **paper** process over a future week's frozen packet and genuinely refreshed read-only snapshots:

```powershell
python -m weekly_strategy.cli scheduler --selection data/weekly_selection.json --market data/current_market.json --database results/weekly-paper.sqlite --report results/weekly-paper.json --log results/weekly-paper.log --poll-seconds 10
```

The second command requires those input files and a producer that updates `current_market.json` atomically with actual observations; it does not fetch quotes itself. Run it in a dedicated terminal and stop it with Ctrl+C. Windows Task Scheduler can launch this exact executable/arguments with this repository as “Start in”, using an operator-controlled startup trigger. Do not configure parallel instances. Keep the process running through exits; waking only at an entry time is insufficient. Actual deployment was not started in this task.

Restart with the same command and SQLite path. Configuration and weekly decisions are immutable within that database. The process reconciles pending/unknown/partial orders and overdue owned positions before any new entries. Unknown status blocks duplicates. Keep durable state, not just the JSON report. Only strategy-owned position IDs can be closed; unrelated PLTR/RKLB positions remain outside the exit process.

`run-once` performs one tick; `replay` accepts a chronological JSON array of `{at, market}` observations. `--at` with the scheduler is allowed only for a one-tick proof. A continuous scheduler uses actual current time and never refreshes the timestamp on stale data.

## Evaluation and remaining evidence

The evaluation records all decision/cash nights, ownership, actual/model fill provenance, paid costs and exceptions. Unresolved positions or unknown costs prevent complete-book net return/drawdown claims. SPY is matched to nights and invested exposure; its gross label remains explicit unless its costs are supplied. Unused exposure stays cash. Separate A/B ledgers prevent executing both exits against one position, and pairing requires the same selection and entries.

Prospective dated sources and observed executable prices/fills are needed to evaluate the weekly thesis. The actual supplied historical flow is incomplete for expired short-DTE contracts; current candidate diagnostics are not an unbiased historical backtest. The original `Research_Report_Rev11.pdf` and `results/` remain comparison evidence; do not relabel them as Revision 12 observations.

Before broker operation, resolve programme fees and round-trip costs, actual instrument/position 24/5 closing, broker fill/cancel behavior, approved risk/loss/capital rules, operator/runtime and alert responsibilities. The proposed $5,000 pilot, 10% per name, three positions and 30% gross cap are paper defaults. The later 15%/45% ceilings are disabled. No weight rule guarantees the account risk-score objective of 3–4.
