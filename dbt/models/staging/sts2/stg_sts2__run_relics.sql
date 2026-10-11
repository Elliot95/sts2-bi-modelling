select
    cast(run_id as int64)               as run_id,
    cast(run_date as date)              as run_date,
    cast(player_id as int64)            as player_id,
    relic_id,
    cast(floor_added_to_deck as int64)  as floor_added_to_deck
from {{ source('sts2', 'fact_relic') }}
