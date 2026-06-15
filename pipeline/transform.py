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
from collections import defaultdict

HERE = pathlib.Path(__file__).parent
SOURCE = HERE / "sources" / "flood_control.json"
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
        "completion_year, start_date, bid_to_ceiling_ratio, risk_flags, risk_score"
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
