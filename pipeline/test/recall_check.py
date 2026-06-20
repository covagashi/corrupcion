"""Ad-hoc recall check on REAL data: how many contract provinces start matching an
official province once aliases are applied. Not part of the test suite; run manually.
"""
import pathlib
import re
import sqlite3
import sys

import polars as pl

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import place_norm  # new canonicalizers

_WS = re.compile(r"\s+")


def old_norm(v):
    if v is None:
        return None
    s = _WS.sub(" ", str(v).strip().lower())
    return s or None


# --- official side: province keys from the real memberships parquet ---
mem = pl.read_parquet(HERE.parent / "sources" / "memberships.parquet")
off_prov = [p for p in mem["province"].to_list()]
off_old = {old_norm(p) for p in off_prov} - {None}
off_new = {place_norm.normalize_province(p) for p in off_prov} - {None}

# --- contract side: distinct provinces + row counts from the seeded local D1 ---
db = next(pathlib.Path(".wrangler").rglob("*d1/miniflare-D1DatabaseObject/*.sqlite"))
con = sqlite3.connect(str(db))
rows = con.execute(
    "SELECT province, COUNT(*) FROM contracts WHERE province IS NOT NULL AND province <> '' GROUP BY province"
).fetchall()

prov_total = len(rows)
contracts_total = sum(n for _, n in rows)
gained_prov, gained_contracts, examples = 0, 0, []
matched_old_prov = matched_new_prov = 0
for province, n in rows:
    m_old = old_norm(province) in off_old
    m_new = place_norm.normalize_province(province) in off_new
    matched_old_prov += m_old
    matched_new_prov += m_new
    if m_new and not m_old:
        gained_prov += 1
        gained_contracts += n
        if len(examples) < 15:
            examples.append((province, place_norm.normalize_province(province), n))

print(f"official province values: {len(off_prov)}  old-keys={len(off_old)} new-keys={len(off_new)}")
print(f"distinct contract provinces: {prov_total}  (covering {contracts_total} contract rows)")
print(f"matched OLD: {matched_old_prov} provinces   matched NEW: {matched_new_prov} provinces")
print(f"GAINED by aliases: {gained_prov} provinces  ->  {gained_contracts} contract rows")
print("examples (contract province -> new key, #contracts):")
for p, k, n in sorted(examples, key=lambda x: -x[2]):
    print(f"  {p!r:45} -> {k!r:25} {n}")
