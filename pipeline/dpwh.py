"""Pure mapping helpers for DPWH transparency parquet records -> contracts rows.

Reuses the date helpers from philgeps. The one DPWH-specific signal is OVER_BUDGET: the amount
disbursed exceeds the project's approved budget (analogous to flood control's OVER_CEILING, but
comparing money *paid* against the *budget* rather than an awarded bid against a ceiling)."""

from __future__ import annotations

from pipeline.philgeps import to_epoch_ms, year_of

# Top-level parquet columns. `location` is a nested struct{province, region} (unnested in transform).
EXPECTED_COLUMNS = {
    "contractId", "description", "category", "componentCategories", "status",
    "budget", "amountPaid", "progress", "location", "contractor",
    "startDate", "completionDate", "infraYear", "programName", "sourceOfFunds",
    "isLive", "livestreamUrl", "livestreamVideoId", "livestreamDetectedAt",
    "latitude", "longitude", "reportCount", "hasSatelliteImage",
}

OVER_BUDGET_FLAG = "OVER_BUDGET"
OVER_BUDGET_WEIGHT = 40


def parse_year(raw: object) -> int | None:
    """infraYear is a free-text string like '2023'. Return the int year or None."""
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def dpwh_flags(budget: object, amount_paid: object) -> tuple[list[str], int]:
    if budget and amount_paid is not None and amount_paid > budget:
        return [OVER_BUDGET_FLAG], OVER_BUDGET_WEIGHT
    return [], 0


def map_row(rec: dict) -> dict:
    budget = rec.get("budget")
    paid = rec.get("amountPaid")
    ratio = (paid / budget) if (budget and paid is not None) else None
    flags, score = dpwh_flags(budget, paid)
    return {
        "id": "dpwh:" + str(rec["contractId"]),
        "source": "dpwh",
        "project_id": rec.get("contractId"),
        "description": rec.get("description"),
        "category": rec.get("category"),
        "contractor": rec.get("contractor"),
        "province": rec.get("province"),
        "region": rec.get("region"),
        "abc": budget,                 # approved budget
        "contract_cost": paid,         # amount disbursed so far
        "bid_to_ceiling_ratio": round(ratio, 6) if ratio is not None else None,
        "latitude": rec.get("latitude"),
        "longitude": rec.get("longitude"),
        "infra_year": parse_year(rec.get("infraYear")),
        "completion_year": year_of(rec.get("completionDate")),
        "start_date": to_epoch_ms(rec.get("startDate")),
        "risk_flags": flags,
        "risk_score": score,
    }
