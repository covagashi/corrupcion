# pipeline

Offline ETL that powers the site. Runs in CI (GitHub Actions), **never** at request time.

```
fetch  ->  transform + compute metric  ->  load into D1
```

Output is precomputed rows; the Worker only reads them. See [../docs/ROADMAP.md](../docs/ROADMAP.md).

## Layout

| Path               | Purpose                                                                              |
| ------------------ | ------------------------------------------------------------------------------------ |
| `fetch.py`         | Download raw datasets into `sources/` (discovers URLs via the BetterGov catalog API) |
| `transform.py`     | Parse raw data, compute the irregularity metric, write `out/contracts.sql`           |
| `congress.py`     | Open Congress TOML → `out/congress.sql` (legislators directory)                       |
| `officials.py`    | Raw Philippine Data parquets → `out/officials.sql` (public officials + area join)      |
| `pcab.py`         | Scrape the PCAB license verification jqGrid → `out/pcab.sql` (owners + suspended)     |
| `dynasties.py`    | Ateneo Policy Center Political Dynasties xlsx → `out/dynasties.sql` (207K + shares)   |
| `sources/`         | Raw downloaded data — gitignored                                                     |
| `out/`             | Generated SQL / SQLite for D1 import — gitignored                                    |
| `../db/schema.sql` | D1 table definitions                                                                 |

## Run locally

```sh
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
python fetch.py            # -> sources/flood_control.json / philgeps.parquet / dpwh / open-congress / raw-ph
python transform.py        # -> out/contracts.sql
python congress.py         # -> out/congress.sql
python officials.py        # -> out/officials.sql
python pcab.py             # -> out/pcab.sql       (no fetch.py dep; scrapes PCAB live)
python dynasties.py        # -> out/dynasties.sql  (reads ../docs/*.xlsx; no fetch.py dep)
```

## Load into D1

```sh
npx wrangler d1 execute corrupcion-db --file=../db/schema.sql

# small dumps: direct --file is fine
npx wrangler d1 execute corrupcion-db --file=out/congress.sql
npx wrangler d1 execute corrupcion-db --file=out/pcab.sql

# big dumps: chunked via split_sql.py (see ../docs/deploy.md)
python split_sql.py out/contracts.sql out/chunks
for f in out/chunks/chunk_*.sql; do npx wrangler d1 execute corrupcion-db --file=$f; done
python split_sql.py out/officials.sql out/chunks-officials
for f in out/chunks-officials/chunk_*.sql; do npx wrangler d1 execute corrupcion-db --file=$f; done
python split_sql.py out/dynasties.sql out/chunks-dynasties
for f in out/chunks-dynasties/chunk_*.sql; do npx wrangler d1 execute corrupcion-db --file=$f; done
```

## Phase 1 source: Flood Control

`flood_control.json` (ArcGIS feature format, ~9,855 records). Useful attributes:
`Contractor, ABC, ContractCost, Region, Province, Municipality, LegislativeDistrict,
DistrictEngineeringOffice, ProjectDescription, InfraYear, Latitude, Longitude, ContractID`.

Metric signals computed in `transform.py`:

- **bid-to-ceiling ratio** = `ContractCost / ABC` — flag when ≥ ~0.99
- **supplier concentration** — a contractor's share of contract value per legislative district
