# Microstructure entry metrics and financial ML validation

**Research audited: November 10, 2026 (Asia/Kolkata); original research: November 9, 2026.** This is a selective, primary-source research map, not an exhaustive list of strategies, investment advice, or evidence that any strategy is profitable. Equations describe research features and model assumptions; implementation gates below are **proposed safeguards**, not measured TradeGuard results. A daily-bar recommendation system must not claim HFT capability: daily OHLCV cannot reconstruct the event ordering, displayed queues, or execution opportunities studied in order-book research.[11][41]

## Horizon map: these are not interchangeable entry signals

| Primary result | Target / clock | What it does not establish |
|---|---|---|
| Gould–Bonart queue imbalance | Direction of the next midpoint change; random event time | A fixed-second return or a costed executable trade.[12] |
| Stoikov microprice slides | Limit over future midpoint-change events; examples compare 1-, 5-, and 10-minute midpoint changes | An uncalibrated weighted midpoint as a universal sub-millisecond fair value.[2] |
| Cont–Kukanov–Stoikov OFI | Same-window price impact on a 10-second grid in the inspected preprint | A forecast known at the beginning of that window.[11] |
| Avellaneda–Stoikov quoting | Inventory control to a finite terminal horizon under modeled arrivals | A universally optimal entry rule or an adverse-selection-free market maker.[4] |
| Gu–Kelly–Xiu ML | Monthly individual-equity excess returns | HFT execution alpha or free access to the original CRSP-based sample.[39] |

## 1. Queue imbalance, spread, depth, and microprice

Let best bid/ask prices be \(b_t,a_t\), displayed sizes \(B_t,A_t\), midpoint \(m_t=(a_t+b_t)/2\), and full spread \(s_t=a_t-b_t\). The normalized queue-imbalance feature is:[12]

\[
I_t=\frac{B_t-A_t}{B_t+A_t},\qquad
w_t=\frac{B_t}{B_t+A_t}=\frac{1+I_t}{2}.
\]

Positive imbalance means more displayed best-bid than best-ask size; it is not signed executed volume.[12] Gould–Bonart find next-midpoint-direction predictive information, stronger for their large-tick stocks than small-tick stocks; this does not establish executable profits.[12]

The **queue-weighted midpoint**, weighting each price by the *opposite-side* size, is:[2]

\[
m_t^{w}=\frac{a_tB_t+b_tA_t}{B_t+A_t}
       =m_t+\frac{s_t}{2}I_t.
\]

A heavy bid pulls this proxy toward the ask.[2] Here `I` is normalized to `[-1,1]`, whereas the Stoikov slides call `w` (in `[0,1]`) imbalance; the slides also use a half-spread convention in their assumptions. Do not copy state bins or spread coefficients between these notations unchanged.[2] This weighted proxy must be distinguished from Stoikov's calibrated microprice construction:[2]

\[
\mu_t=\lim_{k\to\infty}E[m_{\tau_k}\mid\mathcal F_t]
     =m_t+g(w_t,s_t),
\]

Here \(\tau_k\) are successive future midpoint-change times.[2] Existence and martingale properties require the model's assumptions; transition probabilities and the adjustment \(g\) must be estimated.[2] The weighted midpoint coincides only in special models.[2] Do not label the uncalibrated weighted formula a validated fair value or a guaranteed forecast.

**Proposed feature checks:** track spread in ticks and basis points, \(10^4s_t/m_t\); side-specific cumulative depth \(D_t^{b/a}(K)=\sum_{j=1}^{K}q_{t,j}^{b/a}\); and order-size/depth ratios. Reject missing/zero total size and stale/crossed quotes. Large displayed depth can disappear; size alone does not identify executable liquidity. These checks extend the state-based queue perspective, not a published universal entry threshold.[41]

## 2. Cont order-flow imbalance: explanation is not prediction

For consecutive best-quote events \(n-1,n\), Cont–Kukanov–Stoikov define:[11]

\[
\begin{aligned}
e_n={}&\mathbf1_{b_n\ge b_{n-1}}B_n
      -\mathbf1_{b_n\le b_{n-1}}B_{n-1}\\
     &-\mathbf1_{a_n\le a_{n-1}}A_n
      +\mathbf1_{a_n\ge a_{n-1}}A_{n-1},\\
\mathrm{OFI}_{(u,v]}={}&\sum_{u<t_n\le v}e_n.
\end{aligned}
\]

At unchanged prices this reduces to bid-size change minus ask-size change.[11] It includes limit submissions, cancellations, and market-order effects, not just buyer-minus-seller trade volume.[11] Their short-interval relationship is approximately:[11]

