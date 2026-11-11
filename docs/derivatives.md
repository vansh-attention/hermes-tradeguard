# TradeGuard derivatives M1 — offline analytical contract

## What works, and what does not

M1 adds a pure contract-aware analytical engine and the eighth native tool, `tradeguard_derivatives_research`. It supports supplied standard cash-index futures, European cash-settled vanilla index calls/puts, and one-to-one same-expiry bull-call/bear-put debit verticals. It does not implement a live NSE/US derivatives feed, access a broker account, read credentials, size a portfolio or place any order.

The feature checkout uses version 0.2.0; publication/profile activation is separate. The published default branch does not acquire unpushed changes just because local tests pass.

**All final public M1 derivative interest scores are null / ABSTAIN.** Descriptive directional support is available where the matching daily underlier history is usable, but is never a live entry recommendation. Pure scoring-policy tests do not change that evidence boundary.

## Run the actual offline entrypoints

From the repository root:

```bash
# Futures and long-option calculations:
python3 -m tradeguard derivatives --snapshot examples/derivatives_synthetic.json \
  --as-of 2026-11-10T08:00:00Z
python3 -m tradeguard derivatives --snapshot examples/derivatives_synthetic_call.json \
  --as-of 2026-11-10T08:00:00Z --json
python3 -m tradeguard derivatives --snapshot examples/derivatives_synthetic_put.json \
  --as-of 2026-11-10T08:00:00Z --json

# Explicit matched debit verticals, not naked short legs:
python3 -m tradeguard derivatives --snapshot examples/derivatives_synthetic_call.json \
  --short-leg examples/derivatives_synthetic_call_short.json \
  --as-of 2026-11-10T08:00:00Z
python3 -m tradeguard derivatives --snapshot examples/derivatives_synthetic_put.json \
  --short-leg examples/derivatives_synthetic_put_short.json \
  --as-of 2026-11-10T08:00:00Z

# CLI/native/prompt comparison, with a compact derived report:
python3 scripts/exercise_derivatives_offline.py \
  --output artifacts/derivatives_offline_integration.json
```

The example instruments, prices, rates, costs, margins and weekday histories are conspicuously synthetic. They are not exchange-listed products, observed quotes or performance results. The fixed cutoff reproduces the example; an omitted cutoff uses current UTC and can add stale/expired blockers. Developer exercise subprocesses are not part of native tool loading or analysis.

For a native invocation, supply the same normalized object as `snapshot`, optional matching `short_leg`, and an aware ISO `as_of`. The native tool accepts no filesystem path, URL, provider selection or credential argument. CLI reads only explicitly named JSON files through its existing bounded reader.

`--snapshot` is exclusive with roots, `--interactive` and `--kind`. `--short-leg` requires a long snapshot; an invalid explicit short leg never falls back to a single option. JSON stdout remains machine-readable. Exit 0 means observations were produced, including legitimate abstention; malformed/unsupported snapshots exit 2. A well-formed root request exits 1 with `DERIVATIVES_PROVIDER_NOT_IMPLEMENTED`:

```bash
python3 -m tradeguard derivatives NFO:NIFTY --kind options --json
```

`--interactive` accepts bounded root lines and reports the same unavailable live-feed status; EOF/quit exits and interruption returns 130. `--allow-derivatives-data` is reserved and cannot enable an adapter that M1 does not contain.

## One canonical normalized snapshot

`schema_version` is integer 1. Required top-level fields are `contract`, `quote`, `underlying`, `source`; optional `rates`, `margin`, `costs` may be absent or null. Unknown top-level or nested fields are rejected. The five example JSON files are complete accepted shapes.

| Object | Important fields |
|---|---|
| contract | Exact opaque `contract_id`; ASCII `venue`/bare `root`; `family` index_future/index_option; exact `underlying_id`; uppercase three-letter `currency`; `value_per_price_unit`, `tick_size`; aware `last_trade_at`, `expiry_at`, `spec_effective_at`; `spec_source`; `settlement: cash`; `standard_deliverable: true` |
| option contract | `right: call/put`, positive `strike`, `exercise: european`, `underlying_kind: cash_index` |
| quote | Matching contract ID; positive noncrossed on-tick `bid`/`ask`; integer `bid_contracts`/`ask_contracts`; aware observed/received clocks; explicit delay and open/closed/unknown state; optional source-labelled volume/OI with contract units and clocks |
| underlying | Matching ID/currency; positive spot and spot clock; `interval: 1d`, `price_basis: price_index`, `adjustment: raw`; source/retrieval/finalization evidence; bounded sorted unique completed OHLCV bars |
| source | Provider description, retrieval clock, declared data mode, entitlement declaration and historical-vintage description. No field can create trusted live ingress. |
| rates | Matching underlier/currency, dated source, required continuous/ACT365F convention; missing r/q values remain missing, not zero |
| margin | Exact contract/currency, dated `amount_per_contract`, exchange/broker-reference scope, `account_specific: false` |
| costs | Exact contract/currency, dated `round_trip_per_contract`, source and explicit omitted-cost list |

Money inputs use plain exact decimal strings/integers, not binary floats, booleans, scientific notation or nonfinite values. Standalone money helpers support bounded `Decimal` inputs too; public snapshots must contain JSON types. Contract values apply the multiplier once: one reported contract is one derivative contract/lot, not a second multiplication by broker order quantity.

