# Building STS2 BI end to end: what I built, what broke, and what I learnt

This is the story of the project from local save files to an interactive
Power BI report. For each stage it covers what was built, which tools were
used and why, every problem that cost real time, how it was fixed, and the
lesson behind it. Other docs hold the reference detail: setup steps in
[`gcp_setup.md`](gcp_setup.md) and [`powerbi_setup.md`](powerbi_setup.md),
build status in [`progress.md`](progress.md), the evidence-based review in
[`audit.md`](audit.md). This one explains the decisions.

## The finished pipeline

```
Slay the Spire 2 save folder (.run JSON, one file per run)
   │  scripts/upload_to_gcs.py ............. Windows Task Scheduler, monthly
   ▼
GCS bucket  sts2-runs-1995ebj/raw/ ......... landing zone, immutable files
   │  Cloud Function sts2-load-run ......... Eventarc trigger per new object
   ▼
BigQuery  sts2 ............................. raw star-ish landing tables
   │  dbt build ............................ GitHub Actions, daily, keyless
   ▼
BigQuery  sts2_staging (views) → sts2_marts (tested, contract-enforced)
   │  Import mode
   ▼
Power BI PBIP project ...................... 5 report pages, reads marts only

Second source: the installed game (SlayTheSpire2.pck + sts2.dll)
   │  scripts/build_reference_seeds.py ..... card / event / relic / dialogue seeds
   │  scripts/extract_event_images.py ...... event artwork + colour palettes (local only)
```

946 runs reconcile at every stage, from the files on disk to the report's
Total Runs card.

## The toolbox, and why each tool

| Tool | Used for | Why this and not something else |
|---|---|---|
| Python | Uploader, Cloud Function, backfills, game-file readers | One language across the pipeline; the JSON is nested and Python flattens it naturally. |
| Google Cloud Storage | Raw landing zone | Cheap, immutable copy of every source file; lets any later stage be replayed. |
| Cloud Functions (gen2) + Eventarc | Flatten + load on upload | Event-driven: no server, no schedule to keep in sync, free at this volume. |
| BigQuery | Warehouse | Serverless, free tier covers MB-scale data, native partitioning/clustering to show query-cost design. |
| dbt Core | Staging + marts, tests, contracts, seeds | Turns SQL into a tested, documented, versioned layer. Tests caught real bugs (below). |
| GitHub Actions + Workload Identity Federation | Scheduled `dbt build` | Free on a public repo; WIF means no service-account key exists anywhere to leak. |
| Power BI Desktop (PBIP, TMDL) | Semantic model + report | The BI tool the project showcases; PBIP makes the model and report diff-able text in git. |
| Windows Task Scheduler | Monthly upload | The save files live on this PC, so the trigger has to be local. |
| .NET `System.Reflection.Metadata` | Reading card data from `sts2.dll` | Reads metadata and IL without loading or running the game's code. |
| Pillow | Decoding game textures | Decodes DDS (BC1/BC3/BC7) and WebP once wrapped in the right header. |

## Stage 1: Extraction and scheduling

**Built:** `upload_to_gcs.py` copies new `.run` files to GCS and records
each upload in a local manifest, so a re-run only sends new files.
Task Scheduler runs it monthly.

| Problem | Fix | Why it happened / lesson |
|---|---|---|
| The script worked by hand but not under Task Scheduler. | Point the task at the real interpreter path (`python -c "import sys; print(sys.executable)"`), not the `WindowsApps\python.exe` alias. | The Microsoft Store Python alias is a launcher stub that misbehaves non-interactively. **Scheduled jobs need absolute, real paths.** |
| The bucket name was hardcoded, then went missing from the environment, so the next upload would have failed. Found in the audit (F1). | `STS2_GCS_BUCKET` set permanently with `setx`. The script now fails fast if it is empty or the save folder is missing. | **Fail loudly at the start rather than silently half-way.** Configuration belongs in the environment, not in code. |
| A crash mid-run could re-upload files (audit F9). | Save the manifest after every file, not once at the end. | **Checkpoint per unit of work.** |
| Monthly runs are missed if the PC is off. | Ticked "run as soon as possible after a missed start" (audit F2). | A local scheduler is only as reliable as the machine it runs on. |

