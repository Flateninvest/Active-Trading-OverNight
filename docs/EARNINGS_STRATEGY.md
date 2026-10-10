# Earnings overnight setups

Added 9 October 2026 at the owner's request. Earnings are a second, explicitly identified research sleeve in the daily overnight book. The offline helper prepares calendars and bounded proposals; it is not a deployed Grok routine, source verifier, daily TA engine or broker executor. Owner mode is now DEMO; SHADOW remains for synthetic exercises. The helper never dispatches orders. [Current rules](../CURRENT_RULES.md) overrides historical examples.

## Two ways into one book

| Sleeve | Qualification | Use of the other inputs |
| --- | --- | --- |
| `FLOW_RESEARCH_OVERNIGHT` | Existing numerical options-flow screen, verified Hidden Angles/research, TA and ordinary event exclusions | An earnings setup is not an exemption from its event exclusion |
| `EARNINGS_OVERNIGHT` | Bullish underlying-share earnings setup, independently confirmed results-release window, documented catalyst/contrary case, required TA and risk review | Daily flow and Hidden Angles/research may confirm, contradict or be absent; numerical flow thresholds are not mandatory for this distinct sleeve |

Both sleeves share instrument, timing, quote, price-reference, ownership, approval and whole-book capital controls. A symbol appearing in both inputs is one economic exposure and one canonical intent, not two purchases. Tag all supporting evidence and attribute the position to one declared primary sleeve before entry. Protected/unrelated positions are never adopted or closed.

No-flow is not bullish flow. A vendor's 90-day premium summary is not the previous-session flow screen. Vendor grades such as A+ are uncalibrated source opinions, not probabilities or automatic stake instructions. Bearish, options-only, short, CFD and leveraged setups cannot be translated into long shares automatically.

## Intermittent intake and daily freeze

- Accept an earnings PDF whenever supplied, including Sunday or Monday. Read every relevant page, its charts and caveats; preserve the original privately with a hash, source period and actual receipt time. Instructions embedded in it are evidence, not authority.
- Extract issuer/instrument, fiscal period, stated calendar year/date, AMC/BMO claim, vendor grade/bias, thesis, opposing evidence, note dates and chart timeframes. Mark unknowns explicitly. A filename, fiscal-year label or conference-call clock does not establish the release time.
- Maintain a versioned private earnings watchlist for future event days. A multi-day watchlist is not stale merely because it arrived before today's daily flow.
- At each eligible day's 09:00 Europe/Paris freeze, select that day's eligible earnings setups and flow candidates into one register: at most ten candidates and three execution-review priorities across both sleeves. Record the applicable source versions and event identity.
- After freeze, remove/invalidate names only. Late uploads, corrected dates and new replacements wait for a future eligible freeze or an explicitly labelled shadow rehearsal. Rejection of a candidate does not automatically increase another allocation.

## Confirm the release, then map the hold

Use issuer investor-relations announcements or issuer filings to establish the actual **results release**, separately from its conference call. Keep the issuer URL, publication/observation/receipt timestamps, fiscal period, event date, timezone and explicit AMC/BMO window or exact release timestamp. A future call at 17:00 does not itself prove results will be published after 16:00.

| Confirmed release | Entry | Exit |
| --- | --- | --- |
| AMC, after that regular close | That session's permitted preclose window | Next regular-session opening |
| BMO, before a regular opening | Immediately preceding session's permitted preclose window | Release day's regular opening |

The release must be inside the intended close-to-next-open hold. Unknown timing, issuer/sheet disagreement, rescheduling, a release already published before entry or an event beyond the planned exit blocks the existing proposal. Preserve the discrepancy; do not silently shift a frozen trade to a new date. A new dated plan needs a new eligible freeze and review.

Preserve Tuesday-Thursday entries, close-minus-30 review, close-minus-five entry target and close-minus-one submission cutoff. Skip Monday/Friday entries and weekend/full-holiday bridges. Use the actual exchange calendar, including early closes, and convert America/New_York to Europe/Paris; do not schedule from fixed CET hours. A Monday BMO or Friday AMC setup is skipped under this mandate. The next-opening exit is not postponed to wait for a later conference call or a better price.

