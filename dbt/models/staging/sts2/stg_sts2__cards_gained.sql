select
    cast(run_id as int64)       as run_id,
    cast(run_date as date)      as run_date,
    cast(floor_number as int64) as floor_number,
    cast(player_id as int64)    as player_id,
    card_id
from {{ source('sts2', 'fact_cards_gained') }}