## Stage 2: Landing and loading (GCS → Cloud Function → BigQuery)

**Built:** a GCS-triggered function flattens one run's JSON into the landing
tables. It is **idempotent**: for each run_id it deletes the old rows, then
loads, so re-processing a file can never create duplicates. The pure
flattening logic later moved into `cloud_function/flatten.py`, so the
function and the local backfill scripts share one implementation.

| Problem | Fix | Why / lesson |
|---|---|---|
| Linking billing reported `billingEnabled: false`, and the first deploy failed with an Eventarc permission error. | Waited a few minutes and retried the identical command. | **New GCP APIs and IAM grants take minutes to propagate.** Retry before debugging. |
| The deploy failed with "failed to update storage bucket metadata". | Granted the Cloud Storage service agent `roles/pubsub.publisher`. | GCS publishes events to Pub/Sub for Eventarc, and newer projects don't grant this automatically. |
| The function deployed but would have had no permissions. | Explicit BigQuery and Storage roles. Later a dedicated least-privilege `sts2-loader` service account replaced the over-privileged default compute account (audit F4). | Newer projects no longer give the default service account Editor. **Least privilege is also what makes failures visible.** |
| Backfilling 946 files at once hit "Too many DML statements outstanding", and runs were silently dropped. | `--max-instances` capped, the manifest cleared, everything re-uploaded. Idempotency made the replay safe. | BigQuery allows 20 concurrent DML statements per table. **Fan-out serverless meets a shared limit.** The delete-then-load design is what made recovery trivial. |
| 38 duplicate cards and 4 duplicate relics appeared, found only when Power BI refused the relationship. | Deduped once. `--max-instances=1` serialises loads. Strict `unique` source tests in dbt now catch any recurrence the same day. | Two invocations raced the MERGE that adds new cards. BigQuery has no unique constraints or row locks. **Without a test, a data bug surfaces in the dashboard, which is the worst place.** |
| After switching to the new service account, uploads were rejected and nothing errored. | Granted `roles/run.invoker` to the trigger's service account. | Gen2 functions are Cloud Run services, and Eventarc needs permission to invoke them. The rejection appeared only as a WARNING log. |
| Failures were silent in general (audit F3). | A log-based alert policy emails on errors and on "was not authenticated". Created via the REST API because `gcloud alpha monitoring` hung. | **An unmonitored pipeline fails without anyone knowing.** Alert on the specific failure text you have already seen. |
| `bq add-iam-policy-binding` needed allow-listing. | Granted dataset access through the dataset's access list (`bq update --source`). | There is more than one way to grant BigQuery access. Dataset ACLs are the simple one. |
| The timeout was too short for big runs (audit F6). | 300 seconds. | |

## Stage 3: Warehouse design

**Built:** landing tables in `sts2` (`sql/schema.sql`), partitioned by
`run_date` and clustered by the usual filter columns, with the reasoning
written as comments next to each choice.

Findings from the real data that changed the model:

- **`player_id` is a real Steam64 ID.** A single sample file suggested a
  small integer. The full history has genuine 4-player co-op runs, and 25%
  of runs are multiplayer. **Design from the full dataset, not one sample.**
- **`acts_completed` is always 3.** It counts the acts on the map, not
  progress. An early "Avg Floors Reached" built on it was simply wrong.
  `dim_run` now derives `floors_reached` and `acts_reached` from the
  floor-by-floor data. **Profile a column before trusting its name.**
- **5 runs have no floor data.** All were abandoned within seconds. The
  test excludes them explicitly rather than hiding them.
- **Known gap:** only `players[0]`'s character is captured. Documented, not
  guessed.

## Stage 4: The dbt layer

**Built:** `sts2` (raw) → `sts2_staging` (1:1 cleaned views) → `sts2_marts`
(contract-enforced star schema around `dim_run`). Reference seeds, singular
tests, and a `generate_schema_name` macro so the custom schemas keep their
exact names.

