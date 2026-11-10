# TradeGuard: equity/ETF research and recommendation component

**Research snapshot verified November 10, 2026.** This is a working, read-only Hermes plugin, not a proven alpha service. Current installation and distribution instructions are in `README.md`; publication is separate from installed-profile activation and reviewed catalog admission. Source-backed strategy research, working calculations and successful tests are different from validated predictive returns.

## 1. Delivered boundary

- **21 selectable research families**, non-exhaustive, each with horizon, mathematics, proposed rule, data requirements, failure modes, source IDs and implementation status.
- **47 cited source records**, 46 distinct primary-source URLs, 109 body citation occurrences. One source record uses a labeled dated archive of the SEC's own page after the live page was blocked.
- **9 distinct repository/commit license pins**, with exact upstream license bytes re-fetched and hash-checked. Software licenses do not grant market-data rights. No third-party trading-engine implementation was copied or installed; public papers/source are sufficient without binary reverse-engineering.
- Seven native Hermes tools, ticker-only and interactive CLI entrypoints, offline analysis/ranking, opt-in historical-data retrieval, and a causal experimental ML evaluation path. No order adapter, brokerage login, portfolio allocation or active HFT system.

## 2. Major strategy map

The research library covers value/quality, profitability and growth/investment, accruals, cross-sectional momentum, time-series trend, short/long reversal, pullback mean reversion, defensive volatility/beta, sustainable dividends, ETF structure and rotation, risk parity/minimum variance, pairs/statistical arbitrage, event/deal analysis, ML return prediction, queue imbalance, order flow, inventory-based market making and AP-level ETF arbitrage.

These are not all implemented portfolios. `tradeguard_strategy_catalog` distinguishes **heuristic_screen**, **feature_only**, **experimental_baseline** and **researched_only**. The initial recommendation screens are trend, value+quality, mean reversion (exploratory and excluded from the aggregate) and ETF structure. Cost-aware portfolio optimization, sector-neutral factor baskets, pairs/event strategies and HFT quoting remain researched-only.

Primary anchors include the French factor-library definitions and revision notices; Novy-Marx profitability; versioned QMJ/BAB research; Faber's allocation illustration; Gu–Kelly–Xiu asset-pricing ML; Cont–Kukanov–Stoikov OFI; Gould–Bonart queue imbalance; Stoikov microprice; Avellaneda–Stoikov inventory quoting; and ETF issuer/regulator material. Exact locators and claim limitations are in the two JSON source ledgers, not inferred from search snippets. Source IDs are report-local: `eq:*` and `micro:*` are different namespaces.

## 3. What the engine measures

### Fundamental investing — annual/as-reported, not invented TTM

- Earnings yield = net income / defensible observed market cap.
- Free-cash-flow yield = (operating cash flow − positive-outflow capex) / market cap.
- ROE = net income / ending equity; ROA = net income / ending assets.
- Revenue growth = current revenue / comparable prior revenue − 1.
- Operating/gross margins, interest coverage and net debt/assets.
- Cash-flow accrual proxy = (net income − operating cash flow) / mean(current, prior assets).

These are explicit implementation definitions, not exact replications of every published profitability factor. Positive denominators, aligned periods and units are required. Bank/REIT accounting, DCF, custom XBRL taxonomy, automatic TTM reconstruction and full sector-neutral valuation are not implemented. An annual report may omit later quarters, so it is not silently called current TTM.

### Technical/swing observations — completed daily data

SMA20/50/200, EMA12/26 and MACD difference; Wilder-seeded RSI14 and ATR14; 21/63/252-observation price returns; skipped-recent-period momentum; sample 20-return volatility × sqrt(252); whole-history drawdown and mean 20-observation quoted-currency turnover. Raw/split-only price returns exclude unprovided dividends. MACD signal-line/histogram, intraday VWAP and breadth/earnings sentiment are not implemented.

### ETF diagnostics

