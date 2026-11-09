# Hermes TradeGuard — locked initial plan

> Status: scope baseline v0.3, revised 2026-11-09 (IST). User expanded scope from trade-risk review to **cross-market indicators plus risk review** for stocks/ETFs, futures, listed options and prediction markets (Polymarket and Kalshi). This is a plan, not an implemented or security-audited trading system. Further scope changes require an explicit revision; do not silently expand into live trading.

## Goal and pitch

Build a **venue-agnostic, read-only indicator and trade-review plugin for Hermes Agent**. A common evidence contract delegates market data, fees, contract specifications and payoff semantics to venue/instrument adapters. The product goal covers **stocks/ETFs, futures, listed options, and prediction markets on Polymarket and Kalshi**; Coinbase Exchange spot crypto remains an optional fifth adapter. It computes explainable, timestamped *observations* (trend/volatility/liquidity, plus instrument-specific features) and separate risk-check outcomes **PASS / CAUTION / BLOCK / UNVERIFIED**. PASS means stated checks on supplied evidence passed, **not** a profitable-trade recommendation, directional signal, or order authorization. A Hermes `pre_tool_call` hook can reject or escalate specifically configured, recognized order-tool calls, but the MVP never submits an order.

Demo hook: Hermes displays the same evidence format for a stock, a Polymarket contract and a Kalshi contract, while source adapters retain different order-book semantics. Futures and listed options are demonstrated with **explicitly labelled fixtures** until licensed/authorized live feeds are integrated; a fixture is never displayed as a live signal. A stale/insufficient book or exhausted *verified* daily-loss allowance blocks the configured mock order tool. The plugin is **not** a universal firewall: shell, browser, other plugins, external apps, and direct exchange/API access may bypass it. A hook exception may be logged and skipped by Hermes, so hard enforcement belongs inside a future dedicated execution adapter, not in the hook alone.

## Scope decision

- **Target coverage:** stocks/ETFs, exchange-traded futures, listed options, and binary prediction contracts on Polymarket/Kalshi. “Futures” are themselves derivatives; options are the additional derivatives family. This is not a claim to support every venue, margin product or exotic payoff on day one.
- **Hackathon MVP:** live *public* Polymarket and Kalshi order books, a stock/ETF historical-bars + quote adapter **only if a documented licensed/entitled read-only data feed is configured**, and synthetic fixture-backed futures/options examples. The prior Coinbase Exchange spot adapter is optional, not a substitute for a stock/prediction-market demo. Unsupported or unconfigured sources report UNVERIFIED/UNSUPPORTED; no fabricated live data.
- **Core:** one typed evidence/indicator/review contract, an instrument-aware risk engine, targeted `pre_tool_call` guard for a mock execution tool, redacted audit trail, and concise evidence report. Default behavior is no executions, no account access and no wallet signing.
- **Stretch:** Desktop evidence pane/card via the documented Desktop Plugin SDK, only after the backend is tested. A demo with a fake execution tool can prove hook behavior without risking money.
- **Out of scope:** autonomous trading, wallet/private-key handling, uncalibrated universal BUY/SELL scores, universal interception of `terminal`/`execute_code`/browser, live options/futures support without contracted data and specs, OTC/exotic derivatives, cross-venue margin/FX/netting claims, and any live order placement in the hackathon MVP. Additional live venue support is an extension roadmap, not an MVP claim.
- **Privacy:** make public data work without credentials. If private position/P&L reads are later added, declare secrets via Hermes-approved routes and `agent.secret_scope.get_secret`; never read another CLI's token files, `~/.hermes/.env`, browser storage, or wallet secrets. Do not publish the user's balances, positions, local paths, or real trade logs.

## User journey

1. User asks Hermes “Show indicators and review this stock/future/option/prediction contract” and optionally adds a hypothetical BUY/SELL with explicit venue, product ID, quantity/unit, currency and limit. A *pure indicator view* requires no proposed order.
2. The selected adapter resolves the exact product/outcome ID; ambiguous matches cause a request for clarification, not a guess. Unknown venues return UNSUPPORTED, not PASS.
3. Adapter retrieves **timestamped** data appropriate to the instrument: bars for time-series indicators, quote/order book for executable-price and liquidity estimates, and documented product constraints. An authorized read-only feed may be required. A separately sourced risk snapshot is optional; quotes are never misrepresented as guaranteed fills.
4. When a sufficient history exists, indicator engine computes *descriptive* trend/volatility statistics (e.g. moving average, RSI, ATR) with declared lookback, interval, adjustments and data source; with only a current order book it emits spread/depth metrics **but does not invent time-series indicators**. No single RSI or generic score is asserted to have the same interpretation across stocks, options and binary contracts.
5. For an optional hypothetical order, engine calculates fillable quantity, price range and gross quote-currency cost/proceeds; fee module estimates fees only when reliable inputs are known. It applies universal checks (freshness, depth, limit, size, notional) and **instrument-specific checks** (share/corporate-action data, futures multiplier/expiry/margin, option strike/expiry/put-call/Greeks/assignment where sourced, prediction payoff/settlement rules). Missing mandatory account data yields UNVERIFIED/BLOCK per policy.
6. Report separates **indicator observations**, **hypothetical order/risk checks**, and **unknowns**. It includes numeric units/currency, source/timestamps, coverage matrix and reason codes. PASS only asserts the checks actually performed; no placement occurs.
7. Optional demo: a mock `tradeguard_demo_order` call is intercepted by the targeted hook and blocked/escalated. No real order endpoint is present in MVP.

