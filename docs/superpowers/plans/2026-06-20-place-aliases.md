# Place-name aliases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise recall of the contract↔official area join by canonicalizing place names (province aliases + locality rules) before keying, driven by one shared JSON so the Python pipeline and TS Worker can never drift.

**Architecture:** A single checked-in `src/lib/place-aliases.json` holds the alias data. A dependency-free `pipeline/place_norm.py` and the existing `src/lib/officials.ts` each load it and expose `normalize_province`/`normalize_locality` (Python) and `normalizeProvince`/`normalizeLocality` (TS). The pipeline writes `province_key`/`locality_key` with the new functions; the Worker's `getAreaOfficials` keys lookups with them. A shared `pipeline/test/place-cases.json` fixture is asserted from both languages so the "must stay identical" invariant is tested, not just commented.

**Tech Stack:** Python 3 (no new deps; `place_norm.py` avoids `polars`), TypeScript, SvelteKit/Vite (`resolveJsonModule` already on), `tsx` (new devDep) to run the TS parity script.

## Global Constraints

- Matching stays **exact-after-canonicalize** — no fuzzy/edit-distance. Transparent + auditable (CLAUDE.md non-negotiable).
- `normalize_province`/`normalize_locality` (Python) MUST stay behaviorally identical to `normalizeProvince`/`normalizeLocality` (TS). Both read the same `src/lib/place-aliases.json`; only the ~15 lines of string rules are duplicated, and the shared fixture guards them.
- No DB schema change. `province_key`/`locality_key` columns already exist; re-seeding the pipeline output applies the new keys.
- No data run. The real HF-backed seed stays deferred (sandbox blocks `huggingface.co`).
- `place_norm.py` must not import `polars` (keeps the Python test runnable without the data deps).
- Province canonicalization strips parentheticals too (so `Cotabato (North Cotabato)` → `cotabato` needs no alias entry); locality canonicalization strips parentheticals, a leading prefix, a trailing ` city`, and expands a leading abbreviation.

---

### Task 1: Shared alias data + Python canonicalizers

**Files:**
- Create: `src/lib/place-aliases.json`
- Create: `pipeline/place_norm.py`
- Create: `pipeline/test/place-cases.json`
- Test: `pipeline/test/test_normalize.py`

**Interfaces:**
- Produces (Python, importable as `place_norm`):
  - `normalize_place(value: object) -> str | None` — base: trim, lowercase, collapse whitespace.
  - `normalize_province(value: object) -> str | None` — base → strip `(...)` → collapse → `provinceAliases` lookup.
  - `normalize_locality(value: object) -> str | None` — base → strip `(...)` → strip a leading `localityPrefixes` entry → strip trailing ` city` → expand a leading `localityAbbrev` token → collapse.
- Produces (data): `src/lib/place-aliases.json` with keys `provinceAliases` (obj), `localityPrefixes` (string[]), `localityAbbrev` (obj).
- Produces (fixture): `pipeline/test/place-cases.json` with `province` and `locality` arrays of `{ value, key }`.

- [ ] **Step 1: Create the shared alias data**

`src/lib/place-aliases.json`:

```json
{
  "provinceAliases": {
    "metro manila": "ncr",
    "national capital region": "ncr",
    "compostela valley": "davao de oro",
    "north cotabato": "cotabato",
    "western samar": "samar"
  },
  "localityPrefixes": ["city of ", "municipality of ", "mun. of "],
  "localityAbbrev": { "sto.": "santo", "sta.": "santa", "gen.": "general" }
}
```

- [ ] **Step 2: Create the shared test fixture**

`pipeline/test/place-cases.json`:

```json
{
  "province": [
    { "value": "Metro Manila", "key": "ncr" },
    { "value": "National Capital Region", "key": "ncr" },
    { "value": "NCR", "key": "ncr" },
    { "value": "Compostela Valley", "key": "davao de oro" },
    { "value": "North Cotabato", "key": "cotabato" },
    { "value": "Cotabato (North Cotabato)", "key": "cotabato" },
    { "value": "Cebu", "key": "cebu" },
    { "value": "  Davao   del Sur ", "key": "davao del sur" },
    { "value": "", "key": null },
    { "value": null, "key": null }
  ],
  "locality": [
    { "value": "City of Manila", "key": "manila" },
    { "value": "Davao City", "key": "davao" },
    { "value": "Quezon City", "key": "quezon" },
    { "value": "Municipality of Sto. Tomas", "key": "santo tomas" },
    { "value": "City of San Fernando (Pampanga)", "key": "san fernando" },
    { "value": "Mun. of Gen. Trias", "key": "general trias" },
    { "value": "Tagum", "key": "tagum" },
    { "value": "", "key": null },
    { "value": null, "key": null }
  ]
}
```

