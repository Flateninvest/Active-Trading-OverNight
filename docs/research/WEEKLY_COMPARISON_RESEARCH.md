# Weekly research and overnight stock trading

This is the archived 7 October research paper for the separately tested weekly comparison. It describes the original local package, including private inputs and results not distributed in this GitHub repository. The current intended DAILY strategy is documented in `../DAILY_STRATEGY.md`; this paper does not validate or supersede it.

## eToro Active Trading Track Revision 12

**Author:** Sondre Flateraaker

**eToro profile:** Flaten

**Prepared:** 7 October 2026 for the meeting on 8 October 2026
**Status:** Research implementation and paper operation. No real or broker-demo orders are authorized or submitted by this package.

## Abstract

We propose a weekly research universe with repeated overnight exposure. On Tuesday morning, completed Monday options flow and the Hidden Angles information actually available by the selection cutoff identify up to ten stock candidates. Daily deterministic checks can permit, skip or remove those names. Qualifying entries occur on Tuesday through Thursday near the US regular-session close, and the primary exit is the following regular-session opening. The book is intended to be flat after Friday's routine exit. Shares are traded; the options in the source file are evidence, not instruments we buy.

Revision 12 implements and evaluates this process as a new research version. It preserves Revision 11's code, data, paper and historical results as a comparison. It also distinguishes the supplied v0.2 paper's daily short-DTE design from the weekly design. Software tests and synthetic paper exercises establish operational behavior. They do not establish profitable trading, an optimal minute, a win probability or a live-ready autonomous broker service.

The economic question is whether a verifiable company thesis, corroborated by public options activity and followed by restrained overnight exposure, can earn positive returns after achievable costs. A second question is whether a fixed exit five minutes before the regular opening improves the same trades after spreads, liquidity and execution failures. Both remain hypotheses requiring point-in-time observations and actual execution evidence.

## 1 What changed and what remains

The accepted Revision 11 submission contains an Avellaneda–Lee sector-hedged replication, a turnover enhancement and a long-only overnight extension. Those research components remain reproducible in the retained repository. The historical overnight extension uses a prior-data dispersion gate, a top-30 pool by 60-session momentum and ten names ranked by trailing 20-session overnight persistence. Its proposed analyst overlay may remove names only, retains original slots, and applies a five-session flow filter with ask-side premiums of at least $100,000, quantity greater than reported open interest and 180–730 recorded DTE.

The supplied v0.2 paper instead proposes ask-side short-dated activity, 2–10 DTE at each entry, net bullish premium of at least $1 million, bullish share of at least 70%, a recent Hidden Angle and daily technical gates. It proposes three positions and 15% per-name/45% total limits. Its literature and trading claims were not independently verified when it was written. The actual file has been inspected; those numbers are starting values, not optimal parameters or previously approved live settings.

Revision 12 changes the research cadence and the role of DTE. Monday's completed flow informs Tuesday's weekly selection. The 2–10-calendar-DTE screen, $1 million net and 70% share are explicitly declared untuned weekly test rules. They apply at selection, not as a hidden unchanged per-entry band. Each subsequent entry separately checks whether supporting contracts remain relevant through the intended holding window or whether an explicitly reviewed continuing thesis justifies eligibility after expiry. The old mechanical roster and long-DTE filter are comparisons; they are not silently retained as mandatory gates for the new weekly universe.

The continuity is the overnight holding window, evidence assessment, cash when prerequisites fail, no leverage, separate entry/exit fills and measurement of net economics. Revision 12 is neither a swing mandate nor an intraday options strategy. No Friday-close-to-Monday-open position is planned in the initial version.

## 2 Agreed information and trading schedule

Monday is the research gathering day. The completed options-flow export arrives after the US close. No paid options-flow API or daily options upload is required. Tuesday morning is the weekly research review. The candidate universe is frozen with source hashes, record IDs, an information cutoff and a decision ID. A stock may be retained the next week only after the new review, not because it won recently.

Tuesday through Thursday entries use the same frozen universe. Daily prices, instrument checks, events and thesis invalidations can permit, skip or remove candidates. They do not add new tickers or repeat a market-wide flow search. No minimum candidate or position count is forced. Large-cap stocks, including Apple, Alphabet and Micron, can qualify under the same rules; none is inserted merely because it is familiar.