\[
\Delta m_{(u,v]}=\beta\,\mathrm{OFI}_{(u,v]}+\epsilon,
\qquad \beta\propto1/\text{depth}.
\]

The paper measures midpoint changes in ticks; with dollar midpoint `m` here, the fitted slope `β` must absorb tick-size conversion. OFI has the units of displayed size, not the bounded units of queue imbalance.[11] This is chiefly **contemporaneous price-impact explanation**: OFI and price change share the interval.[11] Using its completed OFI to claim an entry at \(u\) is look-ahead. A forecast must instead fix features at decision time \(t\), target a later interval, and survive execution delay and costs. The paper's explanatory fit is not a tradable forecast score.[11]

**Proposed prediction baseline:** fit a logistic next-midpoint-direction model, for example `p(up|x_t)=1/(1+exp(−(θ₀+θ'x_t)))`, using only states known at decision time. Gould–Bonart provide the direction-prediction research anchor, not validated coefficients or a universal imbalance entry threshold.[12] Evaluate calibration, log loss/Brier score and a prevalence-only baseline on later dates; `p(up)>0.5` is not a net-return or fill-probability test.

## 3. Execution economics: no free HFT lunch

**Proposed aggressive-entry gate:** before interpreting midpoint-direction accuracy as a trade, compare expected signed future-midpoint movement with the entry half-spread, fees and impact. That is only an entry-to-future-mid markout test; realizable round-trip P&L must also pay the executable exit cost and account for the distribution of move sizes and elapsed event time. This is a proposed diagnostic, not a measured alpha claim.

**Proposed economic gate:** budget market-data feeds, connectivity, hosting/co-location, compute, compliance, and operational downtime as well as trading costs. Gross spread capture is not a business case. A strategy must retain an edge after competitive queue allocation, realistic fills, and adverse markouts; this report establishes no such edge.[14][41]

For a passive order, a useful **research decomposition**, not a theorem or calibrated strategy, is

\[
E[\Pi\mid x]\approx P(F\mid x)\,
 E[d(m_{t+h}-p_{\rm fill})-c_{\rm exec}\mid F,x]
 -c_{\rm hedge}-c_{\rm inventory},
\]

where \(F\) denotes fill, \(d=+1\) for buying and \(-1\) for selling, and all costs use consistent per-share units. The fill-conditioned markout already contains spread capture and adverse selection: subtracting adverse selection again would double count it. Inventory and hedge terms must likewise avoid overlap. Queue-reactive research explicitly models execution probabilities and warns that cancellation-location assumptions can overestimate fills.[41]

- **Fill probability:** condition on price priority, queue ahead, order size, cancellations, partial fills, and time-to-cancel. A price touching the limit is not proof of a fill.[41]
- **Adverse selection and latency:** proposed diagnostics are signed post-fill markouts at fixed horizons and actual feed-to-decision, submit-to-acknowledgement, and cancel delays. Budish–Cramton–Shim show why stale quotes and speed competition matter; their argument is not a promise of retail latency-arbitrage profits.[14]
- **Inventory:** Avellaneda–Stoikov's stylized reservation price is \(r_t=m_t-q_t\gamma\sigma^2(T-t)\).[4] Long inventory lowers the reservation price; risk aversion \(\gamma\), **absolute dollar-price** variance rate \(\sigma^2\), and remaining horizon determine the shift.[4] Do not substitute annualized percentage-return volatility into this arithmetic-Brownian-price formula without transforming the model and keeping time units consistent. Brownian prices and modeled arrival intensities make this a model-dependent control rule, not a plug-in optimal quote.[4]

**Proposed prerequisites:** sequenced tick/book updates; synchronized exchange and receive timestamps; trades, additions, modifications, cancellations; venue matching rules; fees/rebates; realistic latency and fill replay; and inventory limits. Order-level identifiers help reconstruct priority; aggregated depth needs explicit queue assumptions. Daily bars cannot substitute for this evidence.[41]

**Conduct boundary:** no spoofing, layering, wash trading, or fabricated depth. The cited CFTC Q&A quotes an intent-to-cancel spoofing definition under CEA section 4c(a)(5), in the scope of registered entities such as DCMs/SEFs; it is not a complete or current equity-venue rule survey.[27] The Q&A does not itself document a blanket good-faith-cancellation safe harbor. Observing imbalance is not permission to manufacture it.

## 4. ETF NAV arbitrage is constrained

A diagnostic premium is \(\delta_t=P_t/\widehat{\mathrm{NAV}}_t-1\), but estimated basket value must be contemporaneous and hedgeable. Creation/redemption access is not an ordinary retail trade: authorized participants intermediate the primary-market mechanism.[34] Pan–Zeng show, for corporate-bond ETFs, how liquidity mismatch and AP inventory conflicts can limit or distort arbitrage.[34]