- [ ] **Step 3: Write the failing Python test**

`pipeline/test/test_normalize.py`:

```python
"""Parity + behavior test for the place canonicalizers. No polars needed.
Run: python pipeline/test/test_normalize.py
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # import place_norm from pipeline/

import place_norm  # noqa: E402

CASES = json.loads((HERE / "place-cases.json").read_text(encoding="utf-8"))


def run() -> None:
    failures = []
    for c in CASES["province"]:
        got = place_norm.normalize_province(c["value"])
        if got != c["key"]:
            failures.append(f"province {c['value']!r}: got {got!r}, want {c['key']!r}")
    for c in CASES["locality"]:
        got = place_norm.normalize_locality(c["value"])
        if got != c["key"]:
            failures.append(f"locality {c['value']!r}: got {got!r}, want {c['key']!r}")
    if failures:
        print("\n".join(failures))
        raise SystemExit(f"{len(failures)} case(s) failed")
    total = len(CASES["province"]) + len(CASES["locality"])
    print(f"OK: {total} cases passed")


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `python pipeline/test/test_normalize.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'place_norm'`.

- [ ] **Step 5: Implement `pipeline/place_norm.py`**

`pipeline/place_norm.py`:

```python
"""Place-name canonicalizers for the contract<->official area join.

Loads the shared alias data in src/lib/place-aliases.json and exposes the
province/locality key functions. Keep behavior identical to normalizeProvince /
normalizeLocality in src/lib/officials.ts (guarded by pipeline/test/place-cases.json).
Deliberately free of polars so the test runs without the pipeline data deps.
"""
from __future__ import annotations

import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
ALIASES_PATH = HERE.parent / "src" / "lib" / "place-aliases.json"

_ALIASES = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
_PROVINCE_ALIASES: dict[str, str] = _ALIASES["provinceAliases"]
_LOCALITY_PREFIXES: list[str] = _ALIASES["localityPrefixes"]
_LOCALITY_ABBREV: dict[str, str] = _ALIASES["localityAbbrev"]

_WS = re.compile(r"\s+")
_PAREN = re.compile(r"\s*\([^)]*\)")


def normalize_place(value: object) -> str | None:
    """Base: trim, lowercase, collapse inner whitespace."""
    if value is None:
        return None
    s = _WS.sub(" ", str(value).strip().lower())
    return s or None


def _strip_paren(s: str) -> str:
    return _WS.sub(" ", _PAREN.sub("", s)).strip()


def normalize_province(value: object) -> str | None:
    base = normalize_place(value)
    if base is None:
        return None
    s = _strip_paren(base)
    if not s:
        return None
    return _PROVINCE_ALIASES.get(s, s)


def normalize_locality(value: object) -> str | None:
    base = normalize_place(value)
    if base is None:
        return None
    s = _strip_paren(base)
    for prefix in _LOCALITY_PREFIXES:
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    if s.endswith(" city"):
        s = s[: -len(" city")]
    first, _, rest = s.partition(" ")
    if first in _LOCALITY_ABBREV:
        s = (_LOCALITY_ABBREV[first] + " " + rest).strip() if rest else _LOCALITY_ABBREV[first]
    s = _WS.sub(" ", s).strip()
    return s or None
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `python pipeline/test/test_normalize.py`
Expected: `OK: 19 cases passed`

- [ ] **Step 7: Commit**

```bash
git add src/lib/place-aliases.json pipeline/place_norm.py pipeline/test/place-cases.json pipeline/test/test_normalize.py
git commit -m "feat: shared place-alias data + Python canonicalizers"
```

---

### Task 2: TS canonicalizers + cross-language parity script

**Files:**
- Modify: `src/lib/officials.ts` (add JSON import + two functions)
- Create: `scripts/check-place-aliases.ts`
- Modify: `package.json` (add `tsx` devDep + `test:place` script)

**Interfaces:**
- Consumes: `src/lib/place-aliases.json` (Task 1), `pipeline/test/place-cases.json` (Task 1).
- Produces (TS, from `$lib/officials`):
  - `normalizeProvince(value: string | null | undefined): string | null`
  - `normalizeLocality(value: string | null | undefined): string | null`

- [ ] **Step 1: Add the `tsx` dev dependency**

Run: `npm install -D tsx`
Expected: `tsx` added under `devDependencies` in `package.json`.

- [ ] **Step 2: Add the `test:place` npm script**

In `package.json` `"scripts"`, add:

```json
"test:place": "tsx scripts/check-place-aliases.ts && python pipeline/test/test_normalize.py"
```

- [ ] **Step 3: Write the failing parity script**

`scripts/check-place-aliases.ts`:

