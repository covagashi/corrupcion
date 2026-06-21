"""Split a large .sql dump into ~5MB chunks at statement boundaries.

`wrangler d1 execute --remote --file` switches to the (R2-upload) import API for large files,
which can hang or 500 on a flaky upload. Smaller chunks stay on the direct batched-API path, which
is reliable. We only ever cut AFTER a line ending in ';' so no statement is split across chunks.
The leading DELETEs live in chunk 0, so re-running the full set stays idempotent.

Usage:
    python pipeline/split_sql.py [SRC.sql] [DST_DIR]

Defaults to out/contracts.sql -> out/chunks (backwards compatible). Seed the chunks with, e.g.:
    for f in pipeline/out/chunks/chunk_*.sql; do
      npx wrangler d1 execute corrupcion-db --remote --file="$f" --yes; done
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).parent
TARGET_BYTES = 5_000_000


def split(src: pathlib.Path, dst: pathlib.Path) -> int:
    dst.mkdir(parents=True, exist_ok=True)
    for old in dst.glob("chunk_*.sql"):
        old.unlink()

    idx = 0
    size = 0
    buf: list[str] = []

    def flush() -> None:
        nonlocal idx, size, buf
        if not buf:
            return
        (dst / f"chunk_{idx:03d}.sql").write_text("".join(buf), encoding="utf-8")
        idx += 1
        size = 0
        buf = []

    with src.open("r", encoding="utf-8") as f:
        for line in f:
            buf.append(line)
            size += len(line.encode("utf-8"))
            # Cut only at a statement end, once we've passed the target size.
            if size >= TARGET_BYTES and line.rstrip().endswith(";"):
                flush()
    flush()
    return idx


def main() -> None:
    src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out" / "contracts.sql"
    dst = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "out" / "chunks"
    n = split(src, dst)
    print(f"wrote {n} chunks to {dst}")


if __name__ == "__main__":
    main()
