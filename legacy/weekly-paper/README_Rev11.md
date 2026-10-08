# Trading the night, informed by database

eToro Active Trading Track submission — Sondre Flateraaker.

**Research_Report_Rev11.pdf is the eight-page submission.** It retains the previous report's section order and two main illustrations, corrects accounting and evidence claims, and adds the required baseline equity curves. This is simulated research; the analyst overlay and broker connection are proposed work.

## Reproduce

Tested with Python 3.12. From this folder:

```powershell
python -m pip install -r requirements.txt
python run.py
```

The second command rebuilds the baseline, enhancement, overnight studies, workbook evidence, figures and PDF using the packaged inputs. It requires no downloads or manual editing. Allow several minutes. Numerical and accounting checks:

```powershell
python -m unittest discover -s tests -v
```

`python run.py --skip-flow` runs the price-based models and the supplied external SPY comparison, but skips the proprietary evidence summaries and full PDF. It does not produce an updated submission report. Both workbooks are included in this private submission; their presence is not a redistribution licence.

## What is tested

1. **Replication:** Avellaneda–Lee sector-ETF residual mean reversion. Rolling 60-session OLS and AR(1), s-score thresholds, beta hedges, 1% stock targets and 200% gross cap.
2. **Enhancement:** an extra 0.50 s-score for entries and a 2%-of-NAV no-trade band on aggregate hedge target changes. Exits are unchanged. The report separates reduced turnover from reduced gross exposure.
3. **Original experiment:** a long-only overnight extension. Prior-close 60-day momentum selects a pool of 30; 20-session overnight persistence selects ten. An expanding-median dispersion gate, lagged and requiring 252 observations, chooses eligible nights. The rule was retained during this correction pass, not retuned. Its 48-cell surface and earlier exploration mean the inspected 2025 window is exploratory.

At the required costs, all three lose in 2025: baseline **−10.99% annualized**, enhancement **−5.62% annualized**, and gated overnight **−35.91% total**. The overnight low-cost sensitivities give +18.99% at 6 bp and +12.67% at 9 bp per round trip. These are assumptions, not observed execution costs. Exact values and denominators are generated in `results/`; report tables state annualized versus total return explicitly.

## Data and accounting

- Use all 200 supplied equities and 11 sector ETFs. The old external membership restriction is removed. The frozen universe cannot establish historical membership or eliminate survivorship bias.
- Original OHLCV files remain unchanged. `data_quality.py` applies the eight verified split discontinuities listed in `data/external/corporate_actions.csv` in memory and recognizes already adjusted events. Every listed adjustment has a source URL. Unexplained large discontinuities stop the run for review; they are not silently treated as returns. Prices exclude cash dividends, and cash earns zero interest.
- Baseline signals formed at close t−1 execute at close t, then earn close t to close t+1 returns. Fees use actual trades against drifted holdings, including entry. Short financing uses SOFR + 0.50% over actual calendar days, ACT/360. The 200% cap is rechecked after buffering. Final holdings are marked rather than forcibly liquidated.
- A missing execution quote defers that trade. Existing positions retain their last observed mark and catch up at the next quote. No missing quote is used as a fictitious fill. This valuation convention can temporarily understate risk during unavailable prices.
- The overnight ledger reserves costs before sizing and charges each buy and sell on its executed notional. An unavailable entry leaves cash; no replacement is chosen after seeing exit data. An unavailable exit stays held until an executable open, and blocks all new entries meanwhile. Reporting dates are valuation/exit sessions; entry dates are retained in the trade logs.
- The main overnight portfolio has at most 10% per name and 100% gross at entry. Breadths below ten are explicitly labeled concentration diagnostics exceeding the proposed name cap when fully invested.
- Return risk and t statistics include inactive cash sessions. Benchmarks share date boundaries. SPY is gross of costs and excludes dividends; it is not a net-investable comparator. Missing benchmark coverage is reported, not filled with a strategy return.
- Mandatory costs are **20 bp per side / 40 bp round trip**. Lower scenarios are sensitivities. No calibrated impact, live shortability or broker execution model is claimed.

