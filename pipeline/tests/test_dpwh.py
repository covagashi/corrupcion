import datetime as dt

from pipeline.dpwh import EXPECTED_COLUMNS, dpwh_flags, map_row, parse_year


def test_expected_columns_match_verified_schema():
    # 23 top-level columns; `location` is a struct, unnested to province/region in transform.
    assert EXPECTED_COLUMNS == {
        "contractId", "description", "category", "componentCategories", "status",
        "budget", "amountPaid", "progress", "location", "contractor",
        "startDate", "completionDate", "infraYear", "programName", "sourceOfFunds",
        "isLive", "livestreamUrl", "livestreamVideoId", "livestreamDetectedAt",
        "latitude", "longitude", "reportCount", "hasSatelliteImage",
    }
    assert len(EXPECTED_COLUMNS) == 23


def test_parse_year():
    assert parse_year("2023") == 2023
    assert parse_year(2024) == 2024
    assert parse_year(None) is None
    assert parse_year("n/a") is None


def test_dpwh_flags_over_budget():
    assert dpwh_flags(5_000_000.0, 5_200_000) == (["OVER_BUDGET"], 40)
    assert dpwh_flags(5_000_000.0, 4_000_000) == ([], 0)
    assert dpwh_flags(None, 4_000_000) == ([], 0)
    assert dpwh_flags(5_000_000.0, None) == ([], 0)


def test_map_row_shapes_a_dpwh_contract():
    rec = {
        "contractId": "C-1", "description": "Road repair", "category": "Roads",
        "contractor": "Acme Builders", "province": "Cebu", "region": "Region VII",
        "budget": 5_000_000.0, "amountPaid": 5_200_000,
        "startDate": dt.date(2023, 2, 15), "completionDate": dt.date(2024, 1, 10),
        "infraYear": "2023", "latitude": 10.3, "longitude": 123.9,
    }
    row = map_row(rec)
    assert row["id"] == "dpwh:C-1"
    assert row["source"] == "dpwh"
    assert row["abc"] == 5_000_000.0
    assert row["contract_cost"] == 5_200_000
    assert row["bid_to_ceiling_ratio"] == 1.04
    assert row["province"] == "Cebu"
    assert row["region"] == "Region VII"
    assert row["infra_year"] == 2023
    assert row["completion_year"] == 2024
    assert row["start_date"] == 1_676_419_200_000  # 2023-02-15 UTC
    assert row["risk_flags"] == ["OVER_BUDGET"]
    assert row["risk_score"] == 40
