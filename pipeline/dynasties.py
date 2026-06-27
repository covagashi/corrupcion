"""Parse the Ateneo Policy Center Philippine Political Dynasties Dataset (2022 Update) xlsx into
out/dynasties.sql for D1.

Source xlsx (local): docs/Ateneo Policy Center Philippine Political Dynasties Dataset (2022
Update).xlsx — published by the Ateneo Policy Center and mirrored locally because the live copy on
`data.bettergov.ph` returns 403 from the web sandbox. This pipeline reads the file from disk; if the
xlsx moves, point `ATENEO_XLSX` at the new path.

The dataset is two sheets:

  - 'Data - Politicians' (207,599 rows): one row per (politician, position, year) showing whether
    that politician is/was a member of a "fat" political dynasty. Columns: first_name, last_name,
    party, region, province, municipality, position, year, PSGC_Province, fat_dynasty_indicator.
    `fat` = 52,932 rows; `non-fat` = 154,667. Years span 1987-2022.
  - 'Data - Province' (81 rows): each province's fat-dynasty share per election year
    (1992..2022, every 3 years). Used for the contract-area "Dynasty context" panel.

We persist both:

  - `dynasty_politicians` (one row per source row, with normalized province/locality keys + surname
    for the eventual per-official surname cross-reference). 207K rows is small enough to keep.
  - `dynasty_shares` (long form: province_key + election year -> fat dynasty share %, 81x11 = ~891
    rows after dropping nulls). This is the table the contract detail page reads.

Run AFTER db/schema.sql. The Worker only reads the result. Pure pandas + place_norm (pandas +
openpyxl are in requirements.txt).
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).parent
# Allow `from pipeline.place_norm import ...` when run as `python pipeline/dynasties.py`.
sys.path.insert(0, str(HERE.parent))

from place_norm import normalize_locality, normalize_province  # noqa: E402

ATENEO_XLSX = HERE.parent / "docs" / "Ateneo Policy Center Philippine Political Dynasties Dataset (2022 Update).xlsx"
OUT = HERE / "out" / "dynasties.sql"

ROWS_PER_INSERT = 50

ELECTION_YEARS = [1992, 1995, 1998, 2001, 2004, 2007, 2010, 2013, 2016, 2019, 2022]


def sql_str(v: object) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int,)):
        return repr(int(v))
    if isinstance(v, float):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def _to_str(v: object) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    return s or None


def _to_int(v: object) -> int | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _to_float(v: object) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        f = float(v)
        return f if not pd.isna(f) else None
    except (TypeError, ValueError):
        return None


def _sur(last: object) -> str | None:
    s = _to_str(last)
    return s.upper() if s else None


def _write_batches(f, prefix: str, rows: list[str]) -> None:
    for i in range(0, len(rows), ROWS_PER_INSERT):
        batch = rows[i : i + ROWS_PER_INSERT]
        f.write(prefix + "\n")
        f.write(",\n".join(batch))
        f.write(";\n")


def main() -> None:
    if not ATENEO_XLSX.exists():
        raise SystemExit(
            f"Ateneo xlsx not found at {ATENEO_XLSX}. The 2022 Update xlsx should sit under docs/."
        )

    print(f"Reading {ATENEO_XLSX.name} / Data - Politicians ...")
    polit = pd.read_excel(ATENEO_XLSX, sheet_name="Data - Politicians")
    expected = {
        "first_name", "last_name", "party", "region", "province", "municipality",
        "position", "year", "PSGC_Province", "fat_dynasty_indicator",
    }
    missing = expected - set(polit.columns)
    if missing:
        raise SystemExit(f"Politicians sheet missing columns: {sorted(missing)}")

    print(f"  {len(polit)} politician rows ({(polit['fat_dynasty_indicator']=='fat').sum()} fat dynasties)")

    print(f"Reading {ATENEO_XLSX.name} / Data - Province ...")
    prov = pd.read_excel(ATENEO_XLSX, sheet_name="Data - Province")
    print(f"  {len(prov)} provinces x {len(ELECTION_YEARS)} election years")

    # Build politician rows with normalized keys + surname (for the future surname join).
    poll_rows: list[str] = []
    for _, r in polit.iterrows():
        province = _to_str(r.get("province"))
        municipality = _to_str(r.get("municipality"))
        pkey = normalize_province(province)
        lkey = normalize_locality(municipality)
        surname = _sur(r.get("last_name"))
        is_fat = 1 if r.get("fat_dynasty_indicator") == "fat" else 0
        values = [
            surname,
            _to_str(r.get("first_name")),
            _to_str(r.get("last_name")),
            _to_str(r.get("party")),
            _to_str(r.get("region")),
            province,
            pkey,
            municipality,
            lkey,
            _to_str(r.get("position")),
            _to_int(r.get("year")),
            _to_str(r.get("PSGC_Province")),
            is_fat,
        ]
        poll_rows.append("(" + ", ".join(sql_str(v) for v in values) + ")")

    # Province shares -> long form: (province_key, year, share) per non-null cell.
    share_rows: list[str] = []
    for _, r in prov.iterrows():
        province = _to_str(r.get("province"))
        if not province:
            continue
        pkey = normalize_province(province)
        if not pkey:
            continue
        for y in ELECTION_YEARS:
            col = f"fatdynshare{y}"
            if col not in prov.columns:
                continue
            share = _to_float(r.get(col))
            if share is None:
                continue
            share_rows.append(
                "(" + ", ".join(sql_str(v) for v in [pkey, province, y, round(share, 4)]) + ")"
            )

    print(f"  {len(poll_rows)} politician SQL rows, {len(share_rows)} province-year share rows")

    poll_cols = (
        "surname, first_name, last_name, party, region, province, province_key, municipality, "
        "locality_key, position, year, psgc_province, is_fat"
    )
    share_cols = "province_key, province, year, share"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        f.write("-- Generated by pipeline/dynasties.py. Do not edit by hand.\n")
        f.write("-- Load AFTER db/schema.sql.\n")
        f.write("DELETE FROM dynasty_politicians;\n")
        f.write("DELETE FROM dynasty_shares;\n")
        _write_batches(f, f"INSERT INTO dynasty_politicians ({poll_cols}) VALUES", poll_rows)
        _write_batches(f, f"INSERT INTO dynasty_shares ({share_cols}) VALUES", share_rows)

    print(f"  -> {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print("Done.")


if __name__ == "__main__":
    main()