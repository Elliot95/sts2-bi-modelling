# STS2 BI Modelling — project context

This is a personal BI portfolio project: Slay the Spire 2 run history →
GCS → BigQuery (star schema) → Power BI. It exists partly to showcase
real BI engineering practices (dimensional modelling, partitioning/
clustering for query performance, incremental ingestion), not just to
produce dashboards.

**Read these before making changes** — they carry the actual state and
reasoning, this file is just the entry point:

- `docs/progress.md` — what's built and verified vs. still pending,
  the real GCP resource names/IDs in use, every issue hit during setup
  and its fix, and findings from the real data (read this first for
  "where did we leave off").
- `sql/schema.sql` — the star schema DDL, with the reasoning for every
  partitioning/clustering/denormalization choice inline as comments.
- `docs/gcp_setup.md` — GCP provisioning steps, including a
  Troubleshooting section for gotchas already solved (Eventarc/IAM
  propagation delays, the Cloud Storage service agent Pub/Sub
  permission, BigQuery's 20-concurrent-DML limit).
- `docs/powerbi_setup.md` — connecting Power BI to BigQuery, why Import
  mode over DirectQuery, relationship setup, starter DAX measures.
- `cloud_function/main.py` — the transform/load logic (flattens a `.run`
  JSON file into the star schema, idempotent via delete-then-load per
  run_id).

## Current state (see docs/progress.md for full detail)

- GCP project `sts2-bi-1995ebj`, GCS bucket `sts2-runs-1995ebj`,
  BigQuery dataset `sts2` — all provisioned and live.
- Full run history backfilled: 946 runs, verified no duplicates.
- Ingestion is automated via Windows Task Scheduler
  (`scripts/upload_to_gcs.py`, monthly) — not daily, that was a
  deliberate choice given the concurrency limit is already handled.
- dbt (`dbt/`) builds `sts2_staging` (views) and `sts2_marts` (tested,
  contract-enforced star schema around `dim_run`) from the raw `sts2`
  tables. It runs in GitHub Actions (`.github/workflows/dbt.yml`) via
  keyless Workload Identity Federation. Run locally with
  `dbt/.venv/Scripts/dbt build --profiles-dir .` from `dbt/`.
- Power BI: PBIP project in `powerbi/`, reading **only** `sts2_marts`
  (plus local artwork, see below). Pages: Where runs end, Solo vs
  Multiplayer, Cards, Events, Potions, Explore (+ the user's two scratch
  pages). Dark theme; pages are themed by the Character slicer
  (`character_image` / `character_theme`, `Page *` measures).
- Reference data comes from the user's installed game, never the web:
  `scripts/build_reference_seeds.py` (cards via `tools/sts2_reference`,
  events/options/relics/Ancient dialogue via `scripts/sts2_pck.py`) ->
  dbt seeds. Do not scrape slaythespire2.gg (its ToS forbids it).
- Artwork + palettes: `scripts/extract_event_images.py` ->
  `powerbi/assets/{events,characters,potions}/` (gitignored, Mega Crit IP,
  never commit).
- Adding a raw table: extend `cloud_function/flatten.py` + `FACT_TABLES`,
  add DDL to `sql/schema.sql` and create it, redeploy the function, then
  `python scripts/backfill_table.py <table>` (uploaded runs only by default).
  Power BI embeds it as chunked base64 data URIs (`event_image`,
  `event_theme`). See `docs/powerbi_setup.md`.
- The full story of problems and fixes: `docs/lessons_learned.md`.

## Conventions

- Row-level logic goes in dbt marts; aggregations are DAX measures. Power
  BI never reads the raw `sts2` dataset.
- Power BI model files are TMDL: tab-indented, and properties must be
  indented under their object. Edit them only with Desktop closed, then
  reopen and Refresh to verify. Renaming a table also means updating
  `"Entity"`/`queryRef` names in `powerbi/STS2 BI.Report/report.json`.
- The `bq` CLI is unreliable in `cmd.exe` on this machine (Store Python
  alias). Use PowerShell, or the BigQuery console.
- Report stays in the legacy `report.json` format: always click
  "Don't upgrade" on save (PBIR broke the project before).
- DAX: `id` and `rows` are reserved (not usable as VAR names); `IF` can't
  return tables. A refresh with one invalid measure rolls back the batch.
- To inspect a running Desktop model: its local Analysis Services port is
  in `%USERPROFILE%\Microsoft\Power BI Desktop Store App\AnalysisServicesWorkspaces\*\Data\msmdsrv.port.txt`;
  query it with ADOMD.NET (`Microsoft.PowerBI.AdomdClient.dll` in the
  Desktop install) for DMVs, DAX, and TMSL refreshes.

## Things worth knowing before touching the pipeline

- The Cloud Function's idempotency pattern (DELETE then LOAD per
  run_id) breaks under bulk uploads if `--max-instances` isn't capped
  — see the Troubleshooting section in `docs/gcp_setup.md` before ever
  re-running a large backfill.
- `player_id` is a real Steam64 ID in multiplayer runs (confirmed on
  actual data — one run had 4 distinct players), not the small integer
  a single sample file suggested during initial schema design. See
  the "Findings from the backfilled data" section in `docs/progress.md`.
- `fact_run.character` only extracts `players[0]` — non-host players'
  character choices aren't captured anywhere. Known gap, not a bug.
- A published reference artifact (architecture diagram, ERD, full data
  dictionary, and a "what this can/can't answer" coverage sheet) exists
  from an earlier session — ask the user for the link if you need it;
  it isn't stored in this repo.
- A `dim_patch` feature (attaching game-patch dates to the schema) was
  discussed and deliberately deferred — the user was satisfied with the
  pipeline as-is. Design notes exist if it comes up again: a small
  `dim_patch(build_id, first_seen_run_id, first_seen_date)` table,
  populated by extending the existing `dim_card`/`dim_relic`
  incremental-MERGE pattern in `cloud_function/main.py`.

## Local environment notes

- Python on this machine is the Microsoft Store package. The execution
  alias (`...\WindowsApps\python.exe`) is unreliable for non-interactive
  use (e.g. Task Scheduler) — use `python -c "import sys; print(sys.executable)"`
  to get the real interpreter path when it matters.
- `STS2_GCS_BUCKET` is set as a permanent user environment variable via
  `setx`, not hardcoded in scripts.
