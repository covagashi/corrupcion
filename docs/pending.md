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
- This local run seeded **local** D1 only. The production **remote** D1 seed still happens via CI or
  a logged-in machine (item 2). The Claude-Code-on-the-web sandbox remains blocked on `huggingface.co`
  egress — see [pending-data-run.md](pending-data-run.md).

## 2. One-time deploy setup (you)

From [deploy.md](deploy.md): create the D1 database, paste its real `database_id` into
`wrangler.jsonc`, add the `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` repo secrets, then run the
`Refresh data & deploy` workflow once. After that the monthly cron keeps data fresh.

## 3. Remaining roadmap phases (not started)

- **Phase 4 — Alignment (contracts ↔ politicians ↔ owners).** Needs the Open Congress, SALN and SEC
  datasets and a data model linking districts/contractors to officials and company owners. Each new
  source should have its **Parquet/JSON schema verified before mapping** (the PhilGEPS UUID bug is a
  reminder of why blind mapping is risky).
- **Phase 5 — Polish.**
  - _Map view of flagged projects._ Now feasible — flood-control and DPWH rows carry `latitude` /
    `longitude` — but a map adds client-side JS, which trades off against the mobile-first /
    minimal-JS design rule. Decide the approach (static markers vs. a tile library) before building.
  - _Performance pass for low-end mobile_ (payload size, no heavy JS).

## 4. Known follow-ups within Phase 3

- **DPWH supplier concentration** is not computed: the existing `contractor_district_stats`
  aggregate is keyed by legislative district, which DPWH infrastructure data does not carry.
  Computing concentration per province/region for DPWH is a candidate for a later pass.
