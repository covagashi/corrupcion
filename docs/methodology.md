# Methodology

How each irregularity signal is computed. The guiding rule (from CLAUDE.md): every flag must be
**transparent and auditable** — simple statistics, stated thresholds, no opaque scores. A flag marks
a pattern worth reviewing; **it is never, by itself, proof of fraud or wrongdoing.**

The metric weights and thresholds live in code so this page can quote them verbatim:

- Phase 1 (Flood Control): `pipeline/transform.py`
- Phase 3 (threshold-splitting): constants in `pipeline/metric_config.py`, statistic in
  `pipeline/threshold_splitting.py`, wiring in `pipeline/transform.py`.

---

## Phase 1 — Flood Control (implemented)

Dataset: 9,855 DPWH flood-control contracts. Each has an **ABC** (Approved Budget for the Contract —
the legal ceiling) and an awarded **ContractCost**.

### Why a flat "bid ≥ 99% of ceiling" flag is useless here

The obvious first idea — flag contracts where `ContractCost / ABC ≥ 0.99` — fires on **73%** of this
dataset (median ratio 0.9999). When a pattern is the norm it carries no signal. So instead of one
blunt flag we layer four, weighted by how anomalous each is, and sum the weights into a
`risk_score` (0–100, clamped).

| Flag                 | Condition                                                                                                | Weight | Reading                                                                                     |
| -------------------- | -------------------------------------------------------------------------------------------------------- | -----: | ------------------------------------------------------------------------------------------- |
| `OVER_CEILING`       | `ContractCost / ABC > 1.0`                                                                               |     40 | Awarded **above** the legal ceiling — should never happen. The strongest signal (770 rows). |
| `DISTRICT_DOMINANCE` | one contractor holds **≥ 50%** of a legislative district's total contract value across **≥ 3** contracts |     30 | Weak competition / possible capture (21 contractor-district pairs, 270 contracts).          |
| `EXACT_CEILING`      | `0.9999 ≤ ratio ≤ 1.0`                                                                                   |     15 | Winning bid matched the secret ceiling to within 0.01% — implausibly precise.               |
| `NEAR_CEILING`       | `0.99 ≤ ratio < 0.9999`                                                                                  |      5 | Bid used ≥ 99% of the budget. Context only.                                                 |

`OVER_CEILING`, `EXACT_CEILING` and `NEAR_CEILING` are mutually exclusive (a contract gets at most
one ceiling flag); `DISTRICT_DOMINANCE` stacks on top.

Supplier concentration is precomputed per `(contractor, legislative_district)` in
`contractor_district_stats` (count, total value, and the contractor's share of the district's value).

---

## Phase 3 — Threshold-splitting (implemented)

Adapted from [contractes.cat](https://contractes.cat). This signal does **not** apply to the
Phase 1 flood-control data — those are large infrastructure contracts with no common small-value
ceiling. It applies to **PhilGEPS small-value procurement** (5.48M awarded contracts), where many
small contracts share a fixed legal threshold above which competitive bidding becomes mandatory.

> **The flood-control analog already captured in Phase 1** is the clustering of the bid-to-ceiling
> ratio at exactly 1.0 (`EXACT_CEILING`). That is clustering at each contract's _own_ ceiling, which
> is different from splitting awards to stay below a _single legal_ threshold.

The metric is computed **entirely offline** over all 5.48M PhilGEPS rows (`pipeline/transform.py`
with `polars`). Only two things land in D1: a per-year aggregate (`threshold_splitting_yearly`) and
the monitored-band contracts themselves (flagged rows); the raw 5.48M rows are never stored.

### The threshold `T` (verified)

`THRESHOLD_T = ₱1,000,000` — the **Small Value Procurement** ceiling for national agencies under the
**RA 9184 2016 Revised IRR, Annex H**. That ceiling governs almost the whole data window
(2013–2024). **RA 12009** (the New Government Procurement Act) raises SVP to **₱2,000,000**, but its
IRR only took effect in **2025**, so the bulk of the awarded contracts here fall under the RA 9184
ceiling. The value and citation live in `pipeline/metric_config.py` (`THRESHOLD_T`, `_T_CITATION`).

### The statistic

1. **Monitored band.** Count contracts awarded in the narrow band just below the threshold,
   `[BAND_ALPHA·T, T)` with `BAND_ALPHA = 0.9933` (mirrors contractes.cat: `[14,900, 14,999.99]` of
   a `15,000` ceiling). For `T = ₱1,000,000` the band is `[₱993,300, ₱1,000,000)`, snapped to bin
   edges.
2. **Histogram.** Bin all sub-threshold contracts (`[0, T)`) into fixed-width bins of
   `BIN_WIDTH = ₱25,000` (40 bins below the ceiling).
3. **Expected vs observed.** Fit a smooth, monotonically-decreasing exponential tail to the bins
   _below_ the monitored band by **log-linear least squares** (`log(count) ≈ a + b·i`) and
   extrapolate it into the band to get an **expected** count. Report:
   - observed count and value in the band,
   - expected count and value under the smooth tail,
   - **excess = observed − expected**, in both count and pesos.

   A year with fewer than 3 populated bins below the band is left without an expected figure
   (shown blank), since the tail can't be fit reliably.

4. **Per-contract flag.** Contracts inside the monitored band carry `BELOW_THRESHOLD_CLUSTER`
   (weight **20**, `metric_config.BAND_WEIGHT`), surfaced like any other flag.

5. **Companion series — weight of minor contracts.** Each yearly row also stores `minor_total`, the
   count of all sub-threshold contracts, so the band can be read as a share of minor contracting.

   contractes.cat reference figures (for context): 11,471 observed vs ~467 expected in the band →
   ~11,004 excess contracts and ~€195.1M above expectation; the band is ~1.83% of all minor
   contracts (~1 in 55).

### Presentation rules (carry over from contractes.cat)

- Show **complete years only**; hide rows dated in the current/future partial year.
- Pre-2020 history is thin (especially for minor contracts) — emphasize the **last ~3 years** for
  trend reading.
- State plainly that concentration at the threshold is an **indicator of possible reduced average
  competition, not automatic proof of splitting or irregularity** in any individual contract.
