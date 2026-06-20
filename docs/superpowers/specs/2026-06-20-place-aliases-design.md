# Place-name aliases for the contract↔official join (Phase 4)

**Status:** approved design, ready for implementation plan
**Date:** 2026-06-20
**Roadmap item:** Phase 4 — "Stronger place-name matching (the officials↔contracts join is
exact-after-normalize today); a province/locality alias table would catch more."

## Problem

The contract↔official area panel (`getAreaOfficials` in `src/lib/server/officials.ts`) joins a
contract's `province`/`locality` to officials' terms on a key produced by `normalizePlace`, which
only lowercases, trims, and collapses whitespace. Contract place names come raw from three datasets
(Flood Control ArcGIS, PhilGEPS `location` struct, DPWH) and official place names from a fourth (Raw
Philippine Data). When the same place is written differently across sources — `Metro Manila` vs
`NCR`, `City of Manila` vs `Manila`, `Compostela Valley` vs `Davao de Oro`, `Cotabato (North
Cotabato)` vs `Cotabato` — the keys differ and the join **silently misses**: a real governor/mayor
who held office in that area never appears on the contract page.

## Goal

Raise recall of the area join by canonicalizing place names before keying, **without** introducing
false merges, and **without** the silent-drift risk the current two-copy `normalize_place` design
carries. Province-level matching is the priority — province-wide offices (governor, representative,
board member) are the highest-value, closed-set case.

## Non-goals

- No hand-maintained table of the ~1,600 municipalities/cities (unmanageable, false-positive prone).
  Localities get **rule-based** cleanup only.
- No fuzzy/edit-distance matching. Matching stays exact-after-canonicalize: transparent and auditable
  (a CLAUDE.md non-negotiable).
- No data run. The real HF-backed seed stays deferred (sandbox blocks `huggingface.co`); this change
  is verified by unit fixtures + an extended synthetic officials fixture.

## Design

### Single source of truth

One checked-in JSON file is the authoritative alias data, consumed by **both** sides:

- `src/lib/place-aliases.json`
  - **TS (Worker):** `import aliases from './place-aliases.json'` in `src/lib/officials.ts`.
  - **Python (pipeline):** `json.load` of `../src/lib/place-aliases.json` (resolved relative to
    `pipeline/officials.py`) in `pipeline/officials.py`.

This replaces "keep the two copies identical by hand" (flagged twice in the codebase) with a single
edit point. Shape:

```json
{
  "provinceAliases": {
    "metro manila": "ncr",
    "national capital region": "ncr",
    "compostela valley": "davao de oro",
    "north cotabato": "cotabato"
  },
  "localityPrefixes": ["city of ", "municipality of ", "mun. of "],
  "localityAbbrev": { "sto.": "santo", "sta.": "santa", "gen.": "general" }
}
```

`provinceAliases` maps an already-base-normalized **variant key → canonical key**. The canonical key
is just one chosen normalized spelling; only divergences need entries (a name that already agrees on
both sides needs none). Both contract-side and official-side strings pass through the same function,
so as long as both variants resolve to the same key they match.

### Two canonicalizers over a shared base

`normalizePlace` stays as the base step (trim, lowercase, collapse whitespace) and gains two
purpose-specific wrappers, so province aliasing never contaminates a locality string (e.g. a city
sharing a province's name):

- `normalizeProvince(value)` = base → `provinceAliases` lookup (if the base key is a known variant,
  return its canonical key).
- `normalizeLocality(value)` = base → strip a leading `localityPrefixes` entry → strip a trailing
  `" city"` → drop any `(...)` parenthetical → expand a leading `localityAbbrev` token → collapse
  whitespace again.

Both are pure functions, defined once in `src/lib/officials.ts` and mirrored **exactly** in
`pipeline/officials.py` (`normalize_province` / `normalize_locality`), both driven by the shared
JSON. `normalizePlace`/`normalize_place` remain exported for the base behavior.

### Wiring

- `pipeline/officials.py`: write `province_key = normalize_province(province)` and
  `locality_key = normalize_locality(locality)` (today both use `normalize_place`).
- `src/lib/server/officials.ts` `getAreaOfficials`: `pkey = normalizeProvince(opts.province)`,
  `lkey = normalizeLocality(opts.locality)`.
- No schema change. `province_key` / `locality_key` columns already exist; only how they're computed
  changes. The data must be re-seeded for the new keys to take effect (already required on every
  pipeline run; noted in deploy docs).

## Verification

The repo has no test runner by design (only `npm run check`). Add a **shared case fixture**,
`pipeline/test/place-cases.json`, listing `{ value, province_key, locality_key }` expectations,
checked by both languages so the "must stay identical" invariant is tested directly:

- Python: `pipeline/test/test_normalize.py` — plain `assert`s runnable with `python`, no pytest dep.
- TS: a small script run via `npx tsx` (or equivalent) asserting the same fixture against
  `normalizeProvince`/`normalizeLocality`.

Cases cover: NCR/Metro Manila, City-of/trailing-City, parenthetical disambiguation, Sto./Sta.
abbreviations, already-canonical pass-through (no change), and null/empty.

Plus: extend the existing synthetic officials fixture with one name-variant pair (e.g. contract
province `Metro Manila`, official term province `NCR`) and confirm the area panel now matches where
it previously missed. Then `npm run check` (0 errors) and `npm run lint`.

## Risks

- **False merges.** Mitigated by keeping `provinceAliases` to verified, well-known PH equivalences
  only, and by separating province vs locality canonicalization.
- **Alias coverage is seeded from PH geography knowledge, not the real data** (which isn't reachable
  here). The table is built to be extended; recall should be re-checked against the seeded D1 on a
  logged-in/CI machine. Recorded as a follow-up.
- **Python/TS divergence** is now caught by the shared-fixture parity test rather than relying on a
  comment.
