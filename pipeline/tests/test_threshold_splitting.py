import math

from pipeline.threshold_splitting import (
    band_stats, expected_in_band, fit_log_linear, histogram,
)


def test_histogram_bins_and_excludes_at_or_above_T():
    amounts = [0, 100, 24_999, 25_000, 49_999, 1_000_000, 1_500_000]
    h = histogram(amounts, T=1_000_000, bin_width=25_000)
    assert len(h) == 40
    assert h[0] == 3      # 0, 100, 24_999
    assert h[1] == 2      # 25_000, 49_999
    assert sum(h) == 5    # the two >= T are excluded


def test_fit_recovers_known_exponential():
    # counts[i] = round(1000 * exp(-0.3 i)) — a clean decaying tail
    counts = [round(1000 * math.exp(-0.3 * i)) for i in range(40)]
    a, b = fit_log_linear(counts, fit_upto_bin=39)
    assert b < 0
    assert abs(a - math.log(1000)) < 0.1
    assert abs(b - (-0.3)) < 0.05


def test_expected_in_band_sums_extrapolation():
    a, b = math.log(1000), -0.3
    exp_band = expected_in_band(a, b, lo_bin=37, hi_bin=40)
    manual = sum(math.exp(a + b * i) for i in (37, 38, 39))
    assert abs(exp_band - manual) < 1e-6


def test_band_stats_detects_injected_spike():
    # smooth decaying tail across bins, then dump a big spike into the last (monitored) bin
    amounts = []
    for i in range(39):
        amounts += [i * 25_000 + 1] * round(1000 * math.exp(-0.3 * i))
    spike = 5000
    amounts += [994_000] * spike   # 994k is inside [0.9933*1M, 1M) = [993_300, 1_000_000)
    s = band_stats(amounts, T=1_000_000, bin_width=25_000, band_alpha=0.9933)
    assert s["observed_count"] >= spike
    assert s["expected_count"] is not None
    excess = s["observed_count"] - s["expected_count"]
    assert excess > spike * 0.8     # most of the spike shows up as excess


def test_band_stats_insufficient_data_returns_none_expected():
    s = band_stats([994_500, 999_999], T=1_000_000, bin_width=25_000, band_alpha=0.9933)
    assert s["expected_count"] is None
