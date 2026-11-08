# Hermes TradeGuard — locked initial plan

> Status: scope baseline v0.1, drafted 2026-11-08 (IST). This is a plan, not an implemented or security-audited trading system. Change scope only by editing this file in a later, explicit revision; do not silently expand into live trading.

## Goal and pitch

Build a **read-only, evidence-first trading decision plugin for Hermes Agent**. Given a Polymarket market and a proposed BUY/SELL, it fetches fresh executable book data and current positions/risk inputs, computes what the order would actually cost or return (including available depth), and produces an auditable **GO / CAUTION / BLOCK** decision with reason codes. A Hermes `pre_tool_call` hook can reject or escalate specifically configured, recognized order-tool calls, but the core MVP never submits an order.

Demo hook: Hermes proposes buying a tempting weather contract; TradeGuard catches an exhausted daily-loss allowance or a stale/insufficient book and rejects the configured trade-tool call, showing the evidence and a clear reason. The plugin is **not** a universal firewall: shell, browser, other plugins, external apps, and direct exchange/API access may bypass it. A hook exception may be logged and skipped by Hermes, so hard enforcement belongs inside a future dedicated execution adapter, not in the hook alone.

## Scope decision

- **Market:** Polymarket binary outcome shares only, one market/outcome per evaluation. This is a decision-support plugin, not a prediction model or guaranteed edge finder.
- **MVP:** read-only public market/book adapter, typed proposal evaluation, opt-in targeted `pre_tool_call` guard for one explicitly named execution tool, audit trail, and a concise evidence report. Default behavior is no executions and no wallet signing.
- **Stretch:** Desktop evidence pane/card via the documented Desktop Plugin SDK, only after the backend is tested. A demo with a fake execution tool can prove hook behavior without risking money.
- **Out of scope:** autonomous trading, wallet/private-key handling, inferred profit probabilities, universal interception of `terminal`/`execute_code`/browser, broad multi-exchange support, and any live order placement in the hackathon MVP.
- **Privacy:** make public data work without credentials. If private position/P&L reads are later added, declare secrets via Hermes-approved routes and `agent.secret_scope.get_secret`; never read another CLI's token files, `~/.hermes/.env`, browser storage, or wallet secrets. Do not publish the user's balances, positions, local paths, or real trade logs.

## User journey

1. User asks Hermes: “Evaluate buying 20 YES shares of this weather outcome at at most $0.42.”
2. Tool resolves the exact market/outcome IDs; ambiguous matches cause a request for clarification, not a guess.
3. Adapter retrieves a **timestamped** order book and, if configured, a separately sourced risk snapshot. Quotes are reported as bid/ask with depth and age, never last-trade price as if executable.
4. Engine calculates fillable quantity, worst acceptable price, cash required/received, conservative exposure and any fees known from the source. If fees are unknown, state so and avoid net-return claims.
5. Engine applies explicit guardrails: quote TTL; size/price bounds; slippage/depth; per-market exposure; optional daily-loss ceiling. Missing mandatory risk data yields BLOCK (never “zero losses”).
6. Report prints GO / CAUTION / BLOCK, numeric inputs, source/timestamp, triggered reason codes, and the exact conditions under which a human might reconsider. No placement occurs.
7. Optional demo: a mock `tradeguard_demo_order` call is intercepted by the targeted hook and blocked/escalated. No real order endpoint is present in MVP.

## Safety and correctness contracts

