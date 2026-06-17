# Phase 3a — PhilGEPS ingestion + threshold-splitting metric

Design spec. Status: approved 2026-06-17. First sub-project of roadmap Phase 3.

## Goal

Bring the PhilGEPS awarded-contracts dataset into the site and implement the signature
contractes.cat irregularity metric — **threshold-splitting** (contract amounts clustered just below
the legal small-value procurement threshold). This is the highest-value Phase 3 deliverable: it
unlocks the metric the whole project is modeled on.

In scope:

- Process the full PhilGEPS awarded-contracts file (`philgeps.parquet`, ~470 MB, **5.48M rows**)
  **offline** to compute the metric over every contract.
- Persist to D1 only: the threshold-splitting yearly aggregate, **plus the contracts in the monitored
  band just below the threshold** (a bounded subset, ~tens of thousands) for browse/detail.
  Storing all 5.48M rows in D1 is not viable for a mobile-first site and is explicitly rejected.
- Compute the threshold-splitting statistic (observed vs expected vs excess, per complete year).
- Flag the persisted band contracts with `BELOW_THRESHOLD_CLUSTER` so they appear in list/detail.
- A new mobile-first `/threshold-splitting` analysis page + a simple source filter on the list.

Explicitly **out of scope** (other Phase 3 / Phase 4 pieces):

- DPWH Infrastructure dataset.
- Full unified/advanced search across sources.
- Politician/owner alignment (Phase 4). `awardees.parquet` and `organizations.parquet` are
  downloaded and kept for later but **not processed** in this sub-project.

## Data source (verified 2026-06-17)

Hugging Face `bettergovph/philgeps-data` (CC0, public). File inventory:

