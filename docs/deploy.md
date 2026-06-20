# Deploy (Phase 2)

The site is a Cloudflare Worker (SvelteKit SSR) that reads a D1 database of precomputed contract
rows. Two ways to ship it: **once, manually from a logged-in machine**, or **hands-off in CI**
(`.github/workflows/refresh.yml`). Either way the one-time D1 setup below must happen first.

## One-time: create the D1 database

You need the database **id** so the Worker can bind to it. Pick whichever you can do:

- **With Wrangler** (needs `wrangler login` to work locally):
  ```sh
  npx wrangler login            # opens a browser
  npx wrangler d1 create corrupcion-db
  ```
  Copy the `database_id` it prints.
- **Or from the dashboard** (no Node needed): Cloudflare → Workers & Pages → D1 → Create database →
  name it `corrupcion-db` → open it → copy the **Database ID**.

Then paste that id into `wrangler.jsonc`, replacing the placeholder:

```jsonc
"d1_databases": [
  { "binding": "DB", "database_name": "corrupcion-db", "database_id": "<the-real-id>" }
]
```

Commit that change, then `npm run gen` (regenerates Worker types after a `wrangler.jsonc` edit).

## Option A — deploy manually (logged-in machine)

```sh
# pipeline (Python) -> out/contracts.sql + out/congress.sql
python pipeline/fetch.py        # also clones open-congress-data into pipeline/sources/
python pipeline/transform.py    # -> out/contracts.sql
python pipeline/congress.py     # -> out/congress.sql   (legislators directory)
python pipeline/officials.py    # -> out/officials.sql  (public officials + area alignment)

# load the remote D1 (schema first, then rows) and ship
npx wrangler d1 execute corrupcion-db --remote --file=db/schema.sql --yes
npx wrangler d1 execute corrupcion-db --remote --file=pipeline/out/contracts.sql --yes
npx wrangler d1 execute corrupcion-db --remote --file=pipeline/out/congress.sql --yes
npx wrangler d1 execute corrupcion-db --remote --file=pipeline/out/officials.sql --yes
npm run build && npx wrangler deploy
```

## Option B — deploy from CI (no local Node)

The workflow does all of the above on every monthly cron and on the "Run workflow" button. It needs
two repo secrets (GitHub → repo → Settings → Secrets and variables → Actions → New repository
secret):

| Secret                  | Where to get it                                                                                                                  |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `CLOUDFLARE_API_TOKEN`  | Cloudflare → My Profile → API Tokens → Create Token → **Edit Cloudflare Workers** template, then **add `D1 · Edit`** permission. |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare → Workers & Pages overview (right sidebar), or `wrangler whoami`.                                                     |

With the real `database_id` committed and both secrets set, trigger **Actions → Refresh data &
deploy → Run workflow**. After the first success the monthly cron keeps the data fresh.

## Notes

- `db/schema.sql` and `pipeline/out/contracts.sql` are both idempotent (drop+recreate / delete+insert),
  so re-running is safe.
- Remote `d1 execute --file` of the ~6 MB dump is fine but not instant; if it ever gets unwieldy,
  switch the data step to `wrangler d1 import`.
- **Network:** `pipeline/fetch.py` downloads the bulk datasets from `huggingface.co`. CI runners and
  normal dev machines reach it fine; the Claude-Code-on-the-web sandbox does not unless the host is
  added to the environment's egress allowlist. See [pending-data-run.md](pending-data-run.md).