The proposed daily final decision is 30 minutes before the verified regular close. Entry is approximately five minutes before that close, subject to the configured cutoff. Mode A exits at the first executable price at or after the following regular open. Mode B requests the alternative exit five minutes before that open and uses a documented regular-open fallback for the reconciled remainder. Friday completes the final routine exit and has no new entry.

All schedules derive from the America/New_York exchange calendar and convert to Europe/Zurich and UTC. Normally the open is 15:30 and close 22:00 Swiss time; in the late-October US/European daylight-saving mismatch they are 14:30 and 21:00. Half-days change the entry time. Entries whose next regular opening is separated by a full holiday or weekend are skipped. Unexpected closures or halts can still prevent a planned exit.

An 08:15 Swiss Tuesday freeze is a proposed configurable paper default, not an approved live cutoff. Actual source receipt, upload, ingestion and publication times must be recorded. A workbook row date, filename or later file modification time cannot establish earlier availability. The October 7 inspection cannot retrospectively verify an October 6 Tuesday-morning decision.

## 3 Source inspection and availability

The package inventories all 295 files in the original ZIP and preserves the original archive. The two updated workbooks are copied byte-for-byte into the new repository with SHA-256 identities. Raw rows retain their workbook, sheet, row number and source values. Company notes are evidence; embedded document instructions cannot change this mandate or authorize an order.

The actual flow read found 38,385 dated stock rows from 27 June 2024 through 6 October 2026 and 9,650 dated ETF rows from 27 August 2024 through 6 October 2026. Monday 5 October has 507 stock and 166 ETF rows; Tuesday 6 October has 502 stock and 197 ETF rows. These are source-row counts before the new strategy's filters, not trade recommendations. The companion Source Audit contains the full inventory, calculations and evidence IDs.

Monday-cutoff reconstruction and the later October 7 rehearsal are separate outputs. A later export containing Tuesday records cannot supply them to Tuesday morning. A later-edited research note likewise cannot explain an earlier decision without a recorded availability mismatch. Unknown availability means the relevant forward decision is incomplete, not that the information was available.

Premiums, quantities, contract expiry, DTE and direction are parsed under the actual columns and units. Arithmetic uses the retained records. Calls do not always mean bullish exposure. At/near/above-ask call buying can be an inferred bullish input and corresponding put buying an inferred bearish input; ambiguous sides are unclassified. A supplied sentiment is preserved separately from an inference. Neither establishes an opening transaction, continued ownership, trader identity or knowledge of a Hidden Angle.

Identical-looking records are flagged and retained unless a source identifier or other reliable evidence proves a duplicate. Similar call/put sizes are structural cautions, not proof of linked legs. Quantity above open interest is a tag rather than proof that a particular trade opened a position. Bullish share means bullish premium divided by bullish plus bearish premium in the declared qualifying sample; it is not a measure of the whole market.

The expiry audit found that all 48,035 retained flow records have derived expiries after the latest source session, 6 October 2026; zero expired or same-day-expiring records remain. This is consistent with removal of expired contracts, although the vendor retention policy is not supplied. The audit also retains 1,881 identical-looking excess records and flags nine premium arithmetic mismatches under an assumed standard 100-share multiplier. A nonstandard multiplier is not independently verified. Such a current export cannot support an unbiased complete historical short-DTE backtest. Forward dated snapshots are required. The code must never fill absent historical records with zero activity or retrospectively use the latest database as a point-in-time archive.

## 4 Weekly selection and contract time

The initial paper rule considers the declared completed Monday session and stock records with at least $100,000 premium, relevant ask-side classification and 2–10 calendar DTE at Tuesday selection. It calculates bullish premium B, bearish premium R, net B−R and B/(B+R). The proposed flow screen requires net at least $1 million and share at least 70%. These thresholds are configurable test rules and are frozen for an evaluation version; no scan for a better threshold is performed after seeing outcomes.

The research overlay requires a recent, dated company mechanism and records its source, direction, expected timeframe, contrary evidence and invalidation. A verified event within the holding window is separated from an ongoing thesis supporting several nights and from long-term background with little timing relevance. The source status states whether the original company/analyst evidence was verified or only vendor-reported. The AI may propose an interpretation but must not manufacture a story explaining the options buyer's intentions.

The selection output saves every considered name and its pass, rejection or unresolved reason, plus up to ten candidates. A smaller universe or cash is valid. Research eligibility and operational entry permission are different states. Missing calendar, source verification, event review, quote freshness, underlying-share eligibility or other mandatory inputs blocks the applicable paper decision rather than being offset by a narrative score. No invented probability or decorative conviction scale is used.

