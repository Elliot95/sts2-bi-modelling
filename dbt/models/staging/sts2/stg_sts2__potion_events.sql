-- One row per potion per action on a floor: offered (was_picked says whether
-- it was taken), used, discarded or bought.
select
    cast(run_id as int64)           as run_id,
    cast(run_date as date)          as run_date,
    cast(floor_number as int64)     as floor_number,
    cast(act_index as int64)        as act_index,
    cast(player_id as int64)        as player_id,
    potion_id,
    action,
    was_picked
from {{ source('sts2', 'fact_potion_event') }}
