# Phase 3a — PhilGEPS + Threshold-splitting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest PhilGEPS awarded contracts and implement the contractes.cat threshold-splitting metric, surfacing it as a polished mobile page plus per-contract flags.

**Architecture:** All heavy work stays offline in `pipeline/` (Python). `transform.py` scans the full 5.48M-row `philgeps.parquet` with polars, computes the threshold-splitting statistic per complete year, and emits to `out/contracts.sql` only (a) the yearly aggregate table and (b) the monitored-band contracts as `source='philgeps'` rows. The Cloudflare Worker reads the precomputed rows from D1 and renders a new `/threshold-splitting` page.

**Tech Stack:** Python 3.12 (polars, pytest), SvelteKit (Svelte 5) + TypeScript + Tailwind 4, Cloudflare D1, wrangler.

## Global Constraints

- Heavy data work happens **offline in `pipeline/`**; the Worker never fetches government APIs or computes metrics at request time. (CLAUDE.md)
- The metric must be **transparent and auditable**: simple statistics, no opaque library `.fit()`, thresholds/weights as named constants in `transform.py` that the methodology page quotes verbatim. (CLAUDE.md)
- **Do not store all 5.48M rows in D1.** Persist only the yearly aggregate + the monitored-band subset.
- Mobile-first: minimal client JS, small payloads, **no chart library**, one clear number over a graph. Plain-language English UI. (CLAUDE.md)
- Flag codes/weights must stay in sync across `pipeline/transform.py`, `src/lib/flags.ts`, and `docs/methodology.md`.
- Threshold `T` (legal small-value procurement ceiling): **verify the current peso value in RA 9184 / RA 12009 IRR before hardcoding** (Task 2).
- After any `wrangler.jsonc` edit run `npm run gen` before `npm run check`/`build`. (No wrangler.jsonc change is expected in this plan.)
- Run `npm run check` after TypeScript/Svelte changes; run `npm run format` before committing front-end edits.
- `philgeps.parquet` verified schema (2026-06-17): 12 columns —
  `id`(uuid), `reference_id`, `contract_no`, `award_title`, `notice_title`, `awardee_name`,
  `organization_name`, `area_of_delivery`, `business_category`, `contract_amount`(double),
  `award_date`(timestamp[us]), `award_status`(="active"). 5,481,161 rows.

---

### Task 1: Fetch PhilGEPS parquet + add polars dependency

**Files:**
- Modify: `pipeline/requirements.txt`
- Modify: `pipeline/fetch.py`

**Interfaces:**
- Produces: `pipeline/sources/philgeps.parquet`, `pipeline/sources/awardees.parquet`, `pipeline/sources/organizations.parquet` on disk after `python pipeline/fetch.py`.

- [ ] **Step 1: Add dependencies**

In `pipeline/requirements.txt`, append:

```
# transform.py reads the PhilGEPS parquet and computes the threshold-splitting metric.
polars>=1.0
pytest>=8.0
```

- [ ] **Step 2: Add the PhilGEPS download to fetch.py**

In `pipeline/fetch.py`, add the HF resolve URLs and download them in `main()`. Insert after the
flood-control constants:

```python
# PhilGEPS bulk parquet on Hugging Face (CC0). philgeps.parquet is the main awarded-contracts
# table (~470 MB, 5.48M rows). awardees/organizations are kept for Phase 4 (alignment), unused now.
PHILGEPS_BASE = "https://huggingface.co/datasets/bettergovph/philgeps-data/resolve/main"
PHILGEPS_FILES = ("philgeps.parquet", "awardees.parquet", "organizations.parquet")
```

Extend `main()`:

```python
    print("Fetching PhilGEPS datasets...")
    for name in PHILGEPS_FILES:
        download(f"{PHILGEPS_BASE}/{name}", SOURCES / name)
```

- [ ] **Step 3: Install deps and run the fetch**

Run: `python -m pip install -r pipeline/requirements.txt && python pipeline/fetch.py`
Expected: prints `-> .../philgeps.parquet (470.0 MB)` (approx) and the two smaller files; all three
exist under `pipeline/sources/`.

- [ ] **Step 4: Confirm sources are git-ignored**

Run: `git check-ignore pipeline/sources/philgeps.parquet`
Expected: prints the path (already ignored by `pipeline/.gitignore`). If not, add `sources/` to it.

- [ ] **Step 5: Commit**

```bash
git add pipeline/requirements.txt pipeline/fetch.py pipeline/.gitignore
git commit -m "Phase 3a: download PhilGEPS parquet + add polars/pytest deps"
```

---

### Task 2: Verify and record the legal threshold `T`

**Files:**
- Create: `pipeline/metric_config.py`

**Interfaces:**
- Produces: `THRESHOLD_T: float`, `BIN_WIDTH: float`, `BAND_ALPHA: float`, `MIN_YEAR: int`, `MAX_YEAR: int`, `BAND_FLAG: str`, `BAND_WEIGHT: int`, `MONITORED_BAND_LOW(T)` — imported by `transform.py` and the tests.