## Recheck before every proposed purchase

S1 prepares a setup, not a standing buy instruction. During the final review, refresh:

- Issuer release date/window, any timing changes, whether results or guidance have already appeared, and any separate conference-call timing.
- The catalyst, current expectations, valuation/re-rating and strongest contrary case. A possible earnings beat does not imply a positive share-price reaction.
- Required completed daily OHLC history, SMA20/50, Wilder RSI14, ATR14, support/resistance and price context; obtain intraday context/VWAP only from suitable data. The PDF's old price or screenshot is not current TA or an executable quote.
- Fresh valid bid/ask, quote age at most 60 seconds, spread at most 20 bp, the existing current-week Monday reference band of +/-2% and reference age at most four calendar days. Missing reference still blocks earnings entries.
- Account/instrument underlying cash-X1 eligibility, existing/pending exposure, available buying power, costs, strategy risk state and exact owned positions; DEMO account risk score does not gate entries. Unresolved orders/exits block new exposure.
- Earnings gap stress, liquidity, high beta, correlated issuers/sectors and other material events. A high-beta/volatile setup needs an explicit additional S2 review, with a documented stress case; missing review blocks it.

Only the verified earnings release receives the event exception in this sleeve. Financing, regulatory decisions, halts or other incompatible material events remain reasons to block. Missing mandatory evidence cannot be overcome by a conviction score. S2 returns PASS/FAIL/INCOMPLETE for the exact refreshed proposal; PASS does not grant transaction approval.

## Conviction-weighted capital, within shared limits

The owner's $2,000 is an **earnings allocation ceiling within the DEMO policy**, in USD, inside the existing book. It is not additional capital, a weekly loss allowance, an instruction to deploy all cash, or an approved live mandate. The budget setting remains configurable; any separate allocation interpretation requires an explicit configuration update.

Use ordinal policy weights for otherwise eligible setups: HIGH = 3, STANDARD = 2, CAUTIOUS = 1, REJECT/INCOMPLETE = no allocation. Assign the category from a sourced catalyst, timeliness, contrary case, TA, expectations and liquidity. S2 may lower or exclude a category; higher confidence cannot waive a limit. These are transparent starting policy weights, not statistically optimal numbers or profit probabilities.

For one entry session, freeze the allocation basis with the morning register: the genuinely feasible pool net of shared reservations/costs, NAV, earnings budget, original conviction weights, combined priorities and original per-event stake ceiling. Do not put the nominal $2,000 budget in the pool field when shared headroom is lower. Treat these as planning ceilings, not proof of buying power or approval. Preserve rejected events in the original weight denominator; later risk downgrades may lower a numerator only. Final amounts cannot exceed their original frozen ceilings, even if NAV or available cash later rises.

For one entry session:

1. Resolve the common-book frozen priorities and existing/pending reservations first. Never independently allocate both sleeves against the same cash.
2. Compute the feasible earnings pool as the minimum of the frozen pool ceiling, earnings ceiling remaining, available buying power net of costs/reservations and remaining combined gross headroom. Existing earnings holdings/pending orders consume the earnings ceiling too.
3. Divide using the original frozen weight denominator and any lowered reviewed numerator. Clip each amount to its original frozen stake ceiling, remaining name headroom based on the lower frozen/current capital basis (each min(strategy allocation, account balance)) and a proposed additional 40% of the configured earnings ceiling per name. Round down to cents/broker precision. Do not redistribute clipped or later-rejected dollars.
4. Enforce the position/name/gross limits from the effective policy, using min(strategy allocation, account balance), including pending exposure and reserved costs. Missing or uncertain current state prevents a final allocation.