- Never label a reference midpoint or last trade as an executable price. Use the ask ladder to evaluate BUY and bid ladder for SELL. Normalize outcome token IDs before reading the book.
- Reject stale, missing, malformed, crossed, empty, inconsistent, or insufficient-depth books; reject NaN/infinity/negative amounts. Use `Decimal` for money and explicit currency/units. Include UTC observation time and local receipt time; enforce TTL on the latter unless provider timestamps are trustworthy.
- Require the risk snapshot to name its source, observation time, account scope, starting balance and realized P&L semantics. Distinguish *realized daily loss* from open-position mark-to-market loss. If unavailable, label the check UNAVAILABLE/BLOCK; never fabricate account state or a daily-loss cap.
- Configuration holds policy amounts; proposal cannot override limits. Server-side evaluation takes place at call time. If a future live adapter is built, it must independently re-fetch/re-evaluate immediately before order placement, require explicit human approval, cap price/size, use idempotency protection, and read back accepted/fill/cancel state. A prior GO is not permission to trade.
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
│   ├── polymarket.py               # read-only public market and order-book adapter
│   ├── risk.py                     # pure deterministic evaluation and reason codes
│   ├── report.py                   # evidence and audit rendering
│   └── audit.py                    # profile-scoped minimal event storage
├── skills/tradeguard/SKILL.md      # when to call tool; never execute from GO alone
├── tests/
│   ├── test_risk.py
│   ├── test_books.py
│   ├── test_hook.py
│   ├── test_audit.py
│   └── fixtures/                  # synthetic, not copied from real user account
└── desktop/                        # stretch only: documented SDK plugin.js
```

**Implementation seam:** native Hermes plugin (`plugin.yaml` + `register(ctx)`), a namespaced read-only `tradeguard_evaluate` tool, and `ctx.register_hook('pre_tool_call', ...)`. The hook returns a documented block directive only for explicit known tools/arguments. Check exact Hermes hook/tool schemas and Polymarket API contracts against current official docs before coding; do not guess payload names. Prefer the host's plugin data directory/database for audit state; do not hardcode `~/.hermes` because profiles are isolated. Keep external dependencies minimal and pinned with compatible bounds.

## Build sequence and acceptance gates

### 1. Confirm interfaces and write contract tests
- Inspect current Hermes plugin/doctor, hook directive, Desktop SDK (if used), and Polymarket public market/book API docs; record URLs and versions in README.
- Define fixture JSON and typed schema for proposal, quote, risk snapshot, and result; tests for unknown outcome and malformed payload must fail before implementation.
- **Gate:** fixture tests run offline; every data field maps to a documented source or is explicitly user-configured.

### 2. Implement deterministic risk engine (TDD)
- Add Decimal arithmetic for walking ask/bid depth, limit price, insufficient liquidity, fees-known/unknown, exposure and daily-loss budget.
- Add tests for stale quote, zero depth, partial fill, wrong outcome, price/size bounds, unavailable position/P&L, and cap reached.
- **Gate:** no market network needed for `tests/test_risk.py`; missing mandatory evidence yields BLOCK.

### 3. Add read-only Polymarket adapter and report
- Resolve market → outcome token IDs via public endpoints; fetch book with timeout and validate it before risk evaluation. Cache only within a short configured TTL, always disclose observation times.
- Test with fixture HTTP responses and at least one live public market in read-only mode, clearly separating test fixtures from live evidence.
- **Gate:** live read works without a trading credential; malformed/timeout/rate-limit errors are explicit and never produce GO.

### 4. Package native plugin and targeted demo guard
- Register `tradeguard_evaluate` and a `pre_tool_call` hook with `**kwargs` compatibility; declare the exact tools/hooks in `plugin.yaml`. Ensure hook recognizes only the mock execution tool or a user-specified tool with a verified stable schema.
- Add a bundled skill for safe usage. Store a redacted audit trail in profile-scoped plugin storage.
- **Gate:** `hermes plugins doctor . --ci` and `hermes plugins validate . --install-deps` pass; synthetic order-tool call with exhausted budget is blocked; unrelated tools work normally; plugin cannot place orders.

### 5. Polish and publish
- README: 60-second quickstart, screenshots/demo transcript, threat model, network/privacy/credential disclosures, tested Hermes version, and clear not-a-universal-firewall warning.
- Optional Desktop panel only if SDK documentation and time permit; otherwise focus on a crisp evidence card in tool output.
- Run `python -m pytest -q`, `hermes plugins doctor . --ci`, and `hermes plugins validate . --install-deps`; inspect warnings and scan public repo history for secrets and user data.
- Open plugin-catalog PR against NousResearch/hermes-agent, adding `plugin-catalog/hermes-tradeguard.yaml` pinned to the **full 40-character SHA** of this repo's tested commit. Submit PR + <90-second X demo as hackathon instructions require. Catalog admission/merge is a separate human review, not guaranteed by this plan.

## Demo storyboard (under 90 seconds)

1. Show Hermes evaluating a plausible weather-contract BUY against a live, timestamped public book.
2. Show exact ask depth, proposed fill/cost and an explicit source and risk snapshot (synthetic account fixture is visibly labeled).
3. Change the fixture to exceed the daily-loss budget; call the mock order tool and show hook BLOCK plus audit reason.
4. Show that no wallet key, live execution, or privileged override was needed; show quick install/validation and repo.

## Open decisions before implementation

- Pick the authoritative read-only positions/P&L input for a portable plugin. Until a compliant credential route and accounting semantics exist, use *clearly labeled user-supplied or synthetic risk snapshots*; do not claim live account protection.
- Verify whether the target Hermes release exposes a documented UI bridge for showing live evidence. If not, keep the demo text-only rather than touching private Desktop markup.
- Decide whether a later phase should offer a dedicated approved order adapter; it requires a separate security review and explicit user authorization. It is **not** part of this initial scope.

## Official references (recheck before coding)

- Hermes plugin guide: https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
- Catalog submission: https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission
- Event hooks: https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
- Polymarket developer documentation: https://docs.polymarket.com/