Why it matters:

- **The logic-placement rule.** Row-level logic (floors reached, outcome,
  readable names, colours, death-after-choice flags) lives in dbt, where it
  is tested and reusable. Aggregations (win rate, pick rate) are DAX
  measures. Power BI never reads the raw dataset.
- **Tests that earned their keep.** Strict source `unique` tests (the
  duplicate-card incident), referential integrity from every fact to its
  dimension, grain-uniqueness tests, domain checks (HP within bounds,
  `run_date` matches the run_id timestamp), and a warn-level coverage
  check for cards missing from the catalogue (3 retired cards).
- **Contracts** make a column rename or type change fail the build instead
  of silently breaking a report visual.
- **Honest trade-off:** this is ETL with dbt on top, not pure ELT, because
  the Cloud Function flattens. Moving the flattening into dbt is on the
  roadmap.

| Problem | Fix | Lesson |
|---|---|---|
| A new event choice needed a full re-load of history. | `scripts/backfill_table.py` flattens all local files with the shared `flatten.py` and loads one table with WRITE_TRUNCATE (8,596 event choices). | **Sharing the transform between live and backfill paths** means a new table is one script run, not a re-upload of everything. |
| dbt 1.10+ deprecated the old test syntax. | `data_tests:` with `arguments:`. | Pin versions (dbt-core 1.12.5, dbt-bigquery 1.12.1) and read the deprecation warnings. |
| `dbt_utils` wasn't installed for a composite-key test. | A small singular test in the repo's existing pattern. | Prefer the project's existing idiom over adding a dependency for one test. |

## Stage 5: CI and access

**Built:** `.github/workflows/dbt.yml` runs `dbt build` daily, on PRs and on
pushes, authenticating through **Workload Identity Federation**. GitHub's
OIDC token is exchanged for a short-lived credential on the `dbt-runner`
service account. The pool is restricted to this one repository.

- **Why keyless:** a JSON key is a long-lived secret that can leak. With
  WIF there is nothing to steal, and the trust is scoped to one repo.
- **Why repository variables, not secrets:** the provider name and service
  account email are not sensitive. Only a key would be, and there isn't one.
- **Gotcha:** scheduled workflows only run from the default branch, so the
  daily cron starts only once the PR is merged (audit F5).

## Stage 6: Power BI

**Built:** a PBIP project with a TMDL semantic model and five pages: *Where
runs end*, *Solo vs Multiplayer*, *Cards*, *Events* and *Explore*. It uses
Import mode against the marts only, and has a custom theme, synced
dropdowns, search bars and conditional formatting.

Why Import, not DirectQuery: the data is MB-scale, Import is fastest for
users and has no per-query BigQuery cost, and the free tier has no
scheduled refresh anyway. Refresh is the one manual step (Home → Refresh).

| Problem | Fix | Lesson |
|---|---|---|
| Desktop crashed on opening ("frown" errors). | TMDL is tab-indented, and properties must sit indented under their object. | **TMDL is whitespace-sensitive.** Edit it only with Desktop closed, then reopen and refresh to verify. |
| The newer PBIR report format broke the project (missing `version.json`). | Stay on the legacy `report.json`, and always click **Don't upgrade** on save. | Preview formats aren't worth the risk on a working project. The rule is recorded in memory so it is never forgotten. |
| Visuals broke after renaming tables. | Update the `"Entity"` and `queryRef` names in `report.json` too. | The report binds by name, and the model rename doesn't cascade. |
| The model had a fact-to-fact relationship, so filter paths were ambiguous. | Promoted the run to `dim_run`, a hub with every fact one hop away. `dim_date → dim_run` is the one deliberate snowflake hop. | A clean star makes every measure behave predictably. |
| `Abandoned Runs` ignored the slicer, giving 27.8% instead of 20.8%. | `CALCULATE([Total Runs], KEEPFILTERS(dim_run[outcome] = "Abandoned"))`. | A plain boolean filter in `CALCULATE` replaces the slicer's filter on that column. **KEEPFILTERS intersects instead.** |
| Synced slicers didn't sync. | `syncGroup` goes inside `singleVisual`. | Undocumented JSON shape. Copy what Desktop itself writes. |
| Rows needed character colours, and numbers needed green/red. | Colour measures (`Character Row Color`, `Win Rate Font Color`) bound to conditional formatting with `dataViewWildcard` selectors. Colour hex values come from dbt columns. | Colour is data too: derive it in dbt, apply it with a measure. |
| A search bar was needed. | A dropdown slicer with `selfFilterEnabled` (its built-in search). | |

