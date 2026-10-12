# Roadmap: where the model can grow

The pipeline deliberately models a subset of what's in each `.run` file.
This page lists what's already in the raw JSON but not yet modelled, the
table it would become, and the question it would unlock, so expansion is
a planned extension rather than a rewrite.

Field paths are from the structure discovery in
`data/exploration/structure_10_levels.csv`.

## Unmodelled data already in the raw files

| Raw field | Would become | Question it unlocks |
|---|---|---|
| `modifiers` | `dim_modifier` + `bridge_run_modifier` (many-to-many) | Performance on challenge/modified runs vs standard. |
| `players[1:].character` | `fct_run_player` (grain: run / player) | Co-op analysis: teammate characters (only `players[0]` is captured today, via `fact_run.character`). Would also make the host identifiable, so per-player HP metrics could be filled for multiplayer runs. |
| `acts[]` (act IDs) | `dim_act` | Act-specific difficulty, if act variants differ between runs. |

Adding any of these follows the same pattern: extend `flatten_run()` in
`cloud_function/flatten.py`, add the raw table to `sql/schema.sql`, add a
staging view + mart + tests in `dbt/`, then reprocess the history. The
loader is idempotent per run_id, so reprocessing is safe; see the
backfill notes in `docs/gcp_setup.md`.

## Enrichment

- **Rooms and rest sites**: done. `fct_combat` (one row per fight per
  player: encounter, turns, HP going in, damage as % of max HP, potions
  drunk, died here), `dim_encounter` (names + the game's death lines) and
  `fct_rest_choice` (rest vs smith with HP going in), on the Fights page.
- **Potions**: done. `fct_potion_event` (offered/used/discarded/bought
  per floor) and `fct_potion_run` (run roll-up incl. held at the end),
  with the Potions report page.
- **Card/relic/event metadata**: done. The seeds are built from the
  installed game (`scripts/build_reference_seeds.py`). Event choices are
  modelled as `fct_event_choice` + `dim_event`.
- **Game patches**: `dim_patch(build_id, first_seen_run_id,
  first_seen_date)`, discovered incrementally like `dim_card`, to compare
  win rates across balance patches.

## Architecture

- **True ELT**: today the Cloud Function flattens JSON before loading, so
  dbt sits on top of an ETL step. Landing the raw JSON in BigQuery (JSON
  column or external table) and doing the flattening in dbt staging models
  would put all transformation logic in one tested, versioned place.
- **Incremental models**: at ~1k runs, full rebuilds take seconds. If the
  history grows by orders of magnitude, the fact marts can switch to
  `materialized: incremental` keyed on `run_id`.
- **Published docs**: `dbt docs generate` produces a lineage graph and
  data dictionary that could be published to GitHub Pages from CI.
