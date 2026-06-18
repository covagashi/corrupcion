# Pending: the PhilGEPS data run (blocked in the web sandbox)

Phase 3a (PhilGEPS + threshold-splitting) is **fully implemented and type-checked**, but the parts
that need the actual ~470 MB dataset could **not** be executed in the Claude-Code-on-the-web sandbox
because its network egress policy blocks `huggingface.co`:

```
$ python -c "import httpx; httpx.head('https://huggingface.co/.../philgeps.parquet')"
403 — Host not in allowlist: huggingface.co. Add this host to your network egress settings.
```

## What IS done (no data needed, verified here)

- Pipeline code: `fetch.py` (download), `metric_config.py` (verified `T`), `philgeps.py` (mapping),
  `threshold_splitting.py` (statistic), `transform.py` (parquet scan → SQL emit).
- D1 schema (`db/schema.sql`): new columns + `threshold_splitting_yearly`.
- Front end: `BELOW_THRESHOLD_CLUSTER` flag, `/threshold-splitting` page, source filter, footer links.
- 11 pytest unit tests green; `npm run check` clean.
- The `philgeps.parquet` schema was confirmed against the real file's Parquet metadata, and the
  UUID-`id` handling + the full `build_philgeps` path were validated end-to-end against a
  **schema-exact synthetic parquet** (duckdb-written UUID/double/timestamp columns) that loads
  cleanly into the real D1 schema.

## What could NOT be run here (needs `huggingface.co` reachable)

1. `python pipeline/fetch.py` — download `philgeps.parquet` (+ `awardees`/`organizations`).
2. `python pipeline/transform.py` — scan all 5.48M rows, write `pipeline/out/contracts.sql`
   (flood-control rows + PhilGEPS band rows + the `threshold_splitting_yearly` table).
3. Seed D1 and smoke-test the live pages:
   ```sh
   npx wrangler d1 execute corrupcion-db --local --file=db/schema.sql --yes
   npx wrangler d1 execute corrupcion-db --local --file=pipeline/out/contracts.sql --yes
   npx wrangler d1 execute corrupcion-db --local --yes \
     --command="SELECT source, COUNT(*) FROM contracts GROUP BY source;"
   npm run dev   # check /threshold-splitting shows the headline number + per-year bars
   ```

## How to finish it

- **In CI (recommended):** GitHub Actions has open network, so the existing
  `.github/workflows/refresh.yml` runs steps 1–3 against **remote** D1 unchanged. This needs the
  one-time D1 setup (real `database_id` + `CLOUDFLARE_*` secrets) from [deploy.md](deploy.md).
- **In a future web session:** add `huggingface.co` to the environment's **network egress
  allowlist**, then run steps 1–3 locally.
- **On any logged-in machine:** `pip install -r pipeline/requirements.txt`, then run steps 1–3.

Until one of these runs, the `/threshold-splitting` page renders its empty-state ("No
threshold-splitting data is loaded yet") and the contract list shows only the flood-control rows.