Dated expense ratio, same-date closing price/NAV deviation, disclosed holdings coverage, observed/full HHI and top-ten weight. Partial holdings are not renormalized to 100%. Full concentration is unavailable for partial lists, including an explicit `holdings_complete: false`. With aligned supplied benchmark returns, the module calculates tracking error and relative returns. A close/NAV gap is not identical to an issuer's midpoint/indicative-NAV premium, and is not itself an arbitrage signal.

### HFT/microstructure — feature calculators, not a trading system

Queue imbalance is `(Q_bid − Q_ask)/(Q_bid + Q_ask)`. Opposite-size-weighted midpoint is `(ask×Q_bid + bid×Q_ask)/(Q_bid + Q_ask)`, not automatically a calibrated microprice. The event OFI implementation sums the signed Cont best-quote size/price changes, including equal-price cases. Integer prices, sizes and sequence/nanosecond clocks retain integer precision; finer-than-microsecond ISO strings are rejected rather than truncated.

These metrics require authorized event-quality quotes. Daily candles cannot establish queue position, fill probability, latency advantage, spread capture or adverse-selection economics. The research discusses inventory/volatility/risk aversion, event-arrival intensity, fees/rebates, toxicity and latency, but no live feed, quoting agent or queue simulator is implemented.

## 4. Recommendation policy and honesty gates

The heuristic combines 40% trend screen with 60% stock value+quality or ETF structure. Its weights and thresholds are disclosed design choices, **not paper-estimated coefficients or calibrated probabilities**. Missing checks keep their fixed denominator; no shrinking-denominator confidence boost occurs. Output separates diagnostic score, capped recommendation score, evidence coverage, bullish/bearish reasons and unknowns.

A top stock research-candidate label requires sufficient complete daily history, fresh evidence, explicit annual duration, matching supplemental symbol/currency and a dated capitalization input. Incomplete/provenance-limited evidence cannot attain the top label. Supplied retrieval-day candles require source-supplied exchange timezone and a last-session close clock matching the final bar and no later than retrieval; otherwise they are rejected. This is evidence validation, not independent session-calendar certification. The public adapter conservatively excludes all retrieval-day exchange-local candles.

Every response retains `model_status: unvalidated_heuristic` and `strong_recommendation_eligible: false`. RESEARCH_CANDIDATE means an item deserves further investigation, not BUY, a price target, a success probability or suitability approval. The service ranks only an explicit comparable universe of at most 50 snapshots, not all listed securities.

## 5. Actual ML experiment — including the failed result

Model: dependency-free ridge regression on lagged technical returns, trailing volatility and moving-average distance. Target is `open[t+2]/open[t+1]−1`, with the signal observed after completed close `t` and the hypothetical entry at the next open. Only training labels ending strictly before the prediction date are allowed (`j+2 < t`); training-only scaling and chronological expanding fits prevent the tested forms of future leakage.

Fixed experiment: initial training 252 eligible rows, retrain every 21 observations, ridge penalty 10, long/cash when predicted return exceeds the approximate round-trip cost threshold, 5 basis points per side, switching costs and final liquidation. Buy-and-hold uses identical entry/exit dates and fee convention. Neither model selection nor a probability calibration was performed.

**Out-of-sample period: September 1, 2023–November 9, 2026. Cumulative price-only results, net of the stated assumed fee—not annual returns:**

| Symbol | OOS observations | Experimental ridge | Aligned buy-and-hold | OOS R² vs train-mean forecast |
|---|---:|---:|---:|---:|
| MSFT | 799 | -14.51% | 64.18% | -0.0179 |
| SPY | 799 | 24.66% | 63.56% | -0.0107 |

**Both experiments underperformed.** Both also had worse prediction error than their training-mean forecast baseline. Therefore the ML baseline is not promoted into stronger recommendations. The experiment does not validate or invalidate the separate fundamental heuristic; it measures a specific technical long/cash rule on two selected survivors. Dividends, full spread/impact, taxes, borrow, financing, cash returns, capacity and a historical point-in-time universe are not modeled. Repeated inspection creates selection risk even without changing parameters.

## 6. Real-data exercise and source failures

