# GCP setup

One-time setup to stand up the free-tier pipeline: local `.run` files →
GCS → Cloud Function → BigQuery → Power BI.

Everything here stays inside the GCP Always Free tier for this project's
data volume (a personal run history, a few MB per file): BigQuery gives
10 GB storage + 1 TB queries/month free, GCS gives 5 GB free (US regions),
Cloud Functions gives 2 million invocations/month free. You do need a
billing account attached to the project (GCP requires this even for free
usage), but nothing here should incur charges at this scale.

## 1. Create the project

Console: https://console.cloud.google.com/projectcreate

Or via `gcloud`:
```
gcloud projects create YOUR_PROJECT_ID
gcloud config set project YOUR_PROJECT_ID
```
Attach a billing account to the project (Billing → Link a billing account)
if it isn't already.

## 2. Enable the APIs you need

```
gcloud services enable \
  bigquery.googleapis.com \
  storage.googleapis.com \
  cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com \
  eventarc.googleapis.com \
  artifactregistry.googleapis.com
```

## 3. Authenticate your local machine

Used by `scripts/upload_to_gcs.py` and `scripts/generate_dim_date.py` — no
service-account key file to create or protect:
```
gcloud auth application-default login
```

## 4. Create the GCS landing bucket

```
gsutil mb -l us-central1 gs://YOUR_BUCKET_NAME
```
Pick a globally-unique bucket name (e.g. `sts2-runs-yourname`).

## 5. Create the BigQuery dataset and tables

```
bq mk --dataset --location=US YOUR_PROJECT_ID:sts2
bq query --use_legacy_sql=false < sql/schema.sql
```

## 6. Seed the date dimension

```
pip install google-cloud-bigquery
python scripts/generate_dim_date.py --project YOUR_PROJECT_ID
```

## 7. Deploy the Cloud Function

```
gcloud functions deploy sts2-load-run \
  --gen2 \
  --runtime=python312 \
  --region=us-central1 \
  --source=cloud_function \
  --entry-point=load_run \
  --trigger-bucket=YOUR_BUCKET_NAME \
  --set-env-vars=BQ_DATASET=sts2 \
  --max-instances=10
```

`--max-instances=10` matters more than it looks: BigQuery caps concurrent
DML statements (the DELETE half of the delete-then-load pattern) against
a single table at 20. A steady trickle of runs never gets close to that,
but a bulk backfill — hundreds of files landing on GCS at once — lets
Cloud Functions gen2 scale out past it by default, and every invocation
past the limit fails outright (and does not retry, since the trigger's
retry policy is do-not-retry). Capping instances makes Eventarc queue
and drip-feed events instead.
```

This grants the function's default service account access to the bucket
automatically. If BigQuery writes fail with a permissions error, grant the
function's service account the `roles/bigquery.dataEditor` and
`roles/bigquery.jobUser` roles on the project.

## 8. Point the local uploader at your resources

Set these before running `scripts/upload_to_gcs.py` (or edit the defaults
in the script directly):
```
setx STS2_GCS_BUCKET "YOUR_BUCKET_NAME"
```
(`setx` persists it for future terminal sessions on Windows; use `set` for
just the current session.)

## 9. Automate the upload with Task Scheduler

1. Task Scheduler → Create Task.
2. Trigger: Daily (or whatever cadence matches how often you play).
3. Action: Start a program →
   - Program: path to `python.exe`
   - Arguments: `scripts\upload_to_gcs.py`
   - Start in: the repo root, so relative paths resolve.
4. Run whether the user is logged on or not, if you want it to fire
   unattended.

## 10. Verify end-to-end

Play a run (or copy an existing `.run` file into the save folder under a
new name), run the uploader manually once, then check:
```
bq query --use_legacy_sql=false 'SELECT * FROM sts2.fact_run ORDER BY run_date DESC LIMIT 5'
```
If Cloud Functions logs show an error, `gcloud functions logs read sts2-load-run --gen2` shows the traceback.

## Troubleshooting

A few errors are near-guaranteed the first time you run this on a fresh
project — none of them mean anything is actually wrong, they're just gaps
in what gets auto-configured:

**`functions deploy` fails with an Eventarc/Cloud Run permission error**
right after you've just enabled an API (e.g. `run.googleapis.com`) — IAM
grants for a newly-enabled API's service agent can take a few minutes to
propagate. Wait ~5 minutes and re-run the exact same deploy command.

**`functions deploy` fails with `Failed to update storage bucket
metadata`**, mentioning the Cloud Storage service agent can't publish to
the Eventarc Pub/Sub topic — the GCS service agent isn't automatically
granted `pubsub.publisher` on the project. Get your project number (`gcloud
projects describe YOUR_PROJECT_ID --format="value(projectNumber)"`) and run:
```
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:service-YOUR_PROJECT_NUMBER@gs-project-accounts.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"
```
Then retry the deploy.

**The function deploys fine but fails at runtime (BigQuery/Storage
permission errors in the logs)** — on projects created after ~mid-2024,
the default compute service account no longer gets the broad `Editor`
role automatically. Grant it what the function actually needs:
```
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```
