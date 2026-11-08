# Hermes TradeGuard — locked initial plan

> Status: scope baseline v0.2, revised 2026-11-08 (IST) after the user clarified “any trading venue,” not “any Polymarket category.” This is a plan, not an implemented or security-audited trading system. Further scope changes require an explicit revision; do not silently expand into live trading.

## Goal and pitch

Build a **venue-agnostic, read-only, evidence-first trade-review plugin for Hermes Agent**. A common proposal/decision contract delegates quote, fee and instrument semantics to a venue-specific adapter. The MVP demonstrates portability on **two genuinely different venues: Polymarket binary shares and Coinbase Exchange spot crypto (public book only)**. It estimates executable price and available depth, and produces an auditable **PASS / CAUTION / BLOCK / UNVERIFIED** result with reason codes. PASS means checks on supplied evidence passed, **not** a profitable-trade recommendation or order authorization. A Hermes `pre_tool_call` hook can reject or escalate specifically configured, recognized order-tool calls, but the MVP never submits an order.

Demo hook: Hermes evaluates a Polymarket share purchase and a Coinbase spot purchase under the same high-level risk policy, while venue adapters supply different units, minimums, fees and failure conditions. A stale/insufficient book or exhausted *verified* daily-loss allowance blocks the configured mock order tool. The plugin is **not** a universal firewall: shell, browser, other plugins, external apps, and direct exchange/API access may bypass it. A hook exception may be logged and skipped by Hermes, so hard enforcement belongs inside a future dedicated execution adapter, not in the hook alone.

## Scope decision

- **Markets:** adapter architecture for *any venue in principle*, but only **Polymarket binary shares + Coinbase Exchange spot crypto** are supported/tested in the hackathon MVP. Do not label unimplemented venues supported. Each proposal is one instrument and one side; portfolio-wide cross-venue risk is UNVERIFIED unless an authoritative consolidated position/P&L feed is supplied.
- **MVP:** two read-only public order-book adapters, a common typed proposal/evidence/decision contract, instrument-specific risk policy, opt-in targeted `pre_tool_call` guard for a mock execution tool, redacted audit trail and concise evidence report. Default behavior is no executions, no account access and no wallet signing.
- **Stretch:** Desktop evidence pane/card via the documented Desktop Plugin SDK, only after the backend is tested. A demo with a fake execution tool can prove hook behavior without risking money.
- **Out of scope:** autonomous trading, wallet/private-key handling, inferred profit probabilities, universal interception of `terminal`/`execute_code`/browser, equities/options/futures/DEX adapters, cross-venue margin/FX/netting claims, and any live order placement in the hackathon MVP. Additional venues are an extension roadmap, not an MVP claim.
- **Privacy:** make public data work without credentials. If private position/P&L reads are later added, declare secrets via Hermes-approved routes and `agent.secret_scope.get_secret`; never read another CLI's token files, `~/.hermes/.env`, browser storage, or wallet secrets. Do not publish the user's balances, positions, local paths, or real trade logs.

## User journey

1. User asks Hermes either “Review buying 20 YES shares on Polymarket, max $0.42/share” **or** “Review buying 0.01 BTC on Coinbase Exchange, max $X/BTC.” Venue, product ID, side, quantity unit, quote currency and limit are explicit.
2. The selected adapter resolves the exact product/outcome ID; ambiguous matches cause a request for clarification, not a guess. Unknown venues return UNSUPPORTED, not PASS.
3. Adapter retrieves a **timestamped** public order book and documented product constraints, plus a separately sourced risk snapshot if configured. Quotes are reported as bid/ask with depth and age, never last-trade price as if executable.
4. Engine calculates fillable base quantity, worst allowed unit price and gross quote-currency cost/proceeds; venue fee/rule module estimates fees only when reliable inputs are known. If fees are unknown, mark them UNVERIFIED and avoid net-return claims.
5. Engine applies universal checks (freshness, depth, limit, size, quote-currency notional) and **venue/instrument-specific checks** (binary-share worst-case loss vs spot inventory/cash constraints). Account-wide loss/exposure checks require authoritative, current account data; no snapshot means UNVERIFIED/BLOCK if the policy requires that check.
6. Report prints PASS / CAUTION / BLOCK / UNVERIFIED, numeric inputs with units/currency, source/timestamps, coverage matrix and triggered reason codes. PASS only asserts the checks actually performed; no placement occurs.
7. Optional demo: a mock `tradeguard_demo_order` call is intercepted by the targeted hook and blocked/escalated. No real order endpoint is present in MVP.

## Safety and correctness contracts

