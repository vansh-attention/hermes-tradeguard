# Equity and ETF strategy/metrics library

**Research audited: 2026-11-10 (Asia/Kolkata); original research: 2026-11-09. Scope: broad, deliberately NOT exhaustive.** This is a source-backed design library for a **read-only** recommendation/research module, not a tested strategy, personalized advice, return promise, or order authorization. No current securities are ranked here. Shorting, leverage and event portfolios below are research hypotheses, not runtime capabilities.

**Evidence convention.** Citations identify primary research/methodologies; formulas, thresholds and entry/exit rules marked **H** are proposed, unvalidated implementation choices, not faithful reproductions of the cited portfolios. Historical cross-sectional premia do not establish a profitable signal today. Exact URLs, publication/version dates, access dates and repository licenses are in `sources_equity.json`; numbered links follow below.

## Coverage and status

| Major family | Research scope / horizon | Evidence boundary |
|---|---|---|
| Market exposure and size | Buy-and-hold benchmark; SMB size factor; monthly/annual formation | Factor definitions, not a claim that smaller stocks always outperform.[1] |
| Fundamentals | Value, profitability/quality, investment/growth, accruals; months to years | Original factor constructions differ from the proposed screens.[1][3][39] |
| Price and defensive | Cross-sectional momentum, own-return trend, short/long reversal, low risk; monthly or longer | Different lookbacks, long/short exposure and financing assumptions.[6][7][10] |
| Income and ETFs | Sustainable dividends, strategic allocation/rotation, portfolio risk, tracking, costs, concentration | Index/issuer methodology and proposed diagnostics, not fund-selection alpha.[11][29][41] |
| Relative value and events | Distance pairs versus cointegration extension; deal arbitrage; days to months | Separate borrow, leg-risk, failure-probability and timing requirements.[14][15] |
| Event-level microstructure and ML | Queue imbalance, OFI, execution economics; event time through intraday | See `microstructure_ml_validation.md`; daily bars do not validate an HFT strategy. |

**Status:** the families above are researched, not automatically implemented, replicated or performance-validated. This documentation audit does not certify the plugin's runtime behavior. Buy-and-hold, cash and equal-weight portfolios are proposed comparison baselines, not universally suitable allocations. Options overlays, tax optimization and a comprehensive anomaly inventory are outside scope.

## 1. Data contract before scores

**Proposed contract:** start with liquid US common stocks and plain-vanilla ETFs; other listings and leveraged, inverse or complex fund structures require separate validation. Every observation carries security/share-class ID, currency, source, availability timestamp, fiscal period, adjustment policy, missingness and horizon. Use split-adjusted prices for price features and a dividend-reinvested total-return index `X` for total-return features; never mix them silently. `t` is the latest completed month; decisions using its close become actionable only afterward.

The SEC describes unauthenticated submissions and XBRL financial-statement APIs; this audit checked its page **as archived on 2026-10-29**, not the blocked live page.[16] **Required controls:** reconstruct information available at each decision date using accession/filing timestamps, original versus amended filings, taxonomy, units and share class. A latest company-facts response is not automatically a point-in-time backtest. Obtain survivorship-free histories including delistings, corporate actions and historical universe membership separately; verify data entitlements. With month-end levels indexed through `t`, require endpoints back to `t−12` for skipped-month momentum and `t−60` for long reversal (13 and 61 monthly levels including `t`); five-year annual growth needs both endpoints five years apart. Mark shorter histories unavailable rather than filling with zeros.

**Version/dividend control:** French switched US research-return production from CRSP FIZ to CIZ beginning with the January 2025 release. FIZ monthly returns reinvest dividends at month-end; CIZ compounds daily returns with reinvestment on ex-dates. French also documents historical data revisions and archive cuts.[42] **H safeguard:** store vendor release, download date, return convention and a content checksum; do not splice vintages or compare a historical paper to a revised factor file as if the inputs were identical. Public access does not establish redistribution rights.

## 2. Fundamental families

**Market/size/value distinctions.** French's `Rm−Rf` is market excess return, SMB averages small-minus-big portfolios, and HML is a size-balanced high-minus-low book-to-market factor, not a generic low-P/E screen or an unhedged value basket.[1] **H size feature:** use log market capitalization only after liquidity/capacity gates; do not assume a monotonic small-cap return premium. **Valuation H metrics:** `B/M = common book equity / market equity`; earnings yield `NI_TTM / market equity`; free-cash-flow yield `(CFO − capex)_TTM / market equity`, with capex normalized to a **positive cash investment** rather than blindly subtracting a provider's signed outflow; `EV/EBITDA` with an explicitly defined enterprise-value bridge. Missing, zero or economically invalid denominators are unavailable, not extreme bargains. Rank within comparable sectors; avoid applying industrial-company ratios unchanged to banks/REITs.

