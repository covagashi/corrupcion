# Pending work

Single place that tracks what is **not** done yet on this branch. Phase-level tracking lives in
[ROADMAP.md](ROADMAP.md); the data-run details are in [pending-data-run.md](pending-data-run.md).

## 1. Run the pipeline against the real data (blocked here)

Phase 3a (PhilGEPS) and Phase 3b (DPWH) are fully implemented and type-checked, but the data run
could not execute in the Claude-Code-on-the-web sandbox because its egress policy blocks
`huggingface.co`. Outstanding steps — download → `transform.py` → seed D1 → smoke-test the pages —
and the three ways to finish them (CI / egress allowlist / logged-in machine) are detailed in
[pending-data-run.md](pending-data-run.md).

- **Verify the DPWH download path** in `pipeline/fetch.py` (`DPWH_BASE` / `DPWH_FILE`). The schema is
  verified, but the exact Hugging Face repo path could not be reached to confirm — fix if it 404s.

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
