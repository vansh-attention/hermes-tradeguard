# TradeGuard — Hermes equity/ETF research plugin

A **read-only stocks/ETF research plugin for Hermes Agent**. It separates company fundamentals, daily technical observations, ETF structure and experimental ML evaluation. It does not place orders and does not call a 0–100 heuristic a win probability.

> This is a research prototype, not a proven alpha service or a universal trading firewall. The broader multi-venue roadmap remains in `PLAN.md`; prediction-market/futures/options adapters and a blocking hook are not part of this implementation.

## Install in Hermes

Requires Hermes **0.22.7 or newer**. Install this repository as a native Git-distributed plugin (it is not a reviewed Hermes catalog entry):

```bash
hermes plugins install vansh-attention/hermes-tradeguard --enable

# Optional: permit explicitly requested public historical-data lookups.
# Without this, offline snapshot tools work but ticker fetching stays disabled.
hermes config set plugins.entries.tradeguard.settings.allow_public_data true

hermes plugins show tradeguard
```

Start a **new Hermes chat** after enabling, and follow a restart instruction if Hermes prints one. Then ask:

> Use TradeGuard for MSFT AAPL SPY. Show the 0–1 technical scores, source dates and missing fundamental data; do not treat technical-only scores as combined valuations.

For an immutable installation, add `--ref` followed by the repository's full tested 40-character commit SHA to the install command. No trading keys or broker login are needed. This plugin has seven model-callable tools, zero hooks and zero third-party runtime Python dependencies; loading it does not fetch data or enable networking.

To run the standalone CLI instead:

```bash
git clone https://github.com/vansh-attention/hermes-tradeguard.git
cd hermes-tradeguard
python3 -m tradeguard recommend --interactive --allow-public-data
```

The repository's GitHub Actions run offline tests and source-reference checks on Python 3.11–3.13. Official Hermes `doctor` and `validate --install-deps` remain separate local/plugin-admission gates; a passing repository workflow is not catalog admission.

## Research first, then a tested subset

The strategy library is deliberately **broad, not exhaustive**. See:
- `docs/research/equity_etf_strategy_library.md` — major stock/ETF strategy families, mathematical metrics, candidate entry/exit hypotheses, required data and failure modes.
- `docs/research/microstructure_ml_validation.md` — HFT/microstructure metrics versus daily investing; ML validation, leakage and costs.
- `docs/research/sources_equity.json` and `sources_microstructure.json` — primary-source ledger and official open-source license references.
- `python3 -m tradeguard strategies` — an offline, source-linked directory of covered strategy families, mathematical objectives, data requirements and failure modes. Every family states whether it is researched-only, feature-only, a heuristic screen or an experimental baseline; none is claimed performance-validated.

Original papers and reputable code inform the design; they do **not** validate this implementation's exact scoring thresholds or reproduce a paper's results. No proprietary strategy, binary, paid service or third-party code is decompiled/copied. Public source repositories do not need binary reverse-engineering.

## Runtime scope

| Component | Purpose | Boundary |
|---|---|---|
| Fundamental research | Annual income/cash-flow/balance-sheet ratios; explicit missingness | Not a complete sector-adjusted valuation model, DCF, filing parser or TTM history |
| Daily technical observations | Trend/momentum/volatility/liquidity statistics | No intraday executable quote, validated alpha or guaranteed entry |
| ETF research | Costs, same-date NAV comparison, disclosed-holdings concentration | Partial holdings are not a full look-through portfolio; NAV comparison is not AP arbitrage |
| Recommendation | Explainable heuristic research priority and evidence coverage | No calibrated win rate, price target or position sizing |
| Ranking | At most 50 explicitly supplied comparable snapshots | Same instrument family/currency/end date; no implicit whole-market universe |
| ML experiment | Chronological, label-purged expanding-window ridge baseline with next-open simulation and costs | Technical features only; no fundamental ML without historical point-in-time fundamentals; no model-selection/production-readiness claim |
| Microstructure | Spread, queue imbalance, weighted midpoint, event OFI | Needs supplied quotes/events; no HFT execution, queue/fill simulator or calibrated microprice |