- Never label a reference midpoint or last trade as an executable price. Use ask ladder for BUY and bid ladder for SELL; normalize venue product/outcome IDs before reading the book. A book-based fill estimate is not a guaranteed fill or final fee.
- Shared normalized contract includes `venue`, `instrument_type`, `product_id`, `side`, `quantity`, `quantity_unit`, `quote_currency`, `limit_price`, `book_asof`, `received_at`, `source_url`, `bid_levels`, `ask_levels`, `fee_status` and `constraints`. Adapters must not force binary-share payoff logic onto spot crypto, and unsupported instruments fail explicitly.
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
│   ├── models.py                    # Decimal-backed proposal/book/decision types
│   ├── adapters/
│   │   ├── base.py                 # shared normalized book/product contract
│   │   ├── polymarket.py           # read-only binary outcome adapter
│   │   └── coinbase_exchange.py    # read-only spot crypto adapter
│   ├── policy.py                   # instrument-specific rules + shared checks
│   ├── risk.py                     # pure deterministic evaluation and reason codes
│   ├── report.py                   # evidence and audit rendering
│   └── audit.py                    # profile-scoped minimal event storage
├── skills/tradeguard/SKILL.md      # when to call tool; never execute from GO alone
├── tests/
│   ├── test_risk.py
│   ├── test_books.py
│   ├── test_adapters.py
│   ├── test_policy.py
│   ├── test_hook.py
│   ├── test_audit.py
│   └── fixtures/                  # synthetic, not copied from real user account
└── desktop/                        # stretch only: documented SDK plugin.js
```

**Implementation seam:** native Hermes plugin (`plugin.yaml` + `register(ctx)`), a namespaced read-only `tradeguard_evaluate` tool taking a venue discriminator, adapter registry, pure common evaluator with instrument policy modules, and `ctx.register_hook('pre_tool_call', ...)`. The hook returns a documented block directive only for explicit known tools/arguments. Check exact Hermes hook/tool schemas, Polymarket and Coinbase Exchange read-only API contracts against current official docs before coding; do not guess payload names. Prefer the host's plugin data directory/database for audit state; do not hardcode `~/.hermes` because profiles are isolated. Keep external dependencies minimal and pinned with compatible bounds.

## Build sequence and acceptance gates

### 1. Confirm interfaces and write contract tests
- Inspect current Hermes plugin/doctor, hook directive, Desktop SDK (if used), and **both** venues' public market/book API docs; record URLs and versions in README.
- Define fixture JSON and typed schema for proposal, quote, risk snapshot and result; tests for unknown venue/product, unit mismatch, unsupported instrument and malformed payload must fail before implementation.
- **Gate:** fixture tests run offline; every data field maps to a documented source or is explicitly user-configured.

### 2. Implement deterministic risk engine (TDD)
- Add Decimal arithmetic for walking ask/bid depth, limit price, insufficient liquidity, fees-known/unknown, exposure and daily-loss budget, with separate binary-share and spot-crypto policies.
- Add tests for stale quote, zero depth, partial fill, wrong outcome/product, wrong quantity unit or quote currency, unknown fees, unavailable position/P&L, cap reached, unsupported venue/instrument and cross-venue currency aggregation rejection.
- **Gate:** no market network needed for `tests/test_risk.py`; missing mandatory evidence yields BLOCK.

### 3. Add two read-only adapters and report
- Polymarket: resolve condition/outcome → token ID via public endpoints; fetch book with timeout and validate it. Coinbase Exchange: use a precise spot product ID and its public aggregated order book. Both normalize side/units/timestamps/source into the common contract; preserve venue-specific minimums and fees. Cache only within a short configured TTL.
- Test both with fixture HTTP responses and at least one live public book per venue in read-only mode, clearly separating test fixtures from live evidence. Check product status and market access conditions; a public quote does not establish that the user is eligible to trade.
- **Gate:** both live reads work without trading credentials; malformed/timeout/rate-limit errors are explicit and never produce PASS.

### 4. Package native plugin and targeted demo guard
- Register `tradeguard_evaluate` and a `pre_tool_call` hook with `**kwargs` compatibility; declare the exact tools/hooks in `plugin.yaml`. Ensure hook recognizes only the mock execution tool or a user-specified tool with a verified stable schema.
- Add a bundled skill for safe usage. Store a redacted audit trail in profile-scoped plugin storage.
- **Gate:** `hermes plugins doctor . --ci` and `hermes plugins validate . --install-deps` pass; synthetic order-tool call with exhausted *supplied* budget is blocked; unrelated tools work normally; both venue examples show coverage/unknowns and the plugin cannot place orders.

### 5. Polish and publish
- README: 60-second quickstart, screenshots/demo transcript, threat model, network/privacy/credential disclosures, tested Hermes version, and clear not-a-universal-firewall warning.
- Optional Desktop panel only if SDK documentation and time permit; otherwise focus on a crisp evidence card in tool output.
- Run `python -m pytest -q`, `hermes plugins doctor . --ci`, and `hermes plugins validate . --install-deps`; inspect warnings and scan public repo history for secrets and user data.
- Open plugin-catalog PR against NousResearch/hermes-agent, adding `plugin-catalog/hermes-tradeguard.yaml` pinned to the **full 40-character SHA** of this repo's tested commit. Submit PR + <90-second X demo as hackathon instructions require. Catalog admission/merge is a separate human review, not guaranteed by this plan.

## Demo storyboard (under 90 seconds)

1. Show one Polymarket binary-share BUY and one Coinbase Exchange spot-crypto BUY against live, timestamped public books through the same Hermes tool.
2. Show normalized evidence and distinct risk semantics: binary worst-case loss versus spot notional/inventory; synthetic account fixture is visibly labeled, unknown fees/positions are not silently treated as safe.
3. Change the fixture to exceed the daily-loss budget; call the mock order tool and show targeted hook BLOCK plus audit reason.
4. Show no wallet key, live execution or privileged override was needed; demonstrate quick install/validation and repo.

## Open decisions before implementation

- Pick authoritative read-only position/P&L inputs *for each venue* and a currency normalization policy. Until compliant credential routes and accounting semantics exist, use *clearly labeled user-supplied or synthetic risk snapshots*; do not claim live account or combined-portfolio protection.
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
