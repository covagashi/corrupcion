# Pending work

Single place that tracks what is **not** done yet on this branch. Phase-level tracking lives in
[ROADMAP.md](ROADMAP.md).

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
  machine (see item 2). (The Claude-Code-on-the-web sandbox cannot do this run itself — its egress
  blocks `huggingface.co` — so it must run on a logged-in/CI machine.)

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

**Decided 2026-06-21 — skip `CLOUDFLARE_API_TOKEN` / hands-off CI; refresh with wrangler instead.**
wrangler has no command to mint a Cloudflare API token (only OAuth `login`/`whoami`; `wrangler secret`
is for Worker secrets), and that token was only needed for the unattended monthly cron. So the
`Refresh data & deploy` workflow stays unused, and data refreshes / deploys run from this
logged-in machine with the wrangler steps in [deploy.md](deploy.md) Option A (chunked seed +
`wrangler deploy`). If hands-off CI is ever wanted, the only missing piece is creating that token in
the Cloudflare dashboard (Edit Cloudflare Workers template + `D1 · Edit`) and `gh secret set`-ting it.

## 3. Remaining roadmap phases (not started)

- **Phase 4 — Alignment (contracts ↔ politicians ↔ owners).**
  - _Legislators directory — DONE + LIVE 2026-06-21._ `pipeline/congress.py` ingests the Open
    Congress TOML data (cloned by `fetch.py` into `pipeline/sources/open-congress-data`) → 1,173
    legislators → `out/congress.sql` → `legislators` table. UI: `/legislators` + `/legislator/[id]`.
    Seeded to **remote** D1 (1,173 rows) and deployed; `/legislators` returns 200 in production.
  - _Officials ↔ contracts by area — DONE + LIVE 2026-06-21._ The Raw Philippine Data `memberships`
    table has the missing geographic key (province / locality + position + year). `pipeline/officials.py`
    builds `officials` + `official_terms`. The contract detail page shows "who held office in this
    area" via `getAreaOfficials`. **Real-data run executed on the original PC** (HF is reachable here):
    45,424 officials / 86,234 terms → seeded to remote D1 (chunked) and deployed. Verified live: a
    Davao de Oro contract's area panel now lists the province's governors/mayors (empty before the
    aliases). **`fetch.py` bug fixed** along the way — the Raw PH parquets live under `databases/`,
    not the dataset root, so this run had never actually worked. `normalize_province`/`normalize_locality`
    (Python, in `place_norm.py`) and `normalizeProvince`/`normalizeLocality` (TS) must stay identical
    (guarded by `npm run test:place`).
  - _Open Congress legislators_ stay as a separate bills-focused directory (no district there).
  - _Place-name matching — DONE._ A shared `src/lib/place-aliases.json` now canonicalizes province
    names (aliases: NCR/Metro Manila, Compostela Valley→Davao de Oro, parenthetical disambiguation)
    and municipalities (rules: "City of X"→x, drop parentheticals, Sto./Sta./Gen. expansion) before
    keying the area join, in both the pipeline (`pipeline/place_norm.py`) and the Worker
    (`normalizeProvince`/`normalizeLocality`). A shared fixture is asserted from both languages
    (`npm run test:place`). _Recall verified on real data 2026-06-21_ (`pipeline/test/recall_check.py`):
    over the 419 real contract provinces the canonicalizer now matches **328** (was 157), newly
    covering **171 provinces / ~190,500 contracts** that had an empty area panel before. The dominant
    fix was stripping the DPWH District Engineering Office suffix in the province field
    (`"Bulacan 1st DEO"` → `bulacan`, `"Metro Manila 3rd DEO"` → `ncr`); plus the renamed-province /
    parenthetical aliases. Contract provinces are normalized live in the Worker, so this shipped by
    redeploy with no re-seed. Verified live (a Bulacan DEO contract now lists Bulacan's governors).
  - _Still blocked:_ SEC company ownership and the Ateneo dynasties dataset.
    - **SEC owners:** the data is the SEC General Information Sheet (directors/officers/top-20
      stockholders) — no public API, no bulk download, and scraping eSEARCH is not authorized.
      `ph-check.com` (a third-party aggregator) was investigated 2026-06-23 and is **blocked behind a
      Cloudflare Managed Challenge** — the same wall as the DPWH live API: every request (incl.
      `/js/userdata.js`) returns `403` with `Cf-Mitigated: challenge`. Would need a challenge-solving
      headless browser, and it is only an unofficial aggregator anyway. See
      [data-sources.md](data-sources.md#company-ownership). Parked.
    - **Dynasties:** Ateneo Policy Center dataset on `data.bettergov.ph` returns `403`.
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
