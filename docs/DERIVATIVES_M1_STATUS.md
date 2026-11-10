# Derivatives M1 implementation status

## Authorized boundary

User explicitly selected: **Implement M1: the offline futures/options engine, without live feeds or trades**. Work is on `feat/derivatives-research`, starting from `46434c99ce192f0fa9e3c718d91d57be20d056e4`. No provider, account, credential, profile activation, push or catalog submission is authorized by this execution.

Specification: workspace `.hermes/plans/2026-11-10_224955-futures-options-derivatives.md`. M1 includes supported cash-index futures/European cash options/debit-vertical mathematics, strict snapshots, shared cash-index indicators, gated research scoring, offline CLI and one additive native tool. M2/M3 remain unimplemented.

## Verified baseline

- 2026-11-10 IST: `python3 -m pytest -q --basetemp <scratch>/tradeguard-m1-baseline`: **341 passed in 2.08s**.
- Initial repository worktree clean; package/plugin 0.1.0; seven tools and no hooks.

## Shared implementation contract / ownership

Parallel work owns disjoint files. Parent owns engine, interfaces, documentation, commits and final verification. Children must not commit or modify another stream's files.

- Contracts stream: `tradeguard/derivative_contracts.py`, `tests/test_derivative_contracts.py`, `tests/derivative_cases.py`.
- Math stream: `tradeguard/derivative_math.py`, `tests/test_derivative_math.py`.
- Indicators/policy stream: `tradeguard/indicators.py`, extraction aliases in `tradeguard/equity.py`, `tradeguard/derivative_policy.py`, `tests/test_shared_indicators.py`, `tests/test_derivative_policy.py`.
- Parent: `tradeguard/derivatives.py`, UI/CLI, root native plugin/manifest, integration tests, examples/docs/evidence.

### Normalized snapshot details fixed before integration

Canonical shape follows the plan. Additional precise field names:

- `contract.root` is the bare root (`INDEX` in synthetic cases), `venue` the venue (`TEST`); root requests combine them as `TEST:INDEX`. IDs remain opaque strings.
- `underlying` additionally requires `adjustment: raw`, `source` nonempty string and aware `retrieved_at`; raw numeric OHLC values may be finite int/float because they feed existing cash-price indicators. `spot` and monetary/contract values are exact decimal strings/integers.
- `margin`: `amount_per_contract`, `currency`, `contract_id`, `as_of`, `source`, `scope` in exchange_reference/broker_reference, `account_specific: false`.
- `costs`: `round_trip_per_contract`, `currency`, `contract_id`, `as_of`, `source`, `excludes` list of bounded strings.
- `rates`: plan fields `risk_free`, `dividend_yield`, `as_of`, `source`, `currency`, `underlying_id`, `compounding: continuous`, `day_count: ACT/365F`.
- `validate_snapshot(snapshot, *, as_of)` returns a deep-copied, JSON-serializable normalized snapshot with private `_validation: {blockers: [...], missing_data: [...], warnings: [...]}`. This field is forbidden in input. Input is never mutated; decimals stay serializable strings/ints. Structural errors raise `DerivativeInputError(ValueError)` carrying `.code`; unsupported families/styles use `UNSUPPORTED_INSTRUMENT`; malformed shapes use `INVALID_DERIVATIVE_SNAPSHOT`.
- Expiry/stale/delayed/closed/unknown eligibility is preserved as blockers where safe for descriptive calculation; malformed or unsupported objects fail structurally. Crossed/one-sided/off-tick quotes are never entry candidates.
- Offline ingress always preserves fixture mode or forces user_supplied + unverified entitlement; it adds OFFLINE_PROVENANCE_UNVERIFIED. No JSON flag can assert trusted adapter provenance. All M1 final recommendation scores consequently abstain; separate descriptive directional support remains visible when bars are usable. Pure scoring functions are tested independently and do not establish an actionable entry.
- Incomplete but valid short history returns observations with insufficient-history blockers; duplicate dates, OHLC errors and sparse non-daily history are rejected.
- Synthetic helper `snapshot(kind="future", **overrides)` returns fresh data with TEST venue/root/IDs, fixed cutoff `2026-11-10T08:00:00Z`, future expiry/last trade `2026-12-18T14:30:00Z`, 200 prior weekday bars increasing to close 100, spot 100, multiplier 5/tick 0.25; options are call strike 100, bid 5.75/ask 6, European cash-index. Default quote times at cutoff minus 1 second; source is conspicuously fixture. Include matching dated rates/margin/cost examples only as synthetic evidence.

## Execution checkpoints

- [x] Explicit user approval and bounded scope.
- [x] Original 341-test baseline and clean-tree/HEAD check.
- [x] Feature branch created without changing the published main branch.
- [ ] Pure contract, arithmetic and indicator/policy streams verified.
- [ ] Offline futures/options/vertical reports and adversarial gates verified.
- [ ] CLI/native parity and no-network behavior exercised.
- [ ] Documentation/examples and official Hermes validation refreshed.
- [ ] Independent review findings resolved; exact final test/commit status recorded.

This is progress state, not a claim that unfinished steps or live derivatives support work.
