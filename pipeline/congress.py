"""Parse the Open Congress data (TOML) into out/congress.sql — the legislators directory.

Source: a local checkout of https://github.com/bettergovph/open-congress-data (cloned by
fetch.py into sources/open-congress-data, or point OCD_DIR at an existing checkout). The repo
stores one TOML file per entity under data/person/ and data/congress/.

We build one `legislators` row per person: name, the chambers/congresses they served in
(derived from each person's `memberships[]`), and a senator/representative flag. The dataset has
NO geographic district for a representative, so this is a standalone directory — it deliberately
does not try to join legislators to contracts by area (that key does not exist in the data).

Pure stdlib (tomllib, 3.11+). The Worker only reads the result.
"""

from __future__ import annotations

import json
import os
import pathlib
import tomllib

HERE = pathlib.Path(__file__).parent
# Default checkout location; override with OCD_DIR for an existing clone.
OCD_DIR = pathlib.Path(os.environ.get("OCD_DIR", HERE / "sources" / "open-congress-data"))
OUT = HERE / "out" / "congress.sql"

ROWS_PER_INSERT = 50  # D1 rejects over-long statements (SQLITE_TOOBIG); keep batches small.


def sql_str(v: object) -> str:
    """Render a Python value as a SQL literal (NULL / number / quoted string)."""
    if v is None or v == "":
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def load_congress_ordinals(root: pathlib.Path) -> dict[int, str]:
    """congress_number -> ordinal (e.g. 20 -> '20th'), from data/congress/*.toml."""
    ordinals: dict[int, str] = {}
    for path in sorted((root / "data" / "congress").glob("*.toml")):
        c = tomllib.loads(path.read_text(encoding="utf-8"))
        num = c.get("congress_number")
        if num is not None:
            ordinals[int(num)] = c.get("ordinal") or f"{num}th"
    return ordinals


def build_full_name(p: dict) -> str:
    parts = [
        p.get("name_prefix"),
        p.get("first_name"),
        p.get("middle_name"),
        p.get("last_name"),
        p.get("name_suffix"),
    ]
    return " ".join(s for s in parts if s).strip()


def build_legislator_row(p: dict, ordinals: dict[int, str]) -> list[object]:
    memberships = p.get("memberships") or []
    # Dedupe (congress, subtype); a chamber membership is what tells us senator vs representative.
    seen: set[tuple[int, str]] = set()
    served: list[dict] = []
    is_senator = is_rep = False
    for m in memberships:
        if m.get("type") != "chamber":
            continue
        num = m.get("congress")
        subtype = m.get("subtype")
        if num is None or subtype not in ("senate", "house"):
            continue
        key = (int(num), subtype)
        if key in seen:
            continue
        seen.add(key)
        if subtype == "senate":
            is_senator = True
        else:
            is_rep = True
        served.append({"number": int(num), "ordinal": ordinals.get(int(num), f"{num}th"),
                       "chamber": "Senate" if subtype == "senate" else "House"})

    served.sort(key=lambda s: s["number"])
    numbers = [s["number"] for s in served]
    positions = ", ".join(
        label for flag, label in ((is_senator, "Senator"), (is_rep, "Representative")) if flag
    )

    return [
        p.get("id"),
        build_full_name(p),
        p.get("first_name"),
        p.get("last_name"),
        positions or None,
        is_senator,
        is_rep,
        json.dumps(served) if served else None,
        min(numbers) if numbers else None,
        max(numbers) if numbers else None,
        json.dumps(p["aliases"]) if p.get("aliases") else None,
    ]


def _write_batches(f, prefix: str, rows: list[str]) -> None:
    for i in range(0, len(rows), ROWS_PER_INSERT):
        batch = rows[i : i + ROWS_PER_INSERT]
        f.write(prefix + "\n")
        f.write(",\n".join(batch))
        f.write(";\n")


def main() -> None:
    person_dir = OCD_DIR / "data" / "person"
    if not person_dir.is_dir():
        raise SystemExit(
            f"open-congress-data not found at {OCD_DIR}. Clone it (fetch.py) or set OCD_DIR."
        )

    ordinals = load_congress_ordinals(OCD_DIR)
    print(f"Reading {person_dir} ...")

    cols = (
        "id, full_name, first_name, last_name, positions, is_senator, is_rep, "
        "congresses, first_congress, latest_congress, aliases"
    )
    rows: list[str] = []
    senators = reps = 0
    for path in sorted(person_dir.glob("*.toml")):
        p = tomllib.loads(path.read_text(encoding="utf-8"))
        if not p.get("id"):
            continue
        values = build_legislator_row(p, ordinals)
        if values[5]:  # is_senator
            senators += 1
        if values[6]:  # is_rep
            reps += 1
        rows.append("(" + ", ".join(sql_str(v) for v in values) + ")")

    print(f"  {len(rows)} legislators ({senators} served in the Senate, {reps} in the House)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        f.write("-- Generated by pipeline/congress.py. Do not edit by hand.\n")
        f.write("-- Load AFTER db/schema.sql.\n")
        f.write("DELETE FROM legislators;\n")
        _write_batches(f, f"INSERT INTO legislators ({cols}) VALUES", rows)

    print(f"  -> {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print("Done.")


if __name__ == "__main__":
    main()
