# TradeGuard derivatives M1 — verified offline implementation

**Verified locally: November 11, 2026.** Version 0.2.0 on `feat/derivatives-research`. This report describes a working offline analytical feature, not live market access, a profitable strategy or a published release.

## What is implemented

- Exact supported index-future/European cash-index option identity, currency, multiplier, tick, expiry/style and bounded evidence validation.
- Linear futures cash P&L, notional/tick value and quote-side scenarios. Margin/stop amounts are never presented as maximum loss or verified account affordability.
- Long calls/puts: ask-side premium outlay, gross expiry payoff/breakeven/bounds, optional sourced-rate BSM IV inversion and unit-labelled Greeks.
- Matched bull-call/bear-put debit verticals, including both legs' identity/clocks, coherent underlier history, gross bounds and explicit non-atomic-fill caveat.
- Shared cash-underlier technical observations without changing equity semantics; current directional/model outputs are unavailable when their component evidence is unusable.
- Bounded root metadata selection and a Python-only injected offline-data batch interface with quote-last spot refresh, per-root failures, exact separate root/contract totals and no raw history output.
- Actual CLI, terminal renderer, reserved root prompt and eighth native Hermes tool, `tradeguard_derivatives_research`.
- Research/status documentation, a separate derivative citation ledger and an explicitly unimplemented point-in-time M3 validation protocol.

## Measured verification

The final local verification workflow actually ran:

| Gate | Observed result |
|---|---|
| Full pytest suite | **1,176 passed**; recorded run completed in 4.66 seconds |
| Existing equity/microstructure source-integrity command | `ok: true`; existing source ledgers retained |
| Derivative research/status/version regressions | Included in the full passing suite |
| Offline CLI/native/prompt exercise | **Five synthetic cases passed**; complete CLI/native JSON equality; eight registered tools; root request correctly unavailable; two prompt JSON lines |
| Hermes doctor | Passed; **eight tools, zero hooks** |
| Full Hermes `validate --install-deps --json` | Dependency resolution/preparation succeeded; every structured check passed; **zero warnings** |
| Whitespace check | Passed |

Evidence: `artifacts/verification_run.json` retains real command results and exit codes with local path redaction; `artifacts/derivatives_offline_integration.json` contains compact measured entrypoint comparisons. The verification runner separately rejects dependency-preparation failures even if a host CLI prints ok JSON and exits zero.

### Exercised cases

| Synthetic case | Actual CLI/native agreement | Final entry score |
|---|---|---|
| Cash-index future | Passed | null / ABSTAIN |
| Long call | Passed | null / ABSTAIN |
| Bull-call debit vertical | Passed | null / ABSTAIN |
| Long put | Passed | null / ABSTAIN |
| Bear-put debit vertical | Passed | null / ABSTAIN |

A separate direct call through the public Python batch API used an explicit in-memory synthetic provider: three requested tokens deduplicated to two roots; one root produced observations and the other failed independently; the final quote call followed metadata/history; eligible root count remained zero. This is interface/failure-isolation evidence, not a successful real feed.

Human call/spread commands were also run directly: the renderer displays strike/right, multiplier, ask premium/debit, gross breakeven/bounds, both leg roles and evidence clocks. It marks fixture origin as caller-declared/unverified rather than independently certified synthetic data.

## Try it from this checkout

```bash
python3 -m tradeguard derivatives \
  --snapshot examples/derivatives_synthetic_call.json \
  --as-of 2026-11-10T08:00:00Z
```

For a matched spread, append:

```bash
--short-leg examples/derivatives_synthetic_call_short.json
```

Use `--json` for full model/evidence details. The fixtures deliberately use a fixed past cutoff and invented `TEST` instruments; omitting the cutoff uses current UTC and can add stale/expired blockers.

## Important limits

**M1 is offline only.** All public snapshot ingress is unverified user-supplied data. Fixture classification is a caller declaration; mixed fixture/imported legs are not presented as wholly synthetic. Final current-entry interest is always null, even when a descriptive directional diagnostic is numerically high.

No live NSE/US chain/contract resolver, broker credentials/account reads, trades, sizing, active-profile installation, remote push or catalog submission were performed. The local CI workflow has been updated, but no new remote CI run or public release is claimed.

American/physical/adjusted options, options on futures, commodities, inverse/perpetual futures and naked/credit/calendar/ratio strategies remain unsupported. No derivatives model or recommendation policy is performance-validated. The earlier equity ridge experiment is not derivatives validation.

M2 requires separately approved data access, effective contract/session specifications and a genuinely exercised read-only adapter. M3 requires suitable point-in-time derivatives data and independent chronological evaluation. Their absence is not hidden behind synthetic results.