Explicit public historical downloads produced 1,254 daily bars per symbol, through **November 9, 2026**. The data source is Yahoo's unofficial chart endpoint, not an entitled executable-price feed. The registered native handlers and actual CLI produced equal analysis and ML outputs for both symbols.

- **MSFT: WATCHLIST**, capped score 69/100, metric coverage 82.00%. Incomplete fundamental metric evidence: earnings_yield, fcf_yield, interest_coverage.
- **SPY: WATCHLIST**, capped score 69/100, metric coverage 82.86%. Incomplete ETF metric evidence: hhi, top10_weight.

MSFT's example is independently sourced from the issuer's FY26 annual GAAP earnings release, published July 29, 2026, not a successful SEC download or an automated all-company fundamentals feed. SPY top holdings are dated November 6; NAV is dated November 9. Direct SEC companyfacts access returned **HTTP 403** and remains explicitly unavailable. No fallback SEC result was fabricated. Free access does not establish commercial redistribution or real-time data rights.

## 7. Verification and Hermes integration

- Full offline suite: **341 passed in 1.96s**.
- Source citation/ledger/count checks: passed, no unknown/unused IDs or URL mismatches.
- Immutable upstream license-file re-fetch/hash checks: passed.
- `hermes plugins doctor . --ci`: passed; **seven tools, zero hooks**.
- `hermes plugins validate . --install-deps --json`: passed, no warnings; declared tools match registration, security scan safe, no core override.
- `git diff --check`: passed for existing tracked/staged work. Source archive is separately checked for excluded private/raw/runtime files.

Tools: `tradeguard_strategy_catalog`, `tradeguard_equity_research`, `tradeguard_public_history`, `tradeguard_walk_forward`, `tradeguard_microstructure`, `tradeguard_rank`, `tradeguard_recommend_tickers`. Ticker-only mode returns explicitly labelled technical screens without inventing a fundamental feed; its separate combined score remains unavailable when supplemental evidence is absent.

The official catalog guide was retrieved and followed: public registration surfaces, inert import/registration, explicit network permission, no credential-store reads, no self-updater, truthful manifest and disclosures. Local validation and publishing the Git repository are not catalog admission. A catalog listing additionally requires a full 40-character tested SHA pin and a separately reviewed catalog PR; no catalog listing or active-profile installation is claimed here.

## 8. Run and inspect

```bash
python3 -m tradeguard strategies --asset-type etf
python3 -m tradeguard recommend --interactive --allow-public-data
python3 -m tradeguard strategies --strategy-id value_quality
python3 -m tradeguard analyze --symbol MSFT --allow-public-data \
  --fundamentals examples/msft_fy2026_fundamentals.json
python3 -m tradeguard analyze --symbol SPY --allow-public-data \
  --etf-metadata examples/spy_issuer_metadata.json
python3 scripts/exercise_research.py --offline
python3 scripts/check_research_integrity.py --verify-licenses
```

Working files: `tradeguard/equity.py`, `catalog.py`, `ranking.py`, `providers.py`, `validation.py`, `microstructure.py`; root `plugin.yaml` and `__init__.py`; actual-run evidence under `artifacts/`; source research under `docs/research/`. Vendor histories and full forecast traces stay in git-ignored `data/` and are excluded from the deliverable source archive.

## 9. Before calling recommendations strong

Obtain a reliable authorized stock/ETF feed, historical universe including delistings, point-in-time filings/holdings/corporate actions, full benchmark/distribution conventions and sector-aware accounting. Define the horizon and objective; then pre-register thresholds and promotion tests, fit nested chronological experiments, retain an untouched holdout, test regime/cost/capacity sensitivity and calibration, and shadow/paper-monitor the chosen model. Fundamental and ETF-structure labels need their own outcome validation; results from technical ridge do not transfer.

Initial exercised scope is US stocks/ETFs. NSE/BSE integration, personalized risk/tax suitability, all-market discovery, live fundamental auto-refresh, execution and the broader prediction-market/futures/options adapters remain outside this verified slice.

**Bottom line:** the research library, recommendation infrastructure and validation path work. There is not yet evidence for a strong predictive trading edge, and the implementation refuses to invent one.
