"""Rebuild the eight-page Revision 11 report from current result files.

The Revision 10 section order, three evidence cards, strategy figure and
seven-step workflow are retained. Values come from the corrected ledgers.
"""
from __future__ import annotations

import hashlib
import json
import math
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
from report_layout import Report, LEFT, WIDTH, H, NAVY, GREY, TEAL, PALE, TAN, clean

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT/'results'
PDF=ROOT/'Research_Report_Rev11.pdf'


def pct(x,d=2):
    return 'n/a' if x is None or not np.isfinite(float(x)) else f'{float(x)*100:+.{d}f}%'


def pp(x,d=2):
    return 'n/a' if x is None or not np.isfinite(float(x)) else f'{float(x):+.{d}f}%'


def num(x,d=2):
    return 'n/a' if x is None or not np.isfinite(float(x)) else f'{float(x):.{d}f}'


def foundation_figure():
    import matplotlib
    # Figure 1 customizes global plotting defaults; isolate this figure so
    # full-pipeline and standalone report rebuilds produce the same artifact.
    with matplotlib.rc_context(rc=matplotlib.rcParamsDefault):
        return _foundation_figure()


def _foundation_figure():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import PercentFormatter
    fig,axes=plt.subplots(1,2,figsize=(10.6,3.0))
    for name,label,color in [('baseline','Avellaneda-Lee','#315e9d'),('buffer','Wider no-trade region','#ba842d')]:
        f=pd.read_csv(RESULTS/f'daily_{name}.csv',index_col=0,parse_dates=True)
        for ax,start,end,title in [(axes[0],'2023-01-01','2025-12-31','Full research window'),(axes[1],'2025-01-01','2025-12-31','2025 evaluation')]:
            x=f.loc[start:end,'net_return']
            ax.plot(x.index,(1+x).cumprod()-1,label=label,color=color,lw=1.5)
            ax.set_title(title,fontsize=10,loc='left');ax.yaxis.set_major_formatter(PercentFormatter(1))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6 if ax is axes[0] else 3))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
            ax.set_xlim(x.index.min(),x.index.max())
            ax.grid(alpha=.16);ax.tick_params(labelsize=8)
            ax.spines[['top','right']].set_visible(False)
    axes[0].legend(fontsize=8,frameon=False,loc='lower left')
    for ax in axes:ax.set_ylabel('Net cumulative return',fontsize=8)
    fig.tight_layout(pad=1.4)
    path=RESULTS/'foundation_equity.png';fig.savefig(path,dpi=170);plt.close(fig)
    return path


