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

# build the data: download the dataset, compute the metric, load a local D1
python pipeline/fetch.py
python pipeline/transform.py
npx wrangler d1 execute corrupcion-db --local --file=db/schema.sql --yes
npx wrangler d1 execute corrupcion-db --local --file=pipeline/out/contracts.sql --yes

npm run dev      # dev server (reads the local D1)
npm run check    # types  (run `npm run gen` first if it complains about types)
npm run lint     # prettier + eslint
```

The pipeline is documented in [pipeline/README.md](pipeline/README.md); how each flag is computed,
in [docs/methodology.md](docs/methodology.md) (and on the site's own `/methodology` page).

## Deploy

The whole thing — pipeline, D1 load, and deploy — runs in CI on a monthly cron and a manual button
(`.github/workflows/refresh.yml`), so no local Node is needed. See
[docs/deploy.md](docs/deploy.md) for the one-time setup (create the D1 database, add two repo
secrets) and the local-deploy alternative.

## Data sources

See [docs/data-sources.md](docs/data-sources.md). Built on the open-data work of
[BetterGovPH](https://huggingface.co/bettergovph) and others.

## Status

**Live end to end on the Flood Control dataset** (9,855 contracts): pipeline → irregularity metric →
D1 → mobile-first list, contract detail, and public methodology pages. Automated refresh + deploy
wired in CI. Next: the larger national datasets (PhilGEPS, DPWH) and contract↔politician↔owner
alignment. Full plan in [docs/ROADMAP.md](docs/ROADMAP.md).