```ts
// Asserts the TS canonicalizers match pipeline/test/place-cases.json (the same
// fixture the Python test uses), so the Python/TS pair cannot silently drift.
// Run: npx tsx scripts/check-place-aliases.ts
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { normalizeProvince, normalizeLocality } from '../src/lib/officials.ts';

const casesPath = fileURLToPath(new URL('../pipeline/test/place-cases.json', import.meta.url));
const cases = JSON.parse(readFileSync(casesPath, 'utf-8')) as {
	province: { value: string | null; key: string | null }[];
	locality: { value: string | null; key: string | null }[];
};

const failures: string[] = [];
for (const c of cases.province) {
	const got = normalizeProvince(c.value);
	if (got !== c.key) failures.push(`province ${JSON.stringify(c.value)}: got ${JSON.stringify(got)}, want ${JSON.stringify(c.key)}`);
}
for (const c of cases.locality) {
	const got = normalizeLocality(c.value);
	if (got !== c.key) failures.push(`locality ${JSON.stringify(c.value)}: got ${JSON.stringify(got)}, want ${JSON.stringify(c.key)}`);
}

if (failures.length) {
	console.error(failures.join('\n'));
	process.exit(1);
}
console.log(`OK: ${cases.province.length + cases.locality.length} cases passed`);
```

- [ ] **Step 4: Run it to verify it fails**

Run: `npx tsx scripts/check-place-aliases.ts`
Expected: FAIL — `normalizeProvince`/`normalizeLocality` are not exported from `../src/lib/officials.ts`.

- [ ] **Step 5: Implement the TS canonicalizers**

In `src/lib/officials.ts`, add the import at the top (after the file comment):

```ts
import aliases from './place-aliases.json';

const PROVINCE_ALIASES = aliases.provinceAliases as Record<string, string>;
const LOCALITY_PREFIXES = aliases.localityPrefixes as string[];
const LOCALITY_ABBREV = aliases.localityAbbrev as Record<string, string>;

const PAREN = /\s*\([^)]*\)/g;
```

And add the two functions just below the existing `normalizePlace`:

```ts
function stripParen(s: string): string {
	return s.replace(PAREN, '').replace(/\s+/g, ' ').trim();
}

/** Province key: base → drop parentheticals → province alias. Mirror of normalize_province (Python). */
export function normalizeProvince(value: string | null | undefined): string | null {
	const base = normalizePlace(value);
	if (base == null) return null;
	const s = stripParen(base);
	if (!s) return null;
	return PROVINCE_ALIASES[s] ?? s;
}

/** Locality key: base → drop parentheticals/prefix/trailing " city" → expand abbrev. Mirror of normalize_locality (Python). */
export function normalizeLocality(value: string | null | undefined): string | null {
	const base = normalizePlace(value);
	if (base == null) return null;
	let s = stripParen(base);
	for (const prefix of LOCALITY_PREFIXES) {
		if (s.startsWith(prefix)) {
			s = s.slice(prefix.length);
			break;
		}
	}
	if (s.endsWith(' city')) s = s.slice(0, -' city'.length);
	const sp = s.indexOf(' ');
	const first = sp === -1 ? s : s.slice(0, sp);
	if (LOCALITY_ABBREV[first]) {
		s = sp === -1 ? LOCALITY_ABBREV[first] : `${LOCALITY_ABBREV[first]}${s.slice(sp)}`;
	}
	s = s.replace(/\s+/g, ' ').trim();
	return s || null;
}
```

- [ ] **Step 6: Run the parity script + the combined script to verify they pass**

Run: `npm run test:place`
Expected: `OK: 19 cases passed` from the TS script, then `OK: 19 cases passed` from Python.

- [ ] **Step 7: Run the type check**

Run: `npm run gen && npm run check`
Expected: 0 errors.

- [ ] **Step 8: Commit**

```bash
git add package.json package-lock.json src/lib/officials.ts scripts/check-place-aliases.ts
git commit -m "feat: TS place canonicalizers + cross-language parity test"
```

---

### Task 3: Wire canonicalizers into the pipeline + the area join

**Files:**
- Modify: `pipeline/officials.py` (import from `place_norm`; use new keys for term rows)
- Modify: `src/lib/server/officials.ts` (`getAreaOfficials` keys)
- Modify: `docs/ROADMAP.md`, `docs/pending.md` (mark the item done; record the recall follow-up)

**Interfaces:**
- Consumes: `place_norm.normalize_province` / `place_norm.normalize_locality` (Task 1); `normalizeProvince` / `normalizeLocality` from `$lib/officials` (Task 2).
- Produces: no new exports. `official_terms.province_key`/`locality_key` now carry canonicalized keys; `getAreaOfficials` keys lookups the same way.

- [ ] **Step 1: Refactor `pipeline/officials.py` to use `place_norm`**