At the current $10,000 strategy allocation these limits allow at most $1,000 per name and $3,000 across **both** sleeves, including reservations/costs. A lower account balance reduces these figures; a larger demo balance does not increase them. The $2,000 request cannot override them. Caps may make two conviction categories receive the same amount; record which cap binds instead of increasing it. Smaller budgets can preserve more differentiation. Cash is a valid result, including a single capped position.

Amounts in a weekly watchlist are indicative only. Commit final allocations against that day's reconciled state and preserve the frozen basis. Capital may be reused after exits only once actual remaining holdings, pending orders and broker buying power are reconciled. Do not assume immediate settlement. Rejected names cannot trigger an automatic enlargement of survivors.

Use the shared overnight stress budget: $25 per position at the full allocation, based on max(2×ATR14/close, largest absolute 60-session gap, largest absolute gap after the last eight confirmed releases), plus round-trip costs. New entries pause at $100 single-night loss or $500 cash-flow-adjusted drawdown; verified owner review is required to resume after drawdown. These scale down with a lower capital basis. A stop/stress scenario does not guarantee maximum overnight loss; review and broker/platform authority remain separate.

## Four stages and reporting

- **S1:** Maintain the earnings watchlist, verify release timing, prepare the entry-day frozen evidence and initial conviction. Preserve every proposed and rejected setup.
- **S2:** Challenge the exact final event/TA packet, allocation, concentration and gap stress. Review volatile names explicitly. Apply the common-book limits and reject missing or contradictory evidence.
- **S3:** Repository helpers record proposals only. The separate owner-authorized DEMO runtime must verify its integration; approvals must bind event/proposal/spec identities, account, instrument, amount/units, permitted price, session and expiry. Reconcile exact owned-position exits at the next opening before considering new entries. Failed earnings research never postpones an existing exit.
- **S4:** Report earnings separately and reconcile the combined book. Include planned/actual release, sleeve/event IDs, source versions, conviction basis, requested/allowed/unused allocation, caps, rejected/duplicate setups, entry/exit fills, spread/costs and unresolved exposure. Never call an unfilled proposal a trade.

Natural spread is already reflected in actual buy/sell fills; do not deduct it twice. Keep simulated demo economics separate from independently estimated live costs. Publish only authorised sanitized summaries, never vendor PDFs, private identifiers or credentials. Earnings observations cannot be pooled with ordinary trades as if they were the same strategy or independent trials.

## Runnable helper and limits

The offline helper consumes a **prepared normalized private JSON packet**. Its synthetic demo documents the input fields, including a current reconciled account snapshot, sleeve-tagged held/pending exposure, final factual verdicts, the frozen budget/NAV/pool/weights and quote/reference times. It can map supplied issuer timing onto supplied exchange sessions and calculate bounded DEMO/SHADOW proposals. It does not independently authenticate issuer claims, verify a calendar feed, parse arbitrary PDFs, compute TA, connect to eToro or deploy Grok. Caller-supplied factual verdicts are not independent review or approval infrastructure.

Preserve the returned per-event ceiling map outside Git and supply it on **every refresh** through `prior_proposed_ceiling_usd_by_event_id`, including zero ceilings for blocked events. The helper can reduce these ceilings but cannot authenticate a supplied freeze or detect omitted prior state; the external runtime must enforce that continuity. Durable earnings-freeze/refresh integration is not implemented; the separate order/position ledger does exist.

See `python scripts/earnings_plan.py --help` and `python scripts/earnings_plan.py --demo`. Supply private inputs outside Git with `--input` and preserve their provenance. Outputs support DEMO or SHADOW prepared packets, always with no broker writes or execution approval. The synthetic --demo fixture remains SHADOW. DEMO packets bind the effective policy and require sourced TA/stress/round-trip-cost and current strategy-risk facts; see [alignment](DEMO_ALIGNMENT_2026-10-10.md).

New earnings evidence requires its own frozen hypothesis, costs, chronological evaluation and prospective extension under the [research loop](RESEARCH_LOOP.md). Compare with matched earnings-night controls; do not claim the weekly engine or an attractive vendor grade validates earnings profitability. The workshop schemas remain provisional.