- [ ] **Step 1: Verify the current threshold**

Use a web search for the legal small-value procurement ceiling, e.g. queries:
`RA 12009 IRR small value procurement threshold amount` and
`RA 9184 GPPB small value procurement 1,000,000`.
Record the figure **and its legal citation**. RA 12009 (New Government Procurement Act, 2024) and its
2024 IRR supersede RA 9184 — prefer the RA 12009 IRR value if it is in force for the years covered by
the data; otherwise use the RA 9184 GPPB value (commonly ₱1,000,000 for Small Value Procurement) and
note the transition. Do **not** proceed with a guessed number.

- [ ] **Step 2: Write the config module with the verified value**

Create `pipeline/metric_config.py` (fill `THRESHOLD_T` and `_T_CITATION` with the verified value):

```python
"""Threshold-splitting metric constants. Kept in one place so docs/methodology.md and
src/lib/flags.ts can quote them verbatim. Values are auditable, not opaque scores."""

from __future__ import annotations

# Legal small-value procurement ceiling, in pesos. VERIFIED against the IRR (see citation).
THRESHOLD_T = 1_000_000.0
_T_CITATION = "RA 9184 GPPB Small Value Procurement ceiling (PHP 1,000,000); verify vs RA 12009 IRR"

# Histogram of sub-threshold contracts [0, T): fixed-width bins.
BIN_WIDTH = 25_000.0          # PH-appropriate width relative to T (40 bins below a 1M ceiling)

# Monitored band sits just below the ceiling: [BAND_ALPHA*T, T). 0.9933 mirrors contractes.cat.
BAND_ALPHA = 0.9933

# Only complete calendar years in this window feed the metric (parquet has junk years 1920/2033/2034).
MIN_YEAR = 2013
MAX_YEAR = 2025               # last fully-elapsed year; bump on the yearly refresh

# Per-contract flag for the monitored band.
BAND_FLAG = "BELOW_THRESHOLD_CLUSTER"
BAND_WEIGHT = 20


def monitored_band_low() -> float:
    """Lower edge of the monitored band, in pesos."""
    return BAND_ALPHA * THRESHOLD_T
```

- [ ] **Step 3: Commit**

```bash
git add pipeline/metric_config.py
git commit -m "Phase 3a: record verified threshold-splitting constants (T, band, bins)"
```

---

### Task 3: PhilGEPS row mapping + year filtering (pure functions)

**Files:**
- Create: `pipeline/philgeps.py`
- Create: `pipeline/tests/__init__.py` (empty)
- Test: `pipeline/tests/test_philgeps.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `to_epoch_ms(value) -> int | None` — converts a Python `datetime`/`date`/None to epoch ms.
  - `map_row(rec: dict) -> dict` — maps one parquet record (keys = parquet column names) to a
    `contracts`-shaped dict with keys: `id, source, project_id, description, contractor,
    procuring_entity, category, province, contract_cost, award_date, risk_flags, risk_score`.
    Sets `source='philgeps'`, `id='philgeps:'+rec['id']`, `award_date` as epoch ms.
  - `year_of(value) -> int | None` — calendar year from a datetime/date/None.
  - `EXPECTED_COLUMNS: set[str]` — the 12 parquet column names for the schema assertion.

- [ ] **Step 1: Write the failing test**

Create `pipeline/tests/test_philgeps.py`:

```python
import datetime as dt

from pipeline.philgeps import EXPECTED_COLUMNS, map_row, to_epoch_ms, year_of


def test_expected_columns_match_verified_schema():
    assert EXPECTED_COLUMNS == {
        "id", "reference_id", "contract_no", "award_title", "notice_title",
        "awardee_name", "organization_name", "area_of_delivery", "business_category",
        "contract_amount", "award_date", "award_status",
    }


def test_to_epoch_ms_utc():
    d = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    assert to_epoch_ms(d) == 1_704_067_200_000
    assert to_epoch_ms(None) is None


def test_year_of():
    assert year_of(dt.datetime(2024, 5, 9)) == 2024
    assert year_of(None) is None


def test_map_row_shapes_a_philgeps_contract():
    rec = {
        "id": "abc-123", "reference_id": "REF-9", "contract_no": "C-1",
        "award_title": "Supply of laptops", "notice_title": "Laptop notice",
        "awardee_name": "Acme Inc", "organization_name": "DepEd Region 1",
        "area_of_delivery": "Ilocos Norte", "business_category": "IT",
        "contract_amount": 994_000.0, "award_date": dt.datetime(2024, 6, 1, tzinfo=dt.timezone.utc),
        "award_status": "active",
    }
    row = map_row(rec)
    assert row["id"] == "philgeps:abc-123"
    assert row["source"] == "philgeps"
    assert row["contractor"] == "Acme Inc"
    assert row["procuring_entity"] == "DepEd Region 1"
    assert row["category"] == "IT"
    assert row["province"] == "Ilocos Norte"
    assert row["description"] == "Supply of laptops"
    assert row["contract_cost"] == 994_000.0
    assert row["award_date"] == 1_717_200_000_000
    assert row["risk_flags"] == []   # flags assigned later, in transform


