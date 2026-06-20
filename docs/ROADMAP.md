# Roadmap

Steps to build the Philippine anti-corruption site, in order. Check items off as you go.
Architecture and data sources are in [data-sources.md](data-sources.md); design rules and the
irregularity-metric definition are in [../CLAUDE.md](../CLAUDE.md).

## Architecture (decided)

```
GitHub Actions (cron, monthly)
  1. discover download URLs via the BetterGov catalog API (https://data.bettergov.ph/api/v1)
  2. download the Parquet / JSON data files
  3. compute the irregularity metric + politician/owner alignment
  4. wrangler d1 import  ->  Cloudflare D1
Cloudflare Worker (SvelteKit SSR) -> reads D1 -> small HTML to mobile
```

Heavy work happens offline in CI; the Worker only reads precomputed rows. The catalog API is a
**discovery layer used by the pipeline**, never called at request time. Verified working 2026-06-15.

## Deviations from the original plan (updated 2026-06-19)

What actually got built differs from the first plan in a few important ways. Recording them here so
the checklist below reads honestly.

- **UI was restructured (Phase 5, user-requested).** The original plan put a single contract list at
  `/`. The site is now a plain-language **landing at `/`**, with the searchable list **moved to
  `/contracts`** and a new **`/areas`** province browser ("find your area"). `province` became the
  one location key shared across all contract sources.
- **Phase 4 alignment pivoted from "by legislative district" to "by province / locality".** The
  original goal — join contracts to representatives by `LegislativeDistrict` — is **not supported by
  the available politician data**: the Open Congress `Person` record carries no district. So the work
  split in two:
  - Open Congress became a **standalone legislators directory** (`/legislators`), deliberately *not*
    joined to contracts.
  - The real contract↔official alignment uses a **different dataset, Raw Philippine Data** (its
    `memberships` table has province / locality + position + year), matched on **province/locality
    name near the contract's year** — not by district.
- **Two politician datasets are kept separate on purpose:** `legislators` (Open Congress,
  bills/chamber-focused, national) vs `officials` (Raw PH Data, local governors/mayors with a
  geographic key). They are not merged.
- **Ingestion now also uses `git clone`, not only Parquet/JSON download.** `fetch.py` shallow-clones
  `open-congress-data` (one TOML per entity) alongside the Hugging Face parquet downloads.
- **Owners (SEC) and the Ateneo dynasties dataset are blocked, not merely unstarted.** SEC has no
  public API / reachable bulk source; the dynasties dataset lives on `data.bettergov.ph`, which the
  web sandbox cannot reach (403).
- **Verification reality.** Legislators and the area-alignment join were verified against a **seeded
  local D1** (real Open Congress clone; a synthetic fixture for the officials join). The full
  PhilGEPS / DPWH / officials data runs that need `huggingface.co` are **deferred** to a
  logged-in/CI machine — sandbox egress blocks HF. See [pending.md](pending.md) /
  [pending-data-run.md](pending-data-run.md).

## Phase 0 — Base ✅ (done)

- [x] SvelteKit + TS + Tailwind + Cloudflare Workers adapter scaffolded
- [x] Repo published: https://github.com/covagashi/corrupcion (public)
- [x] Data sources documented and live-tested

## Phase 1 — First dataset end to end: Flood Control

Smallest, richest, highest-impact dataset (9,855 records, 16 MB). Goal: one real page live.

- [x] `pipeline/fetch.py`: download Flood Control JSON
      (`https://raw.githubusercontent.com/bettergovph/bettergov/refs/heads/main/src/data/flood_control/flood_control.json`)
- [x] `pipeline/transform.py`: parse the ArcGIS feature format; extract the useful fields.
      Note: `GlobalID` is the primary key (`ContractID` is not unique — 9,698/9,855).
- [x] Compute first irregularity signals (in `transform.py`):
  - [x] **bid-to-ceiling ratio** = `ContractCost / ABC`. A flat ≥0.99 flag is useless here — 73% of
        the dataset sits at the ceiling, so it's the norm, not a signal. Layered instead:
        `OVER_CEILING` (>1.0, awarded above the legal ceiling — 770 rows, the strong signal),
        `EXACT_CEILING` (≥0.9999), `NEAR_CEILING` (≥0.99, context only).
  - [x] **supplier concentration** — `DISTRICT_DOMINANCE`: one contractor holds ≥50% of a
        legislative district's contract value across ≥3 contracts (21 pairs / 270 contracts).
- [x] Output a `.sql` dump (`pipeline/out/contracts.sql`, batched 50 rows/INSERT for D1's
      statement-length limit). `risk_score` (0–100) is the transparent sum of fired-flag weights.
- [x] D1: schema defined (`db/schema.sql`), binding activated in `wrangler.jsonc`, loaded into the
      **local** D1 (`wrangler d1 execute --local`). Remote `wrangler d1 create` + real `database_id`
      still pending (needs `wrangler login`).
- [x] UI: contract list page (mobile-first) — riskiest first, search, plain-language flag per row
- [x] UI: contract detail page explaining each flag in one sentence + the money + district standing

## Phase 2 — Automate the refresh

Full deploy instructions (local + CI) in [deploy.md](deploy.md).

- [x] GitHub Actions workflow: pipeline → load D1 → deploy, on a monthly cron + manual dispatch
      (`.github/workflows/refresh.yml`)
- [x] Step to load results into D1 via `wrangler d1 execute --remote` (idempotent schema + rows)
- [x] Deploy the site (`wrangler deploy`) — wired in the workflow
- [ ] **Manual one-time setup (you):** create the D1 db, paste its `database_id` into
      `wrangler.jsonc`, add repo secrets `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`,
      then run the workflow once. See [deploy.md](deploy.md).