Remove the local `normalize_place` definition and the `_WS = re.compile(r"\s+")` line, and replace the `import re` usage by importing the canonicalizers. At the top of `pipeline/officials.py`, after the existing imports, add:

```python
from place_norm import normalize_province, normalize_locality
```

(`pipeline/officials.py` is run as a script from `pipeline/`, so a flat `import` resolves. Delete the now-unused `normalize_place` function and the `_WS` regex; keep `import re` only if still used elsewhere — it is not, so remove it.)

- [ ] **Step 2: Use the new keys when emitting term rows**

In `pipeline/officials.py`, the `values` list inside the memberships loop currently ends with `normalize_place(province), normalize_place(locality)`. Change those two to:

```python
            normalize_province(province), normalize_locality(locality),
```

- [ ] **Step 3: Verify the pipeline module still imports**

Run: `python -c "import sys; sys.path.insert(0,'pipeline'); import officials; print('import ok')"`
Expected: `import ok` (this imports `polars`; if polars is not installed in the env, skip — the canonicalizer behavior is already covered by Task 1's polars-free test).

- [ ] **Step 4: Key the area join with the new canonicalizers**

In `src/lib/server/officials.ts`, update the import and `getAreaOfficials`. Change the import line:

```ts
import { normalizeProvince, normalizeLocality, positionRank, type OfficialTerm } from '$lib/officials';
```

Inside `getAreaOfficials`, replace:

```ts
	const pkey = normalizePlace(opts.province);
	if (!pkey) return { provinceWide: [], local: [] };
	const lkey = normalizePlace(opts.locality);
```

with:

```ts
	const pkey = normalizeProvince(opts.province);
	if (!pkey) return { provinceWide: [], local: [] };
	const lkey = normalizeLocality(opts.locality);
```

- [ ] **Step 5: Run the type check**

Run: `npm run check`
Expected: 0 errors. (If `normalizePlace` is now unused in `officials.ts` server file, the unused-import check will flag it — the edit in Step 4 already drops it from the import list.)

- [ ] **Step 6: Update the docs**

In `docs/ROADMAP.md`, change the Phase 4 line
`- [ ] Stronger place-name matching (the officials↔contracts join is exact-after-normalize today); a province/locality alias table would catch more.`
to:

```markdown
- [x] Stronger place-name matching: a shared `src/lib/place-aliases.json` drives province aliases
      (NCR/Metro Manila, Compostela Valley→Davao de Oro, parenthetical disambiguation, …) + locality
      rules ("City of X"→x, drop parentheticals, Sto./Sta./Gen. expansion) in both the pipeline
      (`pipeline/place_norm.py`) and the Worker (`normalizeProvince`/`normalizeLocality` in
      `$lib/officials`). A shared fixture (`pipeline/test/place-cases.json`) is asserted from both
      languages. **Follow-up:** the alias set is seeded from PH geography, not the (unreachable) real
      data — re-check recall against the seeded D1 on a logged-in/CI machine.
```

In `docs/pending.md`, update the "Place-name matching … an alias table would improve recall" sentence to note it is now done, with the same recall follow-up.

- [ ] **Step 7: Commit**

```bash
git add pipeline/officials.py src/lib/server/officials.ts docs/ROADMAP.md docs/pending.md
git commit -m "feat: key the contract↔official area join with place aliases"
```

---

## Self-Review

**Spec coverage:**
- Single source of truth (`place-aliases.json`, consumed by Python + TS) → Task 1 Step 1, Task 1 Step 5, Task 2 Step 5. ✓
- Two canonicalizers over a shared base, province vs locality separated → Task 1 Step 5, Task 2 Step 5. ✓
- Wiring (pipeline term rows + `getAreaOfficials`) → Task 3 Steps 2, 4. ✓
- No schema change → confirmed in Global Constraints; no task touches `db/schema.sql`. ✓
- Verification via shared fixture asserted from both languages → Task 1 (Python), Task 2 (TS via `tsx`), combined in `test:place`. ✓
- Docs/roadmap update + recall follow-up recorded → Task 3 Step 6. ✓
- The spec's "extend the synthetic officials fixture" is **intentionally replaced** by the equal-key proof: the join is `WHERE province_key = ?1` with the same function on both sides, so two variants normalizing to the same key (e.g. `Metro Manila`/`NCR` both → `ncr`, both in the fixture) proves the join now matches without standing up a local D1. Lower-infra, runnable here, same guarantee.

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows full code. ✓

**Type consistency:** `normalizeProvince`/`normalizeLocality` (TS) and `normalize_province`/`normalize_locality` (Python) used consistently across Tasks 1–3; JSON keys `provinceAliases`/`localityPrefixes`/`localityAbbrev` consistent across data file, Python loader, TS loader. ✓
