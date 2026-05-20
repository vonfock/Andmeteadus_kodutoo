"""Source URLs for yearly roadworthiness inspection CSV files."""

from __future__ import annotations

YEAR_URLS = {
    2010: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/9b2d3dbe-e35c-4b5f-baed-6990baa408d0/download-s3",
    2011: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/5139abc3-6823-4121-8d2c-0c82928ac8ac/download-s3",
    2012: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/53f52202-e94e-4cb8-9149-4e311e6f2fdb/download-s3",
    2013: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/3f859ecc-7296-4b9c-ae9b-625b95c90ad9/download-s3",
    2014: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/10103f5a-0b6d-46fc-bd16-99a5c433625e/download-s3",
    2015: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/788a9115-a5da-4f47-bbcc-c1c3b644d3b3/download-s3",
    2016: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/f4f0b51e-8343-4832-9c07-4c04448b8f21/download-s3",
    2017: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/b5a08ea9-0fa8-4cb5-b0bc-7109571d8de4/download-s3",
    2018: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/2d018cd8-f3d7-4242-8514-99633120992a/download-s3",
    2019: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/7ba50767-9844-40bb-8561-af89b634e201/download-s3",
    2020: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/6371e8dc-9906-4555-af9f-f927f2ccf938/download-s3",
    2021: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/f3fe9ef1-897c-45b3-b2dd-908b810aae9c/download-s3",
    2022: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/ba317d52-71b7-473d-bc87-aec0cde38434/download-s3",
    2023: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/1943aed4-8e53-4e70-9946-7fc8ad1f7dfe/download-s3",
    2024: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/af5b081a-3db1-495d-90f3-c334a860938a/download-s3",
    2025: "https://pilv.transpordiamet.ee/s/Iiee4OAYFq4lT1v/download?path=%2F&files=yv_2025.csv",
}


def available_years() -> list[int]:
    """Return known inspection years."""
    return sorted(YEAR_URLS)


def get_year_url(year: int) -> str:
    """Return the remote CSV URL for a year."""
    if year not in YEAR_URLS:
        raise ValueError(f"No URL for year {year}.")
    return YEAR_URLS[year]