## Workbook evidence

`flow-114.xlsx` and `hidden_angle_flow_database_SEP_6th_2026_updated.xlsx` are copied unchanged. Metadata records hashes and the supplied 4 September 2026 snapshot boundary; no original collection timestamp is invented.

The flow filter removes exact duplicate records, requires ask-side, at least $100,000 premium, quantity above reported open interest, 180–730 days to expiry, and bullish/bearish sentiment. It selects 8,512 records across both sheets. The baseline helper's stock/sector source-sheet rules leave 7,784; no records belonging to the fixed 200 equities are removed by that extra rule. A lagged five-session score covers a median ten universe names in 2025. These are descriptive results from a later snapshot, whose historical availability and completeness are unverified. Ask-side classification does not prove investor identity or an unhedged opening trade.

The research file contains 33,154 dated notes, beginning in February 2026: **no overlap with the historical price test**. The export lacks underlying publisher/source links and explicit falsifiers. CI and AVGO examples are traced to exact workbook rows; later conviction aggregates are identified separately. No research-overlay backtest is claimed.

## Held-out continuation

Append continuation OHLCV and SOFR observations to the same supplied files, retaining the historical lookback, and run the same command. No source-code change is needed. The optional cutoff is:

```powershell
python run.py --evaluation-date 2026-06-30
```

The default is the latest supplied price date. Development and 2025 remain fixed; 2026+ statistics are exported separately in the main metrics and overnight continuation outputs. A cutoff does not fetch missing data. Known new corporate actions belong in the sourced metadata file. Missing extended SPY coverage does not prevent strategy evaluation; benchmark comparisons are marked unavailable when incomplete. The PDF remains the fixed historical submission. Tests exercise continuation behavior on synthetic appended observations; the supplied data do not provide a genuine 2026 trading result.

## Files

| File or folder | Purpose |
|---|---|
| `Research_Report_Rev11.pdf` | Eight-page report |
| `run.py`, `config.json` | Baseline, enhancement, flow ablation and complete-build entry point |
| `data_quality.py` | Validated prices, sourced split adjustments and calendar financing |
| `overnight_execution.py` | Shared cash/holdings ledger for overnight simulations |
| `overnight_backtest.py`, `overnight_config.json` | Mechanical overnight comparison and generated `OVERNIGHT_BACKTEST.md` |
| `overnight_strategy_v6.py` | Gated rule, search, benchmarks, bootstrap and Figure 1; filename retained for compatibility |
| `evidence_summary.py`, `flow_layer.py` | Workbook counts, coverage, information checks and example provenance |
| `build_report.py`, `report_layout.py` | Report content, vector workflow and generated baseline figure |
| `analyst_prompt.md`, `forward_protocol.json` | Proposed frozen analyst pass and forward H1/H2 procedure |
| `data/official/` | Unchanged supplied universe, OHLCV and SOFR |
| `data/external/` | Supplied workbooks, split evidence, SPY and retained source provenance |
| `results/` | Rebuilt returns, metrics, targets, executed holdings and audit metadata |
| `results/rev6/` | Gated-strategy results; legacy folder name retained |
| `results/evidence/` | Counts, coverage, information results and workbook row references |
| `tests/` | Timing, capital, costs, split, missing-quote and continuation checks |

`audit_extensions.py` now delegates to the corrected overnight analysis; the duplicate legacy backtest is retired. Download helpers are provenance utilities and are not called during reproduction. The old membership snapshot is retained for provenance but is not used to select names.

## What happens next

Freeze and hash the packaged prompt and protocol before the first forward decision. The analyst may only remove names from the mechanical roster; removed weight remains cash. Verify source, catalyst, falsifier, flow cutoff and broker eligibility, then log decisions and both execution legs. H1 tests the mechanical strategy after observed costs over 252 traded sessions. H2 compares overlay and mechanical daily returns, with an exposure-matched control. The protocol is proposed, not externally preregistered. Execution, live evidence capture and that forward evaluation remain to be built.

The historical result is a negative finding at the assignment friction and a conditional motivation for further research. It does not establish live profitability or an incremental database edge.
