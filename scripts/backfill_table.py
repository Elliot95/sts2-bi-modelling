"""
Backfill one raw table from the full local run history in a single batch.

When a new raw table is added to the loader (e.g. fact_event_choice), the
Cloud Function only fills it for runs uploaded from then on. Re-triggering it
for every historical file would take hours at --max-instances=1, so this
script runs the SAME flattening code (cloud_function/flatten.py) over every
local .run file and loads the result with one BigQuery load job.

The load uses WRITE_TRUNCATE: the table is fully derived from the run files,
so replacing it wholesale is idempotent and safe to re-run.

Usage:
    python scripts/backfill_table.py fact_event_choice [--dry-run]
"""

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "cloud_function"))
from flatten import flatten_run  # noqa: E402

SAVE_FOLDER = Path(os.environ.get(
    "STS2_SAVE_FOLDER",
    r"C:\Users\1995e\AppData\Roaming\SlayTheSpire2\steam\76561199024701292\profile1\saves\history",
))
PROJECT = os.environ.get("GCP_PROJECT", "sts2-bi-1995ebj")
DATASET = os.environ.get("BQ_DATASET", "sts2")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("table", help="raw table to rebuild, e.g. fact_event_choice")
    ap.add_argument("--dry-run", action="store_true", help="flatten and count, but don't load")
    ap.add_argument("--all-local", action="store_true",
                    help="include runs not uploaded yet (default: only runs in the upload manifest, "
                         "so the table covers exactly the runs the other raw tables hold)")
    args = ap.parse_args()

    files = sorted(SAVE_FOLDER.glob("*.run"))
    manifest = REPO / "scripts" / "uploaded_manifest.json"
    if not args.all_local and manifest.exists():
        uploaded = set(json.loads(manifest.read_text(encoding="utf-8")))
        skipped = [f for f in files if f.name not in uploaded]
        files = [f for f in files if f.name in uploaded]
        if skipped:
            print(f"skipping {len(skipped)} runs not uploaded yet (the monthly upload will load them)")
    if not files:
        raise SystemExit(f"No .run files found in {SAVE_FOLDER}")

    rows = []
    for f in files:
        tables = flatten_run(json.loads(f.read_text(encoding="utf-8")))
        if args.table not in tables:
            raise SystemExit(f"Unknown table {args.table!r}; flatten_run produces {sorted(tables)}")
        rows.extend(tables[args.table])
    print(f"{len(files)} runs -> {len(rows)} rows for {args.table}")
    if args.dry_run:
        return

    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT)
    target = f"{PROJECT}.{DATASET}.{args.table}"
    job = client.load_table_from_json(rows, target, job_config=bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE))
    job.result()
    print(f"Loaded {job.output_rows} rows into {target}")


if __name__ == "__main__":
    main()
