"""
Seeds sts2.dim_date with a static calendar range.

Reference/dimension data like a date table is generated once and loaded
directly — it doesn't belong in the per-run Cloud Function alongside
transactional fact loads. Run this manually after the dataset/tables exist
(see docs/gcp_setup.md), and re-run it any time you want to extend the range.

Usage:
    python scripts/generate_dim_date.py --project YOUR_PROJECT_ID
"""

import argparse
import calendar
import datetime

from google.cloud import bigquery

START_YEAR = 2024          # earliest plausible run date
YEARS_AHEAD = 3            # buffer so the table doesn't need re-running constantly


def build_rows(start: datetime.date, end: datetime.date) -> list[dict]:
    rows = []
    current = start
    while current <= end:
        iso_year, iso_week, _ = current.isocalendar()
        rows.append({
            "date_key": current.isoformat(),
            "year": current.year,
            "quarter": (current.month - 1) // 3 + 1,
            "month": current.month,
            "month_name": calendar.month_name[current.month],
            "day": current.day,
            "day_of_week": (current.weekday() + 1) % 7 + 1,  # 1=Sunday..7=Saturday
            "day_name": calendar.day_name[current.weekday()],
            "week_of_year": iso_week,
            "is_weekend": current.weekday() >= 5,
        })
        current += datetime.timedelta(days=1)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--dataset", default="sts2")
    args = parser.parse_args()

    today = datetime.date.today()
    start = datetime.date(START_YEAR, 1, 1)
    end = datetime.date(today.year + YEARS_AHEAD, 12, 31)

    rows = build_rows(start, end)

    client = bigquery.Client(project=args.project)
    table_ref = f"{args.project}.{args.dataset}.dim_date"

    job = client.load_table_from_json(
        rows,
        table_ref,
        job_config=bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        ),
    )
    job.result()

    print(f"Loaded {len(rows)} rows into {table_ref} ({start} to {end})")


if __name__ == "__main__":
    main()