## Safety and correctness contracts

- Never label a reference midpoint or last trade as an executable price. Use ask ladder for BUY and bid ladder for SELL; normalize venue product/outcome IDs before reading the book. A book-based fill estimate is not a guaranteed fill or final fee.
- Keep indicators descriptive and reproducible: name the formula, lookback/window, candle source/adjustment, bar interval, missing-bars policy and observation time. A configured rule may label an observation **bullish / bearish / neutral** and show its exact threshold, but that label is not a universal BUY/SELL instruction or validated edge; evaluate predictive quality only with out-of-sample and regime-aware testing later.
- Never apply equity price indicators directly to option premiums, futures continuous contracts or prediction-market prices without declaring roll/adjustment, strike/expiry, settlement and probability/payoff semantics. Distinguish bid/ask microstructure from a calibrated event probability.
- Prediction-market indicators may include bid/ask spread, depth, price movement and time to resolution. An **estimated edge** requires an independently supplied, source-labelled event probability with uncertainty; the market price itself is not an independent forecast. Show fee/settlement assumptions and do not claim an edge if probability or payoff terms are missing.
- Kalshi's public binary order book exposes YES and NO bids rather than a conventional ask array. Derive a synthetic opposite-side ask only using the documented complement relationship, with correct decimal/fixed-point units and contract sizes; test against official fixtures. Polymarket uses outcome token IDs and explicit bid/ask arrays. Do not normalize these by guessing.
- Futures require exchange-specific tick/multiplier, contract month, settlement method, trading session, margin regime and roll mapping; options require underlying, strike, right, expiry, multiplier, exercise/assignment style and volatility/Greek provenance. If any field needed for a claimed calculation is absent, mark that calculation unavailable.
- Shared normalized contract always includes `venue`, `instrument_type`, `product_id`, `source`, `asof`, `received_at`, `currency` and `coverage`; optional bar/book evidence includes its interval, adjustments, levels and constraints. A *trade review* additionally requires `side`, `quantity`, `quantity_unit`, `limit_price`, bid/ask evidence and `fee_status` where applicable. Adapters must not force binary-share payoff logic onto equities or derivatives, and unsupported instruments fail explicitly.
- Reject stale, missing, malformed, crossed, empty, inconsistent, or insufficient-depth books; reject NaN/infinity/negative amounts. Use `Decimal` for money and explicit currency/units. Include UTC observation time and local receipt time; enforce TTL on the latter unless provider timestamps are trustworthy.
- Require any account risk snapshot to name its source, observation time, account scope, currency, starting balance, positions and realized P&L semantics. Distinguish *realized daily loss* from open-position mark-to-market loss. Do not sum USD/USDC/EUR balances or multiple accounts without explicit conversion rates, timestamps and ownership. If unavailable, mark the check UNVERIFIED/BLOCK; never fabricate account state or a daily-loss cap.
- Configuration holds policy amounts; proposal cannot override limits. Server-side evaluation takes place at call time. If a future live adapter is built, it must independently re-fetch/re-evaluate immediately before order placement, require explicit human approval, cap price/size, use idempotency protection, and read back accepted/fill/cancel state. A prior PASS is not permission to trade.
- Hook only recognizes a small allowlist of configured order-tool names with documented argument schemas. It must never approve a call or disable Hermes approvals. Treat unexpected arguments/unknown tool adapters as outside coverage, not as protected.
- Hook crashes do **not** constitute a fail-closed guarantee in Hermes; do not market the plugin as a universal risk firewall. A future dedicated order adapter must fail closed internally and expose no alternate submit route.
- No network telemetry. Bound request timeouts/rate limits, redact logs, and document every endpoint and permission.

## Architecture / intended repo layout