| File                         |      Size | Use                                          |
| ---------------------------- | --------: | -------------------------------------------- |
| `philgeps.parquet`           | ~470 MB   | **Main** awarded-contracts table (this work) |
| `awardees.parquet`           | ~5.8 MB   | Phase 4 (download, don't process)            |
| `organizations.parquet`      | ~1.3 MB   | Phase 4 (download, don't process)            |
| `oc4ids.json`                | ~984 MB   | not used                                     |
| `area_of_deliveries`, `business_categories` | small | not used in this sub-project    |

The 470 MB main file is comfortably downloadable in a GitHub Actions runner. The earlier "~11 GB"
figure in `docs/data-sources.md` was wrong; correct it to ~1.95 GB total / ~470 MB main parquet.
The "~105K awarded contracts" figure was also wrong.

**`philgeps.parquet` real schema (verified 2026-06-17 by reading the remote parquet footer + columns):**
5,481,161 rows, 12 columns. All rows have `award_status = "active"`, a non-null `contract_amount`,
and (all but one) a non-null `award_date` — i.e. the file *is* the awarded-contracts table.

| Column              | Arrow type         | Maps to `contracts` column                |
| ------------------- | ------------------ | ----------------------------------------- |
| `id`                | uuid               | `id` → `'philgeps:' + id`                 |
| `reference_id`      | string             | `project_id`                              |
| `contract_no`       | string             | (kept in description context; not a column)|
| `award_title`       | string             | `description` (fallback `notice_title`)   |
| `notice_title`      | string             | description fallback                       |
| `awardee_name`      | string             | `contractor`                              |
| `organization_name` | string             | `procuring_entity` (new column)           |
| `area_of_delivery`  | string             | `province` (best-effort location string)  |
| `business_category` | string             | `category` (new column)                   |
| `contract_amount`   | double (PHP)       | `contract_cost`                           |
| `award_date`        | timestamp[us]      | `award_date` (new column, epoch ms)       |
| `award_status`      | string (="active") | not stored                                |

PhilGEPS has **no ABC, no bid_to_ceiling ratio, and no legislative_district** → those stay NULL for
`source='philgeps'` rows. `OVER_CEILING`/`EXACT_CEILING`/`NEAR_CEILING`/`DISTRICT_DOMINANCE` do not
apply to PhilGEPS.

**Amount distribution (PHP, n=5.48M):** median ≈ 145,694; q25 ≈ 39,732; q75 ≈ 699,646; q90 ≈ 3.46M;
max ≈ 141.8B; min = 0. Heavy right tail.

**Monitored-band size by candidate threshold** `T` (band `[0.99·T, T)`): T=50K → ~16.3K rows;
T=100K → ~39.0K; T=500K → ~39.4K; T=1M → ~52.8K. The persisted subset is therefore tens of
thousands regardless of the verified `T` — safe for D1.

**Dirty dates:** `award_date` ranges 1920 → 2034 and includes junk years (1920, 2033, 2034) and the
current/partial year. The metric keeps **complete years only** within a plausible window
(~2013–2025); rows outside it are excluded from the metric (Component 3).

## Architecture

Heavy work stays offline in `pipeline/` (per CLAUDE.md). The Worker only reads precomputed rows.

```
fetch.py    -> download philgeps.parquet (+ awardees/organizations, kept unused)
transform.py-> read parquet (polars), compute threshold-splitting over ALL 5.48M rows,
               emit only (a) yearly aggregate + (b) the monitored-band contracts as
               source='philgeps' rows -> append to flood_control rows in out/contracts.sql
db/schema   -> contracts (extended) + new threshold_splitting_yearly table
D1          <- wrangler d1 execute/import
Worker      -> reads contracts + threshold_splitting_yearly; renders /threshold-splitting
```

### Component 1 — Parquet reading (new dependency: polars)

The current pipeline is pure stdlib. Reading Parquet needs a dependency; **polars** is chosen
(lazy `scan_parquet` + streaming groupby keeps memory bounded over 5.48M rows; expressive for the
histogram aggregation). Add `polars` to `pipeline/requirements.txt`. (`pyarrow` is already present and
was used for schema verification, but polars is the working dependency for `transform.py`.)

The real schema is now known (see Data source table) — no blocking discovery task remains, but the
plan's first transform task still asserts the expected column set so a future schema drift fails loud.

### Component 2 — Mapping PhilGEPS → `contracts`

Reuse the existing `contracts` table, mapping per the Data-source schema table. PhilGEPS rows set
`source='philgeps'` and `id = 'philgeps:' + id` (source-prefixed to avoid collisions with
flood_control GlobalIDs). `abc`, `bid_to_ceiling_ratio`, `legislative_district`, and the
flood-control-only fields stay `NULL`. New columns (`award_date`, `category`, `procuring_entity`) are
added generically (Component 4). **Only the monitored-band subset is mapped and emitted** — not all
5.48M rows.

### Component 3 — Threshold-splitting metric (in transform.py)

Per `docs/methodology.md` §"Phase 3 — Threshold-splitting", made concrete. Computed **offline over all
5.48M rows**; only the yearly aggregate and the band subset are persisted.

0. **Year window** — keep only complete calendar years within a plausible window (drop junk years
   1920/2033/2034 and the current/partial year). Constant `MIN_YEAR`/`MAX_YEAR` in `transform.py`;
   default window ~2013–2025, with the upper bound = last fully-elapsed year.
1. **Threshold `T`** — the legal small-value procurement ceiling. **Verify the current peso value in
   the RA 9184 / RA 12009 IRR before hardcoding** (CLAUDE.md rule). The metric is parameterized by
   `T`; the verified value and its legal citation are recorded in `transform.py` constants and quoted
   on the methodology page.
2. **Histogram** — bin all sub-threshold contracts `[0, T)` into fixed-width bins (PH-appropriate
   width, chosen relative to `T`; documented as a constant).
3. **Smooth-tail fit** — fit a monotonically-decreasing exponential tail to the bins *below* the
   monitored band via **log-linear least squares written explicitly** (fit `log(count) ≈ a + b·x`
   over non-empty bins by the closed-form normal equations; no opaque library `.fit()`), then
   extrapolate `exp(a + b·x)` into the monitored band `[α·T, T)` to get the **expected** count and
   value. `α` is a documented constant (methodology reference uses ≈0.9933).
4. **Report per complete year**: observed count + value, expected count + value, and
   **excess = observed − expected** in both count and pesos.
5. **Per-contract flag** `BELOW_THRESHOLD_CLUSTER` for contracts in the monitored band, with a weight
   added to `WEIGHTS` and documented in `methodology.md` and `src/lib/flags.ts`. These flagged
   band contracts are the PhilGEPS rows persisted to D1.

All thresholds/weights live in `transform.py` constants so the methodology page quotes them verbatim.

### Component 4 — D1 schema changes (`db/schema.sql`)

- Extend `contracts` with generic columns PhilGEPS needs that don't exist yet — at minimum
  `award_date` (epoch ms), `category` (TEXT), `procuring_entity` (TEXT). NULL for flood_control rows.
- New table `threshold_splitting_yearly`:
  | column          | type    | meaning                                  |
  | --------------- | ------- | ---------------------------------------- |
  | year            | INTEGER | complete year (PK)                       |
  | observed_count  | INTEGER | contracts in the monitored band          |
  | observed_value  | REAL    | their peso value                         |
  | expected_count  | REAL    | expected under the smooth tail           |
  | expected_value  | REAL    | expected peso value                      |
  | excess_count    | REAL    | observed − expected (count)              |
  | excess_value    | REAL    | observed − expected (pesos)              |
  | minor_total     | INTEGER | all sub-threshold contracts that year    |

  The Worker reads this aggregate; it never recomputes.

### Component 5 — Server access (`src/lib/server/contracts.ts`)

- Add `award_date`/`category`/`procuring_entity` to `ContractRow`.
- Add a `source` filter option to `listContracts` (values: `flood_control`, `philgeps`).
- New `getThresholdSplitting(platform)` returning the `threshold_splitting_yearly` rows (complete
  years, ordered).

### Component 6 — UI (mobile-first, deliberately polished — not generic)

- **New route `/threshold-splitting`** (SSR, minimal client JS):
  - Headline: one big number — total excess contracts and total excess pesos summed across all
    complete years (the most recent complete year is highlighted separately in the trend below).
  - One plain-language paragraph explaining what threshold-splitting is and what the number means.
  - Yearly trend as a **compact table or pure-CSS bars** (no chart library, no heavy JS), emphasizing
    the last ~3 complete years.
  - Prominent disclaimer: an indicator of possibly reduced competition, **not proof** of splitting or
    wrongdoing in any individual contract.
  - Linked from `/methodology` and the global footer.
- **List/detail**: `BELOW_THRESHOLD_CLUSTER` renders like existing flags (definition in
  `$lib/flags.ts`). Add a simple **source filter** control (flood_control / philgeps / all).
- A design-quality skill is applied during implementation so the new page does not look generic.

## Data flow

1. CI/local: `fetch.py` downloads parquet(s).
2. `transform.py` scans `philgeps.parquet` (polars) over all 5.48M rows, computes the metric + yearly
   aggregate, maps **only the monitored-band subset** to `contracts` rows, appends them to the
   flood_control rows, and writes `out/contracts.sql` (including `DELETE`/`INSERT` for
   `threshold_splitting_yearly`).
3. `wrangler d1 execute --file` loads schema then rows (idempotent).
4. Worker SSR reads `contracts` + `threshold_splitting_yearly`.

## Error handling / edge cases

- Missing/unparseable award amount or date, or a year outside the window → excluded from the metric
  and not persisted. Count of excluded rows is printed by `transform.py`.
- A year with too few sub-threshold contracts to fit a tail → emit the row with `expected_*`/`excess_*`
  as NULL and the page renders "insufficient data" for that year rather than a misleading number.
- `philgeps.parquet` schema differs from assumptions → the first transform task asserts the expected
  12-column set and fails loud before any mapping.
- D1 statement-length limit → keep the existing 50-rows/INSERT batching. Only the band subset
  (~tens of thousands) is emitted, so the dump stays comparable to today's; `wrangler d1 execute
  --file` / `d1 import` already handle that scale.

## Testing

- `transform.py`: unit-test the tail fit and excess computation on a small synthetic histogram with a
  known injected spike (assert excess ≈ injected). Test band/bin boundary inclusivity.
- Schema/SQL: run `db/schema.sql` + generated `contracts.sql` against local D1; assert row counts and
  that `threshold_splitting_yearly` has only complete years.
- Worker: `npm run check`; smoke-test `/threshold-splitting` renders with seeded local D1.
- Verify `risk_flags`/weights are consistent between `transform.py`, `methodology.md`, and
  `$lib/flags.ts`.

## Docs to update

- `docs/methodology.md`: move the Phase 3 section from "planned" to "implemented", fill in the
  verified `T`, bin width, band, and the `BELOW_THRESHOLD_CLUSTER` weight.
- `docs/data-sources.md`: correct the PhilGEPS size (~1.95 GB total / ~470 MB main parquet, not 11 GB)
  and the row count (5.48M awarded, not ~105K).
- `docs/ROADMAP.md`: check off the PhilGEPS + threshold-splitting items.
- `CLAUDE.md`: note the new polars dependency in the pipeline.
