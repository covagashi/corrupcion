"""Parse the Raw Philippine Data persons + memberships parquet into out/officials.sql.

Source: Hugging Face `bettergovph/raw-philippine-data` (downloaded by fetch.py into sources/).
Two tables drive Phase 4 alignment:

  persons       id, first_name, last_name, name_suffix                       (~45K officials)
  memberships   id, person_id, party, region, province, locality, position, year

memberships is the breakthrough: unlike the Open Congress data, it carries a geographic key
(province / locality) + position + year. We store one `official_terms` row per membership with a
NORMALIZED province/locality key, so the Worker can match a contract's province to the officials
who held office there. `normalize_place` MUST stay identical to the TS copy in
src/lib/officials.ts, or the join silently misses.

Run AFTER fetch.py. Emits plain SQL loaded into D1 after db/schema.sql.
"""

from __future__ import annotations

import json
import pathlib
import re
from collections import defaultdict

import polars as pl

HERE = pathlib.Path(__file__).parent
PERSONS_SOURCE = HERE / "sources" / "persons.parquet"
MEMBERSHIPS_SOURCE = HERE / "sources" / "memberships.parquet"
OUT = HERE / "out" / "officials.sql"

ROWS_PER_INSERT = 50  # D1 rejects over-long statements (SQLITE_TOOBIG); keep batches small.

PERSON_COLUMNS = {"id", "first_name", "last_name", "name_suffix"}
MEMBERSHIP_COLUMNS = {"id", "person_id", "party", "region", "province", "locality", "position", "year"}

_WS = re.compile(r"\s+")


def normalize_place(value: object) -> str | None:
    """Lowercase, trim, collapse inner whitespace. Keep identical to src/lib/officials.ts."""
    if value is None:
        return None
    s = _WS.sub(" ", str(value).strip().lower())
    return s or None


def sql_str(v: object) -> str:
    if v is None or v == "":
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def full_name(first: object, last: object, suffix: object) -> str:
    return " ".join(str(p) for p in (first, last, suffix) if p).strip()


def to_int(v: object) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _assert_columns(df: pl.DataFrame, expected: set[str], name: str) -> None:
    missing = expected - set(df.columns)
    if missing:
        raise SystemExit(f"{name}.parquet missing expected columns: {sorted(missing)}")


def _write_batches(f, prefix: str, rows: list[str]) -> None:
    for i in range(0, len(rows), ROWS_PER_INSERT):
        batch = rows[i : i + ROWS_PER_INSERT]
        f.write(prefix + "\n")
        f.write(",\n".join(batch))
        f.write(";\n")


def main() -> None:
    if not PERSONS_SOURCE.exists() or not MEMBERSHIPS_SOURCE.exists():
        raise SystemExit(
            f"Missing {PERSONS_SOURCE.name} / {MEMBERSHIPS_SOURCE.name}. Run fetch.py first."
        )

    print(f"Reading {PERSONS_SOURCE.name} ...")
    persons = pl.read_parquet(PERSONS_SOURCE)
    _assert_columns(persons, PERSON_COLUMNS, "persons")
    print(f"  {persons.height} persons")

    print(f"Reading {MEMBERSHIPS_SOURCE.name} ...")
    memberships = pl.read_parquet(MEMBERSHIPS_SOURCE)
    _assert_columns(memberships, MEMBERSHIP_COLUMNS, "memberships")
    print(f"  {memberships.height} memberships")

    names: dict[str, tuple] = {}
    for p in persons.iter_rows(named=True):
        names[p["id"]] = (p.get("first_name"), p.get("last_name"), p.get("name_suffix"))

    # Aggregate per person while emitting one term row per membership.
    term_count: dict[str, int] = defaultdict(int)
    latest_year: dict[str, int] = {}
    positions: dict[str, set] = defaultdict(set)
    parties: dict[str, set] = defaultdict(set)

    term_rows: list[str] = []
    for m in memberships.iter_rows(named=True):
        pid = m["person_id"]
        first, last, suffix = names.get(pid, (None, None, None))
        name = full_name(first, last, suffix)
        year = to_int(m.get("year"))
        province = m.get("province")
        locality = m.get("locality")
        position = m.get("position")

        term_count[pid] += 1
        if year is not None and (pid not in latest_year or year > latest_year[pid]):
            latest_year[pid] = year
        if position:
            positions[pid].add(position)
        if m.get("party"):
            parties[pid].add(m["party"])

        values = [
            m["id"], pid, name or None, m.get("party"), m.get("region"), province, locality,
            position, year, normalize_place(province), normalize_place(locality),
        ]
        term_rows.append("(" + ", ".join(sql_str(v) for v in values) + ")")

    official_rows: list[str] = []
    for pid, (first, last, suffix) in names.items():
        name = full_name(first, last, suffix)
        if not name:
            continue
        values = [
            pid, name, first, last, suffix,
            term_count.get(pid, 0), latest_year.get(pid),
            json.dumps(sorted(positions[pid])) if positions[pid] else None,
            json.dumps(sorted(parties[pid])) if parties[pid] else None,
        ]
        official_rows.append("(" + ", ".join(sql_str(v) for v in values) + ")")

    print(f"  {len(official_rows)} officials, {len(term_rows)} terms")

    official_cols = (
        "id, full_name, first_name, last_name, name_suffix, term_count, latest_year, "
        "positions, parties"
    )
    term_cols = (
        "id, person_id, full_name, party, region, province, locality, position, year, "
        "province_key, locality_key"
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        f.write("-- Generated by pipeline/officials.py. Do not edit by hand.\n")
        f.write("-- Load AFTER db/schema.sql.\n")
        f.write("DELETE FROM official_terms;\n")
        f.write("DELETE FROM officials;\n")
        _write_batches(f, f"INSERT INTO officials ({official_cols}) VALUES", official_rows)
        _write_batches(f, f"INSERT INTO official_terms ({term_cols}) VALUES", term_rows)

    print(f"  -> {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print("Done.")


if __name__ == "__main__":
    main()