## Run locally

Python 3.11+; the runtime has **no third-party Python dependencies**. Development tests require pytest.

### Just type tickers

No snapshot or fundamentals file is required for a clearly labelled **technical-only** screen:

```bash
python3 -m tradeguard recommend MSFT AAPL SPY --allow-public-data

# Keep a prompt open; then enter only ticker names:
python3 -m tradeguard recommend --interactive --allow-public-data
```

At the prompt, enter `MSFT`, `AAPL SPY` or `msft, aapl`; enter `quit` to exit. One-shot `recommend` prints a readable table; append `--json` for compact machine-readable output. Interactive `--json` emits one JSON object per submitted line, with prompts on stderr. Input is explicitly case-insensitive, original tokens are retained, and duplicate canonical symbols are fetched once. Dot/hyphen share-class punctuation is never silently rewritten. Up to ten tokens are accepted per batch; malformed or oversized input fails before network access. Each failed provider lookup is reported separately and cannot acquire a score.

The table separates **Technical** and **Combined** scores. Ticker-only mode fetches public price history automatically, but does **not** auto-fetch financial statements or ETF holdings, and never silently attaches the bundled Microsoft/SPY examples. A technical score is a price-trend screen, not a substitute for the combined valuation score. It can differ from the earlier combined score because its scope and scoring denominator are different. Both are uncalibrated, not probabilities.

The native `tradeguard_recommend_tickers(tickers, as_of?, fundamentals_by_symbol?, etf_by_symbol?)` tool provides the same one-call mechanism in Hermes when the plugin is enabled and public-data access is explicitly permitted. Its description routes ticker-only requests; the model does not need to relay raw five-year bar arrays between tools. Optional metadata maps must explicitly bind each record to the requested canonical symbol. With supplied metadata the combined result is selected, including abstention if invalid; it never silently falls back to a higher technical score. This is still not an automatically refreshed all-company fundamental feed.

### Detailed analysis and experiments

```bash
python3 -m pytest -q
python3 -m tradeguard --help
python3 -m tradeguard strategies --asset-type etf

# Offline, with a normalized snapshot you are allowed to use:
python3 -m tradeguard analyze --snapshot /path/to/snapshot.json

# Explicitly opt in to the unofficial public historical-data endpoint:
python3 -m tradeguard analyze --symbol MSFT --allow-public-data \
  --fundamentals examples/msft_fy2026_fundamentals.json
python3 -m tradeguard analyze --symbol SPY --allow-public-data \
  --etf-metadata examples/spy_issuer_metadata.json

# Use a locally retained, authorized snapshot for the ML experiment:
python3 -m tradeguard walk-forward --snapshot /path/to/snapshot.json \
  --min-train 252 --cost-bps 5
python3 -m tradeguard rank --snapshots /path/to/comparable-snapshots.json
python3 -m tradeguard microstructure --input /path/to/quote-or-events.json
```

The example fundamentals/ETF metadata are **dated, source-labelled real issuer facts**, not auto-refreshing feeds. Microsoft FY2026 annual GAAP data was published July 29, 2026 and does not incorporate later quarters. SPY top-ten holdings are as of November 6, 2026; NAV was refreshed from the issuer to November 9, 2026. These clocks are separate. `filed_at` in the issuer example means public release date, not an independently verified SEC acceptance timestamp. Current market cap and interest expense are absent, not invented.

The CLI sends results only to stdout and reads only paths you explicitly request. It does not write your portfolio, read a broker login or silently fetch an entire universe.

### Final 0–1 buy-interest conclusion