For each flow row, record the trade date, source availability, contract expiry and DTE at trade, selection and each entry. Monday 0-DTE records that have expired are historical context, never outstanding exposure supporting later nights. Short DTE conveys time sensitivity, not proven predictive accuracy. Eligible nights and the last eligible entry are explicit. Expired support may not be silently carried forward; continuing eligibility needs an explicitly documented, reviewed thesis and its invalidation conditions.

This discipline does not prove that an unexpired Monday options buyer still owns the contract. It records what remains plausible from the observed file. A fresh stock quote validates a price, not persistence of options ownership.

## 5 Deterministic daily entry and sizing

Daily checks are deliberately few. They enforce the calendar and weekly membership, active evidence or an approved continuing thesis, no contradictory news or excluded event, fresh non-delayed bid/ask, acceptable spread, current underlying-share eligibility and configured price freshness limits. Volume-derived VWAP or relative-volume gates are not required because the broker volume field's consolidation and meaning are not established. Prices can be used without purchasing another data feed.

The initial configurable technical rules are a maximum 60-second quote age, maximum 20-bp spread and absolute entry-ask change no greater than 2% from the explicitly identified Monday closing reference. This price check is a new, untuned test rule; it does not prove underpricing. Its reference date, convention and source must be supplied. The optional moving-average gate is disabled by default. Missing or stale prices produce a skipped decision. A daily removal leaves cash and does not trigger a replacement search. The frozen weekly record remains intact; changes and invalidations appear in a separate ledger.

The proposed pilot allocation is $5,000, with at most 10% or $500 per name, zero to three simultaneous positions and at most 30% or $1,500 initial stock exposure. These are meeting proposals and synthetic-paper defaults, not approved live capital. The earlier 15%/45% limits remain outer proposals for a later reviewed stage and never expand the initial implementation automatically. Unused allocation stays cash.

Sizing uses the configured initial paper equity/cash, exact instrument units, permitted fractional precision and minimum amounts. It reserves the declared modeled entry fees; it does not establish an actual broker round-trip fee reservation or dynamic account equity service. Paper buy orders are IOC-limited at the observed ask, and a modeled fill above that limit is rejected. A future unconstrained market order would need its own cap protection. Round down within all caps. Leave undersized slots cash. Existing positions and reserved orders count under the approved portfolio policy. A strategy sleeve is not a recommendation to reduce the whole Flaten account. Core PLTR and RKLB holdings are not liquidated by the exit process; only position IDs created and owned by this strategy can be closed.

The proposed reported-account risk-score objective is 3–4, with a pause/review of new entries at score 5. Programme-specific constraints remain to be confirmed. The displayed score describes the account/portfolio and cannot necessarily be assigned to one sleeve. No 10% weight rule guarantees a score. Dollar/session-loss and drawdown limits and the restart owner require an approved configuration before operational use.

At the illustrative allocation, a $500 holding losing 10% loses $50 or 1% of a $5,000 book. Three $500 holdings losing 5% each lose $75 or 1.5%; three losing 10% lose $150 or 3%. These are scenarios, not maximum losses. A stop cannot guarantee an exit price across a gap, halt or market outage.

## 6 Broker execution and the two exits

Read-only eToro access was checked on October 7. Current instrument identity, bid/ask, price timestamps, explicit real-time rate indicators, underlying real/X1 long eligibility and candle responses were observed for Apple, Alphabet and Micron. These reads verify those fields at their observed times. They do not establish an unattended write process, a scheduled broker service, programme fee entitlement or the ability to close a particular regular-hours underlying-share position before the following open.

The current eligibility response identifies real settlement at X1 for the three inspected long instruments. Fractional trading and a $10 minimum were returned. The daily service must still check the exact selected security/account; these three examples are not a universal eligibility file. A leverage value of one alone is insufficient evidence of underlying ownership. The broker review retains source timestamps and safe read results.

Official eToro announcements describe underlying-share/ETF 24/5 trading and an expansion to S&P 500 and Nasdaq 100 constituents. Eligibility must be checked for the current account, symbol, session and actual position. Older .EXT CFD instruments are not interchangeable with a newer underlying-share position. A public launch announcement does not prove that the API can close the exact position at 15:25 Swiss time.

