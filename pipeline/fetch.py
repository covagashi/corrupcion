"""Download raw datasets into sources/.

Phase 1 pulls the Flood Control dataset. URLs are discovered through the BetterGov
catalog API (https://data.bettergov.ph/api/v1) so they stay correct if the host moves;
we fall back to the known direct URL if the catalog is unreachable.
"""

from __future__ import annotations

import pathlib

import httpx

SOURCES = pathlib.Path(__file__).parent / "sources"
CATALOG = "https://data.bettergov.ph/api/v1"

# Dataset id 2 = "Flood Control Projects Dashboard data" (verified 2026-06-15)
FLOOD_CONTROL_DATASET_ID = 2
FLOOD_CONTROL_FALLBACK_URL = (
    "https://raw.githubusercontent.com/bettergovph/bettergov/"
    "refs/heads/main/src/data/flood_control/flood_control.json"
)

# PhilGEPS bulk parquet on Hugging Face (CC0). philgeps.parquet is the main awarded-contracts
# table (~470 MB, 5.48M rows). awardees/organizations are kept for Phase 4 (alignment), unused now.
PHILGEPS_BASE = "https://huggingface.co/datasets/bettergovph/philgeps-data/resolve/main"
PHILGEPS_FILES = ("philgeps.parquet", "awardees.parquet", "organizations.parquet")


def resolve_download_url(dataset_id: int, fallback: str) -> str:
    """Ask the catalog API for a dataset's first resource download_url."""
    try:
        r = httpx.get(
            f"{CATALOG}/resources",
            params={"dataset_id": dataset_id, "limit": 1},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["data"][0]["download_url"]
    except Exception as exc:  # noqa: BLE001 - catalog is best-effort
        print(f"  catalog lookup failed ({exc}); using fallback URL")
        return fallback


def download(url: str, dest: pathlib.Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  GET {url}")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    print(f"  -> {dest} ({dest.stat().st_size / 1_048_576:.1f} MB)")


def main() -> None:
    print("Fetching Flood Control dataset...")
    url = resolve_download_url(FLOOD_CONTROL_DATASET_ID, FLOOD_CONTROL_FALLBACK_URL)
    download(url, SOURCES / "flood_control.json")

    print("Fetching PhilGEPS datasets...")
    for name in PHILGEPS_FILES:
        download(f"{PHILGEPS_BASE}/{name}", SOURCES / name)
    print("Done.")


if __name__ == "__main__":
    main()
