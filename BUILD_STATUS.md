# Equity research build — continuity checkpoint

Started 2026-11-09 IST. User authorized internet research and implementation of a stocks/ETF recommendation component. No broker/order execution authorized or implemented. Existing PLAN v0.3 is architecture, not live venue support.

## Work boundaries
- Parent: primary-doc discovery, plugin manifest/handlers, providers, CLI, integration, README, adversarial verification.
- Core worker: tradeguard/equity.py + tests/test_equity.py.
- Validation worker: tradeguard/validation.py, tradeguard/microstructure.py + matching tests.
- Research workers: docs/research/equity_etf_strategy_library.md, microstructure_ml_validation.md and source JSONs.

## Acceptance criteria
- Primary-source major-strategy library, mathematics, limitations and source ledger; explicitly not every strategy.
- Stock fundamentals + daily technical observations; ETF-specific costs/holdings metrics, no entity-level company valuation on ETF.
- Explicit data provenance, timestamps, missingness, abstention; unvalidated heuristic score is NOT win probability.
- Chronological, label-purged cost-aware ridge research baseline and aligned buy-and-hold comparison; no false HFT claims.
- Actual loadable Hermes plugin through public ctx APIs only, matching declared tools; doctor and validate run locally.
- Offline tests plus real network read and actual CLI/tool output. SEC 403 or other source failures reported, never replaced with invented real fundamentals.
- No live orders, credentials, self-update, core mutation, telemetry, installed active-profile changes or public catalog submission.

## Discovery
- Local project was not a git checkout; initialized it, attached existing public origin, fetched and mixed-reset to origin/main without overwriting PLAN.md.
- Installed Hermes: v0.22.7+653.gef50e94, Python 3.14.9. No update performed.
- Native web_extract backend cannot extract; fetched official docs via HTTPS and inspected article/code blocks.
- Direct Yahoo chart AAPL request succeeded. Stooq returned HTTP 200 HTML instead of CSV (NOT data). SEC companyfacts returned HTTP 403. Provider must expose this honestly; offline SEC JSON normalization can still be tested.
- Official catalog requires full SHA pin, public surfaces, exact declared tool registration, local validate --install-deps, disclosures, no self-updater/credential-store reads.

## Implementation checkpoint — November 10, 2026 IST

- Existing draft baseline: 214 tests passed; native doctor and full validate passed with five read-only tools.
- Added a source-linked strategy catalog and actual `strategies` CLI/native entrypoint (six tools total); source-ID/ledger consistency is tested.
- Confirmed quarterly/unknown-duration fundamentals could produce a 100-point candidate; added tests first and then gated annual duration, symbol binding and market-cap timing. Added explicit `strong_recommendation_eligible: false` and provenance limitations. Explicit partial ETF disclosure now overrides a near-complete weight sum.
- Added input-boundary regression cases; weekly series is rejected before daily annualization and malformed CLI attachments cannot traceback.
- Refreshed SPY NAV from its official issuer to Nov 9 while retaining Nov 6 holdings clock. Microsoft's annual example was rechecked against its official FY26 release.
- `python3 scripts/exercise_research.py --allow-public-data` completed actual MSFT/SPY downloads through Nov 9; both registered handlers and CLI produced matching analysis/ML output. SEC companyfacts still returned HTTP 403, explicitly recorded.
- Both samples remain WATCHLIST, not strong recommendations. The experimental ridge baseline underperformed buy-and-hold on both; do not promote it. Exact measurements are in `artifacts/integration_verification.json`.
- Parent-owned 149 tests passed; doctor and `validate --install-deps --json` passed with six tools, zero hooks, zero warnings.
- Independent source, financial-boundary and ML/microstructure audits have returned. The source audit covers 47 records and nine repository/commit license pins; the math worker added 30 regressions, including exact integer OFI/clock preservation and sparse-series controls.
- Closed remaining provider/supplied-data audit issues with tests first: explicit `1d` granularity, malformed chart schema failures, SEC numeric-CIK binding, and source-supplied completed-session clock validation. Whole/recent-window daily spacing is checked before annualization. Latest full-suite run: 285 passed.
- Combined verification passed: 285 tests, source-integrity checks, native doctor (six tools, zero hooks), full validator (all checks passed, zero warnings), and `git diff --check`. Raw command/exit evidence is in `artifacts/verification_run.json`; the measured real-data report is `RESEARCH_AND_BUILD_REPORT.md`. No catalog submission, runtime installation, public push or trade execution was performed in this continuation.

