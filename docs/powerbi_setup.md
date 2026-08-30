# Power BI: connecting and modelling

## Connecting

1. Power BI Desktop → Get Data → More → Database → **Google BigQuery**.
2. Sign in with the Google account tied to your GCP project.
3. Select your project → dataset `sts2` → select all tables.
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

- `dim_date[date_key]` → `fact_run[run_date]`
- `fact_run[run_id]` → each of `fact_floor_state`, `fact_card_choice`,
  `fact_cards_gained`, `fact_relic`, `fact_deck_card` on `run_id`
- `dim_card[card_id]` → `fact_card_choice`, `fact_cards_gained`,
  `fact_deck_card` on `card_id`
- `dim_relic[relic_id]` → `fact_relic[relic_id]`

Mark `dim_date` as a **Date table** (Table tools → Mark as date table) so
time-intelligence DAX functions (`SAMEPERIODLASTYEAR`, rolling averages,
etc.) work correctly.

This is a textbook star schema — every fact table sits one hop from a
dimension, no fact-to-fact relationships, no snowflaking. That shape is
what makes Power BI's query engine fast: it can resolve filters through
single-column joins instead of chasing multi-table chains.

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

## Starter DAX measures

```dax
Total Runs = COUNTROWS(fact_run)

Win Rate =
DIVIDE(
    CALCULATE(COUNTROWS(fact_run), fact_run[win] = TRUE),
    [Total Runs]
)

Avg Floors Reached = AVERAGE(fact_run[acts_completed])

Card Pick Rate =
DIVIDE(
    CALCULATE(COUNTROWS(fact_card_choice), fact_card_choice[was_picked] = TRUE),
    COUNTROWS(fact_card_choice)
)

Win Rate When Picked =
CALCULATE(
    [Win Rate],
    TREATAS(
        CALCULATETABLE(VALUES(fact_card_choice[run_id]), fact_card_choice[was_picked] = TRUE),
        fact_run[run_id]
    )
)
```

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
