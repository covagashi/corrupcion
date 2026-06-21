"""Place-name canonicalizers for the contract<->official area join.

Loads the shared alias data in src/lib/place-aliases.json and exposes the
province/locality key functions. Keep behavior identical to normalizeProvince /
normalizeLocality in src/lib/officials.ts (guarded by pipeline/test/place-cases.json).
Deliberately free of polars so the test runs without the pipeline data deps.
"""
from __future__ import annotations

import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
ALIASES_PATH = HERE.parent / "src" / "lib" / "place-aliases.json"

_ALIASES = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
_PROVINCE_ALIASES: dict[str, str] = _ALIASES["provinceAliases"]
_LOCALITY_PREFIXES: list[str] = _ALIASES["localityPrefixes"]
_LOCALITY_ABBREV: dict[str, str] = _ALIASES["localityAbbrev"]

_WS = re.compile(r"\s+")
_PAREN = re.compile(r"\s*\([^)]*\)")
# DPWH puts the District Engineering Office in the province field ("Bulacan 1st DEO", "Tarlac DEO").
# Strip the trailing office suffix to recover the province. No real province name ends in "deo",
# so this never collides; officials never carry it, so it is a no-op on their side.
_DEO = re.compile(r"\s+(?:\d+(?:st|nd|rd|th)\s+)?deo$")


def normalize_place(value: object) -> str | None:
    """Base: trim, lowercase, collapse inner whitespace."""
    if value is None:
        return None
    s = _WS.sub(" ", str(value).strip().lower())
    return s or None


def _strip_paren(s: str) -> str:
    return _WS.sub(" ", _PAREN.sub("", s)).strip()


def normalize_province(value: object) -> str | None:
    base = normalize_place(value)
    if base is None:
        return None
    s = _DEO.sub("", _strip_paren(base)).strip()
    if not s:
        return None
    return _PROVINCE_ALIASES.get(s, s)


def normalize_locality(value: object) -> str | None:
    base = normalize_place(value)
    if base is None:
        return None
    s = _strip_paren(base)
    for prefix in _LOCALITY_PREFIXES:
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    if s.endswith(" city"):
        s = s[: -len(" city")]
    first, _, rest = s.partition(" ")
    if first in _LOCALITY_ABBREV:
        s = (_LOCALITY_ABBREV[first] + " " + rest).strip() if rest else _LOCALITY_ABBREV[first]
    s = _WS.sub(" ", s).strip()
    return s or None
