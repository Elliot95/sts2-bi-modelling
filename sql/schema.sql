-- STS2 BI star schema
--
-- Dataset: sts2 (create first with `bq mk --dataset --location=US <project>:sts2`,
-- see docs/gcp_setup.md). Table names are unqualified — run this with your
-- project set as the active gcloud/bq project, or prefix every table with
-- `your-project.sts2.` if you'd rather be explicit.
--
-- Grain of `run_id`: the epoch seconds in start_time / the .run filename.
-- Unique per run, sorts chronologically, and needs no extra ID generation.
--
-- Design choices worth calling out (this project exists partly to showcase
-- them):
--   * run_date is denormalized onto every fact table, not just fact_run.
--     It's redundant with fact_run.run_date, but BigQuery partition
--     pruning only works on a column that lives on the table being
--     queried — copying the date down is what keeps a "win rate over the
--     last 90 days" query from scanning the whole table.
--   * Facts are fully flattened (one row per run/floor/card-choice/...)
--     rather than left as nested RECORD/ARRAY columns. BigQuery is fine
--     with nested data, but Power BI Import mode models relationally, so
--     flattening here means the warehouse layer matches the shape the
--     dashboard layer wants — no unnesting logic duplicated in Power Query.
--   * dim_card / dim_relic are catalogs discovered from the data itself
--     (there's no external card database), populated incrementally by the
--     loader as new IDs are seen. They start with just the natural key;
--     enriching them with real card names/rarity is flagged as future work.

CREATE TABLE IF NOT EXISTS sts2.dim_date (
  date_key        DATE NOT NULL,
  year            INT64,
  quarter         INT64,
  month           INT64,
  month_name      STRING,
  day             INT64,
  day_of_week     INT64,   -- 1 = Sunday .. 7 = Saturday (matches BigQuery's own convention)
  day_name        STRING,
  week_of_year    INT64,
  is_weekend      BOOL
)
CLUSTER BY date_key;

CREATE TABLE IF NOT EXISTS sts2.dim_card (
  card_id             STRING NOT NULL,   -- natural key, e.g. CARD.SETUP_STRIKE
  first_seen_run_id   INT64,
  first_seen_date     DATE
);

CREATE TABLE IF NOT EXISTS sts2.dim_relic (
  relic_id            STRING NOT NULL,   -- natural key, e.g. RELIC.BURNING_BLOOD
  first_seen_run_id   INT64,
  first_seen_date     DATE
);

-- fact_run: one row per run. The root fact everything else hangs off.
CREATE TABLE IF NOT EXISTS sts2.fact_run (
  run_id              INT64 NOT NULL,     -- = start_time epoch seconds
  run_date            DATE NOT NULL,
  seed                STRING,
  build_id            STRING,
  game_mode           STRING,
  platform_type       STRING,
  ascension           INT64,
  character           STRING,             -- players[0].character; single-player focus for now
  acts_completed      INT64,
  run_time_seconds    INT64,
  killed_by_encounter STRING,
  killed_by_event     STRING,
  was_abandoned       BOOL,
  win                 BOOL,
  schema_version      INT64
)
PARTITION BY run_date
CLUSTER BY character, ascension;

-- fact_floor_state: one row per run/act/map-point/player. The HP & gold
-- timeline the README calls out as "state after events".
CREATE TABLE IF NOT EXISTS sts2.fact_floor_state (
  run_id           INT64 NOT NULL,
  run_date         DATE NOT NULL,
  act_index        INT64,       -- position within map_point_history
  map_point_index  INT64,       -- position within the act
  floor_number     INT64,       -- cumulative floor count across the whole run, for a single x-axis
  player_id        INT64,
  map_point_type   STRING,
  current_hp       INT64,
  max_hp           INT64,
  current_gold     INT64,
  damage_taken     INT64,
  hp_healed        INT64,
  gold_gained      INT64,
  gold_lost        INT64,
  gold_spent       INT64,
  gold_stolen      INT64,
  max_hp_gained    INT64,
  max_hp_lost      INT64
)
PARTITION BY run_date
CLUSTER BY run_id;

-- fact_card_choice: one row per card offered at a choice screen.
-- was_picked drives pick-rate / win-rate-by-pick analysis.
CREATE TABLE IF NOT EXISTS sts2.fact_card_choice (
  run_id               INT64 NOT NULL,
  run_date             DATE NOT NULL,
  floor_number         INT64,
  player_id            INT64,
  card_id              STRING,
  floor_added_to_deck  INT64,
  was_picked           BOOL
)
PARTITION BY run_date
CLUSTER BY card_id, was_picked;

-- fact_cards_gained: cards added outside a choice screen (event/boss rewards etc).
CREATE TABLE IF NOT EXISTS sts2.fact_cards_gained (
  run_id        INT64 NOT NULL,
  run_date      DATE NOT NULL,
  floor_number  INT64,
  player_id     INT64,
  card_id       STRING
)
PARTITION BY run_date
CLUSTER BY card_id;

-- fact_relic: relics held by a player, snapshotted at end of run.
CREATE TABLE IF NOT EXISTS sts2.fact_relic (
  run_id               INT64 NOT NULL,
  run_date             DATE NOT NULL,
  player_id            INT64,
  relic_id             STRING,
  floor_added_to_deck  INT64
)
PARTITION BY run_date
CLUSTER BY relic_id;

-- fact_deck_card: final deck composition, snapshotted at end of run.
CREATE TABLE IF NOT EXISTS sts2.fact_deck_card (
  run_id               INT64 NOT NULL,
  run_date             DATE NOT NULL,
  player_id            INT64,
  card_id              STRING,
  floor_added_to_deck  INT64
)
PARTITION BY run_date
CLUSTER BY card_id;