```text
hermes-tradeguard/
├── PLAN.md                         # this locked scope baseline
├── README.md                       # install, limitations, demo, disclosures
├── LICENSE                         # permissive license
├── plugin.yaml                     # manifest, tools/hooks, config schema, permissions
├── __init__.py                     # register(ctx): tools, hook, bundled skill
├── tradeguard/
│   ├── models.py                    # Decimal-backed instrument/quote/bar/proposal/result types
│   ├── adapters/
│   │   ├── base.py                 # shared normalized book/product contract
│   │   ├── polymarket.py           # read-only binary outcome adapter
│   │   ├── kalshi.py               # YES/NO bids + complement and fixed-point normalization
│   │   ├── equities.py             # entitled read-only quote + bar feed (configured)
│   │   ├── futures.py              # fixture-first, later licensed live feed
│   │   ├── options.py              # fixture-first, later authorized chain/Greek feed
│   │   └── coinbase_exchange.py    # optional spot crypto adapter
│   ├── indicators.py               # pure deterministic time-series/microstructure metrics
│   ├── policy.py                   # instrument-specific rules + shared checks
│   ├── risk.py                     # pure deterministic evaluation and reason codes
│   ├── report.py                   # evidence and audit rendering
│   └── audit.py                    # profile-scoped minimal event storage
├── skills/tradeguard/SKILL.md      # when to call tool; never execute from GO alone
├── tests/
│   ├── test_risk.py
│   ├── test_books.py
│   ├── test_adapters.py
│   ├── test_indicators.py
│   ├── test_policy.py
│   ├── test_hook.py
│   ├── test_audit.py
│   └── fixtures/                  # synthetic, not copied from real user account
└── desktop/                        # stretch only: documented SDK plugin.js
```

**Implementation seam:** native Hermes plugin (`plugin.yaml` + `register(ctx)`), read-only `tradeguard_indicators` and `tradeguard_evaluate` tools, an adapter registry, pure indicator and instrument-policy modules, and `ctx.register_hook('pre_tool_call', ...)`. The hook returns a documented block directive only for explicit known tools/arguments. Check Hermes hooks, all vendor API contracts, entitlement and exchange licensing before coding; do not guess payload names. Prefer the host's plugin data directory/database for audit state; do not hardcode `~/.hermes` because profiles are isolated. Keep external dependencies minimal and pinned with compatible bounds.

## Build sequence and acceptance gates

### 1. Confirm interfaces and write contract tests
- Inspect current Hermes plugin/doctor, hook directive, Desktop SDK (if used), Polymarket/Kalshi market-data schemas, stock-data entitlement, and futures/options exchange/broker data licensing; record sources and versions in README.
- Define one canonical JSON contract for instrument, bar series, quote/book, source/entitlement status, optional proposal, risk snapshot, indicator values and review. Tests for unknown venue/product, unit mismatch, missing history, unsupported instrument and malformed payload must fail before implementation.
- **Gate:** fixture tests run offline; every data field maps to a documented source or is explicitly user-configured.

### 2. Implement deterministic risk engine (TDD)
- Add indicator calculations with fixture OHLCV/book data, followed by Decimal arithmetic for walking ask/bid depth, limit price, insufficient liquidity, fees-known/unknown, exposure and daily-loss budget, with separate equity, futures, options and binary-share policies.
- Test calculation windows, missing/split/rolled candles, stale quote, zero depth, Kalshi YES/NO complement, partial fill, wrong product/unit/currency, unknown fees, unavailable position/P&L, cap reached, unsupported venue/instrument and cross-venue currency aggregation rejection.
- **Gate:** no market network needed for `tests/test_risk.py` or `tests/test_indicators.py`; missing mandatory *order-check* evidence yields BLOCK/UNVERIFIED per configured policy, while an indicator-only request reports the missing metric as unavailable rather than inventing a value.

### 3. Add read-only prediction adapters, then an entitled equity feed
- Polymarket: resolve condition/outcome → token ID via public endpoint; fetch and validate book. Kalshi: fetch current YES/NO bid books, normalize documented complementary asks and fixed-point prices/counts. Stock/ETF feed: explicitly configure a read-only, authorized source and label exchange coverage/delay/adjustments. Coinbase spot can follow as optional adapter.
- Test HTTP fixtures for each adapter and at least one live public Polymarket and Kalshi market, clearly separating fixture data from live evidence. Show equities live only when the configured feed works with valid entitlement; otherwise run clearly labelled fixture tests and mark live equity unavailable. Check product status and access conditions; a public quote does not establish eligibility to trade.
- **Gate:** prediction live reads work without trading credentials; stock data shows source and delay/entitlement; malformed/timeout/rate-limit errors never produce PASS.