## Phase 3 — Add the big contract datasets

- [x] PhilGEPS (`philgeps.parquet`, ~470 MB / 5.48M rows — all agencies) into the pipeline
- [x] Adapt the metric: legal threshold-splitting detection — amounts clustered just below the
      RA 9184 SVP threshold (`T = ₱1,000,000`, verified; RA 12009 raises it to ₱2,000,000 from 2025).
      Full statistic (observed vs expected under a smooth log-linear tail, excess count/value) in
      [methodology.md](methodology.md#phase-3--threshold-splitting-implemented). Surfaced as the
      `BELOW_THRESHOLD_CLUSTER` flag plus the `/threshold-splitting` page.
- [x] DPWH Infrastructure (`dpwh_transparency_data.parquet`, 248,220 projects) into the pipeline.
      Schema verified; mapped to `source='dpwh'` rows with the `OVER_BUDGET` flag (amount paid >
      approved budget). See [methodology.md](methodology.md#phase-3b--dpwh-infrastructure-projects-implemented).
      (The Hugging Face download path in `fetch.py` still needs a live confirmation — see
      [pending-data-run.md](pending-data-run.md).)
- [x] Unified search across all contracts (server-side, returns small HTML). The list spans both
      sources, with a Flood Control / PhilGEPS source filter; search matches contractor, description,
      district, procuring entity, province and category; the list and detail pages render
      source-appropriate fields (ceiling/ratio for flood control, agency/category/award year for
      PhilGEPS).

> **Not yet run:** the PhilGEPS pipeline + metric code and the front end are done and type-checked,
> but the end-to-end data run (download `philgeps.parquet` → `transform.py` → seed D1) could not
> execute in the web sandbox (egress blocks `huggingface.co`). Exact remaining steps and how to
> finish them (CI / egress allowlist / logged-in machine) are in
> [pending-data-run.md](pending-data-run.md).

## Phase 4 — Alignment (contracts ↔ politicians ↔ owners) — partial

Politicians leg done (two ways); owners + dynasties blocked. The headline join is now **by
province/locality**, not legislative district — see the deviations section above.

- [x] **Legislators directory** (the politicians leg). `pipeline/congress.py` parses the Open
      Congress TOML data (1,173 senators/representatives, 8th–20th Congress) into a `legislators`
      table; UI at `/legislators` (search + Senate/House filter) and `/legislator/[id]` (chambers &
      congresses served). Verified end-to-end on a seeded local D1.
- [x] **Officials ↔ contracts by area.** The Raw Philippine Data `memberships` table carries the
      geographic key Open Congress lacked (region / province / locality + position + year), so
      `pipeline/officials.py` builds `officials` + `official_terms` and the contract detail page now
      shows **"who held office in this area"** (province governor / representatives + town mayor,
      near the contract's year). Browse at `/officials`, profiles at `/official/[id]`. Matching is
      on normalized province/locality names (`normalize_place` mirrored in `$lib/officials.ts`), so
      it is best-effort where names differ between sources. Code type-checked + join verified on a
      local fixture; the real data run (HF parquet) is deferred (sandbox blocks huggingface.co).
- [ ] Company owners: SEC records; link contractors to incorporators/owners — no public API / no
      reachable bulk source yet.
- [ ] Political-dynasty dataset (Ateneo Policy Center) for clan context — lives on
      `data.bettergov.ph`, which the web sandbox cannot reach (403).
- [x] Stronger place-name matching: a shared `src/lib/place-aliases.json` drives province aliases
      (NCR/Metro Manila, Compostela Valley→Davao de Oro, parenthetical disambiguation, …) + locality
      rules ("City of X"→x, drop parentheticals, Sto./Sta./Gen. expansion) in both the pipeline
      (`pipeline/place_norm.py`) and the Worker (`normalizeProvince`/`normalizeLocality` in
      `$lib/officials`). A shared fixture (`pipeline/test/place-cases.json`) is asserted from both
      languages (`npm run test:place`). **Follow-up:** the alias set is seeded from PH geography, not
      the (unreachable) real data — re-check recall against the seeded D1 on a logged-in/CI machine.
- [ ] Budget side: the GAA dataset (3.7M appropriation rows by agency/region) for an
      appropriated-vs-awarded comparison.

## Phase 5 — Polish

- [x] Public methodology page (`/methodology`, plain-language, linked from every footer; flag
      definitions rendered from the same `$lib/flags` source the app uses). Dev-facing spec in
      [methodology.md](methodology.md).
- [x] **Landing page + "find your area" browse.** `/` is now a plain-language landing (headline
      numbers, threshold-splitting teaser, navigation cards) instead of a bare list; the full list
      moved to `/contracts`. New `/areas` page groups contracts by **province** (the one location
      field every source carries — flood-control/DPWH province, PhilGEPS area-of-delivery) so people
      can open their own zone; province cards/links feed `/contracts?province=…`. Server side:
      `listProvinces()` aggregate + a `province` filter on `listContracts()`, `idx_contracts_province`.
- [ ] Map view of flagged projects (lat/long already in the data)
- [ ] Performance pass for low-end mobile (payload size, no heavy JS)

## Useful commands

```sh
# always prepend portable Node on the original PC (see CLAUDE.local.md)
npm run dev      # dev server
npm run check    # types
npm run gen      # regenerate worker types after editing wrangler.jsonc
npx wrangler d1 create corrupcion-db
npx wrangler d1 import corrupcion-db --file=./pipeline/out/contracts.sql
npm run build && npx wrangler deploy
```
