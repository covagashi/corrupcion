"""Download PCAB (Philippine Contractors Accreditation Board) licenses and the suspended/revoked
list, then emit out/pcab.sql for D1.

PCAB publishes two jqGrid-backed tables at https://pcabgovph.com/verify/:
  gn=Licenses          - regular licenses currently valid (~18K rows). Columns: id, CompanyName,
                         LicenseNum, AMO (Authorized Managing Officer = the firm's owner), Category
                         (AAAA..E), ValidTo, GovReg (1 = registered for gov't infra projects).
  gn=SuspendedLicenses - revoked/suspended licenses (~25 rows). Columns: id, CompanyName,
                         LicenseNum, Status, FromDate, ToDate, Reason.

The grid backend (phpGrid) requires a session cookie: a first GET to /verify/ sets it, and every
data.php call without that cookie returns a 200 carrying a PHPGRID_ERROR body. Verified 2026-06-27
with curl/httpx-PM on both pcabgovph.com and pcab.construction.gov.ph.

We compute a normalized contractor_key (uppercased alphanumerics only, spaces collapsed) on each
row, so the Worker can match contracts.contractor to a PCAB license by equality without re-running
the heavy contracts pipeline. We also extract the AMO surname (last token, particles dropped) for
the surname-overlap alignment with officials / legislators (Phase 4 alignment, the "owners" leg).

Self-contained: PCAB is paginated jqGrid JSON, not a bulk file, so it stays here rather than in
fetch.py. Run AFTER db/schema.sql. The Worker only reads the result.

Source has no license to scrape beyond the public /verify/ pages, but PCAB's stated mandate is
"license verification" published openly for the public. We rate-limit to 1 req/sec with a clear UA.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import time

import httpx

HERE = pathlib.Path(__file__).parent
# Allow `from pipeline.place_norm import ...` if invoked via `python pipeline/pcab.py`.
sys.path.insert(0, str(HERE.parent))

SOURCES = HERE / "sources"
OUT = HERE / "out" / "pcab.sql"

# PCAB portal. pcab.construction.gov.ph intermittently shows an "under maintenance" splash;
# pcabgovph.com is the canonical live host. Both share the phpGrid backend.
BASE = "https://pcabgovph.com"
DATA_PATH = "/phpGrid/data.php"
WARMUP_PATH = "/verify/"
HEADERS = {
    "User-Agent": "corrupcion.ph pipeline (anti-corruption research; contact: pcab@construction.gov.ph)",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE + WARMUP_PATH,
}

ROWS_PER_INSERT = 50
PAGE_SIZE = 100  # jqGrid rowList accepts 100; keep page count small but per-call payload reasonable.
RATE_LIMIT_SEC = 0.4

# jqGrid grids we ingest. The grid name becomes `gn=` in the data.php query. Field order is fixed
# by the colModel of each page (verified against the page source 2026-06-27); we read by position.
GRID_FIELDS = {
    "Licenses": ["id", "contractor_name", "license_no", "amo_owner", "category", "valid_to", "gov_registered"],
    "SuspendedLicenses": ["id", "contractor_name", "license_no", "status", "from_date", "to_date", "reason"],
}

_NON_ALNUM = re.compile(r"[^A-Z0-9]+")
_PARTICLES = {"de", "del", "dela", "la", "las", "lo", "los", "y", "mac", "mc", "saint", "san", "santo", "sta", "sto"}


def normalize_company_key(name: object) -> str | None:
    """Uppercased alphanumerics only, single-spaced contracting the original tokens.

    e.g. "Z.A.S. CONSTRUCTION AND SUPPLY" -> "ZAS CONSTRUCTION AND SUPPLY"
         "MUA\u00d1A CONSTRUCTION AND DEVELOPMENT CORP." -> "MUA A CONSTRUCTION AND DEVELOPMENT CORP"

    Keep spaces (we want the join to be a string-equality, not a fuzzy contains) — the spaces make
    collisions unlikely. Strip non-alphanumerics because legal entities append punctuation/parens
    inconsistently across datasets ("SB & T CONSTRUCTION OPC" vs "SB AND T...").
    """
    if name is None:
        return None
    s = _NON_ALNUM.sub(" ", str(name).upper()).strip()
    s = re.sub(r"\s+", " ", s)
    return s or None


def surname_of(amo: object) -> str | None:
    """Last name of the AMO owner string. Filipino names often: "ARTEMIO M. SANTOS" -> SANTOS.

    Drop trailing particles (de/la/y/mac/...) and trailing seniority markers (JR/SR/III). Naive but
    adequate for a surface-only overlap signal (not an accusation). Matches the Worker's surnameOf.
    """
    if amo is None:
        return None
    s = re.sub(r"[^A-Za-z \-]", "", str(amo)).strip()
    if not s:
        return None
    tokens = [t for t in s.split() if t]
    if not tokens:
        return None
    # Skip trailing generational suffixes.
    while tokens and tokens[-1].upper() in {"JR", "SR", "JR.", "II", "III", "IV"}:
        tokens.pop()
    while len(tokens) >= 2 and tokens[-2].lower() in _PARTICLES:
        tokens = tokens[:-2] + [tokens[-1]]  # keep the word after the particle as the surname
    if not tokens:
        return None
    return tokens[-1].upper() or None


def sql_str(v: object) -> str:
    if v is None or v == "":
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def _warmup(client: httpx.Client) -> None:
    """Visit /verify/ once to set the phpGrid session cookie before paging data.php."""
    print(f"  warmup GET {BASE}{WARMUP_PATH}")
    r = client.get(WARMUP_PATH, headers={"User-Agent": HEADERS["User-Agent"]})
    r.raise_for_status()


def fetch_grid(client: httpx.Client, gn: str) -> list[dict]:
    """Page through one jqGrid until exhausted. Returns a list of {field: value} dicts."""
    fields = GRID_FIELDS[gn]
    rows: list[dict] = []
    page = 1
    total = 1  # updated by the first response
    while page <= total:
        params = {
            "dt": "json", "gn": gn, "_search": "false",
            "nd": str(int(time.time() * 1000)),
            "rows": str(PAGE_SIZE), "page": str(page),
            "sidx": "1", "sord": "asc",
        }
        r = client.get(DATA_PATH, params=params, headers=HEADERS)
        r.raise_for_status()
        body = r.text
        if body.lstrip().startswith("PHPGRID_ERROR"):
            raise RuntimeError(
                f"{gn}: phpGrid returned {body.splitlines()[0]!r}. The /verify/ warmup cookie was "
                "not accepted — retry, or upstream phpGrid is broken (it sits behind a CF challenge "
                "intermittently on pcab.construction.gov.ph; use pcabgovph.com)."
            )
        data = r.json()
        total = int(data.get("total", 0)) or 1
        records = int(data.get("records", 0))
        grid_rows = data.get("rows", [])
        for gr in grid_rows:
            cells = gr.get("cell", [])
            rows.append({fields[i]: cells[i] for i in range(min(len(fields), len(cells)))})
        print(f"  {gn}: page {page}/{total} ({records} records total)")
        page += 1
        if page <= total:
            time.sleep(RATE_LIMIT_SEC)
    return rows


def main() -> None:
    SOURCES.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    with httpx.Client(base_url=BASE, timeout=60, follow_redirects=True) as client:
        _warmup(client)
        print("Fetching PCAB Regular Licenses...")
        licenses = fetch_grid(client, "Licenses")
        print("Fetching PCAB Suspended / Revoked Licenses...")
        suspended = fetch_grid(client, "SuspendedLicenses")

    # Cache the raw jqGrid responses so re-runs of transform/test can run without hitting PCAB.
    (SOURCES / "pcab_licenses_raw.json").write_text(
        json.dumps(licenses, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (SOURCES / "pcab_suspended_raw.json").write_text(
        json.dumps(suspended, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  cached {len(licenses)} licenses + {len(suspended)} suspended rows")

    # Build SQL. Include the normalized contractor_key and owner surname so the Worker can match
    # without recomputing them on every request.
    license_rows: list[str] = []
    for r in licenses:
        key = normalize_company_key(r.get("contractor_name"))
        owner = r.get("amo_owner")
        surname = surname_of(owner)
        gov = r.get("gov_registered")
        gov_int = None
        if gov in ("0", "1"):
            gov_int = int(gov)
        values = [
            r.get("id"), r.get("license_no"), r.get("contractor_name"), key,
            owner, surname,
            r.get("category"), r.get("valid_to"), gov_int,
        ]
        license_rows.append("(" + ", ".join(sql_str(v) for v in values) + ")")

    suspended_rows: list[str] = []
    for r in suspended:
        key = normalize_company_key(r.get("contractor_name"))
        values = [
            r.get("id"), r.get("contractor_name"), key,
            r.get("license_no"), r.get("status"),
            r.get("from_date"), r.get("to_date"), r.get("reason"),
        ]
        suspended_rows.append("(" + ", ".join(sql_str(v) for v in values) + ")")

    license_cols = (
        "id, license_no, contractor_name, contractor_key, amo_owner, owner_surname, "
        "category, valid_to, gov_registered"
    )
    suspended_cols = (
        "id, contractor_name, contractor_key, license_no, status, valid_from, valid_to, reason"
    )

    with OUT.open("w", encoding="utf-8") as f:
        f.write("-- Generated by pipeline/pcab.py. Do not edit by hand.\n")
        f.write("-- Load AFTER db/schema.sql.\n")
        f.write("DELETE FROM pcab_suspended;\n")
        f.write("DELETE FROM pcab_licenses;\n")
        for i in range(0, len(license_rows), ROWS_PER_INSERT):
            batch = license_rows[i : i + ROWS_PER_INSERT]
            f.write(f"INSERT INTO pcab_licenses ({license_cols}) VALUES\n")
            f.write(",\n".join(batch))
            f.write(";\n")
        for i in range(0, len(suspended_rows), ROWS_PER_INSERT):
            batch = suspended_rows[i : i + ROWS_PER_INSERT]
            f.write(f"INSERT INTO pcab_suspended ({suspended_cols}) VALUES\n")
            f.write(",\n".join(batch))
            f.write(";\n")

    print(f"  -> {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print(f"  total: {len(license_rows)} licenses, {len(suspended_rows)} suspended/revoked")
    print("Done.")


if __name__ == "__main__":
    main()