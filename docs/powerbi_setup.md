# Power BI: connecting and modelling

## Connecting

The model is checked in as a PBIP project: open `powerbi/STS2 BI.pbip`,
sign in to Google when prompted, and Refresh. The steps below are how it
was set up, if you're rebuilding it from scratch.

1. Power BI Desktop → Get Data → More → Database → **Google BigQuery**.
2. Sign in with the Google account tied to your GCP project.
3. Select your project → dataset **`sts2_marts`** → select all tables.
   Read only the marts, never the raw `sts2` landing tables: the marts are
   the layer dbt tests and enforces contracts on, so that's the layer the
   report can trust.
4. Choose **Import**, not DirectQuery.

**Why Import, not DirectQuery:** DirectQuery sends a live query to
BigQuery on every slicer click and visual render, so dashboard performance
becomes a function of BigQuery query latency, not Power BI. On a personal
run-history dataset (thousands of rows, not billions) there's no reason to
pay that cost — Import loads the data once into Power BI's in-memory
VertiPaq engine, which is dramatically faster for interactive dashboards,
and it keeps every query inside your free 1 TB/month BigQuery quota
instead of re-querying on every click.

## Building the model (Model view)

Relationships to create (all single-direction, one-to-many, from the "one"
dimension side to the "many" fact side):

- `dim_run[run_id]` → each of `fct_floor_state`, `fct_card_choice`,
  `fct_card_gained`, `fct_run_relic`, `fct_run_deck_card` on `run_id`
- `dim_card[card_id]` → `fct_card_choice`, `fct_card_gained`,
  `fct_run_deck_card` on `card_id`
- `dim_relic[relic_id]` → `fct_run_relic[relic_id]`
- `dim_date[date_key]` → `dim_run[run_date]`

Mark `dim_date` as a **Date table** (Table tools → Mark as date table) so
time-intelligence DAX functions (`SAMEPERIODLASTYEAR`, rolling averages,
etc.) work correctly.

`dim_run` is the hub: one row per run, carrying both the run's attributes
and its run-level metrics. An earlier version of this model related the
other facts to `fact_run` directly. That's a fact-to-fact relationship,
which makes filter paths ambiguous and couples two fact grains together.
Promoting the run to a dimension gives a clean star: every fact sits one
hop from `dim_run`, and nothing relates fact to fact.

The one deliberate exception to a pure star is `dim_date` → `dim_run`
(a single snowflake hop): the run date is an attribute of the run, so
date filters reach every fact through `dim_run` instead of each fact
carrying its own date key. That avoids multiple filter paths from
`dim_date` to the same fact.

## Modelling hygiene (the stuff that actually shows up in dashboard speed)

- **Hide foreign keys from report view** (right-click each `run_id`,
  `card_id`, etc. on the *many* side → Hide in report view). Keeps the
  field list clean and stops people dragging join keys into visuals by
  accident.
- **Prefer measures over calculated columns.** A calculated column is
  computed once and stored per row, permanently taking up space in the
  compressed model; a measure computes at query time and costs nothing at
  rest. Everything below is written as a measure for that reason.
- **Set numeric ID columns to "Don't summarize"** (column tools →
  Default Summarization → None) so `run_id` doesn't silently show up as a
  SUM in a new visual.
- **Turn off auto date/time** (File → Options → Data Load) now that you
  have a real `dim_date` — otherwise Power BI generates a hidden date
  table per date column, bloating the model.

## DAX measures

Row-level metrics (floors reached, death floor) are columns computed in
dbt; DAX only aggregates them.

```dax
-- dim_run
Total Runs         = COUNTROWS(dim_run)
Wins               = CALCULATE([Total Runs], dim_run[win] = TRUE)
Win Rate           = DIVIDE([Wins], [Total Runs])                -- 0.0%
Avg Floors Reached = AVERAGE(dim_run[floors_reached])
Avg Death Floor    = AVERAGE(dim_run[death_floor])               -- losses only (null otherwise)

-- fct_card_choice
Times Offered  = COUNTROWS(fct_card_choice)
Times Picked   = CALCULATE(COUNTROWS(fct_card_choice), fct_card_choice[was_picked] = TRUE)
Card Pick Rate = DIVIDE([Times Picked], [Times Offered])          -- 0.0%

Win Rate When Picked =
CALCULATE(
    [Win Rate],
    TREATAS(
        CALCULATETABLE(VALUES(fct_card_choice[run_id]), fct_card_choice[was_picked] = TRUE),
        dim_run[run_id]
    )
)
```

An earlier `Avg Floors Reached` averaged the raw `acts_completed`
column, which is always 3 (it counts acts on the map, not progress).
That's the kind of bug that moving row-level logic into dbt, with
documented columns, is meant to prevent.

`Win Rate When Picked`, filtered by a specific card, is the kind of
"decision impact" metric the project README calls out as the end goal —
it answers "do I win more often in runs where I picked this card?".

## Sharing (free tier)

Publishing to the Power BI Service under **My Workspace** is free, and
viewing it yourself there is free. Two ways to make it visible to other
people without a Pro license:

- **Publish to web**: generates a public, no-login link — but it becomes
  fully public (no access control), and scheduled refresh isn't available
  on the free tier, so the published snapshot goes stale until you
  republish. Fine for a portfolio piece you don't mind being public.
- **Share with specific people**: requires either you or the recipient to
  have Power BI Pro (there's normally a free trial) — everyone with access
  then sees live, refreshed data.

Scheduled refresh in the Service (so the dashboard updates itself as new
runs land in BigQuery, without reopening Desktop) also requires Pro or a
capacity-based license — on the free tier, refresh means reopening
Desktop, clicking Refresh, and republishing.
