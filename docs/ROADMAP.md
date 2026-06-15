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

## Phase 0 — Base ✅ (done)

- [x] SvelteKit + TS + Tailwind + Cloudflare Workers adapter scaffolded
- [x] Repo published: https://github.com/covagashi/corrupcion (public)
- [x] Data sources documented and live-tested

## Phase 1 — First dataset end to end: Flood Control

Smallest, richest, highest-impact dataset (9,855 records, 16 MB). Goal: one real page live.

- [ ] `pipeline/` (Python): download Flood Control JSON
      (`https://raw.githubusercontent.com/bettergovph/bettergov/refs/heads/main/src/data/flood_control/flood_control.json`)
- [ ] Parse the ArcGIS feature format; extract the useful fields:
      `Contractor, ABC, ContractCost, Region, Province, Municipality, LegislativeDistrict,
      ProjectDescription, InfraYear, Latitude, Longitude, ContractID`
- [ ] Compute first irregularity signals:
  - [ ] **bid-to-ceiling ratio** = `ContractCost / ABC` — flag when ≥ ~0.99 (winning bid suspiciously
        close to the secret ceiling)
  - [ ] **supplier concentration** — share of contracts/value won by a single contractor per
        LegislativeDistrict / DistrictEngineeringOffice
- [ ] Output a SQLite file or `.sql` dump
- [ ] D1: create db (`wrangler d1 create corrupcion-db`), define schema, load it
      (uncomment the `d1_databases` block in `wrangler.jsonc`, then `npm run gen`)
- [ ] UI: contract list page (mobile-first) with a plain-language risk flag per contract
- [ ] UI: contract detail page explaining each flag in one sentence

## Phase 2 — Automate the refresh

- [ ] GitHub Actions workflow: run the pipeline on a monthly cron + manual dispatch
- [ ] Step to load results into D1 via `wrangler d1 import` (store `CLOUDFLARE_API_TOKEN` as a repo secret)
- [ ] Deploy the site (`wrangler deploy`)

## Phase 3 — Add the big contract datasets

- [ ] PhilGEPS (`philgeps.parquet`, ~493 MB — all agencies) into the pipeline
- [ ] DPWH Infrastructure (`dpwh_transparency_data.parquet`, ~21 MB)
- [ ] Adapt the metric: add legal threshold-splitting detection (amounts clustered just below
      RA 9184 / RA 12009 procurement thresholds — verify current threshold values before hardcoding)
- [ ] Unified search across all contracts (server-side, returns small HTML)

## Phase 4 — Alignment (contracts ↔ politicians ↔ owners)

- [ ] Politicians: Open Congress + SALN data; link by LegislativeDistrict / location
- [ ] Company owners: SEC records; link contractors to incorporators/owners
- [ ] Political-dynasty dataset (Ateneo Policy Center) for clan context
- [ ] Alignment views: "who represents this district + who won the contracts here + who owns them"

## Phase 5 — Polish

- [ ] Public methodology page (how each flag is computed — keep it transparent/auditable)
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