**Proposed gate:** compare the executable premium with basket/ETF spreads, market impact, creation/redemption charges, financing, borrow, hedge/basis risk, and settlement constraints. Verify current fund basket terms and valuation timestamps, especially when underlying markets are closed. A premium to yesterday's published NAV is not itself a riskless HFT entry. These are due-diligence requirements, not a measured arbitrage bound.[34]

## 5. What financial ML evidence establishes

Gu–Kelly–Xiu compare linear, regularized, tree, and neural methods for stock-return/risk-premium prediction.[39] Their monthly asset-pricing setting and gains from nonlinear predictor interactions do not demonstrate intraday execution alpha.[39] Their NBER revision separates chronologically ordered training, validation, and test samples, using 1957–1974, 1975–1986, and 1987–2016 initially, respectively, with annual updating.[39] Use this as methodological motivation, not an expected return for today's assets.

## 6. Proposed chronological, purged walk-forward protocol

López de Prado identifies overlapping labels and serial conditionality as leakage sources; chronological ordering alone does not eliminate them.[40] For TradeGuard research, adopt the following explicit protocol:

1. **Specify the experiment first:** universe, decision timestamp, holding horizon, target, trading calendar, retraining cadence, costs, benchmark, and trial budget. Split by timestamp across assets rather than randomly shuffling ticker rows. Keep a final untouched chronological test period.
2. **Track label availability:** each sample has feature cutoff \(t_i\), label interval \([t_i,u_i]\), and actual availability time \(v_i\). At fit cutoff \(T\), require \(v_i\le T\), not merely \(t_i<T\). A five-session forward return is unavailable until its final price arrives; revised fundamentals require original release vintages.
3. **Purge overlaps:** remove candidate training observations whose label intervals overlap held-out label intervals. Enforce this in inner tuning folds as well as outer evaluation. Do not call ordinary shuffled K-fold or a fixed row gap automatically purged.[40]
4. **Choose gaps by information timing:** an embargo in two-sided purged CV removes nearby *post-test* training observations susceptible to residual dependence. Strict past-only walk-forward has no future-side training inside that fold; use a justified boundary gap, label-maturity rule, and any needed release-lag buffer instead. An arbitrary percentage embargo does not prove independence.[40]
5. **Fit preprocessing only on training data:** scaler means/variances, imputers, clipping thresholds, feature selection, PCA, and calibration belong inside each fold. Apply their frozen transforms to validation/test. Fit microprice transitions and fill-probability models without future events too. Scikit-learn explicitly warns against fitting preprocessing on test data.[16]
6. **Tune without test reuse:** nested chronological validation selects hyperparameters and entry thresholds; outer folds estimate performance. Log every feature/model/universe trial. Repeatedly inspecting a holdout effectively makes it a selection set.[7][8]
7. **Use point-in-time data:** membership, delisted securities and returns, corporate actions, publication lags, revisions, and missingness need documented treatment. Today's surviving constituents must not stand in for the historical investable universe. These are proposed dataset acceptance tests, not claims that downloaded examples satisfy them.
8. **Simulate feasible actions:** next executable price after the signal, turnover, spread, commissions, impact, borrow/funding, position caps, rejected orders, and capacity. Stress costs and latency rather than assuming every prediction can be monetized.

## 7. Selection risk, benchmarks, and acceptance

Bailey–López de Prado's **Deflated Sharpe Ratio (DSR)** adjusts a Sharpe assessment for selection across trials and non-normal returns.[7] Its probabilistic-Sharpe form is:[7]

\[
\mathrm{DSR}=\Phi\!\left(
\frac{(\widehat{SR}-SR_0)\sqrt{T_{\rm obs}-1}}
{\sqrt{1-\widehat\gamma_3\widehat{SR}
 +\tfrac{\widehat\gamma_4-1}{4}\widehat{SR}^{\,2}}}\right),
\]

Here \(T_{\rm obs}\) is return-sample length, \(\gamma_3\) skewness, \(\gamma_4\) **raw** kurtosis, and \(SR_0\) the expected maximum under the multiple-trial null.[7] Distinguish sample length from effective independent trial count \(M\). Under the paper's zero-mean null, its expected-maximum approximation for \(M>1\) is:[7]

\[
SR_0\approx\sigma_{SR}\left[(1-\gamma_E)\Phi^{-1}(1-1/M)
 +\gamma_E\Phi^{-1}(1-1/(Me))\right],
\]

