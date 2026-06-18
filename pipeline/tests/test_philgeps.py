import datetime as dt

from pipeline.philgeps import EXPECTED_COLUMNS, map_row, to_epoch_ms, year_of


def test_expected_columns_match_verified_schema():
    assert EXPECTED_COLUMNS == {
        "id", "reference_id", "contract_no", "award_title", "notice_title",
        "awardee_name", "organization_name", "area_of_delivery", "business_category",
        "contract_amount", "award_date", "award_status",
    }


def test_to_epoch_ms_utc():
    d = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    assert to_epoch_ms(d) == 1_704_067_200_000
    assert to_epoch_ms(None) is None


def test_year_of():
    assert year_of(dt.datetime(2024, 5, 9)) == 2024
    assert year_of(None) is None


def test_map_row_shapes_a_philgeps_contract():
    rec = {
        "id": "abc-123", "reference_id": "REF-9", "contract_no": "C-1",
        "award_title": "Supply of laptops", "notice_title": "Laptop notice",
        "awardee_name": "Acme Inc", "organization_name": "DepEd Region 1",
        "area_of_delivery": "Ilocos Norte", "business_category": "IT",
        "contract_amount": 994_000.0, "award_date": dt.datetime(2024, 6, 1, tzinfo=dt.timezone.utc),
        "award_status": "active",
    }
    row = map_row(rec)
    assert row["id"] == "philgeps:abc-123"
    assert row["source"] == "philgeps"
    assert row["contractor"] == "Acme Inc"
    assert row["procuring_entity"] == "DepEd Region 1"
    assert row["category"] == "IT"
    assert row["province"] == "Ilocos Norte"
    assert row["description"] == "Supply of laptops"
    assert row["contract_cost"] == 994_000.0
    assert row["award_date"] == 1_717_200_000_000
    assert row["risk_flags"] == []   # flags assigned later, in transform


def test_map_row_falls_back_to_notice_title():
    rec = {"id": "x", "award_title": None, "notice_title": "Fallback", "contract_amount": 1.0,
           "award_date": None, "awardee_name": None, "organization_name": None,
           "area_of_delivery": None, "business_category": None}
    assert map_row(rec)["description"] == "Fallback"
