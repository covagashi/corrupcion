# Bantay Kontrata — Philippine public-contracts watchdog

A mobile-first website that makes Philippine public procurement legible to ordinary citizens:

- **Contracts** from DPWH (public works) and PhilGEPS (all agencies), searchable by place,
  agency, and contractor.
- **An irregularity metric** — transparent, statistical flags for suspicious patterns such as
  contract amounts clustered just below legal procurement thresholds (threshold-splitting) and
  abnormal supplier concentration. Inspired by [contractes.cat](https://contractes.cat).
- **Alignment** of contracts with local politicians and the owners of winning companies
  (Open Congress, SALN disclosures, SEC records, political-dynasty research).

Most Filipinos browse on low-end phones over expensive mobile data, so the site is built to be
light: plain-language explanations, minimal JavaScript, no dashboard clutter.

## Stack

SvelteKit (Svelte 5) + TypeScript + Tailwind, deployed on Cloudflare Workers with a D1 database
of precomputed metrics. Heavy data processing happens offline in a separate pipeline; the site
only serves precomputed results.

## Develop

```sh
npm install
npm run dev      # dev server
npm run check    # types
npm run lint     # prettier + eslint
```

Deploy: `npm run build && npx wrangler deploy` (requires a Cloudflare account).

## Data sources

See [docs/data-sources.md](docs/data-sources.md). Built on the open-data work of
[BetterGovPH](https://huggingface.co/bettergovph) and others.

## Status

Early scaffold — data pipeline and UI are under construction.
See [docs/ROADMAP.md](docs/ROADMAP.md) for the step-by-step plan.
