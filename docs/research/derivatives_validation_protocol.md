# Derivatives historical evaluation protocol — NOT IMPLEMENTED

This is the M3 data/evaluation gate, not a fitted model, backtest result or declaration of edge. M1's correct formulas and synthetic entrypoint parity are analytical implementation evidence only.

## 1. Freeze a point-in-time research question

Before looking at the final evaluation period, declare supported venue/root/contract family, entry/exit horizon, exact rules, maximum contracts, research capital, available-account assumptions, stop/gap semantics and benchmark. Record every model/threshold trial; retain an untouched chronological test period. The existing equity ridge return accounting must not be reused as futures account returns or option-premium profitability.

## 2. Require the economic dataset

### Futures

Retain each exact expired/current contract, tradable timestamps, multiplier/tick/currency/spec-effective changes, quotes or executable next-bar assumptions, settlement marks, roll mapping and changing margin references. A retrospectively adjusted continuous series is not proof of the tradeable contract/P&L at a past date. Compute cash P&L and explicit capital returns; do not call margin a maximum-loss budget.

### Options

Require the declared historical chain/universe including expired or unavailable contracts, contemporaneous underlying/quote bid/ask and depth/delay, source availability timestamps, strikes/styles/deliverables, expiry/fixing/settlement rules and corporate/specification changes. Current contract masters cannot reconstruct an old chain. Any IV/rate/yield feature must have existed by the decision timestamp, not be recomputed with future knowledge and called observed.

## 3. Simulate only after information is available

Features use completed observations. Hypothetical entry is at the next tradable opportunity after the signal; no fill at the close that created the signal. A buy uses ask and sell uses bid where available, with bounded size/depth and declared latency/slippage assumptions. Multi-leg simulation must account for non-atomic fills/legging or use a genuine spread quote; two convenient midpoints do not create an executable spread.

Record both legs' costs, exchange/broker fees, applicable taxes, spread/impact, expiry/settlement costs and funding/cash treatment. Unknown costs are unavailable, not zero. Use dated rules; do not project today's tax or margin regime backward without disclosure.

## 4. Chronological evaluation

Partition train/validation/test by time and shared underlying, with overlapping holding windows/expiries purged or embargoed as the target requires. Related strikes/legs from one opportunity must not leak across folds. Fit normalization, feature selection, models and hyperparameters on training/validation data only. Test future-perturbation causality and retain source-availability clocks.

Compare no-trade, an explicitly costed simple directional future/option rule, and any declared hedge benchmark over aligned periods/capital. Report cash P&L, drawdown/tail loss, margin demands, turnover, concentration, realized execution assumptions and sensitivity to costs/latency, not only accuracy or an attractive return percentage.

## 5. Promotion requires independent review

Freeze the policy and promotion criteria before exposing the untouched holdout. Preserve underperformance and failures, count all attempts and require review of multiple testing/calibration and actual source coverage. An underlying forecast alone does not validate strike/expiry/strategy selection. No strong-buy label, profit probability, live trading approval or account-affordability assurance follows from M1/M2.

No model/data provider is installed by this document. Any M3 implementation needs a separately approved dataset, entitlement/redistribution review, reproducible accounting tests and measured evaluation artifacts.
