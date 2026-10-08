# Daily overnight stock strategy

Selected 8 October 2026. This describes the intended DAILY design; the integrated daily runtime is not implemented in this initial upload.

## Research and selection

- Intake at 08:00 Europe/Paris, freeze at 08:15, using the previous completed US session's supplied files.
- Combine options flow, full relevant Hidden Angles/research, primary-source verification, event timing and TA.
- Up to ten candidates and three priorities; no trade quota. Later information can remove names, not add unreviewed replacements.
- Starting flow rules: $100,000 row premium; unambiguous ask-side inference; 2-10 calendar DTE at daily selection; at least $1 million net inferred bullish premium; at least 70% bullish share of qualifying directional premium.
- Supporting contracts cover the planned exit. Flow does not prove opening or continued ownership. Preserve identical-looking prints unless reliable execution IDs prove duplication.
- TA requires 60 completed daily bars, preferably 120, with SMA20/50, Wilder RSI14, ATR14, support/resistance and price context. Mechanical SMA/volume gates remain disabled. VWAP needs reliable traded-share volume.

## Products timing and controls

- Long underlying US stocks/verified US ADRs, cash/X1. No options trading, shorts, leverage, CFDs or ETFs.
- Tuesday-Thursday entries; next regular-opening exits Wednesday-Friday. No planned Monday/Friday buy or weekend/full-holiday hold.
- Review close minus 30 minutes, target entry close minus five, stop new submissions close minus one. Derive times from the actual exchange calendar and convert to Europe/Paris.
- Illustrative $5,000 allocation: at most 10% per name, three positions and 30% gross including pending exposure/costs. Unused allocation stays cash.
- Proposed account risk target 3-4, pause/review new entries at 5 or above; whole-account risk cannot be inferred from this sleeve's weights.
- Quotes at most 60 seconds old; maximum 20-bp spread. Ask within +/-2% of the defined current-week Monday close, reference age at most four calendar days. Missing Monday reference blocks an entry.
- Dollar loss/drawdown settings and actual live mandate remain unset. Only recorded strategy-owned position IDs may be closed; unrelated PLTR/RKLB and copied positions are protected.

## Passive execution hypothesis

Test passive buy-at-bid/sell-at-ask separately in shadow. Verify true resting order support; IOC does not rest and market-if-touched executes a market order after its trigger. Current inspected close-by-position operation is market-rate. Unfilled entry attempts remain cash and expire/cancel within the original cutoff. Quote/bar touch is not proof of a fill.

Waiting for a passive exit changes the next-opening timing. Exit-wait/fallback settings remain unset and the variant disabled until explicitly reviewed. Do not extend a hold merely to avoid spread. Include missed fills, cash nights, adverse selection and fallback costs when comparing methods.

## Evidence

No validated daily overnight win probability, best execution minute or profitable flow-plus-research backtest has been established. Current exports omit expired contracts and cannot reconstruct complete historical short-DTE activity. The legacy weekly tests demonstrate software behavior, not this daily strategy's profitability.

Strategy development now follows the [mandatory workshop research loop](RESEARCH_LOOP.md): a falsifiable owner-reviewed hypothesis, frozen inputs/costs, full trial log, one-change ablations, chronological walk-forward holdout with prior owner preregistration, and fresh reproduction before accepted numerical reporting. The new code checks protocol metadata and artifacts; it does not implement the daily backtester. The disclosed year, genuine plan dates and owner approval remain unset. Existing trading rules above are unchanged.