## Stage 7: The second data source, and doing it properly

The first card catalogue was scraped from a fan wiki. Reading its terms
later showed that automated collection was forbidden (Section 7). The
scraper was deleted and replaced by reading **the game the player owns**:

- `scripts/sts2_pck.py` reads the Godot PCK v3 archive (header, then the
  file directory) and returns any file inside it. 15,890 files.
- `tools/sts2_reference` (.NET) reads `sts2.dll` **metadata only**. It finds
  each card's pool from the generic arguments of method calls, and its
  cost, type and rarity from the integer arguments to the base
  constructor. Nothing is loaded, executed or decompiled into the repo.
  - **Bug:** some cards were mis-parsed (*Genetic Algorithm*, *The Scythe*,
    *Sovereign Blade*).
  - **Fix:** only accept a call whose target is `.ctor`, and clear the
    collected integers at every store or other call.
- `scripts/build_reference_seeds.py` writes the seeds: 596 cards, 70
  events, 201 event options, 306 relics and 287 lines of Ancient dialogue.
  The new card catalogue matched the scraped one with zero genuine
  disagreements.
- **Artwork stays out of the public repo.** The images are Mega Crit's to
  distribute, so they are extracted to a gitignored folder on the
  player's machine and embedded at refresh time (stage 8). The text in the
  seeds is short reference text from the game's localization.

**Lesson:** check a source's terms *before* building on it, and prefer
the primary source. Here it was both more legitimate and more accurate.

## Stage 8: The Events section

**Question:** which event options do I pick, and do runs die soon after?

1. **Extraction.** `fact_event_choice` takes the event from the room's
   `model_id` and the choice from `event_choices[].title.key`. Ancient
   choices are relic keys (`SEA_GLASS.REGENT` → `RELIC.SEA_GLASS`). The
   table was added to the loader and backfilled.
2. **Modelling.** `fct_event_choice` joins each choice to what happened
   next. The definitions are written down because they decide the
   answer:
   - `died_before_next_act` means the run was lost in the same act.
   - `died_within_3_floors` means the run was lost within 3 floors.
   - Abandoned runs never count as deaths.
3. **First insight.** At *Room Full of Cheese* I pick "Gorge" 74% of the
   time (36% win), but "Search" wins 57%. Correlation, not causation, and
   the page says so.

### Artwork and the immersive page

