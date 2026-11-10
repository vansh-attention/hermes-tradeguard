# Research audit — 2026-11-10

**Scope:** documentation and source ledgers only, audited on November 10, 2026 (Asia/Kolkata). Original research date remains November 9, 2026. This audit neither changes nor certifies the plugin, its tests, data providers, trading permissions or performance. Existing staged work was preserved; nothing was staged, committed, pushed or submitted.

## Verification results

Python parsed both JSON ledgers, compared every body citation and Sources-block URL, checked access dates and excerpt matches, and compared original source IDs/pins with the staged versions.

| Check | Equity/ETF | Microstructure/ML |
|---|---:|---:|
| Ledger entries / unique cited IDs / Sources entries | 28 / 28 / 28 | 19 / 19 / 19 |
| Citation occurrences, excluding Sources blocks | 48 | 61 |
| Original source IDs preserved | 27 | 19 |
| Unknown IDs / unused entries / URL mismatches / duplicate IDs | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |

- **47 source records, 46 distinct primary URLs:** 46 live primary-source records and one dated archive of the SEC's own page. All 47 supporting excerpts matched retrieved text after whitespace/Unicode normalization. This is provenance checking, not proof that every proposed rule is empirically justified.
- **9 distinct repository/commit license checks, represented by 11 records:** all eight original equity pins were preserved and their license hashes matched; MLforecast adds the ninth repository. GitHub commit responses matched full SHAs and committer dates. The three microstructure license references and their README references are now pinned rather than `main`/`master` links.
- **10 independent deterministic formula-sanity groups passed:** lookbacks, weighted midpoint, OFI signs, risk contributions, tracking metrics, concentration, local pair hedge, merger payoff, DSR and inventory-price direction. These use artificial algebraic inputs, not market observations, plugin tests or profitable backtests.
- Both ledgers now record actual **2026-11-10** access/verification dates, retrieval provenance and extracted-text checksums. `git diff --check -- docs/research` passed.

## Corrections and strengthened boundaries

1. **French methodology conflict:** retained the legacy detail-page wording but corrected current-vintage OP to include minority interest in its denominator, using the explicit August 2018 revision notice. Added stable equity source **42**; also documented FIZ/CIZ dividend-reinvestment and factor-vintage differences. The ledgers' numeric IDs remain report-local.
2. **Definitions versus proposals:** added major-family coverage/status and horizon tables; distinguished size/value/quality factors from screens, distance pairs from cointegration, BAB from unlevered low-volatility baskets, and proposed ETF rotation from published trend evidence. Kept the October 9, 2013 four-component QMJ draft explicitly versioned.
3. **Timing and mathematics:** clarified skipped-month momentum and long-reversal endpoints, positive-outflow capex convention, portfolio-budget notation, fractional versus absolute risk contributions, local log-spread hedge sizing, and merger payoff horizons. Faber's same-close/cost-exclusion assumptions and futures spot/roll distinctions are explicit.
4. **HFT/ML:** corrected the Cont paper from **arXiv v2 to v3**, pinned all three arXiv versions, distinguished normalized imbalance from Stoikov's state notation, and separated contemporaneous OFI impact from prediction. Added price-variance units, executable-entry economics, and DSR sample-length versus effective-trial notation. Monthly ML evidence is not intraday execution evidence.
5. **Licensing/conduct:** backtrader's inspected source header permits GPL version 3 or later; retained the original upstream `GPL-3.0` identifier separately and recorded the pinned notice. Removed an unsupported claim that the cited CFTC Q&A itself establishes a good-faith-cancellation safe harbor. Neither inspection is an exhaustive legal opinion.

## Retrieval issues and remaining gaps

The live SEC page returned **403**. Its **2026-10-29 11:00:36 UTC** Wayback snapshot was successfully decoded and inspected; a later retry returned **429**. It is labeled archived, not current live content. One author-host TSM download failed TLS verification; the NYU author copy succeeded without disabling TLS verification. Native search/extraction failed, so discovery used fallback providers and documents were fetched directly; no separately callable `web.run` tool was exposed.

No exact portfolio replication, full historical dataset audit, current alpha estimate, calibrated recommendation probability, or book/queue/latency replay was established here. Point-in-time revisions, dividends/delistings, fund/contract vintages, costs, capacity and market-data entitlements still need implementation-level evidence. The strategy map is selective, not exhaustive; open access and code licenses grant neither predictive power nor data rights.

## Key primary-source locators

- French revision notices: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
- Faber's stated signal/data/cost assumptions: https://mebfaber.com/2013/06/07/qtaa-paper-update-manage-your-risk-4/
- Cont–Kukanov–Stoikov, inspected v3: https://arxiv.org/pdf/1011.6402v3
- Gu–Kelly–Xiu, inspected September 2019 revision: https://www.nber.org/system/files/working_papers/w25398/w25398.pdf
- backtrader's inspected license notice: https://raw.githubusercontent.com/mementum/backtrader/b853d7c90b6721476eb5a5ea3135224e33db1f14/backtrader/__init__.py

**Files changed:** `equity_etf_strategy_library.md`, `microstructure_ml_validation.md`, `sources_equity.json`, `sources_microstructure.json`; this `AUDIT.md` is new. No implementation code, README or BUILD_STATUS was edited by this audit.