**Profitability/quality.** French's six-portfolio detail page still says to divide operating profits by book equity.[2] However, its explicit August 2018 revision notice adds **minority interest**: current-vintage operating profitability is `(revenue − COGS − SG&A − interest expense) / (book equity + minority interest)`, using the last fiscal year ending in `t−1` for June formation. Use that versioned notice rather than silently reproducing the stale detail-page denominator.[42] Gross profitability research instead measures `(revenue − COGS) / assets`.[3] The cited October 2013 QMJ draft combines profitability, growth, safety and payout; this version must not be conflated with later definitions.[39] **H metrics:** ROA, ROE, margins, interest coverage and low leverage; normalize robustly within sector and retain component explanations rather than double-counting closely related ratios.

**Growth and investment.** QMJ measures historical improvements in profitability, while French CMA distinguishes conservative from aggressive investment.[39][1] **H metrics:** positive-base revenue/EPS CAGR `(v_t/v_(t−k))^(1/k) − 1`, change in gross profitability, and asset growth `A_t/A_(t−1) − 1`. Negative bases invalidate CAGR; acquisitions, dilution and cyclicality require flags. High growth alone is not evidence of cheapness or attractive expected return.

**Accruals.** Low accruals are a quality component in the versioned QMJ research.[39] **H cash-flow proxy:** `accrual = (NI − CFO) / mean(total assets)`; prefer lower values only alongside sustainable profits and cash conversion. This is not an exact replication of QMJ's balance-sheet accrual construction. Require aligned reporting periods; inspect acquisitions, working-capital seasonality and accounting-policy changes.

**H entry/exit for fundamental baskets:** monthly, select the top 20% of an eligible sector-relative value/quality composite; retain until below the top 40%, thesis invalidation or stale filings. Quarterly accounting updates, sector caps and turnover penalties are candidate controls. Value traps, overstated earnings, expensive quality and prolonged factor underperformance are explicit stress scenarios, not exceptions to hide.

## 3. Price, defensive and income families

**Cross-sectional momentum.** French Mom uses prior months 2–12, skipping the most recent month; the original is a size-balanced, value-weighted winner-minus-loser factor, not a long-only top quintile.[6] **H:** for a decision after month `t`, `M = X_(t−1)/X_(t−12) − 1` compounds 11 monthly returns and omits month `t`; select top-quintile liquid stocks monthly and exit below the top 40%. Test abrupt rebounds, crowded exits and turnover sensitivity. Require dividend/corporate-action-consistent history and exclude unavailable lookbacks.

**Trend/time-series momentum.** Faber's published illustration uses monthly dividend-inclusive total-return series and a 10-month SMA, same-close fills, a 90-day T-bill cash proxy, and excludes taxes, commissions and slippage.[37] Moskowitz–Ooi–Pedersen study own **excess** returns and volatility-scaled long/short futures/forward exposure, not a validated long-only equity-ETF SMA implementation. Their futures returns and spot/roll decomposition must not be replaced with an unadjusted front-contract price series.[7] **H data gate:** retain contract selection/roll, collateral/funding and ETF fee/distribution conventions separately; a continuous chart is not automatically an investable total-return history. **H:** `SMA_10 = mean(X_t,…,X_(t−9))`; enter/retain when `X_t > SMA_10`, otherwise allocate that sleeve to a documented cash proxy; equality retains prior state. Unlike the original same-close illustration, evaluate next-observable-price fills and cash returns. Stress whipsaws, gaps and delayed re-entry.

**Reversals/mean reversion.** French short reversal uses the previous month's return; long reversal uses months 13–60, with loser-minus-winner, size-balanced portfolios.[8][9] For a decision after month `t`, the comparable raw long-reversal lookback is `X_(t−12)/X_(t−60) − 1` (48 monthly returns); a reversal score negates it. This is not minus the full trailing five-year return. **H:** short-reversal score `−r_t`; buy a liquid bottom-decile basket for one month, then reassess. Separately test `z = (log P − rolling mean(log P))/rolling SD(log P)`: enter below −2, exit near 0, time out or invalidate at −3. These thresholds are not empirical guarantees; RSI/Bollinger-style variants need independent validation. Distinguish liquidity bounce from lasting deterioration, and stress spreads/market impact.