Cash-index OHLC uses finite positive numeric int/float values for the existing technical helper; this positive-cash-price assumption is not imposed on the separate linear futures P&L primitive, which accepts mathematically valid negative entry/exit prices. The recommendation universe remains cash-index-only.

### Resource and time limits

Validation bounds snapshots at 16 MiB compact JSON, 30,000 nodes, nesting depth 8, 32 object keys, 2,000 history bars, bounded text/IDs and exact decimal coefficient/scale limits. Cycles/non-JSON objects fail before copying. There is no provider-driven unlimited universe search.

A valid structure can still have unusable evidence. Quote/receipt/spot timing, delay, state, depth, source clock order and freshness produce blockers; malformed crossed/off-tick data fails structurally. Daily-history spacing checks reject sparse/weekly data but are not an independently verified exchange calendar. Missing or old optional evidence remains visible:

- reference margin freshness limit: one hour;
- cost estimate: 24 hours;
- rate/dividend evidence: seven days;
- current-entry quote/receipt/spot reference limits: 15 seconds, with five-second coherence limits.

These are declared engineering gates, not an empirical optimum or proof a source is correct. Supplied session/finalization attestations are unverified. Source clocks cannot be moved forward merely by relabeling a download.

## Calculation and reporting semantics

### Futures

Linear cash P&L is exit minus entry, times value per price unit, quantity and direction. Long entry uses ask, short uses bid. Scenarios vary a disclosed futures reference; they are not spot forecasts or guaranteed fill prices. Tick value, gross notional, optional costs and margin-reference status retain units/currency. Maximum loss is not capped by margin or a stop; account affordability is unverified.

### Options

Long premium uses ask. Expiry intrinsic, breakeven and gross loss/profit bounds are separate from any cost estimate and from early-exit liquidity. The pricing model is `BSM_EUROPEAN_CASH_INDEX_ACT365F`; it requires source-labelled matching rate/dividend inputs. Missing/stale inputs, unsupported styles and out-of-bracket/nonconvergent IV do not invent model values.

IV inverted from the same quote is not independent fair value. Bid/ask/midpoint IVs are model statistics; midpoint is not an execution. Delta/gamma are per index point/point squared, vega and rho per percentage-point move, theta per calendar day. Per-contract sensitivities multiply by value per price unit once. Greeks are not probabilities of profit.

### Debit verticals

Both legs must match underlier, right, currency, expiry/trading cutoff, style, deliverable and multiplier. The underlying histories, price basis, source and finalization attestations must also agree; equal current spot alone cannot reconcile contradictory trends. Equivalent timezone representations of one finalization instant are allowed.

Debit uses long ask minus short bid. Gross expiry bounds, breakeven, both legs' clocks/identity and supplied costs are visible. Two leg quotes do not establish an atomic spread fill. Credit/calendar/ratio/naked-short strategies and physical/early-exercise risks are not silently modeled as a supported debit spread.

## Provenance is explicit

Every public analyzer/native/CLI snapshot enters as `provenance.ingress: user_supplied_snapshot`, with `independently_verified: false` and `trusted_live_source: false`. Provider/entitlement claims cannot promote it. `fixture` is preserved only as a **caller-declared synthetic classification**, not proof that arbitrary bytes are independently known to be synthetic. The renderer says so. A mixed declared-fixture/imported vertical is user-supplied at the aggregate level and retains both leg declarations.

No JSON field, favorable trend value, score formatter or incomplete-data denominator can remove `OFFLINE_PROVENANCE_UNVERIFIED` or produce a numeric final entry-interest score. Structural error responses are JSON with a stable code and no recommendation.

## Offline injected-data batch interface

Library callers may use `tradeguard.derivatives.recommend_derivatives(requests, *, kind, provider, supplemental_by_root=None, as_of=None)`. The injected Python object supplies data; it is not a model-facing URL/class loader, built-in market feed or sandbox for arbitrary caller code. Native/CLI root requests do not instantiate it. The caller remains responsible for its own object's side effects.

The interface uses one bounded metadata call, per-root history/selection, then a final selected-quote call with simultaneous refreshed underlying spots. Wrong root/family, duplicate IDs, currency/underlier ambiguity and selection limits are explicit; stale/missing final spot never falls back to a more attractive earlier one. Data is copied and revalidated as unverified offline evidence; no raw histories are returned.

Root-level totals and contract-level totals have separate units. One root's failure cannot erase another's observations. Supplemental evidence is bounded and bound to exact requested roots/underlying/selected contract IDs; invalid supplied data does not silently fall back to invented complete evidence. All final M1 scores remain null.

## Research and remaining gates

- `docs/research/derivatives_strategy_library.md`: analytical scope versus researched-only/unsupported families.
- `docs/research/sources_derivatives.json`: prior primary-source inspection ledger, including direct/indexed access and source conflicts.
- `docs/research/derivatives_validation_protocol.md`: **unimplemented** point-in-time M3 protocol. The earlier equity ridge experiment does not validate derivatives.
- `docs/DERIVATIVES_M1_STATUS.md`: actual local execution checkpoints and verification state.

M2 needs separate owner approval, actual entitlement/credentials through approved routes, dated product/session specs and an exercised read-only adapter. M3 needs a suitable historical derivatives dataset and independently reviewed chronological evaluation. Neither milestone is implied by M1 tests, plugin validation, local commits or this documentation.
