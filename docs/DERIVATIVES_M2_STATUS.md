# Derivatives M2 — data-source gate

Status: **provider decision/access pending; M2 is not implemented or complete**.

## November 11, 2026 discovery

- M1 remains committed locally at `317acd2a2cab263710c633268a191814e89318e3` on `feat/derivatives-research`.
- Kite was the initial provider proposal; TradingView was subsequently evaluated as an alternative. The provider/access decision remains pending rather than silently choosing either route.
- Authorized credential availability and market-data entitlement have not been established for M2. No secret values or another application's credential files were read; environment/credential contents are not published here.
- TradingView MCP symbol search returned futures roots including `NSE:NIFTY`; that does not establish an exact expiry contract or live quote access.
- The TradingView CDP health check failed; no chart/quote connection was verified. A type-filtered option search returned HTTP 400 and therefore proves no option-chain capability either way.
- The launch tool defaults to killing existing TradingView instances. It was inspected but **not invoked**, and no chart, broker, login or order UI was changed.

## Official-source checks

Direct HTTPS returned HTTP 200 for these sources on November 11, 2026:

| Source | Finding relevant to M2 |
|---|---|
| `https://www.tradingview.com/support/solutions/43000474413-i-need-access-to-your-api-in-order-to-get-data-or-indicator-values/` | TradingView says it does not currently provide a general data/indicator API; its REST integration API is for brokers. |
| `https://www.tradingview.com/policies/` | Sections 3 and 12 restrict non-display/algorithmic reuse and automated extraction under standard terms; do not infer that a subscription or available third-party MCP tooling supplies permission for an automated TradeGuard data backend. |
| `https://www.tradingview.com/support/solutions/43000760837-options-chain-overview/` | A human-facing option-chain UI exists with strike/expiry, bid/ask, model Greeks and IV. UI availability is not evidence of a supported/licensed export API for the engine. |

Official indexed support also describes NSE/BSE real-time access as dependent on account/exchange status. No market-data subscription, professional classification, exchange agreement or non-display authorization was verified for this user.

## Decision boundary

TradingView can remain a human-facing chart/chain reference. Do not silently replace the planned authorized data adapter with internal-endpoint/CDP scraping for algorithmic recommendations. A TradingView-based automated integration would first need explicit permission covering the intended use and a verified technical/data contract; even then exact expiry, units, clocks, delay, depth and model/source provenance remain mandatory.

Otherwise use a permitted market-data API for M2 and TradingView only for visual comparison. Ask the owner which licensed provider/access route they want; do not buy a subscription, request tokens in chat, read browser/broker files or claim a successful live exercise.

No M2 source code, broker connection, profile setting, market-data purchase, trade, remote push or TradingView launch was performed by this discovery.