The inspected order schema supports market, market-if-touched and immediate-or-cancel limit types. No MOC/MOO auction route was established. The phrase market-close-orders describes closing a position, not the closing auction. Current asynchronous open orders return acceptance before execution, and the close-position route likewise requires subsequent status and position reconciliation. An order ID, quote or acknowledgement is not a fill.

Mode A and Mode B share the same selections, intended entries, sizes and entry records in evaluation. A pre-open exit failure is handled by reconciling filled units, unresolved orders and remaining strategy-owned quantity, then following the regular-open procedure for that remainder. Unknown close status blocks a duplicate order. A partial exit remains an owned unresolved holding; it is not recorded as flat. Both alternatives must never be executed against the same live position.

Any unresolved prior strategy exit blocks all new entries. The durable ledger tracks proposed, submitted, acknowledged, partially filled, filled, rejected, cancelled and closed states from observed evidence. Stable keys prevent repeated scheduler runs from buying again. Restart recovery reads the ledger and reconciles before acting. The current package has a paper adapter; broker writes and unattended live deployment are disabled.

## 7 Cost economics

Zero explicit commission is a planning assumption based on the user's expectation of programme coverage. Account, instrument, jurisdiction and programme entitlement still require confirmation. A read-only $500 Micron X1 real-share opening-cost preview returned zero transaction fee, zero markup, $0.07 market spread and zero overnight fee on October 7. This is one hypothetical request, not an observed fill or proof of all instruments, programme entitlement or the complete round trip. The actual response used costs[].value while its schema/example used costs[].amount; the adapter must preserve and flag that discrepancy rather than dropping the amount.

Include spread, slippage, applicable FX, product-specific financing or other charges and actual operating costs. Do not assume CFD financing applies to eligible unleveraged underlying shares. If actual entry ask and exit bid already incorporate the spread, do not subtract it again. Net results use actual fees/currency cash flows where supplied; missing costs do not become zero.

The hypothetical cost endpoint has contradictory shared wording about close support. A preview for opening cannot validate closing fees, and the close calculation cannot be presumed working from examples alone. The package records this limitation and leaves unavailable costs unverified. An official close/open print is a benchmark, not a fill at 21:55 or 15:30.

$5,000 is an operational risk-budget judgement, not a calculated break-even minimum. Smaller permitted amounts can test connectivity; larger capital does not remove percentage frictions or prove profitability. Fixed operating charges should be allocated separately from variable trading costs and reported transparently.

## 8 Evaluation design

Freeze the strategy, numerical defaults, information cutoffs, price conventions, costs and minimum review horizon before observations. Maintain four comparisons: weekly flow plus Hidden Angles; the same weekly flow process without the overlay; SPY overnight over matched nights and the same invested exposure; and paired pre-open versus regular-open exits. SPY is a benchmark, not a pivot of the trading mandate to ETFs.

For the research ablation, retain every qualifying flow candidate and rejected/removed/operationally skipped record. Apply the same eligibility, calendar and cost conventions to both controls. Report how the research overlay changes both stock selection and cash exposure. The exposure-matched SPY control invests the same fraction of starting equity on the same nights and keeps the remaining cash under the same cash-interest convention.

Report returns on total strategy equity and invested capital, gross/net P&L, average net trade, drawdown, worst overnight loss, costs, execution shortfall, failures and exceptions. Daily drawdown uses chronological whole-book equity with inactive/cash sessions retained. Mark unresolved holdings separately from realized results. Quantify completed independent nights/weeks; multiple names on the same night are correlated observations, not independent trials.

The paired exit study uses fixed timestamp rules decided before outcomes. It may not select the better exit retrospectively. Missing or failed prices are retained as missing/operational exceptions; they are not favourable zero returns or discarded nights. A few successful trades and synthetic fixtures cannot prove profitability. Prospective snapshots are needed because the supplied cumulative files cannot establish historical availability/completeness.

Revision 11's 2025 gated overnight result remains −35.91% at 20 bp per executed side. The +18.99% and +12.67% results use hypothetical 6 and 9 bp round trips. Its inspected evaluation and broad prior exploration remain exploratory. These findings motivate measuring costs; they do not validate the new short-DTE weekly overlay or current eToro fills. Synthetic Revision 12 outcomes are operational demonstrations and are never blended into those historical results.

## 9 Research motivation and sources

Pan and Poteshman study options-volume information with distinctions such as buyer-initiated opening activity. An ask-side export without verified open/close flags does not reproduce that input. Their evidence motivates investigating options data, not assigning a calibrated overnight profit forecast to this file. Knuteson's close/open research and the likely Dividendology Micron illustration similarly motivate the overnight question. A hypothetical historical chart is not an audited record of a person executing every trade.

