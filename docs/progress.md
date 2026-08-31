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
| Bulk backfill of full local run history       | ✅ Done — 946/946 runs loaded, no duplicates |
| Task Scheduler automation                     | ✅ Done — monthly, verified with a manual test run (0x0 success) |
| Power BI connected to BigQuery                | ⬜ Not started |
| Power BI report pages / dashboards            | ⬜ Not started |

## Deployed resources

- **GCP project**: `sts2-bi-1995ebj` (region: `us-central1`)
- **GCS bucket**: `sts2-runs-1995ebj` (raw landing zone, objects under `raw/`)
- **BigQuery dataset**: `sts2` (all 9 tables from `sql/schema.sql` created)
- **Cloud Function**: `sts2-load-run` (2nd gen, Python 3.12, triggered on new objects in the bucket)
- **Function service account**: default compute SA (`448620880316-compute@developer.gserviceaccount.com`), granted `roles/bigquery.dataEditor`, `roles/bigquery.jobUser`, `roles/storage.objectViewer`
- **Task Scheduler task**: `STS2 Upload to GCS`, monthly trigger (day 1, 14:32), runs `scripts/upload_to_gcs.py` via the real Python interpreter path (not the Microsoft Store execution alias, which is unreliable under Task Scheduler) — `STS2_GCS_BUCKET` is set as a permanent user environment variable via `setx` rather than hardcoded in the script

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

5. **Bulk backfill (946 files at once) hit BigQuery's 20-concurrent-DML
   limit.** The delete-then-load idempotency pattern issues a `DELETE
   ... WHERE run_id = @run_id` per fact table per run. That's fine for a
   trickle of runs, but 946 files landing on GCS simultaneously let Cloud
   Functions gen2 scale out well past 20 concurrent invocations, each
   racing to DELETE against `fact_run` at once — BigQuery rejected the
   excess with `Too many DML statements outstanding`, and since the
   trigger's retry policy is do-not-retry, every failed invocation's run
   was silently dropped (no automatic retry, no error surfaced except in
   the function logs). Fixed by redeploying with `--max-instances=10`
   (see `docs/gcp_setup.md`) to cap concurrency below the limit, clearing
   the local upload manifest, and re-running the uploader — the
   delete-then-load design makes re-processing already-successful runs a
   safe no-op, so this recovered the dropped runs without any duplicates.
   Final check: 946 total rows, 946 distinct `run_id`s in `fact_run`.

## Findings from the backfilled data

- **Multiplayer is real, not hypothetical.** The schema was designed
  assuming `player_id` might support co-op some day; the actual history
  contains genuine 4-player runs, with `player_id` populated as real
  Steam64 IDs (not a small integer as the single sample file used during
  schema design suggested). Every fact table carries `player_id`, so
  teammates' decks/relics/floor state are already fully queryable.
- **Gap this exposed**: `fact_run.character` only ever extracts
  `players[0]` — non-host players' character choices aren't captured
  anywhere. Worth fixing if co-op analysis becomes a priority.

## Next steps

1. Connect Power BI Desktop to BigQuery (`docs/powerbi_setup.md`), build
   the star schema relationships, and start on report pages.
2. Consider extracting `players[1:]` character identity into `fact_run`
   (or a new player-per-run table) now that real co-op data confirms
   it's worth modelling properly.