### 3b. Futures and options: schema + fixtures first, live data later
- Define futures and listed-options instrument schemas with unit/multiplier/expiry and payoff-specific tests. Render indicators from labelled test fixtures without claiming live support.
- A live adapter must wait for a documented broker/exchange feed, data entitlement and exact contract specification. A stub or synthetic chain must never silently fall back into a live output.
- **Gate:** unsupported live futures/options requests return an explicit unavailable status and source explanation.

### 4. Package native plugin and targeted demo guard
- Register `tradeguard_indicators`, `tradeguard_evaluate` and a `pre_tool_call` hook with `**kwargs` compatibility; declare the exact tools/hooks in `plugin.yaml`. Ensure hook recognizes only the mock execution tool or a user-specified tool with a verified stable schema.
- Add a bundled skill for safe usage. Store a redacted audit trail in profile-scoped plugin storage.
- **Gate:** `hermes plugins doctor . --ci` and `hermes plugins validate . --install-deps` pass; synthetic order-tool call with exhausted *supplied* budget is blocked; unrelated tools work normally; each family is honestly marked LIVE, FIXTURE or UNAVAILABLE and the plugin cannot place orders.

### 5. Polish and publish
- README: 60-second quickstart, screenshots/demo transcript, threat model, network/privacy/credential disclosures, tested Hermes version, and clear not-a-universal-firewall warning.
- Optional Desktop panel only if SDK documentation and time permit; otherwise focus on a crisp evidence card in tool output.
- Run `python -m pytest -q`, `hermes plugins doctor . --ci`, and `hermes plugins validate . --install-deps`; inspect warnings and scan public repo history for secrets and user data.
- Open plugin-catalog PR against NousResearch/hermes-agent, adding `plugin-catalog/hermes-tradeguard.yaml` pinned to the **full 40-character SHA** of this repo's tested commit. Submit PR + <90-second X demo as hackathon instructions require. Catalog admission/merge is a separate human review, not guaranteed by this plan.

## Demo storyboard (under 90 seconds)

1. Show live Polymarket and Kalshi binary markets through the same indicator tool; display their different book shapes and honest coverage labels. Add an equity bar/quote example only if entitled data is configured; otherwise label fixture.
2. Show a futures and an option fixture to prove instrument-aware unit/multiplier/expiry handling, unmistakably labelled NOT LIVE; unknown Greeks/fees/positions are not silently treated as safe.
3. Change a synthetic account fixture to exceed the daily-loss budget; call the mock order tool and show targeted hook BLOCK plus audit reason.
4. Show no wallet key, live execution or privileged override was needed; demonstrate quick install/validation and repo.

## Open decisions before implementation

- Pick authoritative read-only position/P&L inputs *for each venue* and a currency normalization policy. Until compliant credential routes and accounting semantics exist, use *clearly labeled user-supplied or synthetic risk snapshots*; do not claim live account or combined-portfolio protection.
- Decide which stock feed (US or Indian markets) and which licensed futures/options broker/exchange source is available. An IEX-only or delayed feed must not be presented as a full-market live view. Users configure any required key through Hermes's approved secret routes, never through a copied vendor credential file.
- Keep signal research separate from the plugin runtime: descriptive indicators are not a validated trading edge. Any future probabilistic/BUY-SELL model needs timestamped historical data, out-of-sample tests, transaction costs and calibration per instrument family.
- Coinbase Exchange public order-book access is a demonstration of venue portability, **not** support for every Coinbase product or for authenticated Coinbase account risk. Check product status and jurisdiction before making any trading-eligibility claim.
- Verify whether the target Hermes release exposes a documented UI bridge for showing live evidence. If not, keep the demo text-only rather than touching private Desktop markup.
- Decide whether a later phase should offer a dedicated approved order adapter; it requires a separate security review and explicit user authorization. It is **not** part of this initial scope.

## Official references (recheck before coding)

- Hermes plugin guide: https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
- Catalog submission: https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission
- Event hooks: https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
- Polymarket developer documentation: https://docs.polymarket.com/
- Polymarket order book reference: https://docs.polymarket.com/api-reference/market-data/get-order-book
- Coinbase Exchange product book reference: https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductbook
- Kalshi order-book reference: https://docs.kalshi.com/api-reference/market/get-market-orderbook
- Kalshi fixed-point order-book format: https://docs.kalshi.com/getting_started/orderbook_responses
- Example US stock-data entitlement reference: https://docs.alpaca.markets/us/docs/about-market-data-api
- Futures/options data licensing example: https://www.cmegroup.com/market-data/license-data.html
