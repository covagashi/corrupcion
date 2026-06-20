"""Parity + behavior test for the place canonicalizers. No polars needed.
Run: python pipeline/test/test_normalize.py
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # import place_norm from pipeline/

import place_norm  # noqa: E402

CASES = json.loads((HERE / "place-cases.json").read_text(encoding="utf-8"))


def run() -> None:
    failures = []
    for c in CASES["province"]:
        got = place_norm.normalize_province(c["value"])
        if got != c["key"]:
            failures.append(f"province {c['value']!r}: got {got!r}, want {c['key']!r}")
    for c in CASES["locality"]:
        got = place_norm.normalize_locality(c["value"])
        if got != c["key"]:
            failures.append(f"locality {c['value']!r}: got {got!r}, want {c['key']!r}")
    if failures:
        print("\n".join(failures))
        raise SystemExit(f"{len(failures)} case(s) failed")
    total = len(CASES["province"]) + len(CASES["locality"])
    print(f"OK: {total} cases passed")


if __name__ == "__main__":
    run()