def main():
    metrics=pd.read_csv(RESULTS/'metrics.csv').set_index(['strategy','period'])
    b=metrics.loc[('baseline','out_of_sample')];v=metrics.loc[('buffer','out_of_sample')]
    summary=json.loads((RESULTS/'rev6/summary.json').read_text())
    evidence=json.loads((RESULTS/'evidence/summary.json').read_text(encoding='utf8'))
    mechanical=json.loads((RESULTS/'overnight_summary.json').read_text())
    flow,research=evidence['flow'],evidence['research']
    cov=pd.read_csv(RESULTS/'evidence/coverage.csv')
    cov5=cov[(cov.period=='2025')&(cov.window_sessions==5)].iloc[0]
    info=pd.read_csv(RESULTS/'evidence/flow_information.csv')
    info25=info[info.period=='2025']
    s=summary['headline'];g=s['2025'];combined=s['combined']
    bench=pd.DataFrame(summary['benchmarks']['rows'])
    checks=summary['adversarial_checks']
    head=pd.read_csv(RESULTS/'rev6/headline_daily.csv',index_col=0,parse_dates=True).loc[:'2025-12-31']
    on=pd.read_csv(RESULTS/'overnight_daily.csv',index_col=0,parse_dates=True).loc[:'2025-12-31']
    from overnight_strategy_v6 import newey_west_t
    onr=on['basket_overnight_gross'].dropna()
    onmean=float(onr.mean()*1e4);ont=newey_west_t(onr.to_numpy())
    fund=foundation_figure()
    r=Report(PDF)

    # Page 1 - title, abstract, thesis and the original three evidence cards.
    r.label('ETORO ACTIVE TRADING TRACK - RESEARCH REPORT - REVISION 11')
    r.c.setFont('Times-Bold',19);r.c.setFillColor(__import__('reportlab').lib.colors.HexColor(NAVY))
    r.c.drawString(LEFT,H-r.y-19,'Trading the night, informed by database');r.y+=29
    r.text('A replicated model, a tested enhancement, and an overnight strategy with a proposed database overlay.',size=11.0,bold=True,color=GREY,gap=10)
    r.text('Prepared by Sondre Flateraaker | 7 September 2026 | Simulated research; no live orders',size=7.4,color=GREY,gap=12)
    r.box('ABSTRACT',
        f'This submission has three layers. The replication is the Avellaneda-Lee sector-ETF residual model. In 2025 its annualized return is <b>{pct(b.gross_annual_return)} gross and {pct(b.annual_return)} net</b> at the mandated 20 bp per side. The wider no-trade region cuts average daily turnover from {num(b.average_daily_turnover*100,1)}% to {num(v.average_daily_turnover*100,1)}%, with net return {pct(v.annual_return)}. It improves implementation, but does not establish a profitable baseline.<br/><br/>'
        f'The original idea begins with that cost diagnosis. A related overnight-momentum test earns {num(onmean)} bp per session across {len(onr)} sessions (Newey-West t = {num(ont)}). I then trade fewer nights: a prior-data dispersion gate and overnight-persistence rank select ten names from a momentum pool. <b>The gated strategy returns {pp(g["net40_pct"])} in 2025 at the required 40 bp round trip.</b> Hypothetical 6/9 bp round trips give {pp(g["net6_pct"])} / {pp(g["net9_pct"])}. These lower costs are sensitivity assumptions, not measured fills.<br/><br/>'
        f'The proposed selection overlay uses options flow and {research["records"]:,} dated research notes. The notes begin in 2026 and cannot explain the historical result. The mechanical strategy is tested here; the database overlay and execution economics remain forward hypotheses. Revisions correct accounting and data handling without retuning the strategy.',size=9.05)
    r.heading('1','The thesis, and whose it is')
    r.text('A trading day has two halves, and they are economically different. Between the close and next open, prices respond to overnight news, overseas markets and order imbalances. During the regular session, liquidity and opportunities to rebalance are different. Less time trading does not necessarily mean less risk: gaps cannot be exited at a chosen price.')
    r.text('Lou, Polk and Skouras (2019) document a division between overnight and intraday expected returns, including momentum earned overnight. I did not discover that effect. This is a related test on a later, fixed universe, followed by a cost audit and a proposed database-assisted selection process. It is not an exact replication of every portfolio in their paper.')
    r.heading('2','Three elements: the reason, the evidence, the window')
    r.text('The proposed chain is simple: identify a checkable company thesis, look for corroborating flow, and test whether selective overnight exposure captures useful returns. Each link must earn its place in the evidence.',gap=8)
    r.cards([
        ('1 - THE REASON','Hidden Angles','A dated research note about a company and why it matters. A forward decision must add a verified source, a catalyst and a measurable falsifier.'),
        ('2 - THE EVIDENCE','Options flow','Ask-side, at least $100k premium, quantity above reported open interest, 180-730 days to expiry. A possible corroborating signal; not proof of trader identity or an informed opening position.'),
        ('3 - THE WINDOW','Close to next open','The historical overnight window motivates the experiment. Official prints are reference prices; actual broker fills and costs must be measured.')])
    r.end_page()

    # Page 2 - retain sections 3-5 and make their required evidence explicit.
    r.text('Read left to right: a documented reason, corroborating evidence, and a defined holding window. Flow and a thesis can coexist without proving that the market has mispriced the stock. "Not priced in" must mean a dated claim that can be checked against an identifiable source.',size=9.05)
    r.heading('3','Data, and what each layer can support')
    r.table(['Layer','Evidence and limits'],[
        ['Prices','All 200 supplied equities and 11 sector ETFs; 3 Jan 2023-31 Dec 2025, plus SOFR. Raw files are preserved. Eight verified split discontinuities are adjusted; missing quotes are not used for fills. Development: 2023-24. The inspected 2025 evaluation is exploratory, not claimed untouched.'],
        ['Options flow',f'{flow["qualifying_records"]:,} qualifying records across both sheets ({flow["distinct_symbols"]:,} symbols), before sector-source restrictions; {flow["first_qualifying_date"]} to {flow["last_qualifying_date"]}. A five-session, lagged score covers a median {num(cov5.median_names_with_lagged_score,0)} of 200 names in 2025. Snapshot completeness and availability are unverified.'],
        ['Research notes',f'{research["records"]:,} notes, {research["distinct_ticker_tokens"]:,} distinct ticker labels; {research["first_date"]} to {research["last_date"]}. Zero overlap with historical prices. The export has no original-source links or explicit falsifier fields.']],[90,WIDTH-90],size=8.35)
    r.heading('4','Required replication: Avellaneda-Lee')
    r.text('For each stock and sector ETF, a rolling 60-session regression produces cumulative residuals. An AR(1) fit retains mean-reversion times below 30 trading days. Entry is long below -1.25 and short above +1.25; exits are -0.50 and +0.75. Stocks target +/-1% of NAV with beta-scaled ETF hedges and a 200% gross cap.',size=9.05)
    r.text('Signals formed at close t-1 execute at close t and first earn t-to-t+1 returns. Trades use available quotes and drifted holdings. Fees are 20 bp per executed side; short financing accrues SOFR + 0.50% over actual calendar days, ACT/360. Price returns omit cash dividends; cash earns zero.',size=9.05)
    r.label('TABLE 1 - REPLICATION AND ENHANCEMENT; ANNUALIZED RETURNS; 20 BP PER SIDE')
    rows=[]
    for name,label in [('baseline','Replication'),('buffer','Wider no-trade region')]:
        for per,pl in [('development','2023-24'),('out_of_sample','2025')]:
            m=metrics.loc[(name,per)]
            rows.append([label,pl,pct(m.gross_annual_return),pct(m.annual_return),num(m.sharpe),pct(m.max_drawdown,1),f'{m.average_daily_turnover*100:.1f}%'])
    r.table(['Specification','Period','Gross','Net','Sharpe','Max DD','Turnover'],rows,[133,48,64,65,53,60,WIDTH-423],size=7.9)
    r.text(f'2025 net positive-day rate: {b.positive_day_rate*100:.1f}% baseline / {v.positive_day_rate*100:.1f}% enhanced; average stock holding spell: {b.average_holding_days:.1f} / {v.average_holding_days:.1f} sessions. Hit rate means profitable nonzero portfolio-return days, not individual winning trades. Figure 3 shows the equity curves.',size=8.35)
    r.text('OLS residuals sum to zero, so the endpoint score reduces to the negative equilibrium mean divided by equilibrium volatility. Centering that mean across stocks follows the paper; it is not a deviation. These features are retained.',size=8.8)
    d=metrics.loc[('baseline','development')]
    r.text(f'Qualitative check: baseline annualized gross return is {pct(d.gross_annual_return)} in development and {pct(b.gross_annual_return)} in 2025. The full-window curve illustrates period dependence; two samples do not establish a causal regime effect or persistent decay.',size=8.35)
    r.heading('5','Tested enhancement: a wider no-trade region')
    sensitivity=pd.read_csv(RESULTS/'cost_sensitivity.csv')
    pairs=[]
    for cost in [10,20,30,40]:
        ss=sensitivity[sensitivity.cost_bps==cost].set_index('strategy')
        pairs.append(f'{cost}: {pct(ss.loc["baseline","annual_return"],1)} / {pct(ss.loc["buffer","annual_return"],1)}')
    r.text(f'New entries require an extra 0.50 s-score; aggregate hedge target changes below 2% of NAV are buffered, with exits unchanged. In 2025, Sharpe improves by {v.sharpe-b.sharpe:.2f}, maximum drawdown by {(v.max_drawdown-b.max_drawdown)*100:.1f} percentage points, and turnover falls {(1-v.average_daily_turnover/b.average_daily_turnover)*100:.0f}%. Average gross exposure also falls from {b.average_gross_exposure*100:.0f}% to {v.average_gross_exposure*100:.0f}%, so not all drawdown reduction is an execution gain.',size=8.8)
    r.text('Cost sensitivity (bp per side: baseline / enhanced annualized net): '+ '; '.join(pairs)+'. The improvement reduces losses; it does not establish net alpha.',size=8.25)
    r.end_page()

    # Page 3 - the original idea and its two result tables.
    r.box('THE BRIDGE TO THE ORIGINAL IDEA','The baseline motivates an implementation question: can fewer round trips make a weak economic margin more useful? The original experiment changes both the holding window and the exposure. It is a long-only momentum extension, not a market-neutral replica; the required residual model remains the foundation.',fill=TAN,size=9.0)
    r.heading('6','Original idea: testing whether the overnight trade can pay')
    dayret=on.loc['2025','basket_next_daytime_gross']
    r.text(f'Each session, rank all 200 names by 60-day return known at the prior close, buy the top ten equally at the close and sell at the next executable open. In 2025 the mechanical test earns {pct(mechanical["top10_gross_total_return"])} gross, versus {pct(mechanical["spy_gross_total_return"])} for SPY overnight on matched available dates. The same names earn {pct((1+dayret).prod()-1)} in the following intraday windows.')
    r.text(f'Across {len(onr)} historical sessions, its gross mean is {onmean:.2f} bp (Newey-West t = {ont:.2f}). The 2025 arithmetic break-even is about {mechanical["arithmetic_break_even_cost_per_side_bp"]:.2f} bp per side. Raw return is not alpha: the book carries equity and momentum risk, and the assignment cost exceeds its average overnight margin.')
    r.text('<b>Trade fewer nights.</b> The gate requires dispersion of 60-day momentum to exceed its own expanding median, using prior information and at least 252 observations. Within the top 30 momentum names, the ranker is the trailing 20-session mean overnight return. The top ten are selected. This is a theory-motivated rule evaluated after a broad search; it is not a fresh confirmatory test.')
    r.label('TABLE 2 - GATED TEN-NAME STRATEGY; TOTAL RETURNS; COSTS PER ROUND TRIP')
    rows=[]
    for per,pl in [('2023-24','Development'),('2025','2025 evaluation'),('combined','Combined')]:
        z=s[per]
        rows.append([pl,str(z.get('traded_nights',z['n'])),num(z.get('gross_bp_per_active_night',z['bp'])),num(z['t']),pp(z['net6_pct']),pp(z['net9_pct']),pp(z['net40_pct'])])
    r.table(['Period','Entries','Gross bp / active day','t, daily','Net 6 bp','Net 9 bp','Net 40 bp'],rows,[108,46,75,48,72,72,WIDTH-421],size=8.0)
    r.text('The 40-bp case is the required 20 bp on each execution side. Lower costs are hypothetical. Returns and daily t statistics include cash sessions; fees are charged on executed entry/exit notional. An unavailable exit retains the position and blocks new entries until it can close.',size=8.25)
    r.label('TABLE 3 - COMMON-CALENDAR COMPARISON; COMBINED GATED-STRATEGY SPAN')
    brow=[]
    for z in summary['benchmarks']['rows']:
        name=z['series'].replace('Strategy, ','Strategy ').replace('round trip','RT').replace('same calendar span','matched span').replace('same traded nights','matched nights')
        if name.startswith('SPY'): name += ', gross'
        brow.append([name,pp(z['total_pct']),pp(z['annualised_pct']),num(z['sharpe']),pp(z['max_drawdown_pct'],1)])
    r.table(['Exposure / cost assumption','Total','Per year','Sharpe','Max DD'],brow,[228,74,74,59,WIDTH-435],size=7.85)
    r.text('The common span is 4 April 2024-31 December 2025. All comparisons retain inactive sessions and use zero cash interest. SPY is a price-return benchmark; dividends are omitted. Matched-night SPY is shown with the cost convention stated in its label. Annualization and date boundaries are shared. Calendar holding hours are not a sufficient measure of risk.',size=8.15)
    r.text('Read the mandatory-cost result first: this strategy does not clear the assignment friction. The lower-cost cases motivate measuring execution, not replacing the required result. The concentration surface in Figure 1 is exploratory evidence; stronger performance in fewer names also means more concentrated risk.',size=9.0)
    r.end_page()

    # Page 4 - retain Figure 1 and the two original note examples.
    r.image(RESULTS/'rev6/fig1_strategy.png')
    r.text('Figure 1. Left: corrected gated-strategy equity, including the mandatory 40-bp round trip. Right: gross breadth diagnostics. Portfolios below ten names exceed the proposed 10% name cap when fully invested and are concentration diagnostics only. Smoothness is not proof against overfitting.',size=7.5,gap=7)
    r.heading('7','Database inferencing: the reason, recorded in the notes')
    r.text(f'The gate says when; the proposed overlay asks which selected names have a verifiable reason to retain them. {research["conviction_names_in_universe"]} names in the current conviction sheet intersect the fixed universe. The two original examples are retained below. Their notes and the 4 September flow snapshot have different dates. Snapshot totals are as labeled in the supplied workbook, not verified holdings or the historical flow filter.',size=8.8)
    for ex in evidence['examples']:
        cv=ex['conviction_snapshot'];ticker=ex['ticker']
        title=f'{ticker} | NOTE {ex["note_date"]} | {ex["angle_records_on_file"]} NOTES ON FILE'
        snap=f'<b>4 Sep snapshot:</b> bullish ${cv["bull_premium"]/1e6:.1f}m; bearish ${cv["bear_premium"]/1e6:.1f}m; "New Position $" ${cv["new_position_dollars_as_labeled"]/1e6:.1f}m. Those labels do not establish an unhedged opening trade.'
        angle=escape(ex['report_angle_excerpt']);why=escape(ex['report_why_excerpt'])
        interp=('The question is whether stronger bookings eventually offset transition costs. A strong selling season and near-term earnings contraction can both be true.' if ticker=='CI' else 'The note proposes a longer-term upside scenario and a power-capacity constraint. Verify the underlying analyst source and consensus comparison before using it. The snapshot carries a newer note; this is the retained August example.')
        r.box(title,f'{snap}<br/><br/><b>HIDDEN ANGLE</b><br/>"{angle}"<br/><br/><b>WHY IT MATTERS</b><br/>"{why}"<br/><br/>{interp}',size=7.85)
        r.text(f'Source: candidate workbook, Hidden Angles Database row {ex["source_row"]}; conviction snapshot row {cv["row"]}. Underlying publisher/document not linked in the export.',size=7.0,color=GREY,gap=5)
    r.end_page()

    # Page 5 - retain the limitations page, remove defensive inference.
    r.box('WHY THIS IS A PROCESS','A dated note is a starting point. Before a forward decision, the analyst pass must attach the original source, a specific catalyst and a measurable falsifier. The historical export does not supply every required field. Unsupported notes are excluded; the missing details are not invented.',fill=TAN,size=9.0)
    r.heading('8','What this result is not')
    search=summary['search']
    r.text(f'The final surface contains {search["cells"]} gate/ranker/breadth configurations; earlier exploration spans several hundred choices. The headline rules were retained for this correction pass, not selected anew. Because 2025 was inspected, it is an exploratory evaluation. A clean continuation or forward test is still required.')
    r.text(f'The pooled daily gross t statistic is {num(combined["t"])}. A 48-comparison normal approximation has a threshold near 3.28, but it does not cover the entire project search, establish net significance or validate model selection. The breadth and gate sensitivities are checks on fragility, not a substitute for a held-out result.')
    conc=checks['concentration'];boot=checks['bootstrap_2025_net9']
    r.text(f'<b>Concentration matters.</b> At 9 bp, removing the best five observations changes development from {pp(conc["2023-24"]["net9_all_pct"])} to {pp(conc["2023-24"]["net9_ex_best5_pct"])} and 2025 from {pp(conc["2025"]["net9_all_pct"])} to {pp(conc["2025"]["net9_ex_best5_pct"])}. {checks["months_positive"]} calendar months are positive. The 2025 ten-session block bootstrap gives a 95% interval of [{pp(boot["ci95_pct"][0],1)}, {pp(boot["ci95_pct"][1],1)}]; it is conditional on the observed sample and selected rule.')
    r.text('Overnight exposure is exposed to news jumps. It is not right-skewed by construction, and a concentration stress test remains informative. A 12% drawdown review can stop new trading after a loss; it cannot guarantee an exit price or cap an overnight gap.')
    r.heading('9','What this submission cannot establish, and why')
    spread=info25.bullish_minus_bearish_bp
    spread_text=f'{spread.min():+.2f} to {spread.max():+.2f} bp' if spread.notna().any() else 'unavailable'
    r.table(['Layer','Limit and consequence'],[
        ['1  Flow',f'The median five-session 2025 coverage is {num(cov5.median_names_with_lagged_score,0)} of 200. Bullish-minus-bearish overnight means range {spread_text} over 5/20/60-session scores. Coverage is sparse and snapshot provenance is incomplete; no reliable incremental edge is established.'],
        ['2  Research','The notes start in February 2026, after the price window. No historical research-overlay result exists. H2 is a proposed forward comparison, conditional on source verification.'],
        ['3  Significance',f'{s["2023-24"].get("traded_nights",s["2023-24"]["n"])} development entries support the gated rule. Broad exploration and a short evaluation limit inference. A causal signal does not make a selected rule out of sample.'],
        ['4  Execution','6/9 bp round-trip costs are hypothetical. Auction studies are benchmarks, not this account\'s fills. Official prints, commissions, spreads and route eligibility require verification.'],
        ['5  Capacity','No calibrated impact or capacity model is supplied. ADV participation is a planning constraint, not proof of a profitable account size.'],
        ['6  Universe / data','All supplied names are retained. This frozen universe is not a historical membership database, so survivorship cannot be ruled out. Verified splits are handled; dividends and unavailable broker/borrow history remain limitations.']],[90,WIDTH-90],size=8.15)
    r.end_page()

    # Page 6 - execution assumptions, original trade log and forward rules.
    r.heading('10','Execution, cost and capacity')
    r.text('Everything turns on the cost of entering and exiting. Goyal, Jegadeesh and Wu (2026) estimate large-cap closing-auction impact of 4.5 bp on NYSE and 10.2 bp on Nasdaq at 1% of ADV; opening auctions are less liquid. These are single-leg impact estimates. They do not validate a 6-9 bp total round trip.')
    r.text('eToro offers extended-hours trading for eligible instruments, but availability, spread and liquidity differ from the regular session. A premarket exit is a separate execution experiment; it is not substituted for the next-open return in this backtest. Confirm broker routing and submit before its actual cutoff; ordinary NYSE MOC/LOC cutoff is 15:50 ET, with limited exceptions.')
    r.text('<b>Capacity.</b> A 10%-of-NAV position at 1% of a $500m daily dollar volume implies $50m NAV arithmetically. That is a participation illustration, not a cost-viable capacity estimate. The relevant constraint is the least liquid name and exit venue. Measure both legs before claiming capacity.')
    r.label('TABLE 4 - RECORD FOR EACH FORWARD DECISION AND EXECUTION')
    r.table(['Entry leg','Exit leg'],[
        ['Decision timestamp; evidence cutoff and source IDs','Scheduled and actual exit; delay or rejected order'],
        ['Quoted spread; broker route and verified cutoff','Quoted spread; participation as a share of ADV'],
        ['Fill versus official close; fees and order size','Fill versus official open; fees and actual round trip']],[WIDTH/2,WIDTH/2],size=8.25)
    r.text('Report the mandated 20 bp per side and observed costs separately. The proposed review threshold is average round-trip cost above 13 bp over 20 traded nights. It is a conservative operating rule retained from the original plan, not a proven break-even estimate.',size=8.8)
    r.heading('11','The proposed live portfolio')
    r.table(['Rule','Forward procedure'],[
        ['Universe','Same fixed 200 for the assignment. A future broker-eligible subset is declared in advance and evaluated separately.'],
        ['Gate and roster','Prior-data expanding dispersion gate; top 30 by 60-day momentum, top ten by 20-session overnight persistence. No retuning within the test.'],
        ['Overlay / sizing','Verified note plus positive qualifying net bullish premium over five prior sessions. May remove only. Retained names keep at most 10% of NAV; removed weight stays cash. Maximum 100% gross, no leverage or shorts.'],
        ['Exit / missing data','Target the next executable open. If an exit is unavailable, retain and monitor it; block new entries. No assumption that a stop can cap gap losses.'],
        ['Review triggers','Suspend new orders and review at 12% drawdown, or above 13 bp average round-trip cost over 20 traded nights. These forward triggers are not added to the historical strategy.']],[90,WIDTH-90],size=8.2)
    r.box('FORWARD PROTOCOL - FREEZE BEFORE THE FIRST DECISION',
        '<b>H1.</b> Over 252 traded sessions, the mechanical roster returns positively after observed costs. A negative estimate at review or a risk suspension rejects the operating plan.<br/><b>H2.</b> The overlay improves paired daily net returns versus the same mechanical roster. Also report an exposure-matched control: keeping fewer names changes cash exposure as well as selection. The packaged protocol and prompt must be hashed before the first decision.',fill='#edf6f3',accent=TEAL,size=8.7)
    r.heading('12','How this runs, night after night')
    r.text('The intended bot applies deterministic rules before the verified order cutoff, then records evidence and execution. The repository supplies the research prototype and analyst protocol. Broker execution and verified live evidence capture remain to be built.',size=9.0)
    r.end_page()

    # Page 7 - retain the original workflow illustration and three boundaries.
    r.diagram()
    r.text('Figure 2. The retained nightly loop. Steps 1-4 are implemented research code; the analyst and broker steps are the proposed forward process. The analyst can only shorten a fixed roster. The dashed return path permits rule review at session 252, with reasons logged before changes.',size=7.5)
    r.text('<b>It reviews evidence; it does not forecast prices.</b> By the time the analyst prompt runs, the mechanical gate and ten-name roster are fixed. It checks the dated note, original source, catalyst, falsifier and qualifying flow. Notes are treated as evidence to verify, not instructions to follow. The supplied export lacks some prerequisites, so it cannot by itself authorize a retained name.')
    r.text('<b>It can only subtract.</b> A name outside the mechanical roster cannot enter however persuasive its story. If five names remain, each retains its 10% maximum and the rest is cash. There is no forced minimum or replacement search. H2 tests the complete policy and an exposure-matched control; it does not attribute every difference to stock selection.')
    r.text('<b>It does not learn inside the window.</b> The prompt and rules are fixed and hashed before the first forward decision. Observations accumulate in the log, not in the selection rule. Review occurs after 252 traded sessions unless a risk trigger suspends the experiment. Any revised rule begins a new evaluation.')
    r.text('The planned bot reports each morning what was bought, what was sold, any pending exit, and the difference between the actual fill and the reference print. That log is the test of execution economics. Paper fills help test operations; they do not establish achievable live cost. No live order system is claimed in this submission.')
    r.heading('13','Risks, and reproducibility')
    r.text('<b>Execution:</b> the mandatory-cost strategy loses; low-cost cases remain assumptions.<br/><b>Gaps and missing exits:</b> concentrated overnight holdings can lose more than a historical drawdown or review threshold.<br/><b>Regime:</b> the roster is long recent winners and can suffer a momentum reversal; it is not market neutral.<br/><b>Selection:</b> the evaluated rules were inspected during research and the proprietary overlay remains unproven.',size=9.0)
    r.text('For the required long/short baseline, eToro short stock orders are generally CFDs and availability depends on instrument, account and jurisdiction. No live shortability file was supplied: all 200 stocks and ETF hedge legs need daily verification. An unavailable leg suppresses its proposed pair rather than leaving an intentional unhedged trade. The assignment assumption that all names are shortable is not a claim about live access.',size=8.4)
    r.end_page()

    # Page 8 - reproducibility, conclusion, foundation chart and references.
    r.text('<b>Reproduce:</b> install the pinned requirements and run <b>python run.py</b>. It rebuilds the corrected models, evidence summaries, figures and this PDF from packaged inputs. Tests cover timing, split handling, financing, missing quotes, portfolio accounting and continuation behavior. The README explains the ledger and data limitations. The analyst prompt and forward protocol are included; no broker connection is included.',size=8.9)
    r.heading('14','Conclusion')
    r.text(f'The replicated strategy and turnover enhancement both lose after the mandated costs. The overnight extension also fails that test: {pp(g["net40_pct"])} in 2025. Lower-cost sensitivities remain interesting, but they establish neither attainable fills nor an independent database edge. The useful result is a clear cost boundary and a specific experiment to test, not a profitability claim.')
    r.text('I would keep the mechanical rule fixed, verify point-in-time sources and broker eligibility, and collect an execution log before expanding the project. With more time, I would add dividend and short-availability history, an exposure-matched ablation and a clean continuation test. The database overlay earns a place only if it improves that forward comparison.')
    r.image(fund)
    r.text('Figure 3. Required baseline and enhancement equity, with transaction costs and calendar-day financing. Left: the full supplied window. Right: 2025 cumulative net return, reset to zero. The different paths and period metrics describe sample dependence; they do not by themselves identify a stable profitable regime.',size=7.6,gap=8)
    r.heading('','References and source notes')
    refs=[
        '<b>Avellaneda and Lee (2010).</b> Statistical Arbitrage in the U.S. Equities Market. Quantitative Finance 10(7), 761-782. <link href="https://math.nyu.edu/inmemoriam/avellaneda/AvellanedaLeeStatArb20090616.pdf" color="#193650">Author manuscript, Appendix equation 22</link>.',
        '<b>Lou, Polk and Skouras (2019).</b> A Tug of War: Overnight versus Intraday Expected Returns. Journal of Financial Economics 134(1), 192-213. DOI: 10.1016/j.jfineco.2019.03.011.',
        '<b>Goyal, Jegadeesh and Wu (2026).</b> Price Impact in Closing Auctions, Opening Auctions, and Continuous Markets. JFQA. DOI: 10.1017/S0022109026102592; Table 3 and opening-auction analysis.',
        '<b>Execution sources.</b> <link href="https://www.nyse.com/trade/auctions" color="#193650">NYSE auction rules</link>; <link href="https://www.etoro.com/trading/short-selling/" color="#193650">eToro short selling</link> and <link href="https://www.etoro.com/trading/fees/" color="#193650">fees</link>. Accessed 7 September 2026. Broker-specific availability remains unverified.',
        '<b>Data.</b> Supplied eToro candidate prices/universe/SOFR; Nasdaq SPY price data. Verified issuer split dates and links are recorded in corporate_actions.csv. Candidate-provided flow-114.xlsx and Hidden Angles export through 4 September 2026; original-source links are absent from the note database. Workbook hashes, row references and reproducible counts are in the evidence outputs.']
    for item in refs:r.text(item,size=7.35,gap=5,leading=9.6)
    bounds=r.finish()
    manifest={'report':'Research_Report_Rev11.pdf','pages':8,'content_bounds':bounds,
              'method':'Values read from generated result files; no hand-entered backtest headline.',
              'report_input_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [RESULTS/'metrics.csv',RESULTS/'rev6/summary.json',RESULTS/'evidence/summary.json',ROOT/'analyst_prompt.md',ROOT/'forward_protocol.json']}}
    (RESULTS/'report_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Rebuilt {PDF.name}: 8 pages.')
    return PDF


if __name__=='__main__':
    main()