Our weekly selection, event exclusions, spread, timing and broker fills differ from those examples. Longer business theses may support repeated research reviews without establishing a catalyst tonight. The strongest credible opposing explanation is retained for each candidate. The AI's role is source interpretation and evidence assessment; deterministic code controls arithmetic, calendars, caps, order state and reconciliation.

## 10 Current validation and next evidence

All 100 repository tests passed with Python 3.12.14 and the pinned numerical dependencies: 35 original numerical tests, 20 ingestion/selection tests and 45 engine/calendar/scheduler/accounting tests. The initial invocation exposed an environment temporary-directory permission problem; the runner now uses a writable workspace directory without changing a numerical rule. Six additional independent adversarial checks passed. The original price-based and gated comparison rebuilt successfully: 21 regenerated CSV outputs match their supplied numerical values within 1e−9, and the gated summary matches exactly. Proprietary-flow and original-PDF production were excluded under the original documented --skip-flow mode, so those components are preserved but not claimed freshly rebuilt.

The actual Monday diagnostic has seven numeric-flow survivors and the declared later rehearsal has eight; neither has accepted verified research/broker candidates. The later rehearsal was run through a bounded scheduler and entry tick with deliberately empty market facts: $5,000 modeled cash, zero orders and zero fills. That is a successful missing-data control, not an observed trading result. Separate synthetic flow-plus-research, flow-only and paired-exit ledgers demonstrate operation and exposure-matched SPY arithmetic. Executed commands and their limits are recorded in the Validation Report.

The scheduler is an actual documented paper process with persistent state and restart behavior. It consumes supplied timestamped market snapshots; a continuously refreshing authenticated quote producer and broker write adapter are not implemented. The exchange calendar uses the official 2026–2028 schedule and fails closed outside that horizon. A chat response alone is not that runtime. Source interpretation uses the supplied weekly agent instructions and structured decisions; missing research and operational fields result in cash. Environment examples contain no credentials. The new package does not place orders, move funds or start unattended live trading.

Outstanding operational evidence includes confirmation of programme costs, selected-instrument 24/5 availability, exact-position pre-open closing, actual fill/status behavior, account risk and sleeve limits, permitted operator/runtime responsibility and the appropriate human/platform confirmations. A trustworthy forward selection archive, observed round-trip fills and consistent benchmark data are required before a claim about net economic value.

## References

1. Sondre Flateraaker, accepted Research Report Revision 11 and associated code/configuration/results, 7 September 2026. Preserved in the evaluation repository.
2. Supplied Overnight Conviction Basket v0.2 T1 Paper, prepared 6 October 2026. Used as an inspected design comparison; its unverified literature/market claims are not adopted as empirical findings.
3. NYSE, Holidays and Trading Hours, official 2026–2028 schedule, accessed 7 October 2026. https://www.nyse.com/trade/hours-calendars
4. eToro underlying-share 24/5 launch. https://investors.etoro.com/news-releases/news-release-details/etoro-continues-journey-towards-tokenized-future-launch-245
5. eToro S&P 500 and Nasdaq 100 24/5 expansion. https://www.etoro.com/news-and-analysis/press-releases/etoro-enables-24-5-trading-for-all-sp-500-and-nasdaq-100-stocks/
6. eToro order, eligibility and cost documentation and current connector schema, accessed 7 October 2026. https://api-portal.etoro.com/api-reference/trading--real/create-an-order ; https://api-portal.etoro.com/api-reference/trading--real/check-instrument-trading-eligibility ; https://api-portal.etoro.com/api-reference/trading--real/get-what-if-trading-cost-breakdown
7. eToro fees and hours. https://www.etoro.com/trading/fees/ ; https://www.etoro.com/trading/market-hours-and-events/
8. SEC Investor.gov extended-hours bulletin. https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-42
9. Pan and Poteshman, The Information in Option Volume for Future Stock Prices, author manuscript. https://web.mit.edu/junpan/www/volume.pdf
10. Bruce Knuteson research and code index. https://bruceknuteson.github.io/spy-day-and-night/
11. Likely Dividendology Micron illustration. https://substack.com/@dividendology/note/c-320782628

Input hashes, original row references, inspection cutoffs, actual read outcomes and implementation changes are retained in the package's audit and validation files. No numerical edge is asserted for Revision 12.
