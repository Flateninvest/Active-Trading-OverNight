# Overnight momentum backtest — corrected research run

## Objective

Test whether ten high-momentum stocks bought at the close and sold at the next regular-session open outperform SPY over the identical overnight window.

## Retained rule

- Universe: 200 names in the fixed supplied equity universe. The external membership snapshot does not filter this test.
- Momentum: trailing 60 trading-day close-to-close return.
- Timing safeguard: the signal is lagged 1 trading day, so a close-t entry uses information only through close t-1.
- Selection: top 10 names, at most 10% each at entry. Entry fees are reserved from capital.
- Entry/exit: official close t to official open t+1.
- Cost: 20 bp per side, or 40 bp per overnight round trip.
- Benchmark: SPY close t to open t+1.
- Evaluation: calendar 2025; 2023-2024 is development context. Added official prices produce separate continuation results without requiring new SPY observations.
- Missing quotes: unavailable entry leaves cash; unavailable next-open exit remains held and blocks all new entries until the first observed later open. Daily marks use observed close or the last available mark.
- Cash interest: zero; all annualized risk statistics use official-session returns including idle cash dates. Periods are assigned to the next-session valuation date, preserving 2025 results when later prices are added.

## 2025 result

| Measure | Top 10 gross | Top 10 net | SPY gross | Top 10 minus SPY gross |
|---|---:|---:|---:|---:|
| Total return | +21.35% | -55.36% | +7.06% | +12.76% |
| Average daily return | +0.08% | -0.32% | +0.03% | +0.05% |
| Win rate | 55.6% | 30.4% | 59.6% | 50.8% |
| Sharpe (zero rate) | 1.38 | -5.36 | 0.64 | 0.94 |
| Maximum drawdown | -10.85% | -56.83% | -16.17% | -14.37% |

The same selected stocks produced -18.49% gross when measured from the next open to that session's close. This decomposition indicates whether the observed return was concentrated overnight or during regular hours.

Most frequently selected names in 2025: WBD (113), SEDG (102), AVGO (98), NEM (97), AMD (93), MU (88), TSLA (72), ORCL (70), LRCX (69), INTC (68).

## Cost sensitivity

The average gross edge was 8.19 basis points per night. Its arithmetic break-even cost was therefore approximately 4.09 basis points per side.

| Assumed cost per side | 2025 total return | Sharpe |
|---:|---:|---:|
| 0 bp | +21.35% | 1.38 |
| 1 bp | +15.44% | 1.04 |
| 2.5 bp | +7.09% | 0.54 |
| 4 bp | -0.64% | 0.03 |
| 5 bp | -5.49% | -0.31 |
| 10 bp | -26.39% | -1.99 |
| 20 bp | -55.36% | -5.36 |

## Initial interpretation

The stock-selection rule beat SPY before costs. It was not profitable after the prescribed round-trip cost. This is a mechanical hypothesis test, not evidence that a live order would receive the official closing or opening print.

## Limitations

- Fixed supplied universe, not a survivorship-free historical universe; verified raw stock splits are corrected by the shared price loader.
- Stock OHLC excludes cash dividends, so ex-dividend overnight total returns are understated for long positions.
- Official daily open and close prices omit bid-ask spread and opening-auction slippage; the prescribed 20 bp per side is the implementation allowance.
- Earnings dates and overnight news are not included in this first mechanical run.
- SPY OHLC is an external benchmark downloaded from Nasdaq and stored with source metadata.
