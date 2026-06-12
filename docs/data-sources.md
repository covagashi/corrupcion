# Data Sources

All data sources for the Philippine anti-corruption platform. The reference repos live one level up
(`D:\3_workbench\Christian\corrupcion\*-main`) — read-only, never modify them.

## Public works contracts — DPWH Transparency API

- Listing: `https://api.transparency.dpwh.gov.ph/projects?page={page}&limit={limit}` (max `limit=5000`)
- Detail: `https://api.transparency.dpwh.gov.ph/projects/{contractId}`
- ~247K projects total. The API sits behind Cloudflare bot protection: plain `fetch` gets blocked
  (403/429/error 1015). The reference scraper (`dpwh-transparency-data-api-scraper-main`) works around
  it with `curl-cffi` TLS-fingerprint rotation + proxy rotation. Prefer the bulk datasets below; hit the
  live API only for incremental updates.

## All-agency contracts — PhilGEPS

- Bulk data: Hugging Face `bettergovph/philgeps-data` (~11 GB, ~105K awarded contracts).
- PhilGEPS has no usable public API; bulk downloads are the way in.
- The BetterGovPH pipeline already links ~37K PhilGEPS contracts to DPWH projects.

## BetterGovPH datasets (Hugging Face: `huggingface.co/bettergovph`)

| Dataset                              | Contents                                                |
| ------------------------------------ | ------------------------------------------------------- |
| `dpwh-transparency-data`             | DPWH projects, ~37 GB Parquet                           |
| `philgeps-data`                      | PhilGEPS awarded contracts                              |
| `gaa`                                | General Appropriations Act (national budget), 4.5M rows |
| `senate-bills`                       | Senate bills                                            |
| `open-customs-data`                  | Customs import data, 65M rows                           |
| `bir-tax-collection`                 | BIR tax collection                                      |
| `raw-philippine-data`, `gov-library` | Misc government documents                               |

## BetterGov Open Data Portal API

- Base: `https://data.bettergov.ph/api/v1` (spec: `../openapi.json` at workspace root)
- Endpoints: `/datasets`, `/datasets/{id}`, `/resources?dataset_id=`, `/publishers`, `/categories`, `/stats`
- Catalog API: returns dataset metadata + `download_url` per resource. Rate limits 20–100 req/min.
- Notable: **Ateneo Policy Center Political Dynasties Dataset** (local-government clan tracking) — key
  input for the contracts ↔ politicians alignment.

## Politicians

- **Open Congress** (`open-congress-data-main`, `open-congress-api-main`): senators, representatives,
  bills, congress memberships. Scraped from `web.senate.gov.ph` and `congress.gov.ph`, modeled as a
  Neo4j graph; the API repo (Deno + Hono) shows the REST shape over it.
- **SALN** (`saln-tracker-ph-main`): Statements of Assets, Liabilities and Net Worth of public
  officials (President, VP, senators). Coverage is sparse — SALNs are released irregularly. Repo has
  officials data + SALN JSONs in `app/data/`.

## Company ownership

- SEC Philippines company registrations — used by BetterGovPH to cross-reference contractor names with
  incorporators/owners. No public API; data comes from SEC filings. This is the third leg of the
  contracts ↔ politicians ↔ owners alignment.

## Local reference repos

| Repo                                                 | What to learn from it                                                         |
| ---------------------------------------------------- | ----------------------------------------------------------------------------- |
| `contractes-cat-main`                                | The irregularity metric (threshold-clustering anomaly detection), UI patterns |
| `dpwh-transparency-data-api-scraper-main`            | How to scrape the DPWH API reliably                                           |
| `open-congress-api-main` / `open-congress-data-main` | Politician data model and sources                                             |
| `saln-tracker-ph-main`                               | SALN data shape, PH-flavored UI reference                                     |
| `open-data-visualization-main`                       | BetterGovPH visualization approach                                            |
