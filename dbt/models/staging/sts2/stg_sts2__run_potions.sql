-- Potions still held when the run ended, one row per occupied slot.
select
    cast(run_id as int64)                   as run_id,
    cast(run_date as date)                  as run_date,
    cast(player_id as int64)                as player_id,
    potion_id,
    cast(slot_index as int64)               as slot_index,
    cast(max_potion_slot_count as int64)    as max_potion_slot_count
from {{ source('sts2', 'fact_run_potion') }}
