"""Threshold-splitting metric constants. Kept in one place so docs/methodology.md and
src/lib/flags.ts can quote them verbatim. Values are auditable, not opaque scores."""

from __future__ import annotations

# Legal small-value procurement ceiling, in pesos. VERIFIED against the IRR (see citation).
# RA 9184 (2016 Revised IRR, Annex H) sets Small Value Procurement at PHP 1,000,000 for national
# agencies, and that ceiling governs almost the entire data window (2013-2024). RA 12009 (the New
# Government Procurement Act) raises SVP to PHP 2,000,000, but its IRR only took effect in 2025, so
# the bulk of the awarded contracts here fall under the RA 9184 ceiling.
THRESHOLD_T = 1_000_000.0
_T_CITATION = (
    "RA 9184 2016 Revised IRR, Annex H — Small Value Procurement ceiling PHP 1,000,000 "
    "(national agencies). RA 12009 IRR (in force 2025) raises this to PHP 2,000,000."
)

# Histogram of sub-threshold contracts [0, T): fixed-width bins.
BIN_WIDTH = 25_000.0          # PH-appropriate width relative to T (40 bins below a 1M ceiling)

# Monitored band sits just below the ceiling: [BAND_ALPHA*T, T). 0.9933 mirrors contractes.cat.
BAND_ALPHA = 0.9933

# Only complete calendar years in this window feed the metric (parquet has junk years 1920/2033/2034).
MIN_YEAR = 2013
MAX_YEAR = 2025               # last fully-elapsed year; bump on the yearly refresh

# Per-contract flag for the monitored band.
BAND_FLAG = "BELOW_THRESHOLD_CLUSTER"
BAND_WEIGHT = 20


def monitored_band_low() -> float:
    """Lower edge of the monitored band, in pesos."""
    return BAND_ALPHA * THRESHOLD_T
