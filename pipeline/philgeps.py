"""Pure mapping helpers for PhilGEPS parquet records -> contracts rows. No I/O, easy to test."""

from __future__ import annotations

import datetime as dt

EXPECTED_COLUMNS = {
    "id", "reference_id", "contract_no", "award_title", "notice_title",
    "awardee_name", "organization_name", "area_of_delivery", "business_category",
    "contract_amount", "award_date", "award_status",
}


def to_epoch_ms(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return int(value.timestamp() * 1000)
    if isinstance(value, dt.date):
        d = dt.datetime(value.year, value.month, value.day, tzinfo=dt.timezone.utc)
        return int(d.timestamp() * 1000)
    return None


def year_of(value: object) -> int | None:
    if isinstance(value, (dt.datetime, dt.date)):
        return value.year
    return None


def map_row(rec: dict) -> dict:
    return {
        "id": "philgeps:" + str(rec["id"]),
        "source": "philgeps",
        "project_id": rec.get("reference_id"),
        "description": rec.get("award_title") or rec.get("notice_title"),
        "contractor": rec.get("awardee_name"),
        "procuring_entity": rec.get("organization_name"),
        "category": rec.get("business_category"),
        "province": rec.get("area_of_delivery"),
        "contract_cost": rec.get("contract_amount"),
        "award_date": to_epoch_ms(rec.get("award_date")),
        "risk_flags": [],
        "risk_score": 0,
    }