Every `analyze` result now ends with a `buy_recommendation` object in both the JSON CLI and native tool. Its `score` is the existing **evidence-gated, capped recommendation score divided by 100**, not the uncapped diagnostic score, a probability of profit or an independently validated trading signal. No optimistic numerical uplift is applied.

- A valid research candidate is labelled `BUY_RESEARCH_CANDIDATE`, never a validated strong buy.
- Watchlists at 0.60 or above use the constructive label `CONSTRUCTIVE_WATCHLIST`; weaker watchlists remain `MIXED_WATCHLIST`.
- Weak supported setups say `WAIT_FOR_BETTER_SETUP`.
- Abstentions return `score: null` and `verdict: ABSTAIN`: insufficient evidence is not the same as zero buying support.

The final block includes a plain-English conclusion, evidence coverage and remaining cautions. The same commands above work unchanged; stdout remains valid JSON. `strong_buy` stays false until actual recommendation-policy performance is validated. Constructive wording never bypasses stale-data, missingness, source, period or identity gates.

## Native Hermes tools

`plugin.yaml` and root `__init__.py` register only documented `ctx` tool/configuration surfaces:

- `tradeguard_equity_research(snapshot, as_of?)`
- `tradeguard_public_history(symbol)` — **disabled by default**
- `tradeguard_walk_forward(snapshot, min_train?, cost_bps?)`
- `tradeguard_microstructure(quote|events)`
- `tradeguard_rank(snapshots, as_of?)`
- `tradeguard_strategy_catalog(asset_type?, strategy_id?)`
- `tradeguard_recommend_tickers(tickers, as_of?, fundamentals_by_symbol?, etf_by_symbol?)` — opt-in network; up to ten explicit tickers, compact scoped output

Validate a local checkout:

```bash
hermes plugins doctor . --ci
hermes plugins validate . --install-deps --json
```

Optional network permission is plugin-scoped under `plugins.entries.tradeguard.settings.allow_public_data`; `ctx.get_config` reads it. For an installed plugin, opt in through Hermes's configuration command, not by hand-editing configuration files:

```bash
hermes config set plugins.entries.tradeguard.settings.allow_public_data true
```

**This repo does not activate itself in your current Hermes profile.** A catalog listing needs a separate owner-submitted PR, full 40-character tested commit pin and maintainer review. Passing a local validator is not admission.

## Data contract

A snapshot is an object with `symbol`, `asset_type` (`stock`/`etf`), `currency`, `source`, `retrieved_at` (timezone-aware), `data_mode`, `adjustment`, `interval: "1d"`, and a chronological `bars` array. Each bar has `date: "YYYY-MM-DD"`, `open`, `high`, `low`, `close`, `volume`; financial values must be finite, price-positive and unit-consistent. Optional `fundamentals` contains normalized annual amounts, source, publication date, period end and currency. Optional `etf` contains source/as-of, fractional annual `expense_ratio`, dated NAV and fractional-weight holdings. See examples and tests for exact accepted fields. Missing evidence stays missing.

**Recommendation gates:** a stock's highest *research-candidate* label also requires explicit annual duration, issuer-symbol binding and a market-cap observation clock within seven days of the price cutoff. Quarterly/unknown-duration values remain descriptive ratios, not annual-policy confirmation. ETF metadata must bind symbol/currency; an explicit `holdings_complete: false` overrides a seemingly complete weight sum. All outputs set `strong_recommendation_eligible: false`: the heuristic has not been performance-validated, and its 0–100 score is not a probability. Missing-metric coverage never shrinks the fixed scoring denominator. Non-daily sampling is rejected before daily annualization.