**Low volatility/beta.** BAB research concerns beta-managed long/short portfolios under leverage constraints, not a claim that any low-vol ETF reproduces BAB.[10] **H:** `vol = SD(daily returns)√252`; `beta = Cov(r_i,r_m)/Var(r_m)`; select a sector-capped low-volatility quintile, reassess monthly, exit above the median or when risk constraints fail. Beta, total volatility and residual volatility are different features. Test rate sensitivity, changing correlations and estimation-window instability.

**Dividends.** The **August 2025** MSCI methodology combines yield with sustainability, persistence, quality and price-performance screens. Its historical DPS persistence check excludes negative five-year growth, but does **not** exclude missing five-year growth; the stricter missing-data abstention proposed here is not an index replication.[11] **H:** trailing cash-dividend yield `DPS_TTM/P`, payout `dividends/NI` only for positive earnings, cash-flow coverage and positive-base DPS growth. Enter a quarterly sustainable-yield basket; exit on a cut, coverage deterioration or eligibility failure. A TTM implementation differs from MSCI's country-specific dividend annualization. Inspect return of capital, special distributions, withholding taxes and yield traps; distributions are not additional total return.

## 4. ETF allocation and instrument diagnostics

**H rotation/allocation:** define a diversified, investable asset-class universe before testing; monthly rank 3/6/12-month total returns, retain top `k` only above the cash-proxy return and a trend filter, and exit on rank/filter failure. Faber provides the trend-allocation research anchor, not evidence for this combined rotation recipe.[37] Compare buy-and-hold, equal-weight and periodic rebalancing before adding optimization.

**H portfolio mathematics:** compare inverse-volatility weights `w_i ∝ 1/vol_i` with constrained minimum variance `min w'Σw`, subject to `∑_i w_i=1`, `0≤w_i≤cap` (here `Σ` is the covariance matrix, not the summation sign). Fractional variance contribution is `RC_i = w_i(Σw)_i/(w'Σw)` (summing to one when portfolio variance is positive); absolute volatility contribution is `w_i(Σw)_i/√(w'Σw)`. Equal-risk contribution targets equal contributions, and inverse-volatility is not generally the same thing. Study shrinkage/HRP and downside-risk alternatives rather than assuming a sample covariance optimizer is stable.[35][21] Cash/bond sleeves still require duration, credit, currency and liquidity checks; enforce feasible constraints before ranking portfolios.

**NAV premium/discount:** `g = market price/NAV − 1`, with matching valuation timestamps and a stated market-price convention. Issuer research explains that stale underlying closes and valuation methodologies can create optical deviations; AP creation/redemption is distinct from a retail investor's trade.[40] **H gate:** flag unusually wide historical deviations and spreads; withhold an entry recommendation until timestamps and executable costs are verified. A discount alone is not a buy signal; an indicative NAV is not a guaranteed executable fair value.

**Tracking:** `TD_H = total NAV return_H − benchmark total return_H`; `TE = SD(r_NAV − r_index)√A`, where `A` matches sampling frequency. Tracking difference measures level of deviation; tracking error measures its variability.[29] **H reporting convention:** distinguish cumulative-period TD from the single-period active-return series used for TE. State the sample SD convention and frequency; square-root annualization is a reporting convention, not an independence guarantee for serially correlated returns. Compare identical currency, hedging and gross/net dividend conventions. Expense drag, sampling, cash, taxes and securities lending must not be mislabeled alpha; compare market-price and NAV outcomes separately.[29]

**Costs/holdings/concentration:** issuer due diligence emphasizes product structure, holdings, overlap, replication and total costs.[41] **H diagnostics:** bid–ask spread `(ask−bid)/mid`, quoted/depth liquidity, expense ratio, AUM/closure flags, turnover and distribution taxation; `HHI=Σh_i²`, effective holdings `1/HHI`, top-10 weight, sector/country caps, and overlap `Σmin(h_i,a,h_i,b)`. These simple concentration formulas assume normalized long-only holdings; derivatives require exposure-aware look-through. For holding period `h` years, estimate entry+exit commissions, spread/slippage and `expense_ratio × h`; do not subtract expenses again from already net-of-fee fund returns. Reassess eligibility when spreads, tracking or exposure breaches persist; low expense ratio alone cannot establish best execution or portfolio suitability.

## 5. Advanced research only