def test_map_row_falls_back_to_notice_title():
    rec = {"id": "x", "award_title": None, "notice_title": "Fallback", "contract_amount": 1.0,
           "award_date": None, "awardee_name": None, "organization_name": None,
           "area_of_delivery": None, "business_category": None}
    assert map_row(rec)["description"] == "Fallback"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pipeline/tests/test_philgeps.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.philgeps'`.

- [ ] **Step 3: Write minimal implementation**

Create empty `pipeline/tests/__init__.py`. Create `pipeline/philgeps.py`:

```python
"""Pure mapping helpers for PhilGEPS parquet records -> contracts rows. No I/O, easy to test."""

from __future__ import annotations

import datetime as dt

EXPECTED_COLUMNS = {
    "id", "reference_id", "contract_no", "award_title", "notice_title",
    "awardee_name", "organization_name", "area_of_delivery", "business_category",
    "contract_amount", "award_date", "award_status",
}


def to_epoch_ms(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return int(value.timestamp() * 1000)
    if isinstance(value, dt.date):
        d = dt.datetime(value.year, value.month, value.day, tzinfo=dt.timezone.utc)
        return int(d.timestamp() * 1000)
    return None


def year_of(value: object) -> int | None:
    if isinstance(value, (dt.datetime, dt.date)):
        return value.year
    return None


def map_row(rec: dict) -> dict:
    return {
        "id": "philgeps:" + str(rec["id"]),
        "source": "philgeps",
        "project_id": rec.get("reference_id"),
        "description": rec.get("award_title") or rec.get("notice_title"),
        "contractor": rec.get("awardee_name"),
        "procuring_entity": rec.get("organization_name"),
        "category": rec.get("business_category"),
        "province": rec.get("area_of_delivery"),
        "contract_cost": rec.get("contract_amount"),
        "award_date": to_epoch_ms(rec.get("award_date")),
        "risk_flags": [],
        "risk_score": 0,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest pipeline/tests/test_philgeps.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/philgeps.py pipeline/tests/__init__.py pipeline/tests/test_philgeps.py
git commit -m "Phase 3a: PhilGEPS row mapping helpers + tests"
```

---

### Task 4: Threshold-splitting statistic (histogram + tail fit + excess)

**Files:**
- Create: `pipeline/threshold_splitting.py`
- Test: `pipeline/tests/test_threshold_splitting.py`

