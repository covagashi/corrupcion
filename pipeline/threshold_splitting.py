"""The threshold-splitting statistic, written explicitly so the methodology page can describe it.

Bin sub-threshold contract amounts; fit a smooth exponential tail to the bins BELOW the monitored
band by log-linear least squares; extrapolate into the band; report observed vs expected (excess)."""

from __future__ import annotations

import math


def histogram(amounts, T: float, bin_width: float) -> list[int]:
    n_bins = int(T // bin_width)
    h = [0] * n_bins
    for v in amounts:
        if v is None or v < 0 or v >= T:
            continue
        idx = int(v // bin_width)
        if idx < n_bins:
            h[idx] += 1
    return h


def fit_log_linear(counts, fit_upto_bin: int) -> tuple[float, float]:
    """Closed-form least squares of log(count) ~ a + b*i over populated bins 0..fit_upto_bin-1."""
    xs, ys = [], []
    for i in range(min(fit_upto_bin, len(counts))):
        if counts[i] > 0:
            xs.append(float(i))
            ys.append(math.log(counts[i]))
    n = len(xs)
    if n < 2:
        raise ValueError("need >= 2 populated bins to fit")
    sx = sum(xs); sy = sum(ys)
    sxx = sum(x * x for x in xs); sxy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx
    b = (n * sxy - sx * sy) / denom
    a = (sy - b * sx) / n
    return a, b


def expected_in_band(a: float, b: float, lo_bin: int, hi_bin: int) -> float:
    return sum(math.exp(a + b * i) for i in range(lo_bin, hi_bin))


def band_stats(amounts, T: float, bin_width: float, band_alpha: float) -> dict:
    h = histogram(amounts, T, bin_width)
    n_bins = len(h)
    # Snap the monitored band to bin edges so observed count, observed value, and the expected
    # extrapolation all cover the SAME interval [lo_bin*bin_width, T).
    lo_bin = int((band_alpha * T) // bin_width)
    band_low = lo_bin * bin_width

    observed_count = sum(h[lo_bin:n_bins])
    observed_value = sum(v for v in amounts if v is not None and band_low <= v < T)
    minor_total = sum(h)

    populated_below = sum(1 for i in range(lo_bin) if h[i] > 0)
    if populated_below < 3:
        return {"observed_count": observed_count, "observed_value": observed_value,
                "expected_count": None, "minor_total": minor_total}

    a, b = fit_log_linear(h, fit_upto_bin=lo_bin)
    expected_count = expected_in_band(a, b, lo_bin, n_bins)
    return {"observed_count": observed_count, "observed_value": observed_value,
            "expected_count": expected_count, "minor_total": minor_total}
