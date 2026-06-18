"""Parse the raw Flood Control JSON, compute the irregularity metric, write out/contracts.sql.

Pure stdlib (no deps): reads sources/flood_control.json (ArcGIS feature format) and emits a
plain-SQL dump that `wrangler d1 execute --file=` loads into D1. The Worker only reads the result.

The metric is intentionally simple and auditable (see docs/methodology in the roadmap):

  bid-to-ceiling ratio = ContractCost / ABC
    OVER_CEILING   ratio > 1.0       awarded ABOVE the approved budget ceiling      (+40)
    EXACT_CEILING  ratio >= 0.9999   winning bid matched the secret ceiling exactly (+15)
    NEAR_CEILING   0.99 <= ratio     winning bid sat right at the ceiling (context) (+5)
  supplier concentration (per legislative district)
    DISTRICT_DOMINANCE  one contractor holds >= 50% of a district's contract value
                        across >= 3 contracts                                      (+30)

risk_score is the clamped (0-100) sum of the weights of the flags that fired. Flagging plain
">= 0.99" alone is useless here: 73% of this dataset sits at the ceiling, so that pattern is the
norm, not the signal. The discriminating flags are OVER_CEILING and DISTRICT_DOMINANCE.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
from collections import defaultdict

# Allow `from pipeline import ...` whether this runs as `python pipeline/transform.py` (the script
# dir lands on sys.path) or `python -m pipeline.transform` (repo root on sys.path).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import polars as pl  # noqa: E402

from pipeline import metric_config as mc  # noqa: E402
from pipeline import philgeps as pg  # noqa: E402
from pipeline import dpwh as dpwh_mod  # noqa: E402
from pipeline.threshold_splitting import band_stats  # noqa: E402

HERE = pathlib.Path(__file__).parent
SOURCE = HERE / "sources" / "flood_control.json"
PHILGEPS_SOURCE = HERE / "sources" / "philgeps.parquet"
DPWH_SOURCE = HERE / "sources" / "dpwh_transparency_data.parquet"
OUT = HERE / "out" / "contracts.sql"

# Metric thresholds / weights (kept here so the methodology page can quote them verbatim).
OVER_CEILING_RATIO = 1.0
EXACT_CEILING_RATIO = 0.9999
NEAR_CEILING_RATIO = 0.99
DOMINANCE_SHARE = 0.50
DOMINANCE_MIN_CONTRACTS = 3

WEIGHTS = {
    "OVER_CEILING": 40,
    "EXACT_CEILING": 15,
    "NEAR_CEILING": 5,
    "DISTRICT_DOMINANCE": 30,
}

SOURCE_TAG = "flood_control"
ROWS_PER_INSERT = 50  # D1 rejects over-long statements (SQLITE_TOOBIG); keep batches small.


def sql_str(v: object) -> str:
    """Render a Python value as a SQL literal (NULL / number / quoted string)."""
    if v is None or v == "":
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def parse_start_date(raw: object) -> int | None:
    """StartDate looks like '02/15/2024' (MM/DD/YYYY). Return epoch ms or None."""
    if not raw or not isinstance(raw, str):
        return None
    try:
        d = dt.datetime.strptime(raw.strip(), "%m/%d/%Y").replace(tzinfo=dt.timezone.utc)
        return int(d.timestamp() * 1000)
    except ValueError:
        return None


def to_int(v: object) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def compute_flags(ratio: float | None, is_dominant: bool) -> tuple[list[str], int]:
    flags: list[str] = []
    if ratio is not None:
        if ratio > OVER_CEILING_RATIO:
            flags.append("OVER_CEILING")
        elif ratio >= EXACT_CEILING_RATIO:
            flags.append("EXACT_CEILING")
        elif ratio >= NEAR_CEILING_RATIO:
            flags.append("NEAR_CEILING")
    if is_dominant:
        flags.append("DISTRICT_DOMINANCE")
    score = min(100, sum(WEIGHTS[f] for f in flags))
    return flags, score


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
            # `id` is a UUID FIXED_LEN_BYTE_ARRAY(16); polars surfaces it as Binary (16 raw bytes)
            # and cast(String) raises "invalid utf8". Hex-encode to a stable 32-char key string
            # (verified against a duckdb-written UUID parquet, the same writer as the source).
            pl.col("id").bin.encode("hex"),
            "reference_id", "award_title", "notice_title", "awardee_name",
            "organization_name", "area_of_delivery", "business_category",
            "contract_amount", "award_date",
        ])
        .with_columns(pl.col("award_date").dt.year().alias("year"))
        .filter(pl.col("award_date").is_not_null() & pl.col("contract_amount").is_not_null())
        .filter((pl.col("year") >= mc.MIN_YEAR) & (pl.col("year") <= mc.MAX_YEAR))
        .collect(engine="streaming")
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
    band = df.filter(
        (pl.col("contract_amount") >= band_low) & (pl.col("contract_amount") < mc.THRESHOLD_T)
    )
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
        row["award_date"], row["category"], row["procuring_entity"],  # NEW columns
    ]
    return "(" + ", ".join(sql_str(v) for v in values) + ")"


def build_dpwh(contract_rows: list[str]) -> None:
    """Scan dpwh_transparency_data.parquet, map projects to source='dpwh' rows, flag OVER_BUDGET,
    and append them to contract_rows. Large infra contracts — no threshold-splitting applies."""
    if not DPWH_SOURCE.exists():
        print("  dpwh parquet missing; skipping DPWH (run fetch.py)")
        return

    lf = pl.scan_parquet(DPWH_SOURCE)
    cols = set(lf.collect_schema().names())
    assert cols == dpwh_mod.EXPECTED_COLUMNS, f"DPWH schema drift: {cols ^ dpwh_mod.EXPECTED_COLUMNS}"

    df = (
        lf.select([
            "contractId", "description", "category", "contractor",
            # `location` is a struct{province, region}; flatten it for the mapper.
            pl.col("location").struct.field("province").alias("province"),
            pl.col("location").struct.field("region").alias("region"),
            "budget", "amountPaid", "startDate", "completionDate", "infraYear",
            "latitude", "longitude",
        ])
        .collect(engine="streaming")
    )
    print(f"  DPWH: {df.height} projects")

    flagged = 0
    for rec in df.iter_rows(named=True):
        row = dpwh_mod.map_row(rec)
        if row["risk_score"] > 0:
            flagged += 1
        contract_rows.append(dpwh_row_sql(row))
    print(f"  DPWH: {flagged} flagged (paid above approved budget)")


def dpwh_row_sql(row: dict) -> str:
    """Render a mapped DPWH row in the SAME column order as the contracts INSERT."""
    values = [
        row["id"], row["source"], row["project_id"], row["description"],
        None, None,  # type_of_work, infra_type
        row["contractor"],
        row["region"], row["province"], None, None, None, None,  # region..implementing_office
        row["latitude"], row["longitude"],
        row["abc"], row["contract_cost"],
        row["infra_year"], None, row["completion_year"], row["start_date"],  # infra/funding/completion/start
        row["bid_to_ceiling_ratio"],
        json.dumps(row["risk_flags"]), row["risk_score"],
        None, row["category"], None,  # award_date, category, procuring_entity
    ]
    return "(" + ", ".join(sql_str(v) for v in values) + ")"


def main() -> None:
    print(f"Reading {SOURCE} ...")
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    features = [f["attributes"] for f in data["features"]]
    print(f"  {len(features)} records")

    # Pass 1: aggregate contractor value per legislative district -> dominance set.
    district_total: dict[str, float] = defaultdict(float)
    pair_count: dict[tuple[str, str], int] = defaultdict(int)
    pair_value: dict[tuple[str, str], float] = defaultdict(float)
    for a in features:
        district = a.get("LegislativeDistrict")
        contractor = a.get("Contractor")
        value = a.get("ContractCost") or 0.0
        if not district or not contractor:
            continue
        district_total[district] += value
        pair_count[(contractor, district)] += 1
        pair_value[(contractor, district)] += value

    pair_share: dict[tuple[str, str], float] = {}
    dominant_pairs: set[tuple[str, str]] = set()
    for pair, value in pair_value.items():
        total = district_total[pair[1]]
        share = value / total if total else 0.0
        pair_share[pair] = share
        if share >= DOMINANCE_SHARE and pair_count[pair] >= DOMINANCE_MIN_CONTRACTS:
            dominant_pairs.add(pair)
    print(f"  {len(dominant_pairs)} dominant contractor/district pairs")

    # Pass 2: build contract rows.
    contract_cols = (
        "id, source, project_id, description, type_of_work, infra_type, contractor, "
        "region, province, municipality, legislative_district, district_engineering_office, "
        "implementing_office, latitude, longitude, abc, contract_cost, infra_year, funding_year, "
        "completion_year, start_date, bid_to_ceiling_ratio, risk_flags, risk_score, "
        "award_date, category, procuring_entity"
    )
    contract_rows: list[str] = []
    flag_tally: dict[str, int] = defaultdict(int)
    for a in features:
        abc = a.get("ABC")
        cost = a.get("ContractCost")
        ratio = (cost / abc) if (abc and cost is not None) else None
        contractor = a.get("Contractor")
        district = a.get("LegislativeDistrict")
        is_dominant = bool(contractor and district and (contractor, district) in dominant_pairs)
        flags, score = compute_flags(ratio, is_dominant)
        for f in flags:
            flag_tally[f] += 1

        values = [
            a.get("GlobalID"),            # id (the only fully-unique key)
            SOURCE_TAG,
            a.get("ProjectID"),
            a.get("ProjectDescription"),
            a.get("TypeofWork"),
            a.get("infra_type"),
            contractor,
            a.get("Region"),
            a.get("Province"),
            a.get("Municipality"),
            district,
            a.get("DistrictEngineeringOffice"),
            a.get("ImplementingOffice"),
            a.get("Latitude"),
            a.get("Longitude"),
            abc,
            cost,
            to_int(a.get("InfraYear")),
            to_int(a.get("FundingYear")),
            to_int(a.get("CompletionYear")),
            parse_start_date(a.get("StartDate")),
            round(ratio, 6) if ratio is not None else None,
            json.dumps(flags),
            score,
            None, None, None,  # award_date, category, procuring_entity (PhilGEPS-only columns)
        ]
        contract_rows.append("(" + ", ".join(sql_str(v) for v in values) + ")")

    # Pass 3: contractor_district_stats rows.
    stats_cols = (
        "contractor, legislative_district, contract_count, total_value, district_value_share"
    )
    stats_rows: list[str] = []
    for pair, count in pair_count.items():
        contractor, district = pair
        row = [contractor, district, count, round(pair_value[pair], 2), round(pair_share[pair], 6)]
        stats_rows.append("(" + ", ".join(sql_str(v) for v in row) + ")")

    # Pass 4: PhilGEPS — yearly threshold-splitting stat + monitored-band contracts.
    print("Processing PhilGEPS ...")
    yearly_rows = build_philgeps(contract_rows)

    # Pass 5: DPWH infrastructure projects (source='dpwh', OVER_BUDGET flag).
    print("Processing DPWH ...")
    build_dpwh(contract_rows)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        f.write("-- Generated by pipeline/transform.py. Do not edit by hand.\n")
        f.write("-- Load AFTER db/schema.sql.\n")
        f.write("DELETE FROM contracts;\n")
        f.write("DELETE FROM contractor_district_stats;\n")
        _write_batches(f, f"INSERT INTO contracts ({contract_cols}) VALUES", contract_rows)
        _write_batches(
            f, f"INSERT INTO contractor_district_stats ({stats_cols}) VALUES", stats_rows
        )
        f.write("DELETE FROM threshold_splitting_yearly;\n")
        if yearly_rows:
            ts_cols = ("year, observed_count, observed_value, expected_count, expected_value, "
                       "excess_count, excess_value, minor_total")
            _write_batches(f, f"INSERT INTO threshold_splitting_yearly ({ts_cols}) VALUES", yearly_rows)

    size_kb = OUT.stat().st_size / 1024
    print(f"  -> {OUT} ({size_kb:.0f} KB)")
    print("Flag counts:")
    for flag in WEIGHTS:
        print(f"  {flag:<20} {flag_tally[flag]:>5}")
    print("Done.")


def _write_batches(f, prefix: str, rows: list[str]) -> None:
    for i in range(0, len(rows), ROWS_PER_INSERT):
        batch = rows[i : i + ROWS_PER_INSERT]
        f.write(prefix + "\n")
        f.write(",\n".join(batch))
        f.write(";\n")


if __name__ == "__main__":
    main()