| Problem | Fix | Lesson |
|---|---|---|
| The image listing found 0 PNGs. | The PCK holds `*.png.import` stubs and `.godot/imported/*.ctex` textures, not PNGs. Map through those. | Look at what is actually in the archive, not at what you expect. |
| Textures came in three formats: BC7 (BPTC), DXT1 (BC1) and WebP. | Parse the 36-byte `GST2` header and 16-byte image header. Wrap block-compressed data in a DDS DX10 header so Pillow can decode it, and read embedded WebP/PNG directly. Unknown formats are skipped with a warning. | Generalise from the second case, not the first. |
| Power BI can't show images from a local path. | Embed each image as a `data:image/jpeg;base64,...` URI read from the local folder by Power Query. | Image visuals load only `http(s)` or `data:` URLs. Hosting the images publicly would mean redistributing them. |
| A text value is capped at 32,766 characters, which limited images to about 23 KB. | Split the base64 into 30,000-character chunks (one row each) and reassemble them with `CONCATENATEX` in the `Event Image` measure. 1600px backgrounds now work. | Work around engine limits in the model, not by degrading the asset. |
| The page needed to "feel like" the event. | The extractor derives a palette per image: the average hue pushed dark for the background, plus the most vivid dominant colour as the accent. `Theme Bg/Panel/Accent` measures drive every visual's background, border, title and cells. A full-page Image visual is bound to `Event Image`. | Conditional formatting accepts measures almost everywhere: the whole theme is data-driven. |
| Clicking a table row didn't change the background. | The event picker is a **slicer**. | Slicer filters reach formatting expressions on every visual. A cross-highlight from a table doesn't. |
| The picker and the comparison table kept a stale theme. | Give them a fixed neutral style. Set the comparison table to ignore the picker (a NoFilter visual interaction, `type: 3`). | A slicer never filters itself. Design around it rather than fight it. |
| `VAR id = ...` and `VAR rows = ...` failed to parse. | Renamed them `eid` and `lns`. | **`id` and `rows` are reserved words in DAX.** |
| `IF(cond, table1, table2)` failed with "multiple columns cannot be converted to a scalar". | Pick the scalar key with `IF`, then filter once. | `IF` returns scalars, not tables. |
| A refresh of the new tables silently loaded nothing. | Fix the broken measures, then refresh again. | A refresh runs as a transaction, so one invalid measure rolls back the whole batch. |
| Ancients showed "(Blank)" text. | Extract their dialogue per character and visit from `ancients.json`. Show the conversation for the character chosen in the Character slicer (Ironclad by default) in a scrollable panel with an Encounter dropdown. | The "missing" data existed, just under a different key structure. |
| "(Blank)" appeared in the event picker. | Limit the dialogue to Ancients seen in runs, with a relationship test. | A many-side row with no match creates a blank member on the one side. |

## Stage 9: How things were verified

- **Reconciliation, not eyeballing:** 946 runs counted on disk, in the
  manifest, in GCS, raw BigQuery, the marts and the report. The headline
  KPIs were matched against independent SQL.
- **Querying the Power BI engine directly:** Desktop runs a local Analysis
  Services instance. Its port is in `msmdsrv.port.txt`. Through ADOMD.NET
  it was used to:
  - check row counts and partition state (`$SYSTEM.TMSCHEMA_PARTITIONS`)
  - find broken measures (`$SYSTEM.TMSCHEMA_MEASURES WHERE State <> 1`)
  - run DAX to test measures
  - trigger targeted table refreshes with TMSL

  This is how "nothing is showing" was diagnosed: the new tables had never
  loaded.
- **Screenshots of the real report** after every layout change, rather
  than trusting the JSON.
- **A formal audit** ([`audit.md`](audit.md)): status per stage, a findings
  register (F1–F14) and the fixes tracked to commits.

## The ten lessons I'd keep

1. **Make every load idempotent.** Delete-then-load per key turned every
   failure into "just run it again".
2. **Serverless fan-out meets shared limits.** Cap concurrency to what the
   slowest shared resource allows (BigQuery DML, MERGE races).
3. **Test the raw layer strictly, even when staging cleans it.** That's
   where real incidents show up first.
4. **Profile data before trusting column names** (`acts_completed`,
   `player_id`).
5. **Put row logic in the warehouse and aggregations in the semantic
   model.** It is testable, reusable and fast.
6. **Keyless CI and least-privilege service accounts** are cheap to set up
   and remove whole classes of risk.
7. **Silent failures are the real enemy.** Fail fast locally, alert on
   logs in the cloud, and surface rejections that only appear as warnings.
8. **Check a data source's terms before building on it.** The primary
   source is usually better anyway.
9. **Power BI's file formats are text, and edits are fragile.** Edit with
   Desktop closed, verify by reopening, and copy what Desktop writes.
10. **Know the engine's quirks:** KEEPFILTERS, reserved words, `IF` with
    tables, the 32,766-character limit, slicers vs cross-highlighting, and
    refreshes as transactions.

## What's next

See [`roadmap.md`](roadmap.md): per-room combat detail (`fct_room`),
teammate characters, potions, game patches as a dimension, and moving the
flattening into dbt for true ELT.
