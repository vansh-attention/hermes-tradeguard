# Derivatives strategy library — M1 analytical subset

Status: **offline research only; not performance-validated**. No live derivative feed, broker account, order adapter, automatic sizing, historical options backtest or calibrated probability is implemented. Exact contract specifications are supplied evidence, not an exchange certification.

This library is deliberately non-exhaustive. It documents what the implementation calculates, what remains only a hypothesis and what data would be needed to go further.

## Reference and evidence boundaries

The separately namespaced `sources_derivatives.json` retains the prior November 10, 2026 inspection. Direct HTTPS and indexed-primary corroboration are distinct. Source snippets were not invented, no third-party implementation was copied and reference access is not a market-data license.

- Contract cash accounting requires exact currency, multiplier, tick and quantity units. The CME MES example is a specification illustration, not a current listed-contract resolver or margin feed. [D1]
- A daily instrument master is not a current quote. Missing quote keys, reusable tokens and source unit ambiguity cannot be repaired with a guessed price/underlier. [D2]
- Current masters and continuous candles do not establish point-in-time expired-contract/option-chain history. [D3]
- A future authorized feed needs bounded rate/error behavior. M1 deliberately makes no such requests. [D4]
- Settlement/exercise is instrument-specific; the generic clearing summary and NIFTY product text inspected during planning conflict. Effective specifications/circulars must resolve that conflict before a live adapter can certify a supported product. [D5] [D9]
- A margin reference is neither maximum loss nor verified account affordability. [D6]
- Pricing inputs and model scope matter. The implemented model is European, continuous-yield, cash-index BSM with ACT/365F; it is not an American or option-on-futures substitution. [D7] [D11]
- Greeks describe sensitivity with explicit units, not realized premium changes, delta-based success odds or profit probabilities. [D8]
- Eight native tools are declared only because they are implemented; plugin loading is inert and a working handler is verified separately from registration. No installation or catalog admission follows. [D10]
- Conflicting documentation limits/auth versions are a reason to freeze a bounded future adapter contract, not claim the largest advertised capacity. [D12]

## Implemented analytical families

| Family | Implemented observations | Hypothesis/status | Required evidence and failure modes |
|---|---|---|---|
| Linear cash-index future | Multiplier-once notional/tick value; long/short ask/bid-entry cash P&L scenarios; cash-underlier direction | Implemented arithmetic and unvalidated directional screen; final offline score null | Exact contract/currency, fresh quote/depth/session clocks, underlier history; missing margin/costs and source trust remain visible; margin never caps loss |
| Long European cash-index call/put | Ask premium, expiry intrinsic/breakeven/gross payoff bounds; optional quote-inverted IV/Greeks | Implemented analytical model, not independent fair value or profitable entry validation | Explicit strike/right/expiry/multiplier and dated continuous r/q; unsupported exercise/settlement or failed inversion remains unavailable |
| Bull-call / bear-put debit vertical | One matched long/short contract per leg; long ask minus short bid; gross expiry loss/profit/breakeven and scenarios | Implemented matched-spread arithmetic; no atomic fill claim | Same underlier, coherent history/source, expiry, right, multiplier/currency/style; depth/skew/costs for both legs; unmatched/credit/naked strategies rejected |
| Root metadata selection | Exact root/kind, explicit expiry-window policy, bounded strike selection, exclusion counts | Implemented deterministic offline selection; not a liquidity/return optimizer | Bounded explicit metadata, no duplicate-ID repair, no cross-currency/underlier ambiguity, no implicit continuous contract |
| Injected data-batch orchestration | Preflight roots, history-before-selection, final quote/spot refresh, partial failures, separate root/contract totals | Offline library interface; not a built-in network provider or native live tool | User-chosen Python data interface; snapshots revalidated and unverified; no synthetic fallback for absent data |

### Directional screen and contract quality

Four fixed comparisons inspect the matching cash-index series: last close versus SMA20, SMA20 versus SMA50, SMA50 versus SMA200, and last close versus SMA200. Equal comparisons contribute one half; missing required observations do not shrink the denominator. Call/long-future direction and put/short-future direction are separate.

The pure policy combines directional support with an explicit spread penalty. Its thresholds are engineering heuristics, **not optimized or empirically validated**. Evidence blockers dominate: all public M1 snapshot ingress is user-supplied/unverified, so final current-entry interest remains null even if descriptive support is numerically high. A fixture label is a caller declaration, not independent proof of synthetic origin. Mixed fixture/imported legs are not represented as wholly synthetic.

### Pricing and payoff limitations

- An IV inferred from a quote and inserted into the same pricing formula is not independent evidence that the quote is cheap.
- IV bracket failure or missing/old rate/dividend inputs does not become zero volatility or zero Greeks.
- Theta is per calendar day; vega/rho per one percentage-point change; multiply premium-unit sensitivities by the documented contract value per point once.
- Gross expiry bounds exclude unknown costs, legging, early exit and liquidity risk. Finite option/debit-spread bounds do not transfer to futures or unsupported physical exercise.
- A coherent underlier ID and current spot are insufficient if the two legs' valid daily histories contradict each other. Reject the spread rather than choose the more attractive trend.

## Researched-only / not implemented

| Family | Status and next prerequisite |
|---|---|
| Futures basis/curve/carry | Researched-only; needs simultaneous same-family contract/spot observations, financing/dividend/roll conventions and dated specifications |
| IV skew, smile, term structure and IV-versus-realized signals | Researched-only; needs a declared contemporaneous surface and historical statistic with consistent moneyness/maturity/units |
| American/physical options and adjusted deliverables | Unsupported; requires separate exercise/deliverable/assignment modeling and settlement evidence |
| Options on futures / Black-76 | Unsupported; no quiet reuse of the cash-spot BSM function |
| Credit/calendar/ratio/naked-short strategies | Unsupported; no claimed bounded risk from unmatched legs |
| ML, HFT and market making | Not implemented by M1; model/data/evaluation and event/execution infrastructure are separate prerequisites |

## Validation boundary

Numerical tests cover exact linear/option/spread arithmetic, model identities, finite-difference Greek units, IV inversion failures, parameter bounds and source/data gates. Actual CLI and registered native handlers are compared on conspicuously synthetic examples. Neither these tests nor an injected synthetic provider establish live market access, predictive performance or an executable investment recommendation.

The separately documented `derivatives_validation_protocol.md` gates M3 historical evaluation. Do not relabel the existing equity ridge experiment as derivatives validation.
