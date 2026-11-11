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
- [x] Pure contract, arithmetic and indicator/policy streams verified.
- [x] Offline futures/options/vertical reports and core adversarial gates verified.
- [x] CLI/native parity and no-network behavior exercised on the shipped synthetic cases.
- [x] Documentation/examples and official Hermes validation refreshed.
- [x] Independent review findings resolved; final measured test status recorded below; local commit is recorded in Git history.

## Historical parent integration checkpoint (before November 11 continuation)

- Genuine RED observed for missing `tradeguard.derivatives`, missing derivative renderer and absent native registration before adding their code.
- Offline renderer tests: `python3 -m pytest -q tests/test_derivative_cli.py --basetemp <scratch>/tradeguard-m1-ui-green`: **2 passed**.
- Inert registration + existing plugin tests: `python3 -m pytest -q tests/test_derivative_plugin.py::test_derivative_tool_registers_inertly_without_live_surface tests/test_plugin.py --basetemp <scratch>/tradeguard-m1-native-registration-green`: **5 passed**.
- Native registration now declares eight tools in the working branch, but actual derivative handler/calculation integration is **not yet verified**. The offline core streams are running in parallel. No completion or live-support claim follows from registration.
- Parent has prepared futures report and integration tests; option/vertical reporting and CLI integration remain pending dependent core results. No provider module, credentials or network capability has been introduced.
- First local checkpoint commit: `5810f15` (authorized boundary/status document only). No push.

## November 11 continuation / review fixes

- Preserved the existing feature branch and all uncommitted changes instead of restarting from published main. Initial continuation run found seven failures/833 passes; after the selection and developer-exercise fixes, parent verification returned **840 passed in 3.00s**.
- Selection now excludes the wrong contract family before option strike access, rejects eligible mixed currency/underlying ambiguity, and preserves exact single-reason exclusion counts. The unchanged selection test file passed **49 tests**.
- Added `scripts/exercise_derivatives_offline.py`: actual CLI/registered-handler equality for five synthetic future/option/debit-spread cases, eight-tool registration, unavailable root status and two-line prompt behavior. No market data, accounts or secrets are accessed.
- Review regressions first reproduced contradictory spread histories and mixed-source mislabelling. The engine now requires a coherent common underlier history/source/finalization, preserves equivalent timezone instants and reports mixed declared-source legs as user-supplied.
- Provenance correction deliberately preserves `fixture` only as a caller-declared classification, never verification: all public results explicitly carry user-supplied snapshot ingress, no independent verification and no trusted live source. Human rendering must say caller-declared synthetic/unverified; imported JSON cannot assert trust. This avoids falsely certifying arbitrary payloads while retaining honest fixture declarations.
- Additional RED/GREEN regressions prevent stale/unusable history from exposing a current numeric directional view, and prevent stale/unknown/closed quote evidence from yielding available current IV/Greeks. Gross descriptive payoff calculations remain visible.
- Parent review/docs/verifier targeted checkpoint: **48 tests passed in 0.47s**. This is not the final full-suite total.
- Added the derivative source/status library and unimplemented point-in-time M3 protocol, with prior-inspection dates and direct/indexed provenance kept distinct. Package/manifest/runtime metadata are aligned at 0.2.0; no release tag/publication is implied.
- Doctor passed with **eight tools, zero hooks**. One early full validation reported `dependency preparation failed: Dependency inputs changed while preparing publication; retry.` despite exit zero and ok JSON. That run is **not accepted as a successful full admission gate**. Final validation must be rerun after all writers finish.
- Hardened the verification runner against that observed false-positive: preserve actual stdout/stderr/returncode, separately fail dependency-preparation diagnostics, incomplete/failed structured checks or warnings. Added genuine failing regressions before implementing the gate.
- Completed injected offline batch orchestration and detailed payoff rendering. Parent inspected the implementations and reran the frozen-tree gates; no worker success claim was substituted for parent verification.

## Final M1 verification — November 11, 2026

- `python3 scripts/verify_project.py --scratch <scratch>/tradeguard-m1-final-verification` completed with exit 0. Actual full suite: **1,176 passed in 4.66s**. All six recorded commands succeeded and were independently accepted by the stricter verification verdict.
- The actual developer exercise passed five synthetic CLI/native cases (future, long call/put, both debit verticals), eight-tool registration, unavailable root requests and two-line prompt behavior. All final scores remained null, and no raw history was copied into its case summaries.
- Official doctor: **eight tools, zero hooks**. Full `validate --install-deps --json`: dependency preparation completed, all structured checks passed, zero warnings. The earlier changed-input run was not counted as a pass.
- Parent also exercised the public Python batch API: three tokens/two unique roots, one analyzed root and one isolated failure, exact contract counts, quote-last call order and zero eligible roots. Its provider was explicitly synthetic/in-memory, not a real market feed.
- Human option/vertical commands displayed the required strike/right/multiplier/premium/debit/breakeven and leg clocks. `docs/DERIVATIVES_M1_REPORT.md` and the two derived verification artifacts are the handoff.
- M1 source, tests, examples and documentation are ready for the local checkpoint. M2/M3, active-profile installation, remote push and catalog submission remain unimplemented/unperformed; no trading credentials or accounts were accessed.

M1 is analytical implementation evidence only. It is not proof of live derivatives access or recommendation performance.
