"""Regression test: PhilGEPS `id` is a UUID FIXED_LEN_BYTE_ARRAY(16). polars reads it as Binary,
so transform.py hex-encodes it (cast to String raises "invalid utf8"). Lock that behavior."""

import uuid

import polars as pl

from pipeline.philgeps import map_row


def test_uuid_binary_hex_encodes_to_stable_key():
    u = uuid.UUID("7f500222-fc65-45a7-83b0-4f498965a5c3")
    df = pl.DataFrame({"id": [u.bytes]}, schema={"id": pl.Binary})

    # cast(String) is what the old code did — it must NOT be relied on (raises on real bytes).
    # The expression transform.py actually uses:
    hexed = df.select(pl.col("id").bin.encode("hex"))["id"].to_list()
    assert hexed == ["7f500222fc6545a783b04f498965a5c3"]

    # And the mapped contract id is the prefixed hex string.
    assert map_row({"id": hexed[0], "contract_amount": 1.0})["id"] == (
        "philgeps:7f500222fc6545a783b04f498965a5c3"
    )