where \(\sigma_{SR}\) is the across-trial SD of consistently sampled Sharpe estimates and \(\gamma_E\) is Euler's constant. The single-trial zero-null benchmark is zero; do not evaluate the multi-trial quantile approximation at \(M=1\). Effective trial count and dependence assumptions need justification, not the raw number of strongly correlated parameter combinations.[7] Use nonannualized Sharpe inputs at the return-sampling frequency; this formula is not automatically valid for dependent/overlapping return observations. DSR is not the probability of future profitability.

Bailey–Borwein–López de Prado–Zhu's **PBO** uses combinatorially symmetric cross-validation to estimate how often the in-sample winner ranks below the out-of-sample median.[8] It needs the candidate-strategy performance matrix, not just the winner.[8] It is a selection diagnostic, not a substitute for chronological deployment testing; dependence and regime change remain limitations.

**Proposed acceptance report:** compare cash/no-trade, an appropriate buy-and-hold total-return benchmark, and simple momentum/linear predictors on identical dates, universe, and costs. Include net returns, drawdown, turnover, exposure, fold stability, cost break-even, and the full trial count. Use dependence-aware uncertainty estimates, such as time-block bootstrap intervals; overlapping labels must not be counted as independent observations. Separate gross predictability, executable net performance, and paper-trading evidence. No universal Sharpe, imbalance, or ML score guarantees an entry.

## 8. Optional primary implementation references

- **Microsoft Qlib:** quantitative ML research pipeline; official repository license is **MIT**.[43][17]
- **QuantConnect LEAN:** algorithmic research/backtesting engine; **Apache-2.0**.[42][18]
- **Nixtla MLforecast:** lag-feature/time-series ML tooling; **Apache-2.0**.[44][19]

Licenses were re-fetched from each official `LICENSE` file **at the full commit SHA recorded in `sources_microstructure.json`**, with response SHA-256 checksums and matching pinned README files. These projects are references, not installed dependencies or validated TradeGuard integrations. Their code licenses do not automatically grant market-data rights or make a backtest leakage-free. Source IDs are local to this report's ledger and must not be merged numerically with the equity ledger. See `AUDIT.md` for scope and verification counts.

## Sources

[2] https://www.ma.imperial.ac.uk/~ajacquie/Gatheral60/Slides/Gatheral60%20-%20Stoikov.pdf — The Micro-Price
[4] https://math.nyu.edu/inmemoriam/avellaneda/HighFrequencyTrading.pdf — High-frequency trading in a limit order book
[7] https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf — The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality
[8] https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf — The Probability of Backtest Overfitting
[11] https://arxiv.org/pdf/1011.6402v3 — The price impact of order book events
[12] https://arxiv.org/pdf/1512.03492v1 — Queue Imbalance as a One-Tick-Ahead Price Predictor in a Limit Order Book
[14] https://www.cramton.umd.edu/papers2015-2019/budish-cramton-shim-hft-frequent-batch-auctions.pdf — The High-Frequency Trading Arms Race: Frequent Batch Auctions as a Market Design Response
[16] https://scikit-learn.org/stable/common_pitfalls.html — Common pitfalls and recommended practices
[17] https://raw.githubusercontent.com/microsoft/qlib/54355232463878d2eebb91fe0ee5fa7fa1f5976c/LICENSE — Qlib LICENSE
[18] https://raw.githubusercontent.com/QuantConnect/Lean/3afb212b30eff5e73013b5130887a95bf9e4cb4b/LICENSE — LEAN LICENSE
[19] https://raw.githubusercontent.com/Nixtla/mlforecast/16cabe15f701197491384bd3108d6c6ac1edaff7/LICENSE — MLforecast LICENSE
[27] https://www.cftc.gov/sites/default/files/idc/groups/public/%40newsroom/documents/file/dtpinterpretiveorder_qa.pdf — Questions and Answers: Interpretive Guidance and Policy Statement on Disruptive Practices
[34] https://conference.nber.org/confer/2017/LTAMs17/Pan_Zeng.pdf — ETF Arbitrage under Liquidity Mismatch
[39] https://nber.org/system/files/working_papers/w25398/w25398.pdf — Empirical Asset Pricing via Machine Learning
[40] https://www.quantresearch.org/Innovations.htm — Innovations
[41] https://arxiv.org/pdf/1312.0563v2 — Simulating and analyzing order book data: The queue-reactive model
[42] https://raw.githubusercontent.com/QuantConnect/Lean/3afb212b30eff5e73013b5130887a95bf9e4cb4b/readme.md — LEAN repository readme
[43] https://raw.githubusercontent.com/microsoft/qlib/54355232463878d2eebb91fe0ee5fa7fa1f5976c/README.md — Qlib repository README
[44] https://raw.githubusercontent.com/Nixtla/mlforecast/16cabe15f701197491384bd3108d6c6ac1edaff7/README.md — MLforecast repository README