## Buy-interest presentation update

- User requested a final 0–1 buying recommendation with a more constructive tone. Added a final `buy_recommendation` block shared by native analysis and CLI, derived from the existing capped score without changing weights, thresholds, evidence gates or predictive claims.
- Abstention is null, not a false zero or a positive default. Constructive watchlists retain cautions and `strong_buy: false`. Added ten regression cases first; all 295 tests passed after implementation.
- Executed the user's exact network-enabled MSFT command: exit 0, final score 0.69, `CONSTRUCTIVE_WATCHLIST`; missing earnings yield, FCF yield and interest coverage remain disclosed. No account access or trade execution.

## Ticker-only interface update

- Added `recommend` CLI for up to ten case-insensitive ticker tokens, compact readable tables/JSON, and an explicitly requested interactive prompt taking ticker-only lines. Original tokens are retained; canonical duplicates fetch once and malformed inputs fail before networking.
- Added native `tradeguard_recommend_tickers`: one opt-in handler fetches and analyzes requested symbols without returning raw five-year histories. No source/example files are silently attached, and no automatic fundamental feed is claimed. Technical-only and combined recommendations remain explicitly separate; invalid supplied combined metadata never silently falls back to the more attractive technical score.
- Actual CLI, registered handler and interactive prompt were exercised against live public MSFT/AAPL/SPY history through Nov 9. Deterministic metrics/scopes matched; technical scores were 1.00/1.00/0.85, combined scores unavailable. Evidence: `artifacts/ticker_integration_verification.json`.
- Final reviewed verification: 339 tests passed, doctor discovered seven tools/zero hooks, full validator passed with zero warnings, source-integrity and whitespace checks passed. Read-only contract-review suggestions were covered with regressions for blocked raw trend scores, explicit horizons, Unicode/invalid identifiers, disabled/nonboolean native consent, stale supplied metadata, and prompt EOF/cancellation. No installation, profile activation, remote push or orders were performed during that phase.

## Native plugin publication preparation

- Owner authorized publishing the current code to the existing public repository. Native packaging is `plugin.yaml` plus root `register(ctx)`, seven declared tools, no hooks or privileged capabilities, and no third-party runtime dependencies.
- Added Git-based Hermes installation instructions, opt-in data configuration and fresh-chat usage; added an offline Python 3.11–3.13 CI matrix with immutable official action pins.
- Verification logs redact absolute local checkout/home/scratch paths without changing measured exit codes or metrics. Raw vendor histories, private outputs, credentials, caches and generated build directories remain excluded.
- Final local pre-publication suite: 341 tests passed; Hermes doctor and full `validate --install-deps` passed with seven tools, zero hooks and no warnings. Catalog submission and active-profile installation are separate and were not requested.

## Offline derivatives M1 — November 11, 2026

- Local feature branch `feat/derivatives-research` extends the native plugin to version 0.2.0 with an eighth, offline-only derivatives tool. Existing stock/ETF tools remain compatible; no live derivatives adapter, accounts, credentials or trades were added.
- Implemented exact contract/evidence gates, futures cash scenarios, European cash-index option IV/Greeks and payoff bounds, coherent matched debit verticals, root metadata selection, injected offline-data batches and auditable CLI output. Fixture labels are caller declarations; final M1 scores always abstain.
- Parent verification: **1,176 tests passed**; actual CLI/native equality on five synthetic cases; doctor eight tools/zero hooks; full validator including dependency preparation passed with zero warnings; source/whitespace checks passed. Saved real outcome evidence in `artifacts/verification_run.json` and `artifacts/derivatives_offline_integration.json`.
- Full details and remaining M2/M3 gates: `docs/DERIVATIVES_M1_REPORT.md`, `docs/DERIVATIVES_M1_STATUS.md` and `docs/derivatives.md`. No remote push, catalog submission or active-profile activation is claimed for this continuation.