**Interfaces:**
- Consumes: constants from `pipeline.metric_config`.
- Produces:
  - `histogram(amounts: list[float], T: float, bin_width: float) -> list[int]` — counts in bins
    `[0, T)`; bin `i` covers `[i*bin_width, (i+1)*bin_width)`; values ≥ T excluded.
  - `fit_log_linear(counts: list[int], fit_upto_bin: int) -> tuple[float, float]` — returns `(a, b)`
    for `log(count) ≈ a + b·i`, fitted by closed-form least squares over bins `0..fit_upto_bin-1`
    with `count > 0`.
  - `expected_in_band(a: float, b: float, lo_bin: int, hi_bin: int) -> float` — sum of
    `exp(a + b·i)` over bins `lo_bin..hi_bin-1`.
  - `band_stats(amounts, T, bin_width, band_alpha) -> dict` — full statistic for one year's amounts:
    keys `observed_count, observed_value, expected_count, minor_total` (expected/excess value derived
    by caller using the band's observed mean). Returns `expected_count = None` when too few populated
    bins below the band to fit (`< 3`).

- [ ] **Step 1: Write the failing test**

Create `pipeline/tests/test_threshold_splitting.py`:

```python
import math

from pipeline.threshold_splitting import (
    band_stats, expected_in_band, fit_log_linear, histogram,
)


def test_histogram_bins_and_excludes_at_or_above_T():
    amounts = [0, 100, 24_999, 25_000, 49_999, 1_000_000, 1_500_000]
    h = histogram(amounts, T=1_000_000, bin_width=25_000)
    assert len(h) == 40
    assert h[0] == 3      # 0, 100, 24_999
    assert h[1] == 2      # 25_000, 49_999
    assert sum(h) == 5    # the two >= T are excluded


def test_fit_recovers_known_exponential():
    # counts[i] = round(1000 * exp(-0.3 i)) — a clean decaying tail
    counts = [round(1000 * math.exp(-0.3 * i)) for i in range(40)]
    a, b = fit_log_linear(counts, fit_upto_bin=39)
    assert b < 0
    assert abs(a - math.log(1000)) < 0.1
    assert abs(b - (-0.3)) < 0.05


def test_expected_in_band_sums_extrapolation():
    a, b = math.log(1000), -0.3
    exp_band = expected_in_band(a, b, lo_bin=37, hi_bin=40)
    manual = sum(math.exp(a + b * i) for i in (37, 38, 39))
    assert abs(exp_band - manual) < 1e-6


def test_band_stats_detects_injected_spike():
    # smooth decaying tail across bins, then dump a big spike into the last (monitored) bin
    amounts = []
    for i in range(39):
        amounts += [i * 25_000 + 1] * round(1000 * math.exp(-0.3 * i))
    spike = 5000
    amounts += [994_000] * spike   # 994k is inside [0.9933*1M, 1M) = [993_300, 1_000_000)
    s = band_stats(amounts, T=1_000_000, bin_width=25_000, band_alpha=0.9933)
    assert s["observed_count"] >= spike
    assert s["expected_count"] is not None
    excess = s["observed_count"] - s["expected_count"]
    assert excess > spike * 0.8     # most of the spike shows up as excess


def test_band_stats_insufficient_data_returns_none_expected():
    s = band_stats([994_500, 999_999], T=1_000_000, bin_width=25_000, band_alpha=0.9933)
    assert s["expected_count"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pipeline/tests/test_threshold_splitting.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.threshold_splitting'`.

- [ ] **Step 3: Write minimal implementation**

Create `pipeline/threshold_splitting.py`:

```python
"""The threshold-splitting statistic, written explicitly so the methodology page can describe it.

Bin sub-threshold contract amounts; fit a smooth exponential tail to the bins BELOW the monitored
band by log-linear least squares; extrapolate into the band; report observed vs expected (excess)."""

from __future__ import annotations

import math


def histogram(amounts, T: float, bin_width: float) -> list[int]:
    n_bins = int(T // bin_width)
    h = [0] * n_bins
    for v in amounts:
        if v is None or v < 0 or v >= T:
            continue
        idx = int(v // bin_width)
        if idx < n_bins:
            h[idx] += 1
    return h


def fit_log_linear(counts, fit_upto_bin: int) -> tuple[float, float]:
    """Closed-form least squares of log(count) ~ a + b*i over populated bins 0..fit_upto_bin-1."""
    xs, ys = [], []
    for i in range(min(fit_upto_bin, len(counts))):
        if counts[i] > 0:
            xs.append(float(i))
            ys.append(math.log(counts[i]))
    n = len(xs)
    if n < 2:
        raise ValueError("need >= 2 populated bins to fit")
    sx = sum(xs); sy = sum(ys)
    sxx = sum(x * x for x in xs); sxy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx
    b = (n * sxy - sx * sy) / denom
    a = (sy - b * sx) / n
    return a, b


def expected_in_band(a: float, b: float, lo_bin: int, hi_bin: int) -> float:
    return sum(math.exp(a + b * i) for i in range(lo_bin, hi_bin))


def band_stats(amounts, T: float, bin_width: float, band_alpha: float) -> dict:
    h = histogram(amounts, T, bin_width)
    n_bins = len(h)
    # Snap the monitored band to bin edges so observed count, observed value, and the expected
    # extrapolation all cover the SAME interval [lo_bin*bin_width, T).
    lo_bin = int((band_alpha * T) // bin_width)
    band_low = lo_bin * bin_width

    observed_count = sum(h[lo_bin:n_bins])
    observed_value = sum(v for v in amounts if v is not None and band_low <= v < T)
    minor_total = sum(h)

    populated_below = sum(1 for i in range(lo_bin) if h[i] > 0)
    if populated_below < 3:
        return {"observed_count": observed_count, "observed_value": observed_value,
                "expected_count": None, "minor_total": minor_total}

    a, b = fit_log_linear(h, fit_upto_bin=lo_bin)
    expected_count = expected_in_band(a, b, lo_bin, n_bins)
    return {"observed_count": observed_count, "observed_value": observed_value,
            "expected_count": expected_count, "minor_total": minor_total}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest pipeline/tests/test_threshold_splitting.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/threshold_splitting.py pipeline/tests/test_threshold_splitting.py
git commit -m "Phase 3a: threshold-splitting statistic (histogram, tail fit, excess) + tests"
```

---

### Task 5: Wire PhilGEPS into transform.py (parquet scan → SQL emit)

**Files:**
- Modify: `pipeline/transform.py`

**Interfaces:**
- Consumes: `pipeline.philgeps` (`map_row`, `year_of`, `EXPECTED_COLUMNS`),
  `pipeline.threshold_splitting.band_stats`, `pipeline.metric_config` constants.
- Produces: `out/contracts.sql` now also contains PhilGEPS band rows (in `contracts`) and a populated
  `threshold_splitting_yearly` table. Existing flood_control output is unchanged.

- [ ] **Step 1: Add the PhilGEPS step to transform.py**

After the flood-control rows are built (before `OUT.open(...)`), add a function and call it. Add at
top: `import polars as pl`, `from pipeline import philgeps as pg`, `from pipeline.threshold_splitting
import band_stats`, `from pipeline import metric_config as mc`. New function:

```python
PHILGEPS_SOURCE = HERE / "sources" / "philgeps.parquet"


def build_philgeps(contract_rows: list[str]) -> list[str]:
    """Scan philgeps.parquet, compute the yearly threshold-splitting stat over ALL rows, and
    return the threshold_splitting_yearly value tuples. Appends band contracts to contract_rows."""
    if not PHILGEPS_SOURCE.exists():
        print("  philgeps.parquet missing; skipping PhilGEPS (run fetch.py)")
        return []

    lf = pl.scan_parquet(PHILGEPS_SOURCE)
    cols = set(lf.collect_schema().names())
    assert cols == pg.EXPECTED_COLUMNS, f"PhilGEPS schema drift: {cols ^ pg.EXPECTED_COLUMNS}"

    df = (
        lf.select([
            # `id` is an Arrow uuid extension; cast to String for the 'philgeps:'+id key.
            # If polars surfaces it as Binary instead, use pl.col("id").bin.encode("hex").
            pl.col("id").cast(pl.String),
            "reference_id", "award_title", "notice_title", "awardee_name",
            "organization_name", "area_of_delivery", "business_category",
            "contract_amount", "award_date",
        ])
        .with_columns(pl.col("award_date").dt.year().alias("year"))
        .filter(pl.col("award_date").is_not_null() & pl.col("contract_amount").is_not_null())
        .filter((pl.col("year") >= mc.MIN_YEAR) & (pl.col("year") <= mc.MAX_YEAR))
        .collect(streaming=True)
    )
    print(f"  PhilGEPS: {df.height} rows in window {mc.MIN_YEAR}-{mc.MAX_YEAR}")

    band_low = mc.monitored_band_low()
    yearly_rows: list[str] = []
    band_count = 0
    for year in range(mc.MIN_YEAR, mc.MAX_YEAR + 1):
        amounts = df.filter(pl.col("year") == year)["contract_amount"].to_list()
        if not amounts:
            continue
        s = band_stats(amounts, mc.THRESHOLD_T, mc.BIN_WIDTH, mc.BAND_ALPHA)
        obs_c, obs_v = s["observed_count"], s["observed_value"]
        exp_c = s["expected_count"]
        if exp_c is None:
            exp_v = excess_c = excess_v = None
        else:
            mean_band = (obs_v / obs_c) if obs_c else 0.0
            exp_v = exp_c * mean_band
            excess_c = obs_c - exp_c
            excess_v = obs_v - exp_v
        yearly_rows.append("(" + ", ".join(sql_str(v) for v in [
            year, obs_c, round(obs_v, 2),
            round(exp_c, 2) if exp_c is not None else None,
            round(exp_v, 2) if exp_v is not None else None,
            round(excess_c, 2) if excess_c is not None else None,
            round(excess_v, 2) if excess_v is not None else None,
            s["minor_total"],
        ]) + ")")

    # Persist only the monitored-band contracts as flagged rows.
    band = df.filter((pl.col("contract_amount") >= band_low) & (pl.col("contract_amount") < mc.THRESHOLD_T))
    for rec in band.iter_rows(named=True):
        row = pg.map_row(rec)
        row["risk_flags"] = [mc.BAND_FLAG]
        row["risk_score"] = mc.BAND_WEIGHT
        contract_rows.append(philgeps_row_sql(row))
        band_count += 1
    print(f"  PhilGEPS: {band_count} monitored-band contracts persisted")
    return yearly_rows


def philgeps_row_sql(row: dict) -> str:
    """Render a mapped PhilGEPS row in the SAME column order as the contracts INSERT."""
    values = [
        row["id"], row["source"], row["project_id"], row["description"],
        None, None,  # type_of_work, infra_type
        row["contractor"],
        None, row["province"], None, None, None, row["procuring_entity"],  # region..implementing_office
        None, None,  # latitude, longitude
        None, row["contract_cost"],  # abc, contract_cost
        None, None, None, None,      # infra_year, funding_year, completion_year, start_date
        None,                        # bid_to_ceiling_ratio
        json.dumps(row["risk_flags"]), row["risk_score"],
        row["award_date"], row["category"], row["procuring_entity"],  # NEW columns (Task 6)
    ]
    return "(" + ", ".join(sql_str(v) for v in values) + ")"
```

> Note: `philgeps_row_sql` must match the **extended** `contract_cols` (Task 6 adds
> `award_date, category, procuring_entity` to the end of the column list). Flood-control rows get
> `NULL` for those three — update the flood-control `values` list in Task 6 too.

- [ ] **Step 2: Emit the new rows in main()**

In `main()`, change the contract column list to include the three new trailing columns, append
flood-control `None` placeholders for them, then after building flood rows call:

```python
    yearly_rows = build_philgeps(contract_rows)
```

and in the file-writing block add (after the two existing batched inserts):

```python
        f.write("DELETE FROM threshold_splitting_yearly;\n")
        if yearly_rows:
            ts_cols = ("year, observed_count, observed_value, expected_count, expected_value, "
                       "excess_count, excess_value, minor_total")
            _write_batches(f, f"INSERT INTO threshold_splitting_yearly ({ts_cols}) VALUES", yearly_rows)
```

Also add the three new columns to `contract_cols` (append `", award_date, category, procuring_entity"`)
and append `None, None, None` to the flood-control `values` list.

- [ ] **Step 3: Run the transform end to end**

Run: `python pipeline/transform.py`
Expected: prints flood-control flag counts, then `PhilGEPS: <N> rows in window 2013-2025`,
`PhilGEPS: <M> monitored-band contracts persisted`, and writes `pipeline/out/contracts.sql`.
Sanity: `M` is in the tens of thousands (matches the spec's band-size estimate for the chosen `T`).

- [ ] **Step 4: Re-run the unit tests (no regressions)**

Run: `python -m pytest pipeline/ -v`
Expected: PASS (all tests from Tasks 3-4).

- [ ] **Step 5: Commit**

```bash
git add pipeline/transform.py
git commit -m "Phase 3a: compute threshold-splitting over philgeps.parquet, emit band rows + yearly"
```

---

### Task 6: D1 schema — new columns + threshold_splitting_yearly

**Files:**
- Modify: `db/schema.sql`

**Interfaces:**
- Produces: `contracts` gains `award_date INTEGER`, `category TEXT`, `procuring_entity TEXT`;
  new table `threshold_splitting_yearly`.

- [ ] **Step 1: Extend the contracts table**

In `db/schema.sql`, inside `CREATE TABLE contracts (...)`, after `start_date INTEGER, -- epoch ms`
add:

```sql
  award_date                  INTEGER, -- epoch ms (PhilGEPS award date)
  category                    TEXT,    -- PhilGEPS business_category
  procuring_entity            TEXT,    -- PhilGEPS organization_name
```

- [ ] **Step 2: Add the aggregate table + index**

At the end of `db/schema.sql` add:

```sql
-- Threshold-splitting metric, precomputed per complete year (see pipeline/threshold_splitting.py).
DROP TABLE IF EXISTS threshold_splitting_yearly;
CREATE TABLE threshold_splitting_yearly (
  year           INTEGER PRIMARY KEY,
  observed_count INTEGER NOT NULL,
  observed_value REAL    NOT NULL,
  expected_count REAL,            -- NULL when too few bins to fit a tail
  expected_value REAL,
  excess_count   REAL,
  excess_value   REAL,
  minor_total    INTEGER NOT NULL
);

CREATE INDEX idx_contracts_source ON contracts (source);
```

- [ ] **Step 3: Apply to local D1 and verify**

Run:
```bash
npx wrangler d1 execute corrupcion-db --local --file=db/schema.sql --yes
npx wrangler d1 execute corrupcion-db --local --file=pipeline/out/contracts.sql --yes
npx wrangler d1 execute corrupcion-db --local --yes --command="SELECT source, COUNT(*) FROM contracts GROUP BY source;"
npx wrangler d1 execute corrupcion-db --local --yes --command="SELECT COUNT(*) FROM threshold_splitting_yearly;"
```
Expected: two source groups (`flood_control`, `philgeps`); the yearly table has one row per complete
year in range with data.

- [ ] **Step 4: Commit**

```bash
git add db/schema.sql
git commit -m "Phase 3a: D1 schema — award_date/category/procuring_entity + threshold_splitting_yearly"
```

---

### Task 7: Add the BELOW_THRESHOLD_CLUSTER flag (frontend metadata)

**Files:**
- Modify: `src/lib/flags.ts`

**Interfaces:**
- Produces: `FlagCode` includes `'BELOW_THRESHOLD_CLUSTER'`; `FLAGS` has its entry (weight 20, matches `metric_config.BAND_WEIGHT`).

- [ ] **Step 1: Extend the flag union and map**

In `src/lib/flags.ts`, add `| 'BELOW_THRESHOLD_CLUSTER'` to `FlagCode`, and add to `FLAGS`:

```ts
	BELOW_THRESHOLD_CLUSTER: {
		label: 'Priced just below the bidding threshold',
		explanation:
			'This contract’s amount sits just under the legal limit above which open competitive bidding becomes mandatory — a pattern that, across many contracts, can indicate splitting to avoid competition.',
		weight: 20,
		severity: 'medium'
	}
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: no new errors. (`parseFlags` already filters by `c in FLAGS`, so the new code flows through.)

- [ ] **Step 3: Commit**

```bash
npm run format
git add src/lib/flags.ts
git commit -m "Phase 3a: add BELOW_THRESHOLD_CLUSTER flag metadata"
```

---

### Task 8: Server access — new fields, source filter, getThresholdSplitting

**Files:**
- Modify: `src/lib/server/contracts.ts`

**Interfaces:**
- Consumes: D1 tables from Task 6.
- Produces:
  - `ContractRow` gains `award_date: number | null; category: string | null; procuring_entity: string | null;`
  - `listContracts(platform, opts)` accepts `opts.source?: 'flood_control' | 'philgeps'`.
  - `getThresholdSplitting(platform): Promise<ThresholdYear[]>` returning complete years ascending.
  - `interface ThresholdYear { year; observed_count; observed_value; expected_count; expected_value; excess_count; excess_value; minor_total; }` (numbers; nullable for expected_/excess_).

- [ ] **Step 1: Extend ContractRow and the source filter**

In `ContractRow` add the three fields. In `listContracts`, add to `opts` the `source?` field and:

```ts
	if (opts.source) {
		where.push(`source = ?${binds.length + 1}`);
		binds.push(opts.source);
	}
```

(Place this before building `whereSql`; ensure the `?N` index lines up — simplest is to push the
search bind first as today, then append source as the next positional bind.)

- [ ] **Step 2: Add the threshold-splitting reader**

Append:

```ts
export interface ThresholdYear {
	year: number;
	observed_count: number;
	observed_value: number;
	expected_count: number | null;
	expected_value: number | null;
	excess_count: number | null;
	excess_value: number | null;
	minor_total: number;
}

export async function getThresholdSplitting(
	platform: App.Platform | undefined
): Promise<ThresholdYear[]> {
	const res = await db(platform)
		.prepare('SELECT * FROM threshold_splitting_yearly ORDER BY year ASC')
		.all<ThresholdYear>();
	return res.results ?? [];
}
```

- [ ] **Step 3: Type-check**

Run: `npm run check`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
npm run format
git add src/lib/server/contracts.ts
git commit -m "Phase 3a: server — ContractRow fields, source filter, getThresholdSplitting"
```

---

### Task 9: /threshold-splitting page (mobile-first, no chart library)

**Files:**
- Create: `src/routes/threshold-splitting/+page.server.ts`
- Create: `src/routes/threshold-splitting/+page.svelte`

**Interfaces:**
- Consumes: `getThresholdSplitting` (Task 8), `formatPeso`/number helpers in `src/lib/format.ts`
  (reuse existing; if a peso formatter is absent, use `toLocaleString`).

- [ ] **Step 1: Loader**

Create `src/routes/threshold-splitting/+page.server.ts`:

```ts
import type { PageServerLoad } from './$types';
import { getThresholdSplitting } from '$lib/server/contracts';

export const load: PageServerLoad = async ({ platform }) => {
	const years = await getThresholdSplitting(platform);
	const withExcess = years.filter((y) => y.excess_count != null);
	const totalExcessCount = withExcess.reduce((s, y) => s + (y.excess_count ?? 0), 0);
	const totalExcessValue = withExcess.reduce((s, y) => s + (y.excess_value ?? 0), 0);
	return { years, totalExcessCount, totalExcessValue };
};
```

- [ ] **Step 2: Page (mobile-first; pure-CSS bars, plain language)**

Create `src/routes/threshold-splitting/+page.svelte`. Lead with one big number; render the yearly
trend as accessible pure-CSS bars (bar width = `excess_count` relative to the max), emphasizing recent
years; include the not-proof disclaimer. Match the existing pages' Tailwind style (slate palette,
`max-w` container). Reference `src/routes/methodology/+page.svelte` for tone/structure. Apply a
design-quality skill (e.g. `impeccable`/`frontend-design`) so it is polished, not generic. Example
skeleton:

```svelte
<script lang="ts">
	let { data } = $props();
	const peso = (n: number) => '₱' + Math.round(n).toLocaleString('en-PH');
	const maxExcess = Math.max(1, ...data.years.map((y) => y.excess_count ?? 0));
</script>

<svelte:head><title>Contracts priced just below the bidding threshold</title></svelte:head>

<main class="mx-auto max-w-2xl px-4 py-6">
	<h1 class="text-2xl font-bold text-slate-900">Priced to dodge open bidding</h1>
	<p class="mt-2 text-slate-600">
		Above a legal peso limit, government contracts must go through open competitive bidding. When
		many contracts cluster <em>just below</em> that limit, it can mean awards were split to stay
		under it. Here is how many more such contracts we see than a normal price spread would predict.
	</p>

	<p class="mt-6 text-4xl font-extrabold text-slate-900">
		{Math.round(data.totalExcessCount).toLocaleString('en-PH')}
		<span class="block text-base font-medium text-slate-500">
			extra contracts just below the threshold ({peso(data.totalExcessValue)} above expectation)
		</span>
	</p>

	<section class="mt-8 space-y-2">
		{#each data.years as y (y.year)}
			<div class="text-sm">
				<div class="flex justify-between"><span>{y.year}</span>
					<span class="text-slate-500">{y.excess_count == null ? '—' : Math.round(y.excess_count).toLocaleString('en-PH')}</span>
				</div>
				<div class="h-2 rounded bg-slate-100">
					<div class="h-2 rounded bg-amber-500" style="width: {((y.excess_count ?? 0) / maxExcess) * 100}%"></div>
				</div>
			</div>
		{/each}
	</section>

	<p class="mt-6 text-xs text-slate-500">
		This is an indicator of possibly reduced competition, <strong>not proof</strong> of splitting or
		wrongdoing in any individual contract.
	</p>

	<footer class="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
		Source: PhilGEPS awarded contracts (via BetterGov).
		<a href="/methodology" class="text-blue-700 underline">How we flag contracts</a>.
	</footer>
</main>
```

- [ ] **Step 3: Type-check + smoke test**

Run: `npm run check` then `npm run dev` and open `/threshold-splitting`.
Expected: page renders with the headline number, per-year bars, recent years populated, no console
errors. (Local D1 must be seeded from Task 6.)

- [ ] **Step 4: Commit**

```bash
npm run format
git add src/routes/threshold-splitting
git commit -m "Phase 3a: /threshold-splitting analysis page (mobile-first, no chart lib)"
```

---

### Task 10: Wire it into the UI — source filter + footer links

**Files:**
- Modify: `src/routes/+page.server.ts`
- Modify: `src/routes/+page.svelte`
- Modify: `src/routes/contract/[id]/+page.svelte`
- Modify: `src/routes/methodology/+page.svelte`

**Interfaces:**
- Consumes: `listContracts` `source` option (Task 8); the `/threshold-splitting` route (Task 9).

- [ ] **Step 1: Pass the source filter from the home loader**

In `src/routes/+page.server.ts`, read `const source = url.searchParams.get('source') as
'flood_control' | 'philgeps' | null;` and pass `source: source ?? undefined` into `listContracts`;
return `source` in the payload.

- [ ] **Step 2: Add the source selector to the home page**

In `src/routes/+page.svelte`, add a small `<select name="source">` (All / Flood Control / PhilGEPS)
inside the existing search `<form>` so it submits via GET like the current query box. Keep it minimal
(no client JS beyond the native form submit).

- [ ] **Step 3: Add /threshold-splitting links to the three footers**

In `src/routes/+page.svelte`, `src/routes/contract/[id]/+page.svelte`, and
`src/routes/methodology/+page.svelte` footers, add next to the methodology link:
`· <a href="/threshold-splitting" class="text-blue-700 underline">Below-threshold pricing</a>`.

- [ ] **Step 4: Type-check + smoke test**

Run: `npm run check` then `npm run dev`. Verify the home source filter narrows to PhilGEPS rows and
the footer links reach `/threshold-splitting`.

- [ ] **Step 5: Commit**

```bash
npm run format
git add src/routes
git commit -m "Phase 3a: home source filter + footer links to /threshold-splitting"
```

---

### Task 11: Documentation

**Files:**
- Modify: `docs/methodology.md`
- Modify: `docs/data-sources.md`
- Modify: `docs/ROADMAP.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: methodology.md — mark Phase 3 implemented**

Replace the "planned, not yet implemented" Phase 3 section with the implemented description: the
verified `T` and citation, `BIN_WIDTH`, `BAND_ALPHA` band, the log-linear tail fit, the
`BELOW_THRESHOLD_CLUSTER` flag (weight 20), and that the metric is computed offline over all 5.48M
PhilGEPS rows with only complete years (2013–2025) and that excess counts are observed − expected.
Keep the "indicator, not proof" framing.

- [ ] **Step 2: data-sources.md — fix PhilGEPS figures**

Correct the PhilGEPS entry: bulk repo is ~1.95 GB total; `philgeps.parquet` is ~470 MB / **5.48M
awarded rows** (not ~11 GB / ~105K). Note the 12-column schema.

- [ ] **Step 3: ROADMAP.md — check off Phase 3 items**

Check `[x]` the PhilGEPS-into-pipeline item and the threshold-splitting-metric item. Add a note that
DPWH Infrastructure and full unified search remain.

- [ ] **Step 4: CLAUDE.md — note the polars dependency**

In the pipeline description, note `transform.py` now depends on `polars` (Parquet) and that PhilGEPS
data is processed offline with only aggregates + the monitored-band subset persisted to D1.

- [ ] **Step 5: Commit**

```bash
git add docs/methodology.md docs/data-sources.md docs/ROADMAP.md CLAUDE.md
git commit -m "Phase 3a: docs — methodology, data-sources, roadmap, CLAUDE updated"
```

---

## Final verification

- [ ] `python -m pytest pipeline/ -v` — all green.
- [ ] `python pipeline/fetch.py && python pipeline/transform.py` — produces `out/contracts.sql` with
  both sources and the yearly table.
- [ ] Reseed local D1 (Task 6 commands) and `npm run check` — no type errors.
- [ ] `npm run dev`: `/` lists both sources and filters; `/threshold-splitting` shows the headline
  number + per-year bars; a PhilGEPS contract detail page shows the `BELOW_THRESHOLD_CLUSTER` flag.
- [ ] Flag weight 20 is consistent across `metric_config.py`, `flags.ts`, and `methodology.md`.
