# Pending work

Single place that tracks what is **not** done yet on this branch. Phase-level tracking lives in
[ROADMAP.md](ROADMAP.md); the data-run details are in [pending-data-run.md](pending-data-run.md).

## 1. Run the pipeline against the real data — DONE locally 2026-06-18

Phase 3a (PhilGEPS) and Phase 3b (DPWH) ran end-to-end on a logged-in local machine:
`fetch.py` (downloaded philgeps.parquet 470 MB + DPWH 23 MB), `transform.py` (scanned 5.13M
in-window PhilGEPS rows → 42,229 monitored-band contracts + 248,220 DPWH projects + the 13-year
`threshold_splitting_yearly` table), then **seeded local D1** and verified: contracts by source
(dpwh 248,220 / philgeps 42,229 / flood_control 9,855) and the headline (~65,871 excess contracts,
~₱65.4 B, clustered just below the ₱1M ceiling, all years 2013–2025 populated).

- **DPWH download path confirmed** — `DPWH_BASE` / `DPWH_FILE` in `pipeline/fetch.py` resolved with
  no 404; schema assertion passed against the real parquet.
- **DPWH OVER_BUDGET = 0 flagged** — no project's `amountPaid` exceeded `budget` in the data; not an
  error, just nothing to flag with the current rule.
- **Visual render verified** — ran `npm install` + `npm run check` (0 errors) + `npm run dev` under
  Node 22 and fetched the pages: `/threshold-splitting` returns 200 with the headline (65,871 excess
  / ₱65.4 B) and all 13 year rows (not the empty state); `/`, `/methodology` and `/?source=philgeps`
  all return 200. (This machine ships Node 20.17.0, below the `engine-strict` ≥22 floor some deps
  need; a portable Node 22 was used just for this.)
- **Remote D1 seeded + deployed 2026-06-18.** Same run was pushed to production from the logged-in
  machine (see item 2). The Claude-Code-on-the-web sandbox remains blocked on `huggingface.co`
  egress — see [pending-data-run.md](pending-data-run.md).

## 2. One-time deploy setup — DONE 2026-06-18 (CI token still optional)

Done from a logged-in machine (`wrangler` OAuth, account `clopez@tuta.io`):

- Created the `corrupcion-db` D1 instance; its real `database_id`
  (`7c485949-e604-4b12-aef4-488207ccf74a`) is committed in `wrangler.jsonc`.
- Seeded **remote** D1 with all 300,304 rows (dpwh 248,220 / philgeps 42,229 / flood_control 9,855)
  - the 13-year `threshold_splitting_yearly` table.
- `npm run build` + `npx wrangler deploy` → **live at https://corrupcion.clopez-5fd.workers.dev**;
  `/`, `/threshold-splitting`, `/methodology`, `/?source=philgeps` all return 200 with real data.
- Set the `CLOUDFLARE_ACCOUNT_ID` GitHub repo secret.

**Seeding gotcha:** `wrangler d1 execute --remote --file` switches to the R2-upload import API for
the 125 MB dump and hung with 0 rows written; `pipeline/split_sql.py` splits it into ~5 MB
statement-aligned chunks that seed reliably via the direct batched API. Re-seeds should use the
chunk loop, not a single `--file`.

**Still optional — `CLOUDFLARE_API_TOKEN`** for hands-off CI (`Refresh data & deploy` workflow):
wrangler OAuth can't mint it, so create it in the Cloudflare dashboard (Edit Cloudflare Workers
template + `D1 · Edit`) and add it as a repo secret. Until then, re-deploys run from a logged-in
machine. The site is already live without it.

## 3. Remaining roadmap phases (not started)

- **Phase 4 — Alignment (contracts ↔ politicians ↔ owners).**
  - _Legislators directory — DONE._ `pipeline/congress.py` ingests the Open Congress TOML data
    (cloned by `fetch.py` into `pipeline/sources/open-congress-data`) → 1,173 legislators →
    `out/congress.sql` → `legislators` table. UI: `/legislators` + `/legislator/[id]`. Verified by
    running the pipeline here and seeding a **local** D1 (1,173 rows; search + chamber filter +
    detail all render). Remote seed/deploy still runs from a logged-in/CI machine (deploy.md +
    refresh.yml updated to build + load `congress.sql`).
  - _The actual alignment join is blocked._ Open Congress `Person` carries no electoral district
    (only senate/house membership), so legislators cannot be tied to a contract's area. SALN is
    reachable but national-only and its names live in Firebase (not in the repo). The Ateneo
    dynasties dataset is on `data.bettergov.ph` (sandbox-blocked, 403). SEC company ownership has no
    public API. Verifying each source's schema **before mapping** confirmed these gaps up front.
- **Phase 5 — Polish.**
  - _Landing page + "find your area" browse._ **DONE** — `/` is a plain-language landing; the list
    moved to `/contracts`; `/areas` groups by province and links into `/contracts?province=…`
    (`listProvinces()` + `province` filter + `idx_contracts_province`). Type-checked + built here;
    not yet visually verified against seeded data (sandbox D1 is empty — same constraint as Phase 3).
  - _Map view of flagged projects._ Now feasible — flood-control and DPWH rows carry `latitude` /
    `longitude` — but a map adds client-side JS, which trades off against the mobile-first /
    minimal-JS design rule. Decide the approach (static markers vs. a tile library) before building.
  - _Performance pass for low-end mobile_ (payload size, no heavy JS).

## 4. Known follow-ups within Phase 3

- **DPWH supplier concentration** is not computed: the existing `contractor_district_stats`
  aggregate is keyed by legislative district, which DPWH infrastructure data does not carry.
  Computing concentration per province/region for DPWH is a candidate for a later pass.