**Statistical arbitrage/pairs.** Gatev and coauthors match normalized-price paths by distance; that is not a cointegration test.[14] **H extension:** fit `s_t = log P_A − α − β log P_B` on formation-only data; require residual stationarity and stable, positive hedge estimates; use `z_s = (s−mean(s))/SD(s)`. At `z_s>2`, hypothesize short A/long B; reverse below −2; exit at `|z_s|<0.5`, invalidate at 3.5, a time limit or structural break. For short-A magnitude `n_A`, a locally exposure-matched hedge is `n_B = β n_A P_A/P_B`, not a bare β share count; this log-spread hedge is local, not an exact finite-price-change identity, and rebalancing adds costs. Factor-residual baskets are a separate extension. Require synchronized quotes, dividends, borrow availability/cost, corporate actions and leg-risk estimates; correlation is insufficient and structural breaks defeat convergence.

**Event-driven/merger arbitrage.** Original research documents asymmetric deal-failure losses and greater market dependence in downturns.[15] **H:** for cash offer `C`, current target price `P`, failure price `B` and independently estimated completion probability `q`, expected simple return is `q(C/P−1)+(1−q)(B/P−1)−costs`. A spread is not an independent probability estimate. This simple-return expression requires consistent payoff horizons or explicit discounting and financing; it is not an annualized return. Enter only if a probability interval and completion-time scenarios survive costs; exit on completion, cancellation, revised terms or thesis failure. Stock deals need an exchange-ratio hedge. Require timestamped deal filings, financing/regulatory conditions and credible break-price scenarios. Earnings drift, buybacks, index changes and spinoffs remain separate, unvalidated extensions.

## 6. Recommendation/ML design and evidence gate

**Proposed architecture:** eligibility/data gates → explainable features → within-universe ranks → cost/risk-aware portfolio comparison → evidence card. Never blend stocks and ETFs into an unexplained universal BUY score. Abstain on stale, unlicensed or insufficient inputs; separate signal strength, uncertainty, liquidity and portfolio fit. Missing account/horizon/tax constraints prevent personalized suitability claims.

Gu–Kelly–Xiu compare nonlinear methods for asset-pricing prediction; their historical findings do not establish a deployed model's performance.[17] **H progression:** fixed equal-weight feature baseline, regularized linear model, then gradient boosting; predict horizon-specific excess returns or ranks, not fabricated confidence percentages. Prefer a small orthogonal feature set before neural/RL complexity.

**Proposed release gate:** date-grouped rolling train/validation/test splits; embargo/purge overlapping forward labels; preprocessing fitted only on training data; nested tuning, an untouched final period and an experiment ledger. Multiple backtest trials create selection risk; a single holdout is not a universal cure.[18] Report net-of-cost performance against investable baselines, Spearman rank IC, turnover, exposure, drawdown `min(W_t/max_(u≤t)W_u−1)`, annualized Sharpe `mean(r−rf)/SD(r−rf)√A`, and tail-loss scenarios with uncertainty. Test regimes, delistings, cost shocks and parameter perturbations; shadow/paper evaluation precedes any claim of useful recommendations. No current evidence here warrants profitability claims.

## 7. Open-source implementations worth studying

Licenses below were checked against actual upstream license files; exact inspected commits and pinned license URLs are recorded in the JSON. These are **study candidates**, not installed dependencies or endorsements; no implementation code was copied.

| Project | License observed | Study target / boundary |
|---|---|---|
| PyPortfolioOpt | MIT | Mean–variance, shrinkage, Black–Litterman and HRP; unstable inputs remain a concern.[35] |
| Riskfolio-Lib | BSD-3-Clause | Risk measures, risk parity and constrained optimization; compare assumptions and solver behavior.[21] |
| statsmodels | BSD-3-Clause | Econometric diagnostics, OLS and time-series testing for research.[22] |
| scikit-learn | BSD-3-Clause | Reproducible preprocessing, regularization and model selection; design finance-aware splits explicitly.[23] |
| Microsoft Qlib | MIT | Feature/dataset and research-workflow organization; audit data availability and leakage.[24] |
| QuantConnect LEAN | Apache-2.0 | Event-driven simulation, corporate-action/data normalization; study offline only, not broker integration.[25] |
| bt | MIT | Portfolio-level allocation/rebalancing simulations.[26] |
| backtrader | GPL-3.0-or-later in inspected source header; GPLv3 license text | Event-driven backtesting reference; review per-file license compatibility before reuse.[27] |

Review per-file/dependency/data licenses separately; an engine's license does not license its market feeds. Repository accessibility does not establish maintenance quality, correctness or strategy validity.

