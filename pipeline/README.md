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
| `sources/`         | Raw downloaded data — gitignored                                                     |
| `out/`             | Generated SQL / SQLite for D1 import — gitignored                                    |
| `../db/schema.sql` | D1 table definitions                                                                 |

## Run locally

```sh
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
python fetch.py            # -> sources/flood_control.json
python transform.py        # -> out/contracts.sql
```

## Load into D1

```sh
npx wrangler d1 execute corrupcion-db --file=../db/schema.sql
npx wrangler d1 execute corrupcion-db --file=out/contracts.sql
```

## Phase 1 source: Flood Control

`flood_control.json` (ArcGIS feature format, ~9,855 records). Useful attributes:
`Contractor, ABC, ContractCost, Region, Province, Municipality, LegislativeDistrict,
DistrictEngineeringOffice, ProjectDescription, InfraYear, Latitude, Longitude, ContractID`.

Metric signals computed in `transform.py`:

- **bid-to-ceiling ratio** = `ContractCost / ABC` — flag when ≥ ~0.99
- **supplier concentration** — a contractor's share of contract value per legislative district