The public-history adapter supplies **provider-reported split-adjusted OHLC, not dividend-reinvested total return**. It requires explicit vendor `1d` granularity and excludes every bar on the retrieval's exchange-calendar date, even after close, to avoid an incomplete daily candle. For offline/native supplied snapshots on the retrieval day, the contract instead requires `exchange_timezone` and source-supplied `session_close_at`: a timezone-aware finalization clock on the last bar's exchange date, no later than retrieval. This validates supplied evidence; it does not certify a calendar or detect a dishonest provider. Without a timezone the earliest civil date is used conservatively. Missing vendor rows are flagged, not filled. Retrospectively adjusted data is not a historical vintage database; `as_of` filtering is not a complete point-in-time data guarantee.

SEC companyfacts normalization exists as a library function for standard USD US-GAAP annual 10-K contexts. It checks the payload's numeric CIK against the caller's exact ten-digit identifier before attributing a source, and selects one eligible accession and matching periods; it does not sum vaguely related debt tags or infer market cap from weighted-average diluted shares. Custom taxonomy, IFRS, consolidated debt mapping and TTM are not implemented. In this environment direct SEC requests returned **HTTP 403**; no fake response replaces that error. Issuer-sourced examples provide an explicit alternative, not a claim that the SEC feed worked.

## Security / network / privacy disclosure

- **No orders, accounts, keys, wallet signing, secret reads, telemetry, background jobs, shell children, core overrides or self-updater.** No hooks are registered.
- Native snapshot analysis/ranking/ML/book/catalog tools have no network or filesystem reads. The public-history tool makes one opt-in HTTPS request to `query1.finance.yahoo.com` with the requested ticker. The ticker-only tool makes one such request per unique supplied symbol, at most ten tokens and three joined concurrent workers; it does not start persistent jobs, read example files or discover an implicit universe.
- Explicit library use of `fetch_sec_fundamentals` makes an HTTPS request to `data.sec.gov` with a supplied exact ten-digit CIK; resolve issuer identity separately first. It is not called automatically by analysis.
- Hostnames are fixed/allowlisted; redirects outside allowed HTTPS hosts are refused; responses have size/time limits. TLS peer/hostname verification stays enabled. On macOS the provider also loads the public `/etc/ssl/cert.pem` OS CA bundle to support Python interpreters missing their own bundle.
- Yahoo's chart endpoint is unofficial and unentitled: access can break or be restricted. Free access does **not** grant commercial use, redistribution or real-time trading rights. Choose a licensed data source before deployment. Raw vendor histories are not bundled or committed.
- Local CLI JSON inputs may contain sensitive data you choose to supply. Native tools do not accept arbitrary filesystem paths. Reports can expose supplied values: do not publish private inputs or reports.

## Before enabling stronger recommendations

The reproducible developer exercise fetches two exact symbols, invokes both the actual CLI and registered native handlers, checks their output equality and records a chronological experiment. Network access must be explicit; use retained snapshots offline afterward:

```bash
python3 scripts/exercise_research.py --allow-public-data
python3 scripts/exercise_research.py --offline
python3 scripts/check_research_integrity.py
# Optional explicit network check of immutable upstream license files:
python3 scripts/check_research_integrity.py --verify-licenses
```

This script writes public-research summaries to `artifacts/` and raw histories to git-ignored `data/`; it is a developer command, not a plugin load hook. It runs local CLI subprocesses for integration verification only. See `artifacts/integration_verification.json` for actual dates, source failures and measured baseline results. These few-symbol experiments do **not** validate the fundamental heuristic or establish whole-market performance. A failed/underperforming model is not promoted to stronger recommendations.

Add a licensed/broad-coverage feed and point-in-time universe including delistings; dated filings/corporate actions/ETF holdings; sector-aware accounting; walk-forward selection with an untouched holdout; turnover, spread, slippage, borrow and capacity assumptions; multiple-testing and calibration diagnostics; and paper-trading monitoring. A few symbols and a good-looking backtest do not meet that bar. HFT additionally needs event-quality data, latency/queue modelling and execution infrastructure; daily OHLC cannot stand in for those.

Research-only, not personalized investment advice. Every output must retain its horizon, date, missingness and validation status.
