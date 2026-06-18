"""Split out/contracts.sql into ~5MB chunks at statement boundaries.

`wrangler d1 execute --remote --file` switches to the (R2-upload) import API for large files,
which can hang on a flaky upload. Smaller chunks stay on the direct batched-API path, which is
reliable. We only ever cut AFTER a line ending in ';' so no statement is split across chunks.
The leading DELETEs live in chunk 0, so re-running the full set stays idempotent.
"""

from __future__ import annotations

import pathlib

HERE = pathlib.Path(__file__).parent
SRC = HERE / "out" / "contracts.sql"
DST = HERE / "out" / "chunks"
TARGET_BYTES = 5_000_000

DST.mkdir(parents=True, exist_ok=True)
for old in DST.glob("chunk_*.sql"):
    old.unlink()

idx = 0
size = 0
buf: list[str] = []


def flush() -> None:
    global idx, size, buf
    if not buf:
        return
    (DST / f"chunk_{idx:03d}.sql").write_text("".join(buf), encoding="utf-8")
    idx += 1
    size = 0
    buf = []


with SRC.open("r", encoding="utf-8") as f:
    for line in f:
        buf.append(line)
        size += len(line.encode("utf-8"))
        # Cut only at a statement end, once we've passed the target size.
        if size >= TARGET_BYTES and line.rstrip().endswith(";"):
            flush()
flush()

print(f"wrote {idx} chunks to {DST}")