**Research limitations:** this is a library, not an exhaustive anomaly survey, reproducibility study or investment recommendation. On 2026-11-10, the live SEC page returned HTTP 403; a dated Wayback copy of the SEC's own page was checked instead. The native search/extraction backend failed; live search used its fallback providers and primary documents were fetched directly. No separately callable `web.run` tool was exposed in this subagent session. See `AUDIT.md` for measured citation/license checks and remaining gaps. No runtime files, trading settings or orders were changed.

## Sources

[1] https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5_factors_2x3.html — French: Fama/French 5 Factors (2x3)
[2] https://mba.tuck.dartmouth.edu/pages/Faculty/ken.french/Data_Library/six_portfolios_me_op.html — French: 6 Portfolios Formed on Size and Operating Profitability
[3] https://www.nber.org/papers/w15940 — Novy-Marx: The Other Side of Value: Good Growth and the Gross Profitability Premium
[6] https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor.html — French: Monthly Momentum Factor (Mom)
[7] https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum — Moskowitz, Ooi and Pedersen: Time Series Momentum; inspected author full text: https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf (Published Journal of Financial Economics 104 (2012), 228–250, author university copy.)
[8] https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_st_rev_factor.html — French: Monthly Short-Term Reversal Factor (ST_Rev)
[9] https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_lt_rev_factor.html — French: Monthly Long-Term Reversal Factor (LT_Rev)
[10] https://www.aqr.com/Insights/Research/Journal-Article/Betting-Against-Beta — Frazzini and Pedersen: Betting Against Beta; inspected author full text: https://w4.stern.nyu.edu/facdir/lpederse/papers/BettingAgainstBeta.pdf (Author university copy explicitly dated May 10, 2013; distinct from the 2014 AQR journal-article page.)
[11] https://www.msci.com/indexes/documents/methodology/3_MSCI_High_Dividend_Yield_Indexes_Methodology_20250829.pdf — MSCI High Dividend Yield Indexes Methodology
[14] https://www.nber.org/papers/w7032 — Gatev, Goetzmann and Rouwenhorst: Pairs Trading: Performance of a Relative Value Arbitrage Rule
[15] https://www.aqr.com/Insights/Research/Journal-Article/Characteristics-of-Risk-and-Return-in-Risk-Arbitrage — Mitchell and Pulvino: Characteristics of Risk and Return in Risk Arbitrage
[16] https://www.sec.gov/search-filings/edgar-application-programming-interfaces — SEC: EDGAR Application Programming Interfaces (APIs); primary page as archived 2026-10-29T11:00:36Z, retrieved https://web.archive.org/web/20261029110036id_/https://www.sec.gov/search-filings/edgar-application-programming-interfaces
[17] https://www.aqr.com/insights/research/journal-article/empirical-asset-pricing-via-machine-learning — Gu, Kelly and Xiu: Empirical Asset Pricing via Machine Learning
[18] https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf — Bailey, Borwein, Lopez de Prado and Zhu: The Probability of Backtest Overfitting
[21] https://github.com/dcajasn/Riskfolio-Lib — dcajasn/Riskfolio-Lib official repository and license
[22] https://github.com/statsmodels/statsmodels — statsmodels/statsmodels official repository and license
[23] https://github.com/scikit-learn/scikit-learn — scikit-learn/scikit-learn official repository and license
[24] https://github.com/microsoft/qlib — microsoft/qlib official repository and license
[25] https://github.com/QuantConnect/Lean — QuantConnect/Lean official repository and license
[26] https://github.com/pmorissette/bt — pmorissette/bt official repository and license
[27] https://github.com/mementum/backtrader — mementum/backtrader official repository and license
[29] https://www.vanguard.co.uk/professional/vanguard-365/investment-knowledge/etf-knowledge/what-affects-index-tracking — Vanguard: What affects index tracking?
[35] https://github.com/PyPortfolio/PyPortfolioOpt — PyPortfolio/PyPortfolioOpt official repository and license
[37] https://mebfaber.com/2013/06/07/qtaa-paper-update-manage-your-risk-4 — Faber: QTAA Paper Update: Manage Your Risk 4/10
[39] https://images.aqr.com/-/media/AQR/Documents/Insights/Working-Papers/Quality-Minus-Junk.pdf — Asness, Frazzini and Pedersen: Quality Minus Junk, October 2013 draft
[40] https://www.ishares.com/us/investor-education/etf-education/etf-premiums-and-discounts — iShares: All about ETPs: Premiums and discounts
[41] https://www.ssga.com/us/en/institutional/insights/a-etf-due-diligence-checklist — State Street: An ETF due diligence checklist
[42] https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html — French: Data Library — return vintages and operating-profitability revision notices
