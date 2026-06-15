# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Mobile-first anti-corruption website for the Philippines. It surfaces public procurement contracts
(DPWH + PhilGEPS), flags statistical irregularities, and aligns contracts with local politicians and
the owners of winning companies. Modeled on contractes.cat, which this project adapts to PH data.

## Stack and commands

SvelteKit (Svelte 5) + TypeScript + Tailwind 4, deployed to **Cloudflare Workers**
(`@sveltejs/adapter-cloudflare`, config in `wrangler.jsonc`). Node >= 20.19 required (Vite 8).

- `npm run check` — wrangler types check + svelte-check. Run after any change.
- `npm run lint` / `npm run format` — Prettier + ESLint.
- `npm run gen` — regenerate `worker-configuration.d.ts`. **Required after every `wrangler.jsonc`
  edit**, otherwise `build` and `check` fail with "types out of date".
- Deploy: see @docs/deploy.md (local with `wrangler login`, or hands-off via the CI workflow).
- D1 binding (`DB`) is active in `wrangler.jsonc` with a placeholder `database_id` — replace it with
  the real id after `wrangler d1 create` (or from the dashboard) to deploy. Local dev works as-is.
- **Run `npm run gen` right before `npm run check`/`npm run build`** — `wrangler types --check`
  otherwise reports a spurious "types out of date".

## Architecture decisions

- **All heavy data work happens offline**, in `pipeline/` (Python): `fetch.py` downloads bulk
  datasets, `transform.py` computes the irregularity metric and writes `out/contracts.sql`, which is
  loaded into D1 (`db/schema.sql` defines the tables). The Worker only reads precomputed rows —
  never compute metrics or fetch government APIs at request time. Server-side D1 access lives in
  `src/lib/server/contracts.ts`; flag definitions in `src/lib/flags.ts` feed both the UI and the
  public `/methodology` page. Metric details: @docs/methodology.md.
- Data sources, endpoints, and bulk datasets are documented in @docs/data-sources.md.
- The DPWH live API is behind Cloudflare bot protection; plain `fetch` gets blocked. Use the bulk
  Hugging Face datasets instead (see data-sources doc).

## The irregularity metric

Adapted from contractes.cat: detect statistically anomalous clustering of contract amounts just
below legal procurement thresholds (threshold-splitting), plus supplier concentration per agency and
contracts ↔ politicians ↔ company-owners alignment. The metric must stay **transparent and
auditable**: simple statistics, documented methodology on a public page, no opaque scores.
PH thresholds come from RA 9184 / RA 12009 IRR — verify current values before hardcoding.

## Design rules (non-negotiable)

- 99% of the audience browses on mobile, often low-end Android on expensive data: mobile-first
  layouts, minimal client JS, small payloads, no chart-heavy dashboards.
- Plain-language English UI. Explain findings in sentences a non-expert understands; one clear
  number beats a graph.

## Reference repos (original dev machine only)

On the original workspace these sit one level up (`../contractes-cat-main`, `../*-main`): the
contractes.cat source, DPWH scraper, Open Congress, SALN tracker. **Read-only** — never modify them;
all new code lives in this repo.
