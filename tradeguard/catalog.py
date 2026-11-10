"""Non-exhaustive, source-linked strategy research directory.

Sources use stable namespaces in docs/research/sources_{equity,microstructure}.json.
Rules are proposed hypotheses, not replications or evidence of profitability.
No network, files, account state, recommendations or order placement here.
"""
from __future__ import annotations

from copy import deepcopy


def _row(identifier, assets, horizon, status, formula, rule, data, risks, sources):
    return {"id": identifier, "asset_types": assets.split(","), "horizon": horizon,
            "implementation_status": status, "metric_or_objective": formula,
            "proposed_rule_not_validated": rule, "required_data": data,
            "failure_modes": risks, "source_ids": sources.split(","),
            "performance_validated": False}


_FAMILIES = (
    _row("value_quality", "stock", "years", "heuristic_screen",
         "NI/market_cap; (CFO-capex)/market_cap; ROA; ROE; cash accruals",
         "Research high-quality reasonably valued firms, with fixed missingness-aware checks; no automatic buy.",
         "Symbol-bound annual statements, aligned capitalization clock, sector/accounting context",
         "Value traps, cyclicality, negative denominators, banks/REITs comparability", "eq:1,eq:2,eq:3,eq:39"),
    _row("growth_investment", "stock", "years", "feature_only",
         "revenue/revenue_prev-1; asset growth; profitability improvement",
         "Test sector-relative growth and conservative-investment baskets, not growth at any price.",
         "Multiple point-in-time annual statements, dilution/acquisition context",
         "Restatements, expensive growth, acquisition distortion", "eq:1,eq:39"),
    _row("accrual_quality", "stock", "quarters_to_years", "feature_only",
         "(NI-CFO)/mean(assets)",
         "Compare cash conversion with sustainable profits; not an exact QMJ replication.",
         "Aligned cash-flow/income periods and consecutive balance sheets",
         "Seasonality, acquisitions, accounting mapping", "eq:39"),
    _row("cross_sectional_momentum", "stock,etf", "months", "feature_only",
         "prior months 2-12 total return; rank within a declared universe",
         "Test monthly top-quintile ranking with turnover buffers; current code only measures one-asset price momentum.",
         "Survivorship-aware universe, dividend-consistent histories, liquidity",
         "Momentum crashes, crowded exits, selection bias", "eq:6"),
    _row("trend_following", "stock,etf", "weeks_to_months", "heuristic_screen",
         "price/SMA200; SMA50/SMA200; skip-recent-month momentum",
         "Existing daily screen; monthly 10-month-SMA allocation is a separate proposed experiment.",
         "Completed consistent-basis daily bars; cash proxy for allocation tests",
         "Whipsaw, gaps, correlated indicators, dividend omissions", "eq:37,eq:7"),
    _row("mean_reversion", "stock,etf", "days_to_weeks", "heuristic_screen",
         "Wilder RSI14; price/SMA20; optional rolling log-price z-score",
         "Investigate pullbacks with long-trend context; capped exploratory screen, no entry authorization.",
         "Completed prices, spread and liquidity estimates",
         "Falling knives, structural breaks, bid-ask bounce", "eq:8"),
    _row("short_reversal", "stock,etf", "one_month", "researched_only",
         "negative prior-month total return",
         "Test liquid loser baskets with explicit costs; not identical to an RSI strategy.",
         "Point-in-time universe, distributions and executable-cost model",
         "Illiquidity, deterioration, impact", "eq:8"),
    _row("long_reversal", "stock,etf", "years", "researched_only",
         "negative prior months 13-60 total return",
         "Test long-horizon loser versus winner baskets, separately from recent reversal.",
         "At least five years of total returns and delisting treatment",
         "Secular decline, survivorship, multi-year drawdowns", "eq:9"),
    _row("defensive_low_volatility", "stock,etf", "months_to_years", "feature_only",
         "sample volatility; beta=Cov(asset,benchmark)/Var(benchmark)",
         "Test sector-capped defensive baskets; not a leveraged BAB replication. Only own-price vol is currently computed.",
         "Aligned asset/benchmark total returns, sectors, leverage assumptions",
         "Rate sensitivity, concentration, changing correlations", "eq:10"),
    _row("sustainable_dividends", "stock,etf", "years", "researched_only",
         "DPS_TTM/price; payout ratio; cash coverage; positive-base dividend growth",
         "Test yield plus sustainability rather than selecting maximum yield.",
         "Dated distributions, earnings, cash flow and tax context",
         "Yield traps, special dividends, return of capital", "eq:11"),
    _row("etf_structure", "etf", "months_to_years", "heuristic_screen",
         "expense ratio; same-date close/NAV-1; holdings HHI; top10 weight; tracking error",
         "Research low-cost liquid funds with verified exposure; partial holdings cannot prove full concentration.",
         "Issuer fees, dated NAV/holdings, aligned benchmark returns, fund mechanics",
         "Stale NAV, hidden concentration, tracking/difference confusion, leveraged fund resets", "eq:29,eq:40,eq:41"),
    _row("etf_rotation", "etf", "months", "researched_only",
         "ranks of 3/6/12-month total return plus an independently specified trend filter",
         "Test a predefined asset-class universe versus equal weight and buy-and-hold.",
         "Total-return histories, cash proxy, investable historical membership",
         "Data snooping, turnover, correlated exposures", "eq:37"),
    _row("risk_parity", "stock,etf", "portfolio_months", "researched_only",
         "RC_i=w_i*(Sigma*w)_i/(w' Sigma w); equalize risk contributions",
         "Compare constrained equal-risk weights; inverse-volatility is not generally equal risk.",
         "Synchronized returns, covariance estimator, leverage/caps and rebalance policy",
         "Correlation instability, leverage and hidden duration", "eq:21,eq:35"),
    _row("minimum_variance", "stock,etf", "portfolio_months", "researched_only",
         "minimize w' Sigma w subject to sum(w)=1 and 0<=w_i<=cap",
         "Compare shrinkage and feasible caps against equal weight before optimizing expected returns.",
         "Aligned returns, covariance estimation and transaction costs",
         "Estimation error, concentration, infeasible constraints", "eq:35"),
    _row("pairs_statistical_arbitrage", "stock,etf", "days_to_months", "researched_only",
         "s=log(P_A)-alpha-beta*log(P_B); formation-only residual z-score",
         "Test a cointegration extension separately from Gatev distance matching, with borrow/leg risk.",
         "Synchronized histories/quotes, formation sample, borrow and corporate actions",
         "Structural breaks, short squeezes, nonstationarity, execution mismatch", "eq:14"),
    _row("event_driven", "stock", "deal_or_event_horizon", "researched_only",
         "cash deal expected return=q*(C/P-1)+(1-q)*(B/P-1)-costs",
         "Require independent deal-success probability and failure scenarios; the spread is not the probability.",
         "Timestamped deal/earnings filings, terms, financing, event calendars",
         "Deal failure, revisions, overnight gaps, asymmetric tail losses", "eq:15"),
    _row("technical_ridge", "stock,etf", "next_open_to_following_open", "experimental_baseline",
         "open[t+2]/open[t+1]-1 from completed-close[t] technical features; ridge loss",
         "Chronological purged training; long/cash cost-aware evaluation only, not promoted into recommendations.",
         "Consistent daily OHLCV and declared per-side cost; untouched validation for promotion",
         "Negative OOS skill, overfitting, omitted dividends/impact and survivorship", "eq:17,eq:18,micro:16"),
    _row("queue_imbalance", "stock,etf", "event_level", "feature_only",
         "(Q_bid-Q_ask)/(Q_bid+Q_ask); opposite-size-weighted midpoint",
         "Use as descriptive features; one-tick probability and calibrated microprice need separate training.",
         "Authorized timestamped best quotes and queue sizes, tick rules",
         "Latency, disappearing depth, adverse selection, no fill advantage", "micro:2,micro:12"),
    _row("order_flow_imbalance", "stock,etf", "ordered_quote_events", "feature_only",
         "sum signed best-bid/best-ask price-size update contributions including equal-price cases",
         "Measure completed-interval OFI; do not relabel contemporaneous explanation as future tradable alpha.",
         "Ordered event-quality bid/ask changes with sequence/clock precision",
         "Missing events, price jumps, timestamp loss, window leakage", "micro:11"),
    _row("market_making", "stock,etf", "subsecond_to_seconds", "researched_only",
         "reservation price s-q*gamma*sigma^2*(T-t) under stylized inventory assumptions",
         "Study inventory-aware quoting only after queue, latency, fees and fill validation.",
         "Full event feeds, matching rules, queue position, rebates, venue permissions",
         "Toxic flow, inventory tails, latency races, cancellation/fill uncertainty", "micro:4,micro:14,micro:41"),
    _row("etf_primary_market_arbitrage", "etf", "intraday_creation_redemption", "researched_only",
         "basket versus ETF price net of hedge, funding and creation/redemption costs",
         "Not retail buy-at-discount logic: authorized-participant access and basket mechanics matter.",
         "AP arrangements, current basket/hedge quotes, fees and inventory constraints",
         "Liquidity mismatch, stale underlying prices, funding and basis risk", "micro:34,eq:40"),
)


def strategy_catalog(asset_type: str | None = None, strategy_id: str | None = None) -> dict:
    """Describe covered research families and actual implementation status."""
    if asset_type is not None and asset_type not in ("stock", "etf"):
        raise ValueError("asset_type must be stock or etf")
    if strategy_id is not None and (not isinstance(strategy_id, str)
                                    or strategy_id not in {r["id"] for r in _FAMILIES}):
        raise ValueError("unknown exact strategy_id")
    selected = [row for row in _FAMILIES if (asset_type is None or asset_type in row["asset_types"])
                and (strategy_id is None or row["id"] == strategy_id)]
    return {"strategies": deepcopy(selected), "count": len(selected), "exhaustive": False,
            "research_only": True, "source_ledger_namespaces": {
                "eq": "docs/research/sources_equity.json", "micro": "docs/research/sources_microstructure.json"},
            "warning": "Researched is not implemented; tested formulas are not validated alpha. No strategy here is performance-promoted."}
