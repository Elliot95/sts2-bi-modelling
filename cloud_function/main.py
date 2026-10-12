"""
GCS-triggered Cloud Function (2nd gen). Fires when a new .run file lands in
the raw bucket, flattens it into the star schema defined in sql/schema.sql,
and loads it into BigQuery.

Idempotency: BigQuery load jobs only append. Re-processing the same run_id
(e.g. the function retries after a transient failure) would duplicate rows
if we only appended — so for every fact table we DELETE any existing rows
for this run_id before loading the new ones. Delete-then-load at the run
grain is simpler and cheaper here than a MERGE, since a whole run is always
replaced atomically as one unit, never patched field-by-field.

Deploy (see docs/gcp_setup.md for the full walkthrough):
    gcloud functions deploy sts2-load-run \
        --gen2 --runtime=python312 --region=us-central1 \
        --source=cloud_function --entry-point=load_run \
        --trigger-bucket=YOUR_BUCKET_NAME \
        --set-env-vars=BQ_DATASET=sts2
"""

import json
import os

import functions_framework
from google.cloud import bigquery, storage

from flatten import flatten_run

DATASET = os.environ.get("BQ_DATASET", "sts2")

bq_client = bigquery.Client()
storage_client = storage.Client()

FACT_TABLES = (
    "fact_run",
    "fact_floor_state",
    "fact_card_choice",
    "fact_cards_gained",
    "fact_relic",
    "fact_deck_card",
    "fact_event_choice",
    "fact_potion_event",
    "fact_run_potion",
)


def _replace_run_rows(run_id: int, tables: dict[str, list[dict]]) -> None:
    for table_name in FACT_TABLES:
        full_table = f"{bq_client.project}.{DATASET}.{table_name}"

        bq_client.query(
            f"DELETE FROM `{full_table}` WHERE run_id = @run_id",
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("run_id", "INT64", run_id)]
            ),
        ).result()

        rows = tables.get(table_name, [])
        if rows:
            job = bq_client.load_table_from_json(
                rows,
                full_table,
                job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND"),
            )
            job.result()


def _upsert_dimensions(run_id: int, run_date: str, tables: dict[str, list[dict]]) -> None:
    card_ids = {row["card_id"] for row in tables["fact_card_choice"] if row.get("card_id")}
    card_ids |= {row["card_id"] for row in tables["fact_cards_gained"] if row.get("card_id")}
    card_ids |= {row["card_id"] for row in tables["fact_deck_card"] if row.get("card_id")}

    relic_ids = {row["relic_id"] for row in tables["fact_relic"] if row.get("relic_id")}

    for dim_table, natural_key, ids in (
        ("dim_card", "card_id", card_ids),
        ("dim_relic", "relic_id", relic_ids),
    ):
        if not ids:
            continue
        full_table = f"{bq_client.project}.{DATASET}.{dim_table}"
        bq_client.query(
            f"""
            MERGE `{full_table}` T
            USING UNNEST(@ids) AS new_id
            ON T.{natural_key} = new_id
            WHEN NOT MATCHED THEN
              INSERT ({natural_key}, first_seen_run_id, first_seen_date)
              VALUES (new_id, @run_id, @run_date)
            """,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ArrayQueryParameter("ids", "STRING", sorted(ids)),
                    bigquery.ScalarQueryParameter("run_id", "INT64", run_id),
                    bigquery.ScalarQueryParameter("run_date", "DATE", run_date),
                ]
            ),
        ).result()


@functions_framework.cloud_event
def load_run(cloud_event):
    bucket_name = cloud_event.data["bucket"]
    object_name = cloud_event.data["name"]

    if not object_name.endswith(".run"):
        print(f"Skipping non-.run object: {object_name}")
        return

    blob = storage_client.bucket(bucket_name).blob(object_name)
    data = json.loads(blob.download_as_text())

    tables = flatten_run(data)
    run_id = tables["fact_run"][0]["run_id"]
    run_date = tables["fact_run"][0]["run_date"]

    _replace_run_rows(run_id, tables)
    _upsert_dimensions(run_id, run_date, tables)

    print(f"Loaded run {run_id} ({object_name}) into BigQuery.")
