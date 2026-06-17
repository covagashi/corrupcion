# Phase 3a — PhilGEPS ingestion + threshold-splitting metric

Design spec. Status: approved 2026-06-17. First sub-project of roadmap Phase 3.

## Goal

Bring the PhilGEPS awarded-contracts dataset into the site and implement the signature
contractes.cat irregularity metric — **threshold-splitting** (contract amounts clustered just below
the legal small-value procurement threshold). This is the highest-value Phase 3 deliverable: it
unlocks the metric the whole project is modeled on.

In scope:

- Ingest all awarded PhilGEPS contracts (`philgeps.parquet`, ~470 MB) into D1 for browse/detail.
- Compute the threshold-splitting statistic (observed vs expected vs excess, per complete year) as a
  precomputed aggregate.
- Flag individual contracts that fall in the monitored band just below the threshold.
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

## Architecture

Heavy work stays offline in `pipeline/` (per CLAUDE.md). The Worker only reads precomputed rows.

```
fetch.py    -> download philgeps.parquet (+ awardees/organizations, kept unused)
transform.py-> read parquet (polars), map to contracts rows (source='philgeps'),
               compute threshold-splitting per year, write out/contracts.sql
db/schema   -> contracts (extended) + new threshold_splitting_yearly table
D1          <- wrangler d1 execute/import
Worker      -> reads contracts + threshold_splitting_yearly; renders /threshold-splitting
```

### Component 1 — Parquet reading (new dependency: polars)

The current pipeline is pure stdlib. Reading Parquet needs a dependency; **polars** is chosen
(lazy/streaming, low RAM for 470 MB, auditable row-by-row). Add it to `pipeline/requirements.txt`.

**First implementation task (blocking, before any column hardcoding):** download `philgeps.parquet`,
print its schema and row count, and record the real column names for: award amount, award date,
category, procuring entity/organization, contractor/awardee, location. The mapping below uses
placeholder names that MUST be reconciled against the actual schema in the plan's first step.

### Component 2 — Mapping PhilGEPS → `contracts`

Reuse the existing `contracts` table. PhilGEPS rows set `source='philgeps'` and `id='philgeps:<key>'`
(source-prefixed to avoid collisions with flood_control GlobalIDs). Fields PhilGEPS lacks
(e.g. ABC, bid_to_ceiling_ratio) are `NULL`. New columns are added generically (Component 4).

### Component 3 — Threshold-splitting metric (in transform.py)

Per `docs/methodology.md` §"Phase 3 — Threshold-splitting", made concrete:

1. **Threshold `T`** — the legal small-value procurement ceiling. **Verify the current peso value in
   the RA 9184 / RA 12009 IRR before hardcoding** (CLAUDE.md rule). The metric is parameterized by
   `T`; the verified value and its legal citation are recorded in `transform.py` constants and quoted
   on the methodology page.
2. **Histogram** — bin all sub-threshold contracts `[0, T)` into fixed-width bins (PH-appropriate
   width, chosen relative to `T`; documented).
3. **Smooth-tail fit** — fit a monotonically-decreasing tail (exponential) to bins *below* the
   monitored band by least squares, written explicitly in Python (no opaque library fit), and
   extrapolate into the monitored band `[α·T, T)` to get the **expected** count.
4. **Report per complete year**: observed count + value, expected count + value, and
   **excess = observed − expected** in both count and pesos. Hide the current/partial year.
5. **Per-contract flag** `BELOW_THRESHOLD_CLUSTER` for contracts in the monitored band, with a weight
   added to `WEIGHTS` and documented in `methodology.md` and `src/lib/flags.ts`.

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
2. `transform.py` reads `philgeps.parquet` (polars), maps rows, computes the metric + yearly
   aggregate, appends PhilGEPS rows to the flood_control rows, and writes `out/contracts.sql`
   (including `DELETE`/`INSERT` for `threshold_splitting_yearly`).
3. `wrangler d1 execute --file` loads schema then rows (idempotent).
4. Worker SSR reads `contracts` + `threshold_splitting_yearly`.

## Error handling / edge cases

- Missing/unparseable award amount or date → row still ingested for search; excluded from the metric
  (can't bin it). Count of excluded rows is printed by `transform.py`.
- A year with too few sub-threshold contracts to fit a tail → emit the row with `expected_*`/`excess_*`
  as NULL and the page renders "insufficient data" for that year rather than a misleading number.
- `philgeps.parquet` schema differs from assumptions → caught by the blocking first task; the plan
  stops to reconcile before proceeding.
- D1 statement-length limit → keep the existing 50-rows/INSERT batching; with ~105K rows the dump
  grows large but `wrangler d1 execute --file` / `d1 import` already handle the flood_control dump.

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
- `docs/data-sources.md`: correct the PhilGEPS size (~1.95 GB total / ~470 MB main parquet, not 11 GB).
- `docs/ROADMAP.md`: check off the PhilGEPS + threshold-splitting items.
- `CLAUDE.md`: note the new polars dependency in the pipeline if relevant.
```
