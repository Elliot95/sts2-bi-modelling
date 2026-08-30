# Progress log

Running record of what's actually built and verified, as distinct from
what the setup docs describe in the abstract. Update this as milestones
land — it's the fastest way to answer "where did we leave off?"

## Status

| Component                                   | Status         |
|----------------------------------------------|----------------|
| GCP project created, billing linked           | ✅ Done        |
| APIs enabled (BigQuery, Storage, Functions, Eventarc, Cloud Build, Artifact Registry) | ✅ Done |
| GCS landing bucket                            | ✅ Done        |
| BigQuery dataset + star schema tables         | ✅ Done        |
| `dim_date` seeded                             | ✅ Done (2024–2029) |
| Cloud Function deployed (GCS → BigQuery)      | ✅ Done        |
| End-to-end test (1 real run, upload → BigQuery) | ✅ Verified — `fact_run` returned the correct row |
| Bulk backfill of full local run history       | ⬜ Not yet run |
| Task Scheduler automation (daily upload)      | ⬜ Not yet set up |
| Power BI connected to BigQuery                | ⬜ Not started |
| Power BI report pages / dashboards            | ⬜ Not started |

## Deployed resources

- **GCP project**: `sts2-bi-1995ebj` (region: `us-central1`)
- **GCS bucket**: `sts2-runs-1995ebj` (raw landing zone, objects under `raw/`)
- **BigQuery dataset**: `sts2` (all 9 tables from `sql/schema.sql` created)
- **Cloud Function**: `sts2-load-run` (2nd gen, Python 3.12, triggered on new objects in the bucket)
- **Function service account**: default compute SA (`448620880316-compute@developer.gserviceaccount.com`), granted `roles/bigquery.dataEditor`, `roles/bigquery.jobUser`, `roles/storage.objectViewer`

## Verified end-to-end

Uploaded one real run (`1781627594.run`) directly to the bucket via `gsutil cp`.
The Cloud Function fired automatically and `SELECT * FROM sts2.fact_run`
returned the correctly parsed row (ascension 10, `CHARACTER.REGENT`, win = true,
3 acts completed). Confirms the full path — GCS trigger → flatten → BigQuery
load — works without manual intervention.

## Issues hit during setup (and the fixes)

These aren't obvious from Google's docs and cost real time — recorded here
so they don't have to be re-diagnosed if this pipeline is ever rebuilt from
scratch (a new environment, a second machine, etc.):

1. **`gcloud billing projects link` returned `billingEnabled: false`**
   immediately after linking, despite no error. Cause was just propagation
   delay after the billing account itself had only just been created —
   re-checking with `gcloud billing projects describe` a bit later showed
   `true`. Not an actual failure, just needed to wait.

2. **First `functions deploy` failed with an Eventarc permission error**
   ("Permission denied while using the Eventarc Service Agent") right
   after enabling `run.googleapis.com` for the first time. Same cause —
   IAM propagation delay for a newly-enabled API's service agent. Fixed
   by waiting ~5 minutes and retrying the identical deploy command.

3. **Second deploy attempt failed with**
   `Failed to update storage bucket metadata` / Cloud Storage service
   agent unable to publish to the Eventarc Pub/Sub topic. This is a
   known gap: the GCS service agent doesn't automatically get
   `pubsub.publisher` on the project. Fixed with:
   ```
   gcloud projects add-iam-policy-binding sts2-bi-1995ebj \
     --member="serviceAccount:service-448620880316@gs-project-accounts.iam.gserviceaccount.com" \
     --role="roles/pubsub.publisher"
   ```

4. **Function deployed successfully but would have failed at runtime**
   without explicit IAM grants. Newer GCP projects (created after ~mid-2024)
   no longer auto-grant the default compute service account the broad
   `Editor` role that older projects got for free. Had to explicitly grant
   `roles/bigquery.dataEditor`, `roles/bigquery.jobUser`, and
   `roles/storage.objectViewer` to the function's service account before
   it could read from GCS or write to BigQuery.

## Next steps

1. Bulk-upload the full local run history via `scripts/upload_to_gcs.py`
   and confirm `fact_run` row count matches total run count.
2. Set up Task Scheduler for daily automatic uploads (`docs/gcp_setup.md`
   step 9).
3. Connect Power BI Desktop to BigQuery (`docs/powerbi_setup.md`), build
   the star schema relationships, and start on report pages.
