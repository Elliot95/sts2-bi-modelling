-- Grain: one row per relic held at end of run (run / player / relic).
select
    run_id,
    player_id,
    relic_id,
    floor_added_to_deck
from {{ ref('stg_sts2__run_relics') }}
